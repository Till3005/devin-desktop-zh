#!/usr/bin/env python3
"""Devin Desktop 中文补丁器 v2 — additive language option, apply/restore, stdlib only.

Chinese is ADDED as new display-language options (zh-cn/zh-tw/zh-hk/zh-mo).
English and other languages are never modified: all injections are keyed by the
app's selected nls locale, and restore() returns byte-identical originals.

Usage:
  python3 patch_app.py apply   --app <resources/app dir> [--translations dir]
  python3 patch_app.py restore --app <resources/app dir>
  python3 patch_app.py status  --app <resources/app dir>

Patches (idempotent, .devin-zh-backup restore points):
  - webview bundles: resources:n,lng:"en" -> resources for all 4 zh locales added
                     via Object.assign IIFE + lng reads _VSCODE_NLS_LANGUAGE
  - hardcoded literals -> (DICT[locale]||en) conditional lookups
  - extensions/<windsurf*>/package.nls.<loc>.json written (VS Code picks the file
    matching the selected locale; package.json itself is untouched)
"""
import json, os, re, sys, shutil, argparse, hashlib, base64

BUNDLES = [
    "out/vs/workbench/windsurf-chat-client/index.js",
    "out/vs/sessions/sessions.desktop.main.js",
]
EXT_DIRS = ["windsurf", "windsurf-auth", "windsurf-remote-devin", "windsurf-remote-openssh",
            "windsurf-remote-wsl", "windsurf-dev-containers", "theme-windsurf"]
LOCALES = ["zh-cn", "zh-tw", "zh-hk", "zh-mo"]
MARKER = ".devin-zh-patched"
LANG_EXPR = '(globalThis._VSCODE_NLS_LANGUAGE||navigator.language||"en")'
# substrings unique to the en dict JSON.parse payloads (used to exclude them
# from literal replacement)
DICT_ANCHORS = ['adminPromotionOwner', 'Part {{number}} of {{total}}']


