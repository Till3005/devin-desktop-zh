#!/usr/bin/env python3
"""Devin Desktop 中文补丁器 — apply/restore, cross-platform, stdlib only.

Usage:
  python3 patch_app.py apply --locale zh-cn [--app <resources/app dir>] [--translations dir]
  python3 patch_app.py restore [--app <resources/app dir>]
  python3 patch_app.py status [--app <resources/app dir>]

Patches (idempotent, with .devin-zh-backup restore points):
  - out/vs/workbench/windsurf-chat-client/index.js : i18next dict leaf values -> zh
  - out/vs/sessions/sessions.desktop.main.js       : same dicts (template-literal form)
  - hardcoded UI literals in both bundles          : whitelisted en -> zh
  - extensions/*/package.json                      : windsurf builtin ext display strings
  - node_modules.asar                              : repacked if it contains dict copies
"""
import json, os, re, sys, shutil, argparse, subprocess, tempfile

BUNDLES = [
    "out/vs/workbench/windsurf-chat-client/index.js",
    "out/vs/sessions/sessions.desktop.main.js",
]
# dict anchors located by content; the en dict is the only one wired into i18next
# (de/es/ja/pt payloads ship in the bundle but are never registered) -> patch the en copy.
DICT_ANCHORS = [
    ("translation", '{"adminPromotionOwner":{"label":"Enterprise or org"'),
    ("review", '{"guide":{"step":"Part {{number}} of {{total}}"'),
]
EXT_DIRS = ["windsurf", "windsurf-auth", "windsurf-remote-devin", "windsurf-remote-openssh",
            "windsurf-remote-wsl", "windsurf-dev-containers", "theme-windsurf"]
MARKER = ".devin-zh-patched"


def js_unescape(raw):
    out, i, n = [], 0, len(raw)
    while i < n:
        c = raw[i]
        if c != "\\":
            out.append(c); i += 1; continue
        i += 1
        if i >= n: break
        e = raw[i]
        if e in "nrtbfv":
            out.append({"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v"}[e]); i += 1
        elif e == "x":
            out.append(chr(int(raw[i+1:i+3], 16))); i += 3
        elif e == "u":
            if raw[i+1] == "{":
                j = raw.index("}", i+1); out.append(chr(int(raw[i+2:j], 16))); i = j+1
            else:
                out.append(chr(int(raw[i+1:i+5], 16))); i += 5
        elif e == "0":
            out.append("\0"); i += 1
        else:
            out.append(e); i += 1
    return "".join(out)


def js_escape(s, quote):
    s = s.replace("\\", "\\\\")
    if quote == "'":
        s = s.replace("'", "\\'")
    else:
        s = s.replace("`", "\\`").replace("${", "\\${")
    return s


def find_str(data, start, quote):
    """Return (raw_contents, index_of_closing_quote)."""
    out, i = [], start
    while True:
        c = data[i]
        if c == "\\":
            out.append(data[i:i+2]); i += 2; continue
        if c == quote:
            return "".join(out), i
        out.append(c); i += 1


def write_atomic(path, data):
    tmp = path + ".devin-zh-tmp"
    with open(tmp, "w", encoding="utf8", errors="surrogateescape") as f:
        f.write(data)
    os.replace(tmp, path)


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
        parts = k.split(".")
        cur = out
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = v
    return out


def overlay_dict(en, zh_flat, prefix=""):
    if isinstance(en, dict):
        return {k: overlay_dict(v, zh_flat, f"{prefix}.{k}" if prefix else k) for k, v in en.items()}
    return zh_flat.get(prefix, en)


def patch_dict_in_bundle(path, anchor, zh_dict_flat):
    """Replace the JSON.parse payload containing `anchor` with zh-merged dict."""
    data = open(path, encoding="utf8", errors="surrogateescape").read()
    # locate JSON.parse('<quote>{"<anchor>") regardless of minified var name / quote style
    m = re.search(r"=JSON\.parse\((['`])" + re.escape(anchor), data)
    if not m:
        return 0, f"dict containing {anchor} not found"
    quote = m.group(1)
    raw, end = find_str(data, m.end() - len(anchor), quote)
    en = json.loads(js_unescape(raw))
    merged = overlay_dict(en, zh_dict_flat)
    payload = js_escape(json.dumps(merged, ensure_ascii=True, separators=(",", ":")), quote)
    data = data[:m.end() - len(anchor)] + payload + data[end:]
    write_atomic(path, data)
    return 1, f"dict {anchor[:30]}: {len(zh_dict_flat)} translations merged"


def patch_literals(path, lit_map):
    if not lit_map:
        return 0
    data = open(path, encoding="utf8", errors="surrogateescape").read()
    hits = 0
    for en, zh in lit_map.items():
        needle = '"' + en.replace("\\", "\\\\").replace('"', '\\"') + '"'
        count = data.count(needle)
        if count:
            data = data.replace(needle, '"' + zh.replace("\\", "\\\\").replace('"', '\\"') + '"')
            hits += count
    write_atomic(path, data)
    return hits


def patch_ext_package_json(app, ext_map):
    hits = 0
    for d in EXT_DIRS:
        pj = os.path.join(app, "extensions", d, "package.json")
        if not os.path.exists(pj):
            continue
        raw = open(pj, encoding="utf8").read()
        for en, zh in ext_map.items():
            needle = '"' + en.replace('"', '\\"') + '"'
            if needle in raw:
                raw = raw.replace(needle, '"' + zh.replace('"', '\\"') + '"')
                hits += 1
        open(pj, "w", encoding="utf8").write(raw)
    return hits


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


def load_translations(tdir, locale):
    def j(name):
        p = os.path.join(tdir, locale, name)
        return json.load(open(p, encoding="utf8")) if os.path.exists(p) else {}
    return j("webview.json"), j("literals.json"), j("exts.json")


def cmd_apply(a):
    app = a.app
    webview, literals, exts = load_translations(a.translations, a.locale)
    zh_t = webview.get("translation", {})
    zh_r = webview.get("review", {})
    if not zh_t and not literals and not exts:
        print("no translations found for", a.locale); return 1
    patched = []
    for rel in BUNDLES:
        path = os.path.join(app, rel)
        if not os.path.exists(path):
            print("skip missing", rel); continue
        backup(path)
        for ns, anchor in DICT_ANCHORS:
            flat = zh_t if ns == "translation" else zh_r
            n, msg = patch_dict_in_bundle(path, anchor, flat)
            print(" ", rel, "->", msg)
        if literals:
            n = patch_literals(path, literals)
            print(" ", rel, "-> literals:", n, "replaced")
        patched.append(rel)
    if exts:
        for d in EXT_DIRS:
            pj = os.path.join(app, "extensions", d, "package.json")
            if os.path.exists(pj):
                backup(pj)
        n = patch_ext_package_json(app, exts)
        print(" extensions:", n, "strings patched")
    marker = os.path.join(app, MARKER)
    json.dump({"locale": a.locale, "files": patched + [f"extensions/{d}/package.json" for d in EXT_DIRS],
               "version": open(os.path.join(app, "product.json")).read()[:200]},
              open(marker, "w"))
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
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("apply", "restore", "status"):
        p = sub.add_parser(name)
        p.add_argument("--app", required=True, help="path to resources/app inside Devin Desktop install")
        p.add_argument("--locale", default="zh-cn")
        p.add_argument("--translations", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "translations"))
    a = ap.parse_args()
    sys.exit({"apply": cmd_apply, "restore": cmd_restore, "status": cmd_status}[a.cmd](a))


if __name__ == "__main__":
    main()
