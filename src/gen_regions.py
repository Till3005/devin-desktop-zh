#!/usr/bin/env python3
"""Derive zh-TW / zh-HK / zh-MO translations from translations/zh-cn via OpenCC + regional term maps.

zh-TW: s2twp (Taiwan phrases) + TW overrides
zh-HK: s2hk (HK char variants) + HK overrides
zh-MO: copy of zh-HK (per project decision)
"""
import json
import pathlib
import re
import opencc

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "translations" / "zh-cn"

FILES = ["webview.json", "review.json", "nls.json", "exts.json", "literals.json", "webapp.json"]

# Applied to the post-OpenCC traditional text.
SHARED = [
    ("登錄", "登入"),
    ("默認", "預設"),
    ("通過", "透過"),
    ("創建", "建立"),
    ("文件", "檔案"),   # 文件=file in virtually all gap strings; document-usage is rare
    ("信息", "資訊"),
    ("打印", "列印"),
    ("內存", "記憶體"),
    ("視頻", "影片"),
    ("鼠標", "滑鼠"),
    ("自定義", "自訂"),
    ("數據", "資料"),
    ("界面", "介面"),
    ("鏈接", "連結"),
]
TW_ONLY = [
    ("用戶", "使用者"),
    ("程序", "程式"),
]
HK_ONLY = [
    ("程序", "程式"),
]

cc_tw = opencc.OpenCC("s2twp")
cc_hk = opencc.OpenCC("s2hk")


def convert_text(s, cc, maps):
    s = cc.convert(s)
    for a, b in maps:
        if a in s:
            s = s.replace(a, b)
    return s


def convert_obj(obj, cc, maps):
    if isinstance(obj, str):
        return convert_text(obj, cc, maps)
    if isinstance(obj, list):
        return [convert_obj(v, cc, maps) for v in obj]
    if isinstance(obj, dict):
        return {k: convert_obj(v, cc, maps) for k, v in obj.items()}
    return obj


def main():
    for loc, cc, extra in (("zh-tw", cc_tw, TW_ONLY), ("zh-hk", cc_hk, HK_ONLY)):
        dst = ROOT / "translations" / loc
        dst.mkdir(parents=True, exist_ok=True)
        maps = SHARED + extra
        for f in FILES:
            data = json.loads((SRC / f).read_text(encoding="utf-8"))
            out = convert_obj(data, cc, maps)
            (dst / f).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(loc, "done")

    mo = ROOT / "translations" / "zh-mo"
    mo.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        (mo / f).write_text((ROOT / "translations" / "zh-hk" / f).read_text(encoding="utf-8"), encoding="utf-8")
    print("zh-mo = zh-hk done")


if __name__ == "__main__":
    main()
