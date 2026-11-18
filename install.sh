#!/usr/bin/env bash
# Devin Desktop 中文语言包一键安装 / 自愈脚本 (macOS & Linux)
# 用法: bash install.sh          — 安装四个中文语言包 + webview/扩展补丁
#       bash install.sh restore — 完全还原（卸载补丁，语言包仍在）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

find_app() {
  for c in \
    "$HOME/Applications/Devin.app/Contents/Resources/app" \
    "/Applications/Devin.app/Contents/Resources/app" \
    "$HOME/.devin/share/devin/resources/app" \
    "$HOME/.local/share/devin/resources/app" \
    "/usr/share/devin/resources/app" \
    "/opt/devin/resources/app"; do
    [ -d "$c" ] && { echo "$c"; return; }
  done
  echo "error: 未找到 Devin Desktop 安装目录，请用 --app 指定" >&2; exit 1
}

APP=""
MODE="${1:-apply}"
if [ "$MODE" = "--app" ]; then APP="$2"; MODE="${3:-apply}"; fi
[ -z "$APP" ] && APP="$(find_app)"
EXT_HOME="${XDG_DATA_HOME:-$HOME/.devin}/extensions"

if [ "$MODE" = "restore" ]; then
  python3 "$ROOT/src/patch_app.py" restore --app "$APP"
  echo "✓ 已还原 webview/扩展补丁（语言包仍安装在 $EXT_HOME，可在设置里切换语言）"
  exit 0
fi

echo "== 1/3 安装语言包到 $EXT_HOME"
for loc in zh-cn zh-tw zh-hk zh-mo; do
  src="$ROOT/packs/$loc"
  [ -d "$src" ] || { echo "  缺少 packs/$loc（先运行 python3 src/build_packs.py）"; continue; }
  dst="$EXT_HOME/devin-zh.$loc-1.0.0"
  rm -rf "$dst"; mkdir -p "$dst"
  cp -R "$src/"* "$dst/"
  echo "  $loc → $dst"
done

echo "== 2/3 应用 webview + 扩展补丁（新增式，英文不受影响）"
python3 "$ROOT/src/patch_app.py" apply --app "$APP" --translations "$ROOT/translations"

echo "== 3/3 完成"
cat <<EOF
重启 Devin Desktop 两次后，在菜单栏选择语言：
  Devin → 设置/搜索 "Configure Display Language" → 选 中文(简体)/中文(台灣)/中文(香港)/中文(澳門)
英文和其它语言完全不受影响，随时可切回。
OTA 升级后重跑 bash install.sh 即可自愈（补丁幂等）。
EOF
