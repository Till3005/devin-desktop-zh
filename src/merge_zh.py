#!/usr/bin/env python3
"""Merge work/zh-cn/*.partNN.tsv into translations/zh-cn/*.json."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = ROOT / "work" / "zh-cn"
OUT = ROOT / "translations" / "zh-cn"
EN = ROOT / "work"


def read_parts(prefix):
    """Return dict of key->zh merged from all work/zh-cn/<prefix>.partNN.tsv files."""
    merged = {}
    for f in sorted(WORK.glob(f"{prefix}.part*.tsv")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            if "\t" not in line:
                sys.exit(f"{f.name}:{i}: no tab")
            k, v = line.split("\t", 1)
            merged[k] = v
    return merged


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}

    # webview + review: flat dotted-key dicts
    for name in ("webview", "review"):
        en_lines = (EN / f"{name}.en.tsv").read_text(encoding="utf-8").splitlines()
        en_keys = [l.split("\t", 1)[0] for l in en_lines if "\t" in l]
        zh = read_parts(name)
        missing = [k for k in en_keys if k not in zh]
        (OUT / f"{name}.json").write_text(
            json.dumps({k: zh[k] for k in en_keys if k in zh}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")
        report[name] = (len(en_keys), len(zh), len(missing))
        if missing:
            pathlib.Path(f"/tmp/missing-{name}.txt").write_text("\n".join(missing))
            print(f"WARN {name}: {len(missing)} missing -> /tmp/missing-{name}.txt")

    # nls: nested {module: {key: zh}} parallel to nls-gap.en.json
    en_nls = json.loads((EN / "nls-gap.en.json").read_text(encoding="utf-8"))
    zh_flat = read_parts("nls")
    out_nls, missing_nls = {}, []
    for mod, entries in en_nls.items():
        for k in entries:
            flat = f"{mod}/{k}"
            if flat in zh_flat:
                out_nls.setdefault(mod, {})[k] = zh_flat[flat]
            else:
                missing_nls.append(flat)
    (OUT / "nls.json").write_text(
        json.dumps(out_nls, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n_en = sum(len(v) for v in en_nls.values())
    report["nls"] = (n_en, len(zh_flat), len(missing_nls))
    if missing_nls:
        pathlib.Path("/tmp/missing-nls.txt").write_text("\n".join(missing_nls))
        print(f"WARN nls: {len(missing_nls)} missing -> /tmp/missing-nls.txt")

    # exts + literals: parallel arrays (null where untranslated), indexed by en list
    for name in ("exts", "literals"):
        en_list = json.loads((EN / f"{name}.en.list.json").read_text(encoding="utf-8"))
        zh = read_parts(name)
        arr, translated = [], 0
        for i in range(len(en_list)):
            v = zh.get(str(i))
            arr.append(v)
            translated += v is not None
        (OUT / f"{name}.json").write_text(
            json.dumps(arr, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        report[name] = (len(en_list), len(zh), len(en_list) - translated)

    for name, (en, zh_n, miss) in report.items():
        print(f"{name}: {zh_n} zh keys covering {en - miss}/{en} en entries ({miss} untranslated)")


if __name__ == "__main__":
    main()
