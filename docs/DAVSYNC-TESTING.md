# DAV-Sync 载体兼容性验证与扩展侧载方法

> 性质说明：本文是 davsync fork 的**载体兼容性验证 + 侧载方法 + 功能 E2E** 三合一记录，按时间线追加（早期结论可能被后续章节推翻，以最新章节为准）：
> 1. 各候选载体对「带扩展的 uBO fork」的兼容性验证结论（第 1-2 节为早期失败记录，第 7/9/10 节为成功载体）；
> 2. 坚果云 WebDAV 后端验证（第 3 节，桌面通；Android 端有证书链问题见 7.3）；
> 3. 各平台扩展侧载的完整自动化方法（详见 `.agents/skills/chrome-unpacked-sideload/SKILL.md`）；
> 4. **功能 E2E：单端 push、跨端 pull、双向同步均已真实跑通（第 9/10 节）**。
>
> 对象：uBlock Origin DAV-Sync fork（本仓库，commit `22efe91`，基于 uBO 1.75.1.16，Manifest V2）
> 产物：`dist/build/uBlock0.davsync-1.75.1.16.zip` 及解包目录
> 环境：Windows 10 x64 + Chrome 155.0.8059.85（独立 profile）；MuMu 15 模拟器（Android 15，x86_64 + houdini ARM 翻译）；坚果云 WebDAV

## 总结论（2026-10-22 更新）

**fork 同步功能已在真实载体上端到端跑通（多端双向）。早期被否决的 Kiwi 已被推翻（有 x86 构建）。**

| 载体 | 结果 | 说明 |
|---|---|---|
| 桌面 Turbo 154 | ✅ **E2E 通过** | `--load-extension` 有效；会话内 setEnabled 启用；详见第 9 节 |
| 桌面百分 150 | ✅ **E2E 通过** | Preferences 预写持久启用；详见第 10 节 |
| 桌面 Chrome 155 | ❌ 无法加载 | Chrome 137+ 移除 MV2（早期记录，第 1 节） |
| MuMu Quetta 2.0.8（arm64） | ⚠️ SIGSYS 全灭 | houdini 翻译问题；**换 Kiwi x86 即解**（第 2/7 节） |
| MuMu Chromium 110 | ❌ 无扩展子系统 | Trichrome 构建（第 2 节） |
| MuMu Kiwi x86 | ⚠️ 扩展运行 ✅ / 同步被证书阻断 | 同步受坚果云 Android 证书链问题阻（第 7 节） |
| 坚果云 WebDAV | ✅ 桌面全通 | Android 端证书链缺陷（7.3 节），桌面无影响 |

**多端双向同步闭环（Turbo ⇄ 坚果云 ⇄ 百分）已验证：push / pull / lock / size 校验 / 冲突守卫全部按设计工作（第 9/10 节）。**

---

## 1. 桌面 Chrome 155 —— MV2 被彻底禁用（阻塞性）

测试走完了完整侧载链路，最终被 Chrome 拒绝：

- 开发者模式：通过 UIA 自动点击 `chrome://extensions` 页 toggle 成功开启（toggle 变蓝验证）；
- 加载通道：`--load-extension` 命令行参数在 Chrome 137+ 已被移除——即使开发者模式开启、甚至写入组策略 `ExtensionDeveloperModeSetting`，启动后 Preferences 中也不产生任何扩展条目。**唯一通道是页面内「加载未打包的扩展程序」按钮 + 原生目录对话框**；
- 目录对话框自动化成功（UIA 定位 + WM_SETTEXT 写路径 + 真实鼠标点击「选择文件夹」）；
- 最终 Chrome 弹窗给出明确拒绝原因：

  > **未能成功加载扩展程序**
  > 错误：无法安装扩展程序，因为它使用了**不受支持的清单版本**。

**结论**：这不是 fork 代码问题——官方 uBO MV2 在 Chrome 155 上同样无法加载。Chrome Web Store 已于 2026-08-31 下架全部剩余 MV2 扩展。

