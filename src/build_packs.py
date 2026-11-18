#!/usr/bin/env python3
"""Build the four regional language packs from:
  - vendor/ms-pack/{zh-hans,zh-hant}   (Microsoft base, MIT-licensed vscode-loc)
  - translations/<loc>/nls.json        (our translations for strings MS misses)
Output: packs/<loc>/ — each a complete VS Code-format language pack extension dir.
"""
import json, os, sys, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# locale -> (ms base dir, our nls file, display names)
LOCALES = {
    "zh-cn": ("zh-hans", "translations/zh-cn/nls.json", "Chinese (Simplified)", "中文(简体)"),
    "zh-tw": ("zh-hant", "translations/zh-tw/nls.json", "Chinese (Traditional)", "中文(台灣)"),
    "zh-hk": ("zh-hant", "translations/zh-hk/nls.json", "Chinese (Hong Kong)", "中文(香港)"),
    "zh-mo": ("zh-hant", "translations/zh-hk/nls.json", "Chinese (Macau)", "中文(澳門)"),
}

PACK_VERSION = "1.0.0"


def load(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}


def main():
    out_root = os.path.join(ROOT, "packs")
    os.makedirs(out_root, exist_ok=True)
    for loc, (base, nls_rel, lname, lloc) in LOCALES.items():
        nls_path = os.path.join(ROOT, nls_rel)
        custom = load(nls_path)  # {module: {key: zh}}
        base_dir = os.path.join(ROOT, "vendor/ms-pack", base)
        main = load(os.path.join(base_dir, "translations/main.i18n.json"))["contents"]

        # merge our translations into a copy of the MS contents
        contents = {m: dict(kv) for m, kv in main.items()}
        added = 0
        for mod, kv in custom.items():
            contents.setdefault(mod, {})
            for k, v in kv.items():
                if contents[mod].get(k) != v:
                    contents[mod][k] = v
                    added += 1

        pack = os.path.join(out_root, loc)
        if os.path.exists(pack):
            shutil.rmtree(pack)
        os.makedirs(os.path.join(pack, "translations/extensions"))

        json.dump({"contents": contents},
                  open(os.path.join(pack, "translations/main.i18n.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)

        # copy MS extension translations
        ext_src = os.path.join(base_dir, "translations/extensions")
        entries = [{"id": "vscode", "path": f"./translations/main.i18n.json"}]
        for f in sorted(os.listdir(ext_src)):
            shutil.copy(os.path.join(ext_src, f), os.path.join(pack, "translations/extensions", f))
            eid = f[:-len(".i18n.json")]
            entries.append({"id": eid, "path": f"./translations/extensions/{f}"})

        # our custom extension translations (translations/<loc>/extensions/*.i18n.json)
        custom_ext_dir = os.path.join(ROOT, f"translations/{'zh-hk' if loc=='zh-mo' else loc}/extensions")
        if os.path.isdir(custom_ext_dir):
            for f in sorted(os.listdir(custom_ext_dir)):
                shutil.copy(os.path.join(custom_ext_dir, f),
                            os.path.join(pack, "translations/extensions", f))
                eid = f[:-len(".i18n.json")]
                entries.append({"id": eid, "path": f"./translations/extensions/{f}"})

        pkg = {
            "name": f"devin-language-pack-{loc}",
            "displayName": f"{lname} ({lloc}) Language Pack for Devin Desktop",
            "description": f"{lname} language pack for Devin Desktop (community build)",
            "version": PACK_VERSION,
            "publisher": "devin-desktop-zh",
            "engines": {"vscode": "^1.100.0"},
            "license": "MIT",
            "contributes": {"localizations": [{
                "languageId": loc,
                "languageName": lname,
                "localizedLanguageName": lloc,
                "translations": entries,
            }]},
        }
        if loc == "zh-mo":
            # zh-mo reuses zh-hk translations but declares its own locale
            pass
        json.dump(pkg, open(os.path.join(pack, "package.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        total = sum(len(v) for v in contents.values())
        print(f"{loc}: {total} strings ({added} custom overrides/additions)")


if __name__ == "__main__":
    main()
