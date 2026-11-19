# 工作状态（崩溃恢复用）

目标：Devin Desktop 完整中文本地化 → github.com/Till3005/devin-desktop-zh
四层语言包 zh-cn/zh-tw/zh-hk/zh-mo + 一键安装器 + webview 补丁 + OTA 自愈。

## 已完成
- 提取：extracted/（nls.metadata/messages、webview-CV/CH、sessions-OZo/zZo、literals、extensions、product）
- MS 基线包 vendor/ms-pack/{zh-hans,zh-hant}（v1.131.x，覆盖 nls 84%）
- src/patch_app.py：按内容锚点定位 en 字典（`{"adminPromotionOwner":{"label":"Enterprise or org"` / `{"guide":{"step":"Part {{number}}`），JSON.parse 载荷 zh 覆盖 + 字面量白名单 + 扩展 package.json；备份/恢复/状态子命令；原子写。**已在真机验证：补丁后 app 正常启动，webview 中文生效**（macOS 签名无阻碍）
- ~/.devin/argv.json 已设 locale=zh-cn；语言包机制 = 装到 ~/.devin/extensions + extensions.json 登记 + argv.json locale；需两次重启
- 术语表 glossary.md（含 zh-TW/zh-HK 地区词表与翻译规则）
- 语料：work/webview.en.tsv 33920、work/review.en.tsv 1448、work/nls-gap.en.json 4420、work/literals.en.list.json 938、work/exts.en.list.json 491

## 进行中：zh-CN 精翻
- work/zh-cn/webview.partNN.tsv：逐块翻 webview.en.tsv（key\tzh，行序一致）；partNN 对应 en.tsv 行段
- 进度：见下方「翻译进度」
- 完成后：review/literals(先人工筛选可翻项!)/exts/nls-gap
- 合并脚本 src/merge_zh.py（待写）：partNN.tsv → translations/zh-cn/{webview,nls,literals,exts}.json
- OpenCC：zh-cn→zh-tw(s2twp)/zh-hk(s2hk)+地区词表 → zh-mo=zh-hk

## 注意
- 字面量白名单危险：只翻显示文本（之前 "Next" 24 处替换无语法错但可能改语义——逐条核）
- patch_app.find_str 返回闭引号下标（i，非 i+1）
- node --check 验证补丁后 bundle 语法
- **补丁改为增量注入（用户要求：中文=菜单新增项，不替换英文，零兼容风险）**：
  i18next init 在两 bundle 中为 `vO.use(wA).init({resources:n,lng:"en",fallbackLng:"en",ns:["translation","review"],...})`（chat: `resources:n` / sessions: `resources:p`，dict 变量 CJ/CQ、zIn/jZo）。
  - 补丁1：`lng:"en"` → `lng:(globalThis._VSCODE_NLS_LANGUAGE||navigator.language||"en")`（`_VSCODE_NLS_LANGUAGE` 是 VS Code 注入的 argv.json locale；两 bundle 都已读它，chat webview 内可能未设则回落 navigator.language）
  - 补丁2：在 `i&&vO.addResourceBundle("en","translation",i,!0,!0)`（chat）/ `l&&oI.addResourceBundle("en","translation",l,!0,!0)`（sessions）后追加 IIFE：只在 `_VSCODE_NLS_LANGUAGE` ∈ {zh-cn,zh-tw,zh-hk,zh-mo} 时 JSON.parse 对应字典并 addResourceBundle 两个 ns；zh-mo 映射复用 zh-hk 字典
  - en 资源完全不动；zh 以外语言 → i18next fallbackLng:"en" 自动回英文；MS 语言包天然以「新增语言」进显示语言菜单
  - patch_app.py 需按此重写（旧版覆盖 en dict 叶值）
- 应用路径 ~/Applications/Devin.app/Contents/Resources/app；deb 测试副本 /tmp/devin-app/usr/share/devin-desktop/resources/app
- python 用 /opt/homebrew/bin/python3.12（系统 3.9 不支持 dict|None）

## 翻译进度
webview: 33920/33920 ✅ 全部完成（part01-145）
review: 1448/1448 ✅ 全部完成（part01-09）
nls-gap: 4420/4420 ✅（part01-34 全部完成）
literals: ~360/938（part01 已写，覆盖 0-458 白名单 + 459+ 句选；其余为图标/CSS/激活事件不译） 待办（先手工白名单）| exts: 0/491 待办

新词（本段2）：等价生产工程小时 equivalent productive engineering hours, 移动平均 moving average, LOB, 生产会话 productive session, 合并率 merge rate, 绕权限 bypass permissions, 本地手 Local Hands, 配对码 pairing code, 维护者编辑 maintainer edited, 玩偶 plushie, 编排会话 orchestrator session, 共享 VM shared VM, 已定 settled, 脱敏值 redacted value, 集合 collection, 服务用户 service user, 供应 provision

新词（本段）：审计 audit log, 注册 enroll/enrollment, 组映射 group mappings, 联邦凭据 federated credential, 身份提供商 identity provider, 静态 key static key, 工作负载 workload, 横幅 banner, 档 tier（机器大小也用 档/大小）, 槽 slot, 嵌套虚拟化 nested virtualization, 回退档位 fallback tier, 端点服务 endpoint service, NLB, PrivateLink, 投递 delivery, 可筛字段 filterable fields, 签名密钥 signing secret, 目标组 target group, 学习 Devin University/课程/认证/考试/测验, 差异构建 differential builds, 挡 block, 共享连接 shared connection, 个人 token personal tokens, 工具权限 tool permissions, 利用率 utilization
## 状态 2026-11-19
- 全部语料完成：webview 33,920 / review 1,448 / nls-gap 4,420 / exts 白名单 247 / literals 白名单 ~393
- 4 地区包已生成+构建（packs/zh-{cn,tw,hk,mo}，各 28,812 条）
- patch_app.py v2 新增式补丁已上线实测：菜单/设置/webview/扩展命令全中文，English 可切回，完整性校验通过（checksums 回写）
- 安装器 install.sh/install.ps1 完成
- 剩余：登录态界面未验证（本机登出）

## webapp-host 第三面 (2026-11-19)
- en 语料已抽：work/zh-cn/webapp.en.tsv 26,509 行（translation 429 ns + review 50 ns），1 个 EXPR 行(review.onboarding.intro.features)
- 分 54 份：work/zh-cn/webapp-parts/webapp.part00-53 (500行/份)
- 翻译中：翻完写 webapp.partNN.zh.tsv（part00-52 完成 26500/26509，下一份 part53）
- 源：chunk-entry-host-editor-mode-menu-BWLlgqZu.js (mu=sl/au; JSON.parse 与字面量混合)
- 待办：注册 zh chunk 到 gu[]（en/ja/pt/es/de 同款 {code,label,translation,review}），语言检测接 _VSCODE_NLS_LANGUAGE；patch_app 扩展；Devin Settings/Local 会话面板补截图
- Devin Settings 页/会话面板 = webapp-host surface（已确认登录态渲染英文）