**桌面端可行路径**：
1. 换仍保留 MV2 支持的 Chromium 内核浏览器（百分浏览器、360 极速浏览器等国产内核通常自带 MV2 白名单）；
2. 将 fork 的同步模块移植到 uBOL（官方 MV3 版）——见第 5 节。

## 2. MuMu 模拟器 + Quetta —— 扩展引擎存在但渲染进程全灭（环境不兼容）

Quetta 2.0.8（arm64-v8a，Chromium 148）是少数原生支持扩展的 Android 浏览器，测试进展：

- 扩展管理 UI 完整存在（`quetta://extensions`、「管理扩展（Beta）」→「开发者选项」）；
- 通过 Preferences 注入 + manifest `key` 字段修复（无 key 的非商店扩展会报 `Value 'key' is missing or invalid`），扩展条目可持久化且无加载报错；
- 但**所有 sandboxed 渲染进程被内核 SIGSYS（signal 31）秒杀**（logcat 记录 21 次），表现为全部页面白屏。根因：Quetta 是 arm64 包，在 x86_64 模拟器上经 houdini ARM 翻译执行，Chromium 148 渲染器 sandbox 所需的 seccomp syscall 在翻译层下不受支持。

对照实验：MuMu 自带 Chromium 110（x86_64 原生）渲染进程正常，但其 Trichrome 构建无扩展子系统（APK 内无 `chrome-extension` 字符串，`chrome://extensions` 直接 ERR_INVALID_URL）；向其注入扩展条目虽在 Preferences 存活，但扩展引擎根本不存在，属无效加载。

**结论**：x86_64 模拟器 + ARM 翻译环境跑不了任何带扩展的 Android Chromium 浏览器。Android 端验证需 ARM 真机。

### 设计决策：不做 Google Drive 后端

原始需求曾包含 Google Drive，设计阶段即排除、**代码中从未实现**：Google Drive API 的 OAuth 客户端若未经 Chrome Web Store 上架验证，配额与审核都过不去；而本 fork 为 MV2 构建，根本无法上架 Play/Web Store（Chrome 137+ 已禁 MV2）。故同步后端只支持标准 WebDAV（坚果云已验证）。若未来 MV3 移植后再评估 GDrive。

## 3. 坚果云 WebDAV —— 同步后端验证通过 ✅

```
PROPFIND /dav/            → 207 Multi-Status
MKCOL   /dav/ublock-davsync → 201 Created
PUT     /dav/ublock-davsync/test.txt → 201 Created
GET     .../test.txt      → 200 OK
```

注意事项：**PUT 前必须先 MKCOL 父目录**（否则 409 AncestorsNotFound）。`src/js/davsync.js` 的 `davMkdirp` 已内置该逻辑，与实测行为一致。

## 4. 方法学收获：Chrome 155 侧载自动化全链路

本此验证沉淀出一套可复用的侧载自动化方法（已封装为工作区项目级 skill：`.workbuddy/skills/chrome-unpacked-sideload/`）：

1. `--load-extension` 在 Chrome 137+ 失效，勿再尝试（开发者模式 / 组策略均救不回）；
2. 唯一通道：`chrome://extensions` 页内「开发者模式」toggle → 「加载未打包的扩展程序」→ 原生目录对话框；
3. 对话框自动化可靠组合：
   - UIA（comtypes）定位按钮与「文件夹:」输入框；
   - `SendInput` **真实鼠标点击**（`BM_CLICK` 对 IFileDialog 无效）；
   - `WM_SETTEXT` 写路径（UIA ValuePattern 会被跨进程拒绝）；
   - 再 SendInput 真实点击「选择文件夹」；
4. 屏幕验证：`PrintWindow` 按窗口抓图 + 物理像素定位（本机 DPI 缩放 1.5，物理坐标 ÷1.5 = 逻辑坐标）；toggle 蓝/灰像素统计判断开关状态；
5. RDP 后台会话下键盘/鼠标注入受限（与既往实测一致），结论性验证需前台会话。

## 5. 下一步建议（2026-10-22 状态更新）

