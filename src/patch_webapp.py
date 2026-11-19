#!/usr/bin/env python3
"""Patch devin-webapp-host assets: install zh locale chunks and register
zh-CN/zh-TW/zh-HK/zh-MO in the app's language list (gu[] + __vite__mapDeps).

Additive only: existing locales untouched. Idempotent.
"""
import glob
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "packs" / "webapp-host"

LABELS = {"zh-CN": "简体中文", "zh-TW": "繁體中文（台灣）", "zh-HK": "繁體中文（香港）", "zh-MO": "繁體中文（澳門）"}


def find_assets_dir(app_resources):
    d = pathlib.Path(app_resources) / "out/vs/workbench/devin-webapp-host/assets"
    return d if d.is_dir() else None


def find_entry_chunk(assets):
    for f in assets.glob("chunk-*.js"):
        s = f.read_text(encoding="utf-8")
        if "__vite__mapDeps" in s and "code:`de`" in s:
            return f, s
    return None, None


def chunk_files():
    out = {}
    for loc in LABELS:
        tr = list(CHUNKS.glob(f"chunk-{loc}-*.js"))
        rv = list(CHUNKS.glob(f"chunk-{loc}-review-*.js"))
        tr = [f for f in tr if "-review-" not in f.name]
        if tr and rv:
            out[loc] = (tr[0], rv[0])
    return out


def unpatch(s):
    """Reverse our additions to the entry chunk (rebuild pristine source)."""
    m = re.search(r"m\.f\|\|\(m\.f=\[(.*?)\]\)", s)
    if m:
        arr = re.sub(r',"\./chunk-zh-[A-Z]{2}-[^"]+\.js"', "", m.group(1))
        s = s[: m.start(1)] + arr + s[m.end(1):]
    marker = "{code:`en`,label:`English`}"
    j = s.find(marker)
    if j >= 0:
        j += len(marker)
        k = s.find(",{code:`ja`", j)
        if k > j and s[j:k].startswith(",{code:`zh-"):
            s = s[:j] + s[k:]
    return s


def backup(path):
    b = str(path) + ".devin-zh-backup"
    if not os.path.exists(b):
        import shutil
        shutil.copy2(path, b)
        return True
    return False


def patch(app_resources):
    assets = find_assets_dir(app_resources)
    if not assets:
        print("SKIP: webapp-host assets dir not found")
        return False
    entry, s = find_entry_chunk(assets)
    if not entry:
        print("SKIP: entry chunk with gu[] not found")
        return False
    b = str(entry) + ".devin-zh-backup"
    if not os.path.exists(b):
        if "code:`zh-CN`" in s:  # patched before backup support existed
            pathlib.Path(b).write_text(unpatch(s), encoding="utf-8")
        else:
            backup(entry)

    files = chunk_files()
    if not files:
        print("SKIP: no zh chunks built (run build_webapp.py first)")
        return False

    # 1. copy chunk files
    for loc, (tr, rv) in files.items():
        for f in (tr, rv):
            (assets / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

    if "code:`zh-CN`" in s:
        print("already patched: gu[] has zh-CN")
        return True

    # 2. extend __vite__mapDeps m.f array
    m = re.search(r"m\.f\|\|\(m\.f=\[(.*?)\]\)", s)
    if not m:
        print("FAIL: __vite__mapDeps array not found")
        return False
    arr = re.findall(r'"(\./chunk-[^"]+\.js)"', m.group(1))
    base = len(arr)
    add, indices = [], {}
    i = base
    for loc, (tr, rv) in files.items():
        add.append(f'"./{tr.name}"')
        indices[(loc, "t")] = i
        i += 1
        add.append(f'"./{rv.name}"')
        indices[(loc, "r")] = i
        i += 1
    new_arr = m.group(1) + "," + ",".join(add)
    s = s[: m.start(1)] + new_arr + s[m.end(1):]

    # 3. insert gu[] entries after the `en` element
    entries = []
    for loc, label in LABELS.items():
        if loc not in files:
            continue
        ti, ri = indices[(loc, "t")], indices[(loc, "r")]
        tn, rn = files[loc][0].name, files[loc][1].name
        entries.append(
            f"{{code:`{loc}`,label:`{label}`,"
            f"translation:()=>fu(()=>import(`./{tn}`).then(e=>e.default),__vite__mapDeps([{ti},1]),import.meta.url),"
            f"review:()=>fu(()=>import(`./{rn}`).then(e=>e.default),__vite__mapDeps([{ri},1]),import.meta.url)}}"
        )
    marker = "{code:`en`,label:`English`}"
    j = s.find(marker)
    if j < 0:
        print("FAIL: en entry in gu[] not found")
        return False
    j += len(marker)
    s = s[:j] + "," + ",".join(entries) + s[j:]

    entry.write_text(s, encoding="utf-8")
    print(f"patched {entry.name}: +{len(files)} locales, mapDeps {base}->{len(arr)+len(add)}")
    return True


def restore(app_resources):
    assets = find_assets_dir(app_resources)
    if not assets:
        return False
    ok = False
    for b in assets.glob("chunk-*.js.devin-zh-backup"):
        b.replace(b.with_suffix(""))
        print("restored", b.name[:-len(".devin-zh-backup")])
        ok = True
    for f in assets.glob("chunk-zh-*.js"):
        f.unlink()
        print("removed", f.name)
        ok = True
    return ok


if __name__ == "__main__":
    target = sys.argv[2] if len(sys.argv) > 2 else str(pathlib.Path.home() / "Applications/Devin.app/Contents/Resources/app")
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore(target)
    else:
        patch(target)
