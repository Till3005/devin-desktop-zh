#!/usr/bin/env python3
"""Build devin-webapp-host zh dictionaries and Vite-style chunk modules.

1. Merge work/zh-cn/webapp-parts/*.zh.tsv -> translations/zh-cn/webapp.json
   (flat keys `translation.<ns>...` / `review.<ns>...`, nested on '.').
2. For every translations/<loc>/webapp.json (zh-cn + derived regions),
   emit two ES modules matching the app's official locale-chunk shape:
     chunk-<loc>-<sha>.js         -> default export = translation dict
     chunk-<loc>-review-<sha>.js  -> default export = review dict
   into packs/webapp-host/.
"""
import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PARTS = ROOT / "work" / "zh-cn" / "webapp-parts"
OUT = ROOT / "packs" / "webapp-host"


def parse_parts():
    d = {}
    for p in sorted(PARTS.glob("webapp.part*.zh.tsv")):
        key = None
        for line in p.read_text(encoding="utf-8").split("\n"):
            if "\t" in line:
                k, v = line.split("\t", 1)
                d[k] = v
                key = k
            elif line.strip() and key:
                d[key] += "\n" + line
    return d


def nest(flat):
    out = {}
    for k, v in flat.items():
        node = out
        segs = k.split(".")
        for s in segs[:-1]:
            node = node.setdefault(s, {})
        node[segs[-1]] = v
    return out


def split_namespaces(flat):
    tr, rv = {}, {}
    for k, v in flat.items():
        if k.startswith("translation."):
            tr[k[len("translation."):]] = v
        elif k.startswith("review."):
            rv[k[len("review."):]] = v
    return tr, rv


def chunk_name(stem, body):
    h = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
    return f"chunk-{stem}-{h}.js"


def emit_chunks():
    OUT.mkdir(parents=True, exist_ok=True)
    # stale files from previous builds
    for f in OUT.glob("chunk-*.js"):
        f.unlink()
    names = {}
    for loc in ("zh-cn", "zh-tw", "zh-hk", "zh-mo"):
        src = ROOT / "translations" / loc / "webapp.json"
        if not src.exists():
            continue
        data = json.loads(src.read_text(encoding="utf-8"))
        tr, rv = data["translation"], data["review"]
        code = loc.replace("-", "-")
        code = loc.upper().replace("-", "-")  # zh-CN style handled below
        code = "-".join([loc.split("-")[0], loc.split("-")[1].upper()])
        results = {}
        for kind, d in (("", tr), ("-review", rv)):
            body = "const t=" + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";export{t as default};\n"
            name = chunk_name(f"{code}{kind}", body)
            (OUT / name).write_text(body, encoding="utf-8")
            results[kind or "-translation"] = name
        names[loc] = results
        print(loc, results)
    return names


def main():
    flat = parse_parts()
    tr, rv = split_namespaces(flat)
    nested = {"translation": nest(tr), "review": nest(rv)}
    dst = ROOT / "translations" / "zh-cn"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "webapp.json").write_text(json.dumps(nested, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("zh-cn webapp.json:", len(tr), "translation keys,", len(rv), "review keys")
    emit_chunks()


if __name__ == "__main__":
    main()