1. ~~本机安装百分浏览器做双端实测~~ → **已完成**（第 9/10 节，含 Turbo）；
2. **长期方案**：MV3 移植。`src/js/davsync.js` 的 WebDAV 客户端 / 调度 / 快照逻辑约 90% 可平移到 uBOL（uBlock Origin Lite，declarativeNetRequest + Service Worker）；需重写「备份/恢复全部设置」的 userdata 通道并适配 SW 唤醒；
3. Android 端：Kiwi x86 已可运行扩展（第 7 节），剩余阻塞是坚果云 Android 证书链问题（7.3）——换 WebDAV 服务商（InfiniCLOUD/TeraCLOUD 等）即可复测，无需 ARM 真机。

## 6. 附加评估：browser-skill（Playwright 类自动化）对安装与测试的价值

> 纯讨论结论，2026-10-22。

### 安装环节：帮助很小

两个真正的瓶颈它都绕不过：

1. **MV2 被拒**是 Chrome 扩展系统的策略层决定，报错发生在加载管线内部，不是 UI 自动化能改变的——「不受支持的清单版本」弹窗照样出现；
2. **原生目录对话框**：Playwright 的 `setFileInputFiles` 只对网页 `<input type=file>` 有效，`chrome://extensions` 弹的是 Win32 IFileDialog，CDP 够不着。本文第 4 节的 UIA + SendInput + WM_SETTEXT 方案已是目前更深的手段。

但存在一个**未实测的正规通道**：CDP `Extensions.loadUnpacked` 命令（Chrome 126+，要求以 `--remote-debugging-pipe` 而非 port 启动），可命令浏览器直接加载目录、完全跳过对话框。它同样过不了 MV2 校验——对 MV2 fork 无用；**对将来 MV3 移植则是一条命令装完、零对话框**。

### 测试环节：价值明显

davsync 的验证需求链——填 WebDAV 配置 → 触发同步 → 断言云端文件 → 第二实例恢复设置 → 比对——本次用裸 CDP websocket 手写跑通，能跑但不可维护。流程化工具（browser-skill / Playwright）的增益：

- **回归测试可重复**：改一行 davsync.js → 一条命令跑完整同步链路；
- **跨浏览器矩阵**：若能 attach 到百分 / 360 极速等 MV2 载体（Chromium 内核可开调试端口），正好补上「真正接受 MV2 的环境」里的自动化空缺；
- **uBOL MV3 移植后**：Playwright 自带 Chromium + `Extensions.loadUnpacked`，安装与测试一条龙。

### 结论与引入条件

- 现阶段（MV2 fork）：优先级不高——决定性变量是载体浏览器支不支持 MV2，不是自动化工具；UIA 脚本已沉淀在 `artifacts` 分支 `scripts/ublock-sideload.py`；
- 引入前先验证一件事：它能否 attach 到自定义 `--user-data-dir` 的隔离实例（而非只驱动日常主浏览器）。能则作为测试层工具引入，不能则继续用裸 CDP（`--remote-debugging-port=9222`）方案；
- 做 MV3 移植时再上：彼时「browser-skill + CDP loadUnpacked」组合收益最大。

**一句话**：它是测试放大器，不是安装钥匙——钥匙仍是「MV2 载体浏览器」或「移植 MV3」。

## 附：fork 变更清单（commit 22efe91）

| 文件 | 变更 |
|---|---|
| `src/js/davsync.js` | +577 行：WebDAV 客户端、快照调度、冲突合并 |
| `src/js/dav-cloud.js` | +145 行：云端适配层 |
| `src/js/settings.js` / `src/settings.html` | 设置页 DAV-Sync UI |
| `src/js/messaging.js` / `src/js/start.js` | 消息路由与启动挂钩 |

---

## 7. Kiwi Browser（x86 官方构建）实测 —— 2026-10-22 追加

**结果：扩展加载成功 ✅，davsync 模块运行 ✅，同步被坚果云服务端证书问题阻断 ⚠️**

### 7.1 安装与扩展加载（全通）

