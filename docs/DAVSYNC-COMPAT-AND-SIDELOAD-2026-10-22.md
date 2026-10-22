# DAV-Sync 载体兼容性验证与扩展侧载方法

> 性质说明：这**不是** davsync 同步功能的测试报告——受 MV2 限制，fork 在本轮所有载体上均未能真正运行，同步链路（配置→同步→恢复→比对）尚未执行过。本文记录的是：
> 1. 各候选载体对「带扩展的 uBO fork」的兼容性验证结论；
> 2. 坚果云 WebDAV 后端连通性验证；
> 3. Chrome 137+ 未打包扩展侧载的完整自动化方法（可复用）。
>
> 真正的功能测试报告待 MV2 载体（百分浏览器等）就绪后另行产出。
>
> 日期：2026-10-22
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
