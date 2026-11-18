# Devin Desktop 中文语言包一键安装 (Windows)
# 用法: powershell -ExecutionPolicy Bypass -File install.ps1
#       powershell -ExecutionPolicy Bypass -File install.ps1 -Mode restore
param([string]$Mode = "apply", [string]$App = "")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $App) {
  $candidates = @(
    "$env:LOCALAPPDATA\Programs\Devin\resources\app",
    "$env:ProgramFiles\Devin\resources\app",
    "${env:ProgramFiles(x86)}\Devin\resources\app"
  )
  foreach ($c in $candidates) { if (Test-Path $c) { $App = $c; break } }
  if (-not $App) { throw "未找到 Devin Desktop 安装目录，请用 -App 指定" }
}
$ExtHome = Join-Path $env:APPDATA ".devin\extensions"
$Py = (Get-Command python -ErrorAction SilentlyContinue) ?? (Get-Command python3 -ErrorAction SilentlyContinue)
if (-not $Py) { throw "需要 Python 3 在 PATH 中" }

if ($Mode -eq "restore") {
  & $Py.Source "$Root\src\patch_app.py" restore --app "$App"
  Write-Host "已还原 webview/扩展补丁（语言包仍在 $ExtHome）"
  exit 0
}

Write-Host "== 1/3 安装语言包到 $ExtHome"
foreach ($loc in @("zh-cn","zh-tw","zh-hk","zh-mo")) {
  $src = Join-Path $Root "packs\$loc"
  if (-not (Test-Path $src)) { Write-Host "  缺少 packs\$loc（先运行 python src/build_packs.py）"; continue }
  $dst = Join-Path $ExtHome "devin-zh.$loc-1.0.0"
  if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
  Copy-Item -Recurse $src $dst
  Write-Host "  $loc → $dst"
}

Write-Host "== 2/3 应用 webview + 扩展补丁（新增式，英文不受影响）"
& $Py.Source "$Root\src\patch_app.py" apply --app "$App" --translations "$Root\translations"

Write-Host "== 3/3 完成"
Write-Host "重启 Devin Desktop 两次后，搜索 'Configure Display Language' 选择中文语言。"
Write-Host "英文不受影响，可随时切回；OTA 升级后重跑本脚本即可自愈。"