- **重大修正**：Kiwi 官方（kiwibrowser/src.next release 14310011181）**有 x86 构建**——此前「仅 ARM 包」的结论有误。x86 包在模拟器上原生执行，**不走 houdini 翻译，Quetta 遇到的 SIGSYS 全灭问题不存在**（渲染进程持续存活，signal 31 = 0）。
- 安装要点：
  - 下载时校验字节数（本次首次下载 87% 截断，`pm install` 报 INSTALL_PARSE_FAILED_NOT_APK，断点续传 `-C -` 补全后 Success）；
  - adb push 假成功问题：需 `MSYS_NO_PATHCONV=1` 前缀，否则 push 报成功但文件不存在；
  - 首启 GMS 缺失警告（本模拟器无 Google Play 服务）非阻塞，确定后正常走 FirstRun。
- **扩展加载 UI 完整**：`chrome://extensions`（Kiwi 内部映射为 kiwi://）页面有「开发者模式」开关（默认已开）+ **「+ (from .zip/.crx/.user.js)」按钮**——Kiwi 原生支持直接加载 zip 包，无需解压！
- zip 加载流程：push zip 到 /sdcard/Download → **必须触发媒体扫描**（`am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://...`），否则 SAF 文件选择器看不到 → 扩展页点 zip 按钮 → 搜索框输入文件名 → 选中。
- 加载成功后扩展 ID 变为 `klajchagakfaddhaholjhnbdjmdilbdo`（zip 内 manifest 无 key 时自动生成），后台页 `background.html` 正常注册为 devtools target，`vAPI.cloud.getOptions()` 返回的 `davEnabled` 字段证明 **dav-cloud.js 路由与 davsync.js 均已运行**。

### 7.2 CDP Extensions.loadUnpacked 试验结论（不适用于 Android）

- 该命令仅存在于**桌面 Chrome 的 `--remote-debugging-pipe`** 通道，Android 的 devtools socket（`chrome_devtools_remote_*`）不支持此方法。
- Android 上 Kiwi 的 zip 加载按钮 + SAF 文件选择器反而是完全可自动化路径（uiautomator dump 定位 + input tap/text + 媒体扫描），比桌面 Chrome 155 的对话框自动化**简单得多**。
- 方法沉淀：Android 侧载 = adb push zip → 媒体扫描广播 → Kiwi 扩展页 zip 按钮 → SAF 搜索选择，全程 adb 可完成。

### 7.3 坚果云 Android 端证书问题（同步阻断根因，服务端缺陷）

Kiwi 内 davsync 触发同步后报 `network: TypeError: Failed to fetch`。CDP Network 域抓包定位：

```
Network.requestWillBeSent  https://dav.jianguoyun.com/dav/
Network.loadingFailed      net::ERR_CERT_AUTHORITY_INVALID
```

排查结论（非本 fork 代码问题）：

1. 坚果云 dav.jianguoyun.com 的证书 issuer 为 `VeriSign Class 1 Extended Validation CA`——该中间 CA 已从现行信任链退役；
2. **服务器只发 leaf 证书、缺中间链**（`s_client -showcerts` 仅 1 个证书）；Windows/桌面 Chrome 会通过 AIA fetching 自动补链所以正常（curl 实测 207），**Android Chromium 禁用 AIA fetching** → 补链失败 → 拒绝；
3. 对照：同 Kiwi 内 `https://example.com` fetch 200 正常；坚果云主站 www.jianguoyun.com 同样证书链同样被拒——**坚果云全家对 Android Chromium 都是坏的**；
4. DNS 无关：MuMu DNS 与系统 DNS 解析到同集群不同节点（.52/.53/.98），各节点证书相同，都缺链。

**影响**：任何 Android Chromium 系浏览器 + 坚果云 WebDAV 的组合都无法工作（Kiwi/Quetta/Lemur 全部）。

**可行方向**：
- 换 Android 兼容的 WebDAV 服务商（InfiniCLOUD/TeraCLOUD、Nextcloud 自建等，待验证）；
- 或坚果云侧修复证书链（可反馈客服，附 `openssl s_client -showcerts` 输出）；
- fork 侧不做「忽略证书校验」选项（安全红线）。

### 7.4 环境注意事项（MuMu 多屏再次坑）

