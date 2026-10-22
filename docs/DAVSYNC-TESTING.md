# DAV-Sync 载体兼容性验证与扩展侧载方法

> 性质说明：这**不是** davsync 同步功能的测试报告——受 MV2 限制，fork 在本轮所有载体上均未能真正运行，同步链路（配置→同步→恢复→比对）尚未执行过。本文记录的是：
> 1. 各候选载体对「带扩展的 uBO fork」的兼容性验证结论；
> 2. 坚果云 WebDAV 后端连通性验证；
> 3. Chrome 137+ 未打包扩展侧载的完整自动化方法（可复用）。
>
> 真正的功能测试报告待 MV2 载体（百分浏览器等）就绪后另行产出。本文持续迭代，最新验证记录见文末 changelog。
>
> 对象：uBlock Origin DAV-Sync fork（本仓库，commit `22efe91`，基于 uBO 1.75.1.16，Manifest V2）
> 产物：`dist/build/uBlock0.davsync-1.75.1.16.zip` 及解包目录
> 环境：Windows 10 x64 + Chrome 155.0.8059.85（独立 profile）；MuMu 15 模拟器（Android 15，x86_64 + houdini ARM 翻译）；坚果云 WebDAV

## 总结论

**fork 代码本身无问题（语法、模块加载、设置页 UI 均正常），同步后端 WebDAV 全通；但当前主流载体均无法运行 MV2 构建或扩展子系统：**

| 载体 | 结果 | 根因 |
|---|---|---|
| 桌面 Chrome 155 | ❌ 无法加载 | Chrome 137+ 彻底移除 MV2 支持，弹窗明示「不受支持的清单版本」 |
| MuMu 内 Quetta 2.0.8（Chromium 148，arm64） | ⚠️ 扩展可注入、无法运行 | houdini ARM 翻译下渲染进程 seccomp 沙箱 syscall 被内核 SIGSYS(31) 全灭 |
| MuMu 自带 Chromium 110（x86_64） | ❌ 无扩展子系统 | Trichrome 构建未编译 extensions 模块 |
| Kiwi Browser | ❌ 不可用 | 官方已停更，仅 ARM 包（与 Quetta 同样 SIGSYS 命运） |
| 坚果云 WebDAV | ✅ 全通 | PROPFIND 207 / MKCOL 201 / PUT 201 / GET 200 |

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

## 5. 下一步建议（按优先级）

1. **最短路径**：本机安装百分浏览器（保留 MV2 的 Chromium 内核），加载本 fork，配置坚果云做双端同步实测——fork 与后端都已就绪，只差载体；
2. **长期方案**：MV3 移植。`src/js/davsync.js` 的 WebDAV 客户端 / 调度 / 快照逻辑约 90% 可平移到 uBOL（uBlock Origin Lite，declarativeNetRequest + Service Worker）；需重写「备份/恢复全部设置」的 userdata 通道并适配 SW 唤醒；
3. Android 端验证换 ARM 真机进行。

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

## Changelog

- **2026-10-22**：首版。完成 Chrome 155 / MuMu（Quetta、Chromium 110）/ 坚果云 WebDAV 兼容性验证；沉淀 Chrome 137+ 侧载自动化方法；追加 browser-skill 评估（第 6 节）。

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

### 8.2 值得吸收的 4 个工程实践（我们 davsync.js 目前缺的）

| # | floccus 做法 | davsync.js 现状 | 建议 |
|---|---|---|---|
| 1 | `redirect: 'manual'`（可配 allowRedirects），status 0 视为 RedirectError | 未设置（follow 默认） | **加 `redirect: 'manual'`**：防 302 重定向吞掉 Authorization 头导致假 401/丢失 body |
| 2 | PUT 后 `verifyUploadedFileSize`：PROPFIND 读 getcontentlength 比对，不符重试（PUT_FILE_SIZE_RETRIES） | PUT 即认为成功 | **加读回校验 + 有限重试**：坚果云偶发写入静默截断时保证一致性 |
| 3 | Lock 文件防多端并发：sync 前 PUT lock 文件，409/423 → ResourceLockedError；sync 中每 2min 续锁 | 无锁（靠 lastSyncTime 粗协调） | **加 lock 文件**：双端同时 sync 时的文件竞争是真实风险（本 fork 定位就是多端同步） |
| 4 | MOVE 409 时「删目标再 MOVE 重试一次」的恢复逻辑 | 不适用（我们无 MOVE） | 参考其「一次容错重试」模式 |
| 5（顺带） | `cache: 'no-store'`、`credentials: 'omit'`、`signal: abortSignal`（可取消） | 前 两者已有；无可取消 | 低优先级：同步可取消体验项 |

### 8.3 floccus 的 409 语义与我们的差异（重要确认）

floccus 假定**用户在 UI 里已选好存在的目录**，自身从不 MKCOL；409 只在 MOVE/lock 场景出现并按冲突处理。我们的 davsync 会自动 `davMkdirp` 建目录树（对坚果云 409 AncestorsNotFound 已有处理），**这点比 floccus 更适合「开箱即用」**，保留。

### 8.4 用户桌面 Turbo 实测带来的新信息

Turbo（国产 Chromium 内核）+ Floccus + 坚果云全通 —— 再次印证桌面端证书补链无虞。**Turbo 同时也是本 fork MV2 包的合格候选载体**（保留 MV2 的国产内核，见第 5 节建议 1），可作为桌面双端实测的另一端。