def js_escape(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _scan_str(data, start, quote):
    """Scan a JS string literal starting at `start` (right after the opening
    quote char). Returns (end_index_of_closing_quote)."""
    i = start
    while True:
        c = data[i]
        if c == "\\":
            i += 2
            continue
        if c == quote:
            return i
        i += 1


def flatten(d, prefix=""):
    res = {}
    for k, v in d.items():
        p = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            res.update(flatten(v, p))
        else:
            res[p] = v
    return res


def unflatten(flat):
    out = {}
    for k, v in flat.items():
        cur = out
        parts = k.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = v
    return out


def write_atomic(path, data):
    tmp = path + ".devin-zh-tmp"
    with open(tmp, "w", encoding="utf8", errors="surrogateescape") as f:
        f.write(data)
    os.replace(tmp, path)


def backup(path):
    b = path + ".devin-zh-backup"
    if not os.path.exists(b):
        shutil.copy2(path, b)


def restore(path):
    b = path + ".devin-zh-backup"
    if os.path.exists(b):
        shutil.copy2(b, path)
        return True
    return False


def load_translations(tdir):
    """Return {locale: {webview_flat, literals_arr, exts_arr}} plus en lists."""
    out = {}
    for loc in LOCALES:
        d = os.path.join(tdir, loc)
        if not os.path.isdir(d):
            continue
        def j(name, default):
            p = os.path.join(d, name)
            return json.load(open(p, encoding="utf8")) if os.path.exists(p) else default
        out[loc] = {
            "webview": j("webview.json", {}),
            "review": j("review.json", {}),
            "literals": j("literals.json", []),
            "exts": j("exts.json", []),
        }
    return out


def build_resources_injection(trans):
    """Return JS expr turning `res` var into res with all zh locales added.

    (r=>{r["zh-cn"]=JSON.parse('...');...;r["zh-mo"]=r["zh-hk"];return r})
    """
    assigns = []
    for loc in LOCALES:
        t = trans.get(loc)
        if not t or not t["webview"]:
            continue
        # zh-mo shares zh-hk payload
        src = "zh-hk" if loc == "zh-mo" else loc
        src_t = trans.get(src, {})
        web = unflatten(t["webview"]) if loc != "zh-mo" else None
        rev = unflatten(t["review"]) if loc != "zh-mo" else None
        if loc == "zh-mo":
            if trans.get("zh-hk", {}).get("webview"):
                assigns.append(f'r["zh-mo"]=r["zh-hk"]')
            continue
        payload = js_escape(json.dumps(
            {"translation": web, "review": rev}, ensure_ascii=False, separators=(",", ":")))
        assigns.append(f'r["{loc}"]=JSON.parse(\'{payload}\')')
    if not assigns:
        return None
    return "(r=>{" + ";".join(assigns) + ";return r})"


def build_literal_dict(trans, en_literals):
    """{locale: {en: zh}} for literals that have any translation."""
    d = {}
    for loc in LOCALES:
        arr = trans.get(loc, {}).get("literals", [])
        m = {}
        for i, zh in enumerate(arr):
            if zh and i < len(en_literals):
                m[en_literals[i]] = zh
        if m:
            d[loc] = m
    return d


def patch_bundle(path, res_inject, lit_dict):
    data = open(path, encoding="utf8", errors="surrogateescape").read()
    touched = 0

    # 1. literals FIRST (scan pristine bundle; injected payloads must not be re-scanned)
    if lit_dict:
        need_bootstrap = "__devinZhLit" not in data
        lit_json = js_escape(json.dumps(lit_dict, ensure_ascii=False, separators=(",", ":")))
        lookup = "globalThis.__devinZhLit=globalThis.__devinZhLit||JSON.parse('" + lit_json + "');"

        # Exclude the en dict JSON.parse payload regions: replacing inside them
        # would turn i18next dict values into literal expression text.
        spans = []
        for anchor in DICT_ANCHORS:
            for m0 in re.finditer(r"JSON\.parse\((['`])", data):
                q = m0.group(1)
                try:
                    e = _scan_str(data, m0.end(), q)
                except IndexError:
                    continue
                if anchor in data[m0.end():e]:
                    spans.append((m0.start(), e))
        hits = 0
        en_keys = lit_dict.get("zh-cn", lit_dict.get(next(iter(lit_dict), ""), {}))
        for en in en_keys:
            needle = json.dumps(en, ensure_ascii=False)
            zh_map_expr = (f'(globalThis.__devinZhLit[{LANG_EXPR}]'
                           f'&&globalThis.__devinZhLit[{LANG_EXPR}][{needle}]||{needle})')
            pos = 0
            while True:
                i = data.find(needle, pos)
                if i < 0:
                    break
                if any(s <= i < e for s, e in spans):
                    pos = i + len(needle)
                    continue
                data = data[:i] + zh_map_expr + data[i + len(needle):]
                hits += 1
                pos = i + len(zh_map_expr)
        if need_bootstrap:
            data = lookup + data
        touched += hits

    # 2. resources:<var> -> resources:<inject>(<var>)   (only the one adjacent to lng:"en")
    m = re.search(r"resources:([A-Za-z_$][\w$]*),\s*lng:\"en\"", data)
    if m and res_inject:
        data = data[:m.start()] + f"resources:{res_inject}({m.group(1)}),lng:\"en\"" + data[m.end():]
        i = data.index(f"resources:{res_inject}({m.group(1)}),lng:\"en\"")
        j = data.index('lng:"en"', i)
        data = data[:j] + "lng:" + LANG_EXPR + data[j + len('lng:"en"'):]
        touched += 1
    elif not m:
        return 0, "i18next init (resources:x,lng:\"en\") not found"

    write_atomic(path, data)
    return touched, "ok"


def localize_exts(app, trans, en_exts):
    """Convert inline display strings in windsurf extension package.jsons into
    %key% nls indirection, then emit package.nls.json (en) + package.nls.<loc>.json.
    Fully additive: English resolves through package.nls.json unchanged."""
    zh_by_loc = {}
    for loc in LOCALES:
        arr = trans.get(loc, {}).get("exts", [])
        zh_by_loc[loc] = {en_exts[i]: arr[i] for i in range(len(arr)) if i < len(en_exts) and arr[i]}
    any_loc = next((m for m in zh_by_loc.values() if m), {})
    if not any_loc:
        return 0
    written = 0
    for d in EXT_DIRS:
        pj = os.path.join(app, "extensions", d, "package.json")
        if not os.path.exists(pj):
            continue
        data = json.load(open(pj, encoding="utf8"))
        keymap = {}   # en -> %key%
        def walk(o):
            if isinstance(o, dict):
                for k in list(o):
                    v = o[k]
                    if isinstance(v, str) and v in any_loc:
                        o[k] = "%" + keymap.setdefault(v, f"devinzh.{len(keymap)}") + "%"
                    else:
                        walk(v)
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    if isinstance(v, str) and v in any_loc:
                        o[i] = "%" + keymap.setdefault(v, f"devinzh.{len(keymap)}") + "%"
                    else:
                        walk(v)
        walk(data)
        if not keymap:
            continue
        backup(pj)
        json.dump(data, open(pj, "w", encoding="utf8"), ensure_ascii=False, indent="\t")
        ext = os.path.join(app, "extensions", d)
        inv = {keymap[v]: v for v in keymap}
        json.dump(inv, open(os.path.join(ext, "package.nls.json"), "w", encoding="utf8"),
                  ensure_ascii=False, indent=2)
        for loc in LOCALES:
            m = zh_by_loc.get(loc, {})
            out = {keymap[v]: m[v] for v in keymap if v in m}
            if out:
                json.dump(out, open(os.path.join(ext, f"package.nls.{loc}.json"), "w", encoding="utf8"),
                          ensure_ascii=False, indent=2)
        written += len(keymap)
    return written


def update_checksums(app):
    """Recompute product.json checksums for patched files so VS Code's
    integrity check stops flagging the install as corrupt."""
    pj = os.path.join(app, "product.json")
    d = json.load(open(pj, encoding="utf8"))
    cs = d.get("checksums")
    if not cs:
        return 0
    changed = 0
    for rel in BUNDLES:
        key = rel[len("out/"):] if rel.startswith("out/") else rel
        path = os.path.join(app, rel)
        if key in cs and os.path.exists(path):
            h = base64.b64encode(hashlib.sha256(open(path, "rb").read()).digest()).decode().rstrip("=")
            if cs[key] != h:
                cs[key] = h
                changed += 1
    if changed:
        backup(pj)
        json.dump(d, open(pj, "w", encoding="utf8"), ensure_ascii=False, indent="\t")
    return changed


def cmd_apply(a):
    app = a.app
    trans = load_translations(a.translations)
    if not trans:
        print("no translations found"); return 1
    en_exts = json.load(open(os.path.join(a.translations, "..", "work", "exts.en.list.json"), encoding="utf8")) if os.path.exists(os.path.join(a.translations, "..", "work", "exts.en.list.json")) else []
    en_literals = json.load(open(os.path.join(a.translations, "..", "work", "literals.en.list.json"), encoding="utf8")) if os.path.exists(os.path.join(a.translations, "..", "work", "literals.en.list.json")) else []

    res_inject = build_resources_injection(trans)
    lit_dict = build_literal_dict(trans, en_literals)
    for rel in BUNDLES:
        path = os.path.join(app, rel)
        if not os.path.exists(path):
            print("skip missing", rel); continue
        backup(path)
        n, msg = patch_bundle(path, res_inject, lit_dict)
        print(" ", rel, "->", msg, f"({n} patches)")
    if en_exts:
        w = localize_exts(app, trans, en_exts)
        print(" extensions:", w, "strings localized via package.nls.<loc>.json")
    c = update_checksums(app)
    if c:
        print(" product.json:", c, "checksums refreshed (integrity check stays green)")
    import patch_webapp
    patch_webapp.patch(app)
    marker = os.path.join(app, MARKER)
    json.dump({"locales": list(trans), "files": BUNDLES}, open(marker, "w"))
    print("patched. marker:", marker)
    return 0


def cmd_restore(a):
    app = a.app
    for rel in BUNDLES:
        p = os.path.join(app, rel)
        print(("restored " if restore(p) else "no backup ") + rel)
    for d in EXT_DIRS:
        pj = os.path.join(app, "extensions", d, "package.json")
        if restore(pj):
            print("restored", pj)
        for name in ["package.nls.json"] + [f"package.nls.{loc}.json" for loc in LOCALES]:
            p = os.path.join(app, "extensions", d, name)
            if os.path.exists(p):
                try:
                    if "devinzh." in open(p, encoding="utf8").read():
                        os.remove(p); print("removed", p)
                except OSError:
                    pass
    pj = os.path.join(app, "product.json")
    if restore(pj):
        print("restored product.json")
    import patch_webapp
    patch_webapp.restore(app)
    m = os.path.join(app, MARKER)
    if os.path.exists(m):
        os.remove(m)
    return 0


def cmd_status(a):
    m = os.path.join(a.app, MARKER)
    print("patched" if os.path.exists(m) else "unpatched")
    for rel in BUNDLES:
        p = os.path.join(a.app, rel)
        print(" ", rel, "exists" if os.path.exists(p) else "missing",
              "(backup)" if os.path.exists(p + ".devin-zh-backup") else "")
    import patch_webapp
    assets = patch_webapp.find_assets_dir(a.app)
    if assets:
        entry, s = patch_webapp.find_entry_chunk(assets)
        zh = "code:`zh-CN`" in s if s else False
        print("  devin-webapp-host:", "zh locales registered" if zh else "unpatched",
              "(backup)" if entry and os.path.exists(str(entry) + ".devin-zh-backup") else "")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("apply", "restore", "status"):
        p = sub.add_parser(name)
        p.add_argument("--app", required=True)
        p.add_argument("--translations",
                       default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "translations"))
    a = ap.parse_args()
    sys.exit({"apply": cmd_apply, "restore": cmd_restore, "status": cmd_status}[a.cmd](a))


if __name__ == "__main__":
    main()