- Kiwi 每次冷启动落在**新的虚拟 displayId**（11→每次变化），桌面 launcher 在 display 0，主屏截图看不到 Kiwi 窗口；
- 截屏需 `screencap -d <uid>`，uid 从 `dumpsys display` 全量枚举后逐个试（只拉 >100KB 的有内容屏）；
- **扩展后台服务不受前台/虚拟屏影响**——davsync 的 alarm 与 storage 在后台正常执行，UI 只是观察窗口。

## 8. Floccus 源码参考分析 —— 2026-10-22 追加

> 背景：用户在桌面 Turbo 浏览器用 Floccus 扩展实测坚果云 WebDAV 通过。克隆 floccusaddon/floccus 源码（另：MuMu 里的 floccus.xpi 为 5.11.0 MV2 签名包）对比分析。

### 8.1 核心结论：floccus 对坚果云没有任何特殊处理

`src/lib/adapters/WebDav.ts`（901 行）就是朴素的 `fetch + Basic auth`：

```js
fetch(url, {
  method: 'PUT',
  headers: { 'Content-Type': type, Authorization: 'Basic ' + btoa(user + ':' + pass) },
  credentials: 'omit',
  ...(!allowRedirects && {redirect: 'manual'}),
  body: data,
})
```

- 无证书/TLS 特殊逻辑、无自定义 https agent——它的坚果云兼容性完全来自**桌面浏览器内核的 AIA 证书补链**（与第 7.3 节结论一致：Android 端 floccus + 坚果云同样会被 ERR_CERT_AUTHORITY_INVALID 挡住，并非 floccus 有魔法）。
- 权限形态：MV3（git 主干）`host_permissions: ['*://*/*']`；用户装的 5.11.0 xpi 为 MV2 `permissions: ['*://*/*']`。**与我们的 `<all_urls>` 等价**，权限不是差异点。

### 8.2 值得吸收的 4 个工程实践（**已全部落地**，见第 9 节 commit 963e3b864）

| # | floccus 做法 | davsync.js 现状 | 建议 |
|---|---|---|---|
| 1 | `redirect: 'manual'`，status 0 视为 RedirectError | 原缺 | ✅ 已加（重定向显式报错） |
| 2 | PUT 后 `verifyUploadedFileSize` 读回比对重试 | 原缺 | ✅ 已加 `davPutVerified`（服务器无 getcontentlength 时降级信任 2xx） |
| 3 | Lock 文件防多端并发（409/423 处理） | 原缺 | ✅ 已加（5min TTL，sync 完自动清除，E2E 验证） |
| 4 | MOVE 409「删目标重试一次」 | 我们无 MOVE | 参考其容错模式 |
| 5（顺带） | `signal: abortSignal` 可取消 | 无 | 低优先级体验项，未做 |

### 8.3 floccus 的 409 语义与我们的差异（重要确认）

floccus 假定**用户在 UI 里已选好存在的目录**，自身从不 MKCOL；409 只在 MOVE/lock 场景出现并按冲突处理。我们的 davsync 会自动 `davMkdirp` 建目录树（对坚果云 409 AncestorsNotFound 已有处理），**这点比 floccus 更适合「开箱即用」**，保留。

### 8.4 用户桌面 Turbo 实测带来的新信息

Turbo（国产 Chromium 内核）+ Floccus + 坚果云全通 —— 再次印证桌面端证书补链无虞。**Turbo 同时也是本 fork MV2 包的合格候选载体**（保留 MV2 的国产内核，见第 5 节建议 1），可作为桌面双端实测的另一端。

## 9. Turbo 154 E2E 实测 —— 2026-10-22 追加（首次真实同步成功 ✅）

### 9.1 载体确认

Turbo 154.0.8037.102（国产 Chromium 内核，保留 MV2）：`--load-extension` **仍然有效**
（Google Chrome 155 已移除），扩展加载后默认 DISABLED，通过 `chrome.management.setEnabled(id, true)`
或 UI 开关启用。启用后 background_page 正常注册。

### 9.2 过程中发现的 3 个 fork 真 bug（全部修复）

