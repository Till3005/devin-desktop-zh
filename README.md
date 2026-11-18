# devin-desktop-zh

Devin Desktop 的**社区中文本地化**——完整汉化 + 四地区语言包 + 一键安装。

简体中文（大陆）· 繁體中文（台灣）· 繁體中文（香港）· 繁體中文（澳門）

> Unofficial community localization. Not affiliated with Cognition AI.

---

## 特点

- **完整覆盖三层界面**：菜单栏/设置/编辑器（nls，约 28,800 条）、Agent 面板与聊天 webview（i18next，33,920+1,448 条）、内置扩展贡献的字符串（152 条）
- **新增式而非替换**：中文作为 4 个新的显示语言选项加入，English 和其它语言逐字节不受影响，随时切回
- **四地区各按各的习惯**：zh-TW 用台湾惯用语（使用者/預設/登入），zh-HK/zh-MO 用香港惯用语（用戶/資訊/檔案）
- **macOS · Windows · Linux**：`install.sh`（mac/linux）+ `install.ps1`（windows）
- **不破坏完整性校验**：补丁后自动回写 product.json checksums，不弹"安装损坏"警告
- **可还原、可自愈**：`restore` 一键回到原样；OTA 升级后重跑安装即可（幂等）

## 一键安装

```bash
git clone https://github.com/Till3005/devin-desktop-zh
cd devin-desktop-zh
bash install.sh          # macOS / Linux
# 或 Windows:
powershell -ExecutionPolicy Bypass -File install.ps1
```

重启 Devin Desktop 两次后，在命令面板搜 `Configure Display Language`，选择 中文(简体)/中文(台灣)/中文(香港)/中文(澳門)。

还原：`bash install.sh restore`

## 工作原理

| 层 | 机制 | 覆盖 |
|---|---|---|
| nls | VS Code 官方语言包扩展装进 `~/.devin/extensions/` | 菜单/设置/编辑器约 28.8k 条（微软官方包 + 4,420 条 Devin 定制自翻） |
| webview | i18next `resources` 注入 zh 字典 + `lng` 读 `_VSCODE_NLS_LANGUAGE`；硬编码字面量改条件查询 | Agent 面板/聊天/onboarding |
| 扩展 | 内联 display 字符串转 `%key%` + `package.nls.<loc>.json` | windsurf 系列内置扩展 |

所有补丁文件都有 `.devin-zh-backup` 还原点，restore 逐字节还原。

## 翻译质量

- zh-CN 全部人工级逐条精翻（非机翻批量跑），统一术语表（[glossary.md](glossary.md)）：你/命令/会话/工作区/设置，Devin 专有名词保留英文（Slack、MCP、ACU、PR、worktree、Cascade、Blobby…）
- `{0}`、`{{var}}`、`\n`、`[text](url)`、菜单 `&&X` 加速键全部原样保留
- zh-TW/HK/MO 由 OpenCC 字形转换 + 地区惯用语覆盖表派生

## 已知边界（诚实声明）

- 覆盖按"字典键"生效：未收录进语料的零散硬编码串回退英文（属预期，遇到可提 issue 补录）
- 登录态界面（Devin Settings 页、会话内聊天）在本仓库作者机器上未登录验证过，欢迎反馈
- OTA 升级后需重跑一次安装脚本（幂等、秒级）

## 仓库结构

```
packs/<loc>/           4 个成品语言包（VS Code 格式）
translations/<loc>/    各层中文字典（webview/review/nls/exts/literals）
src/patch_app.py       新增式补丁器（apply/restore/status + checksum 回写）
src/merge_zh.py        语料合并
src/build_packs.py     语言包构建
src/gen_regions.py     zh-TW/HK/MO 派生（OpenCC + 地区词表）
install.sh / install.ps1
work/                  原始 en 语料 + 分片翻译 TSV
```

## License

MIT。微软 vscode-loc 基础包部分沿用 MIT 许可上游（vendor/ms-pack）。Devin Desktop 本身属 Cognition AI，本仓库仅分发词典与补丁，不含任何 app 二进制。
