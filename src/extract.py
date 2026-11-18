#!/usr/bin/env python3
"""Extract all translatable English sources from a Devin Desktop install.

Usage: python3 src/extract.py <path-to-resources/app> [--out extracted]

Surfaces extracted:
  - nls.metadata.json / nls.messages.json   (VS Code workbench nls layer)
  - webview-CV.en.json / webview-CH.en.json (chat client i18next dicts)
  - sessions-*.en.json                      (agent window i18next dicts, same content, template-literal form)
  - literals.en.json                        (hardcoded JSX/object literals not in any dict)
  - extensions.json                         (built-in extension package.json display strings)
"""
import json, os, re, sys


def js_unescape(raw: str) -> str:
    out = []
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if c != "\\":
            out.append(c); i += 1; continue
        i += 1
        if i >= n:
            break
        e = raw[i]
        if e in "nrtbfv":
            out.append({"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v"}[e]); i += 1
        elif e == "x":
            out.append(chr(int(raw[i + 1:i + 3], 16))); i += 3
        elif e == "u":
            if raw[i + 1] == "{":
                j = raw.index("}", i + 1)
                out.append(chr(int(raw[i + 2:j], 16))); i = j + 1
            else:
                out.append(chr(int(raw[i + 1:i + 5], 16))); i += 5
        elif e == "0":
            out.append("\0"); i += 1
        else:
            out.append(e); i += 1
    return "".join(out)


def find_js_string(data: str, start: int, quote: str) -> tuple[str, int]:
    """Return (raw escaped string contents, index past closing quote)."""
    out = []
    i = start
    while True:
        c = data[i]
        if c == "\\":
            out.append(data[i:i + 2]); i += 2; continue
        if c == quote:
            return "".join(out), i + 1
        out.append(c); i += 1


def extract_json_parse_dict(data: str, varname: str) -> dict | None:
    """Find `varname=JSON.parse('...')` or backtick variant and decode it."""
    m = re.search(r"\b" + varname + r"=JSON\.parse\('", data)
    quote = "'"
    if not m:
        m = re.search(r"\b" + varname + r"=JSON\.parse\(`", data)
        quote = "`"
    if not m:
        return None
    raw, _ = find_js_string(data, m.end(), quote)
    return json.loads(js_unescape(raw))


def count_leaves(o) -> int:
    if isinstance(o, dict):
        return sum(count_leaves(v) for v in o.values())
    return 1 if isinstance(o, str) else 0


def main() -> None:
    app = sys.argv[1]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "extracted"
    os.makedirs(out, exist_ok=True)

    # 1. nls layer
    for f in ("nls.metadata.json", "nls.messages.json", "product.json"):
        src = os.path.join(app, "out" if f.startswith("nls") else "", f)
        with open(os.path.join(app, "out", f) if f.startswith("nls") else os.path.join(app, f)) as fh:
            json.dump(json.load(fh), open(os.path.join(out, f), "w"), ensure_ascii=False, indent=1)
        print("ok", f)

    # 2. webview i18next dicts (chat client: single-quoted; sessions bundle: backtick)
    chat = open(os.path.join(app, "out/vs/workbench/windsurf-chat-client/index.js"), encoding="utf8", errors="ignore").read()
    for var in ("CV", "CH"):
        d = extract_json_parse_dict(chat, var)
        assert d, f"{var} dict not found"
        json.dump(d, open(os.path.join(out, f"webview-{var}.en.json"), "w"), ensure_ascii=True, indent=1)
        print("ok", f"webview-{var}", count_leaves(d), "leaves")

    sess = open(os.path.join(app, "out/vs/sessions/sessions.desktop.main.js"), encoding="utf8", errors="ignore").read()
    for var in ("OZo", "zZo"):
        d = extract_json_parse_dict(sess, var)
        if d:
            json.dump(d, open(os.path.join(out, f"sessions-{var}.en.json"), "w"), ensure_ascii=True, indent=1)
            print("ok", f"sessions-{var}", count_leaves(d), "leaves")

    # 3. hardcoded literals (display props), minus strings already covered by dicts
    inset = set()
    def walk(o):
        if isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, str):
            inset.add(o)
    for f in os.listdir(out):
        if f.startswith(("webview-", "sessions-")):
            walk(json.load(open(os.path.join(out, f))))

    prop_re = re.compile(
        r'(?:children|label|title|placeholder|description|message|text|content|tooltip|ariaLabel|'
        r'header|body|hint|detail|summary|badge|caption|subtitle):"((?:[^"\\]|\\.)*)"')
    cands = set()
    for f in ("out/vs/sessions/sessions.desktop.main.js", "out/vs/workbench/windsurf-chat-client/index.js"):
        data = open(os.path.join(app, f), encoding="utf8", errors="ignore").read()
        for m in prop_re.finditer(data):
            s = m.group(1)
            if not 3 <= len(s) <= 160 or "\\x" in s or "\\u" in s:
                continue
            if not re.match(r"^[A-Za-z0-9][A-Za-z0-9 ,.!?\'’\-–—:;()/+%@&#]*$", s):
                continue
            if s in inset:
                continue
            cands.add(s)
    json.dump(sorted(cands), open(os.path.join(out, "literals.en.json"), "w"), ensure_ascii=False, indent=1)
    print("ok literals", len(cands))

    # 4. built-in extension display strings (package.json contributes)
    ext = {}
    for name in os.listdir(os.path.join(app, "extensions")):
        pj = os.path.join(app, "extensions", name, "package.json")
        if not os.path.exists(pj):
            continue
        p = json.load(open(pj))
        ext_id = f"{p.get('publisher', 'vscode')}.{p['name']}"
        nls = os.path.join(app, "extensions", name, "package.nls.json")
        strings = []
        def collect(o):
            if isinstance(o, dict):
                for v in o.values(): collect(v)
            elif isinstance(o, list):
                for v in o: collect(v)
            elif isinstance(o, str) and len(o) > 2 and " " in o and o[0].isalpha() and not o.startswith("%"):
                strings.append(o)
        collect(p.get("contributes", {}))
        ext[ext_id] = {
            "dir": name,
            "hasNls": os.path.exists(nls),
            "displayStrings": sorted(set(strings)),
        }
    json.dump(ext, open(os.path.join(out, "extensions.en.json"), "w"), ensure_ascii=False, indent=1)
    print("ok extensions", sum(len(v["displayStrings"]) for v in ext.values()))


if __name__ == "__main__":
    main()