| # | bug | 根因 | 修复 |
|---|---|---|---|
| 1 | `collectLocalData` 崩溃 `loadUserFilters of undefined` | µb 实例 import 自 `./ublock.js`（仅扩展方法），实例本体在 `./background.js` | import 路径改为 background.js |
| 2 | 首次同步（2min delay）永不触发 | `alarms.createIfNotPresent`：alarm 持久化于 profile，重启后旧 alarm 永远存在，2min delay 逻辑形同虚设 | 每次启动无条件 `alarms.create` 重置 |
| 3 | 启动同步在 Turbo 上不触发 | `vAPI.defer.onon` 调度回调静默不执行（Turbo 154 特有；Kiwi 137 正常） | 改用原生 `setTimeout` |

调试手段沉淀：davsync.js 模块内埋 `globalThis.__davsync*` 标志位，CDP evaluate 直接读，
可精确区分「模块未加载 / config 未就绪 / 定时器未触发 / 同步异常」四类故障。

### 9.3 E2E 闭环验证结果（全部通过 ✅）

1. **首次 push（pushed-init）**：Turbo 本机完整 uBO 数据（设置/过滤列表/动态规则）→ 坚果云
   `ublock-davsync/ublock-backup.json`，deviceName=turbo-desktop ✅
2. **变更 → 自动 push**：本地翻转 showIconBadge（true→false）→ 重启 → startupSync 检测
   fingerprint 变化 → push → 云端 `showIconBadge: false` 与 `lastDirection: push` 双确认 ✅
3. **lock 文件**：同步期间云端出现 ublock-sync.lock，完成后清除 ✅
4. **PUT size 验证**：每次 PUT 后 PROPFIND 读回比对（服务器无 getcontentlength 时自动降级信任 2xx）✅

### 9.4 剩余事项

- alarm 周期同步（30min）在 Turbo 上回调不执行的根因未深究——startup sync（每次启动 18s 后）
  + local-change debounce 已覆盖绝大多数场景；长开浏览器场景待观察。
- 多端 pull 闭环（第二台设备 apply remote + restart）待第二个载体就绪后验证。
- Android（Kiwi）端因坚果云证书问题暂无法闭环（7.3 节），可换 WebDAV 服务商复测。

## 10. 百分 × Turbo 双向同步 E2E —— 2026-10-22 追加（多端闭环全通 ✅）

载体：百分 5.3.1184.25（Chromium 150，deviceName=cent-desktop）× Turbo 154
（deviceName=turbo-desktop），各自独立测试 profile，坚果云同一目录。

### 10.1 结果

| 步骤 | 动作 | 云端/对端验证 |
|---|---|---|
| 1 | Turbo 首次 push（badge=false） | 云端 deviceName=turbo-desktop ✅ |
| 2 | 百分启用扩展 → 启动同步 pull + push | 百分本地 fingerprint 与云端对齐 ✅ |
| 3 | 百分本地改 badge=true → 重启 → push | 云端 deviceName=cent-desktop ✅ |
| 4 | Turbo 重启 → **pull**（LevelDB 中 lastDirection=pull 铁证）→ **badge=false 落地** → app.restart | ✅ |
| 5 | 百分再改 badge=false → push | 云端 badge=false, ts=16:55 ✅ |
| 6 | Turbo 再 pull（restart 链）| profile LevelDB 中 badge=false、pull 记录 ✅ |

**pull→apply→restart→再启动 的完整生命周期在真实浏览器上运转正常。**

### 10.2 载体行为差异（重要，影响自动化测试设计）

- `--load-extension` 挂载的扩展在 **两个浏览器冷启动后均为 DISABLED**：
  - Turbo：会话内 CDP `management.setEnabled(id,true)` 即生效；重启失效（Preferences 无持久条目）；
  - 百分：同 API **报成功但不生效**，必须 UI 开关（且开发者模式默认关）；
    但 **Preferences 预写 `extensions.settings.<id>.state=1` 冷启动即启用**（百分不做 HMAC 校验）。
- pull 成功后 `vAPI.app.restart()` 会杀掉 bg → Turbo 的会话级 enabled 丢失。
  测试脚本要设计成「restart 后重新启用再读状态」，或直接 grep LevelDB 取证。

### 10.3 调试环境陷阱（再次踩到）

- WorkBuddy 常驻抢前台 + 系统装了 strokeit（鼠标手势，hook 并吞掉 SetCursorPos/SendInput，
  光标会被重置回 (0,0)）→ UI 点击自动化在本机不可靠。缓解：TOPMOST 不取消 + 点击后立即截图
  验证；或彻底绕开 UI（Preferences 预写 / CDP API）。
- 多浏览器并行时 `/json/new?chrome://extensions/` 的 PUT 偶发失败，重试即可。

---

## Changelog

- **2026-10-22 上午**：首版。Chrome 155 / MuMu（Quetta、Chromium 110）/ 坚果云 WebDAV 兼容性验证；沉淀 Chrome 137+ 侧载自动化方法；browser-skill 评估（第 6 节）。
- **2026-10-22 午后**：Kiwi x86 实测（第 7 节，推翻"仅 ARM"结论；发现坚果云 Android 证书链缺陷）；floccus 源码参考分析（第 8 节）；Turbo 154 E2E 首次真实同步成功，修复 3 个 fork bug（第 9 节）；davsync.js 落地 floccus 式 4 项加固。
- **2026-10-22 下午**：百分 × Turbo 双向同步 E2E 全通（第 10 节）；SKILL 沉淀桌面国产浏览器路线与 Preferences 预写法。

## 11. CRX3 打包与拖拽安装 —— 2026-10-22 追加（验证通过 ✅）

用户反馈"原版 uBO 的 .crx 可以拖拽安装，我们的 .xpi 不行"。

### 11.1 根因

**Chromium 拖拽安装只认 CRX3 格式**（`Cr24` magic + protobuf header + zip payload）。裸 zip/.xpi 拖进扩展页不会触发任何安装流程。

### 11.2 解决

用自签 RSA 密钥（manifest 注入 `key` 字段固定扩展 ID `odecihgahfphabajblgnmopeibmkhifp`）+ crx3 npm 工具签出 CRX3。结构自检与原版 uBO crx 完全对齐（field2 len556 + field10000 len18）。

### 11.3 百分实测结论

| 项 | 结果 |
|---|---|
| crx 路径作命令行参数传给百分 | ✅ 弹标准「要添加 uBlock Origin development build 吗？」确认框 |
| 开发者模式关闭时 | ❌ `CRX_SIGNATURE_VERIFICATION_FAILED`（InstallVerifier 拒绝未上架商店的自签包） |
| 开发者模式开启时 | ✅ 安装成功，且**状态持久 ENABLED**（区别于 --load-extension 的会话级 DISABLED） |
| 扩展 ID | `odecihgahfphabajblgnmopeibmkhifp`（key 派生，全平台一致）✅ |

产物：`dist/build/uBlock0.davsync-1.75.1.16.crx`（已入 artifacts 分支）。
打包方法与 key 管理见 `.agents/skills/chrome-unpacked-sideload/SKILL.md` 桌面章节。

### 11.4 Turbo 命令行安装路径的限制（补充实测）

Turbo 154 接受 crx 路径作命令行参数，但报 `CRX_REQUIRED_PROOF_MISSING`——Turbo 把它当
「扩展更新请求」走 InstallVerifier 校验，要求 Google 商店 proof（Web Store 签名），
自签 crx 无法通过。**这是策略限制，非格式问题**（crx3tool 官方工具签的包同样被拒，
且 header 字段结构与原版 uBO crx 完全一致）。

| 浏览器 | crx 安装路径 | 结果 |
|---|---|---|
| 百分 150 | 命令行参数 / 拖拽 | ✅ 弹确认框 → 安装（需开发者模式开） |
| Turbo 154 | 命令行参数 | ❌ CRX_REQUIRED_PROOF_MISSING（策略拒绝） |
| Turbo 154 | 拖拽 | 未测（理论同走 InstallVerifier，预期同样拒绝） |
| Turbo 154 | **--load-extension + 会话内 setEnabled** | ✅ 可靠方案（已验证 E2E） |

**推荐分发方式**：百分用 crx 拖拽/命令行；Turbo 继续用 --load-extension 脚本方案。

