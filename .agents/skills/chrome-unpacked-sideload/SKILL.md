---
name: chrome-unpacked-sideload
description: 扩展侧载与测试的全平台操作手册（实测验证）。覆盖：① Windows Chrome 137+ 对话框自动化（--load-extension 失效场景）② Android Kiwi x86 adb 全自动 zip 加载 ③ 桌面国产浏览器（Turbo/百分，保留 MV2，双向同步 E2E 已通）。触发词：侧载、加载扩展、load-extension、加载未打包、chrome://extensions、扩展测试、Kiwi、Turbo、百分、双向同步。
---

# 扩展侧载与测试手册（Windows / Android / 桌面国产浏览器）

> 范围：**项目级 skill**——本工作区（uBlock DAV-Sync fork）扩展测试专用。
> 章节：① Windows Chrome 137+（MV2 被拒场景）② Android Kiwi x86 ③ 桌面国产浏览器 Turbo/百分（MV2 E2E 主载体）。

## 核心事实（2026-10 实测）

1. **`--load-extension` 已被移除**（Chrome 137 起）。以下手段全部无效，不要浪费时间：
   - 开发者模式开启后重启 + `--load-extension`；
   - `--disable-extensions-except` 组合；
   - 组策略 `HKCU\Software\Policies\Google\Chrome\ExtensionDeveloperModeSetting=1`（能让 toggle 常开，但救不回 --load-extension）；
   - `Preferences` 文件预写 `extensions.ui.developer_mode`（Chrome 启动时会覆盖）。
2. **唯一通道**：`chrome://extensions` 页 → 「开发者模式」toggle → 「加载未打包的扩展程序」按钮 → Windows 原生目录对话框。
3. **MV2 扩展在此版本必然被拒**，弹窗报「不受支持的清单版本」。先确认目标扩展是 MV3，否则换载体（如保留 MV2 的国产内核浏览器）。
4. RDP 后台会话下鼠标/键盘注入受限——结论性验证须在前台会话进行（与既往记忆一致）。

## 依赖

```bash
python -m pip install --target <隔离site-packages> comtypes websocket-client
```

- UIA 自动化：`comtypes` + `UIAutomationClient`；
- 截图：`ctypes` PrintWindow（纯 ctypes 即可，无需 pywin32）+ `Pillow`。

## 流程

### 0. 启动测试实例

```bash
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --user-data-dir=<独立profile目录> --no-first-run \
  --remote-debugging-port=9222 "chrome://extensions" &
```

不要传 `--load-extension`（无效且无害）。

### 1. UIA 定位并点击「开发者模式」toggle

```python
import sys, time, ctypes
sys.path.insert(0, r'C:/Users/xiongbin/.workbuddy/binaries/python/envs/default/site-packages')
import comtypes.client
import comtypes.gen.UIAutomationClient as UIA

iuia = comtypes.client.CreateObject(UIA.CUIAutomation._reg_clsid_, interface=UIA.IUIAutomation)
element = iuia.ElementFromHandle(<chrome_hwnd>)

# toggle 是一个 Name 为「开发者模式」的 Button（ControlType=50000）
cond = iuia.CreatePropertyCondition(30003, 50000)   # UIA_ControlTypePropertyId, Button
btns = element.FindAll(7, cond)                      # TreeScope_Subtree
devbtn = next(b for b in [btns.GetElement(i) for i in range(btns.Length)]
              if (b.CurrentName or '') == '开发者模式')
r = devbtn.CurrentBoundingRectangle   # 屏幕逻辑坐标
cx, cy = (r.left + r.right)//2, (r.top + r.bottom)//2
```

**toggle 的常见陷阱**：
- 「开发者模式」文本节点（Text 类型）不是按钮；按钮是同容器最后一个兄弟。
- 该按钮一般**只支持 InvokePattern 探测失败**——直接用 `SendInput` 真实鼠标点击按钮中心最可靠。
- 点击前后用颜色验证（见第 3 节）：蓝=开、灰=关。可能需要点两次（第一次点到文本上）。

### 2. 点击「加载未打包的扩展程序」并自动化目录对话框

按钮名：**「加载未打包的扩展程序」**（非「加载已解压」）。dev mode 关闭时该按钮不存在——先确认 toggle 已开。

```python
cond = iuia.CreatePropertyCondition(30005, '加载未打包的扩展程序')  # UIA_NamePropertyId
btn = element.FindFirst(7, cond)
r = btn.CurrentBoundingRectangle
cx, cy = (r.left + r.right)//2, (r.top + r.bottom)//2
```

**SendInput 真实点击**（`mouse_event` 亦可，但 `SendMessage BM_CLICK` / UIA `Invoke()` 对这个按钮和对话框都无效）：

```python
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long), ('mouseData', ctypes.c_ulong),
                ('dwFlags', ctypes.c_ulong), ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.c_void_p)]
class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [('mi', MOUSEINPUT)]
    _anonymous_ = ['i']
    _fields_ = [('type', ctypes.c_ulong), ('i', _I)]
def real_click():
    d = INPUT(type=0); d.mi = MOUSEINPUT(0,0,0,2,0,None)   # LEFTDOWN
    u = INPUT(type=0); u.mi = MOUSEINPUT(0,0,0,4,0,None)   # LEFTUP
    ctypes.windll.user32.SendInput(1, ctypes.byref(d), ctypes.sizeof(INPUT))
    time.sleep(0.05)
    ctypes.windll.user32.SendInput(1, ctypes.byref(u), ctypes.sizeof(INPUT))
```

点击前 `SetForegroundWindow(chrome_hwnd)` 并 sleep ≥1s 确保前台；UIA 元素每次重新获取（COM 指针易失效，`ElementFromHandle` 便宜）。

### 3. 对话框（「选择扩展程序目录」）自动化

1. EnumWindows 找标题含「选择扩展程序目录」的可见窗口，拿 hwnd；
2. UIA 找「文件夹:」输入框（ControlType Edit=50004，注意排除地址栏 combobox 的 edit——用 `CurrentName == '文件夹:'` 且 `top > 300` 过滤）；
3. **写路径用 `WM_SETTEXT`**（对原生 edit 的 hwnd 发消息）：

```python
hwnd_edit = folder_edit.CurrentNativeWindowHandle
ctypes.windll.user32.SendMessageW(hwnd_edit, 0x000C, 0, ext_path)  # WM_SETTEXT
# 读回验证：
val = ctypes.create_unicode_buffer(300)
ctypes.windll.user32.SendMessageW(hwnd_edit, 0x000D, 300, val)     # WM_GETTEXT
assert ext_path in val.value
```

   - UIA `ValuePattern.SetValue` 会跨进程失败；
   - `keybd_event`/剪贴板粘贴在后台会话不可靠，且偶发 GlobalLock 崩溃——不要用。
4. 「选择文件夹」按钮：同样 `SendInput` 真实点击其 `CurrentBoundingRectangle` 中心（`BM_CLICK` 无效）；
5. 等待 ≥8s 让 Chrome 完成加载。

### 4. 验证结果（三选二以上）

- **devtools targets**：`curl http://127.0.0.1:9222/json`，找 `chrome-extension://<id>/` 开头的 target（service_worker 或 page）；
- **Preferences**：`<profile>/Default/Preferences` 的 `extensions.settings` 出现新条目（注意 Chrome 落盘有延迟，`taskkill` 强杀会丢——验证前先温和关闭或直接读 CDP）；
- **PrintWindow 截图**：扩展卡片出现在列表；若弹「未能成功加载扩展程序」错误框，错误原因就写在框里（如 MV2 拒绝），照单处理。

截图模板（物理像素，DPI 缩放需 ÷scale 换算鼠标逻辑坐标）：

```python
import ctypes, ctypes.wintypes as wt
from PIL import Image
user32 = ctypes.windll.user32; gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()
rect = wt.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(rect))
w, h = rect.right - rect.left, rect.bottom - rect.top
hwndDC = user32.GetWindowDC(hwnd)
saveDC = gdi32.CreateCompatibleDC(hwndDC)
bmp = gdi32.CreateCompatibleBitmap(hwndDC, w, h)
gdi32.SelectObject(saveDC, bmp)
user32.PrintWindow(hwnd, saveDC, 2)
class BMIH(ctypes.Structure):
    _fields_ = [('biSize', ctypes.c_uint32), ('biWidth', ctypes.c_int32), ('biHeight', ctypes.c_int32),
                ('biPlanes', ctypes.c_uint16), ('biBitCount', ctypes.c_uint16), ('biCompression', ctypes.c_uint32),
                ('biSizeImage', ctypes.c_uint32), ('biXPelsPerMeter', ctypes.c_int32), ('biYPelsPerMeter', ctypes.c_int32),
                ('biClrUsed', ctypes.c_uint32), ('biClrImportant', ctypes.c_uint32)]
bmi = BMIH(); bmi.biSize = ctypes.sizeof(BMIH); bmi.biWidth = w; bmi.biHeight = -h
bmi.biPlanes = 1; bmi.biBitCount = 32
buf = ctypes.create_string_buffer(w*h*4)
gdi32.GetDIBits(saveDC, bmp, 0, h, buf, ctypes.byref(bmi), 0)
img = Image.frombuffer('RGB', (w, h), buf.raw, 'raw', 'BGRX', 0, 1)
img.save(out_path)
```

### 5. 失败速查

| 现象 | 原因 / 处置 |
|---|---|
| 「加载未打包」按钮不存在 | dev mode 未开（toggle 灰）→ 回第 1 步 |
| toggle 点了没反应 | 点到了文本节点 → 用 UIA 按钮矩形中心，SendInput 点击 |
| 对话框出现但路径没进去 | 用了 ValuePattern/键盘 → 改 WM_SETTEXT |
| WM_SETTEXT 后点确认无反应 | 用了 BM_CLICK → 改 SendInput 真实点击 |
| 弹「不受支持的清单版本」 | 扩展是 MV2 → 换浏览器载体或移植 MV3 |
| 弹「无法加载清单」/「key missing」 | manifest JSON 损坏或缺 `key` 字段 → 校验 JSON、注入 RSA key |
| 鼠标点击全部无效 | RDP 后台会话 → 切前台会话重试 |

---

## Android 路线：Kiwi Browser（模拟器/真机，实测可行 ✅）

**Kiwi 是 Android 上唯一可用的完整扩展载体**（chrome://extensions 完整、开发者模式默认开、原生支持直接加载 zip）。 MuMu 等 x86 模拟器**必须用 Kiwi 的 x86 构建**（github kiwibrowser/src.next releases，文件名含 `-x86-`）——arm64 包走 houdini 翻译，渲染进程会被 SIGSYS 全灭（Quetta/Kiwi-arm64 均如此），x86 原生执行无此问题。

### A. 安装 Kiwi（adb 全程）

```bash
# 1. 下载后校验字节数（GitHub 下载易截断；截断时 pm install 报 INSTALL_PARSE_FAILED_NOT_APK）
curl -sIL <apk-url> | grep -i content-length   # 先拿真实大小
curl -sL -C - -o kiwi-x86.apk <apk-url>         # -C - 断点续传补全

# 2. push 必须 MSYS_NO_PATHCONV=1（Git Bash 下否则报成功但文件不存在）
MSYS_NO_PATHCONV=1 adb -s 127.0.0.1:16384 push kiwi-x86.apk /data/local/tmp/kiwi.apk
adb -s 127.0.0.1:16384 shell "pm install -r /data/local/tmp/kiwi.apk"
```

首启 GMS 缺失警告（模拟器无 Google 服务）非阻塞——点确定后正常走 FirstRun 引导。

### B. 加载扩展 zip（adb 全自动化，比桌面对话框简单得多）

```bash
A="adb"; DEV=127.0.0.1:16384

# 1. 推 zip
MSYS_NO_PATHCONV=1 $A -s $DEV push uBlock0-davsync.zip /sdcard/Download/

# 2. 关键：触发媒体扫描，否则 SAF 文件选择器看不到 adb push 的文件
$A -s $DEV shell "am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Download/uBlock0-davsync.zip"

# 3. 打开 Kiwi 扩展页（菜单 → 扩展程序；直接输 kiwi://extensions 会被重定向，不稳定）
#    uiautomator dump 定位「+ (from .zip/.crx/.user.js)」按钮 → input tap

# 4. SAF 文件选择器：点搜索图标 → input text '文件名' → 点结果条目
#    （adb push 的文件只在搜索中出现，"最近"列表按 MIME 过滤会漏 zip）

# 5. 验证：ps -A | grep -cE 'kiwibrowser.*sandboxed'   # 渲染进程 >0 = 存活
#    cat /proc/net/unix | grep devtools                # 拿 socket 后 forward curl /json
#    找 "chrome-extension://<id>/background.html" target = 扩展在运行
```

### C. Android 侧验证与配置（CDP）

```bash
# Kiwi 的 socket 是带 pid 后缀的（chrome_devtools_remote_<pid>）；不带后缀的可能属于其他浏览器。
# 逐个 forward 试 /json/version 的 Android-Package 字段区分。
adb -s $DEV forward tcp:9444 localabstract:chrome_devtools_remote_<pid>
curl http://127.0.0.1:9444/json   # 列 targets；扩展后台页类型是 "other"
```

- 后台页 target 可直接 `Runtime.evaluate`：`vAPI.cloud.getOptions()` 返回含 `davEnabled` 字段 = davsync 模块已运行；
- 配置注入：`chrome.storage.local.set({ davSyncConfig: {...} })`（回调式 API），**改配置后需重启浏览器**（davsync 只在启动时读一次 config，无 storage.onChanged 监听）；
- 网络抓包：CDP `Network.enable` + `Runtime.evaluate(fetch...)`，`Network.loadingFailed` 的 `errorText`（如 `net::ERR_CERT_AUTHORITY_INVALID`）就是真实失败原因；
- ⚠️ MuMu 多屏：Kiwi 每次冷启动换新虚拟 displayId，主屏截图看不到它。`screencap -d <uid>` 的 uid 从 `dumpsys display` 全量枚举逐个试（只拉 >100KB 的有内容屏）。**不影响后台扩展运行**。

### D. Android 特有陷阱速查

| 现象 | 原因 / 处置 |
|---|---|
| SAF 选择器里找不到 push 的 zip | 未触发媒体扫描 → `am broadcast MEDIA_SCANNER_SCAN_FILE` |
| push "成功"但模拟器里没文件 | Git Bash 路径转换 → `MSYS_NO_PATHCONV=1` 前缀 |
| `pm install` 报 NOT_APK / parse fail | APK 下载截断 → 对比 Content-Length，`curl -C -` 补全 |
| 渲染进程全灭、页面全白 | 用了 arm64 包 → 换 **-x86-** 构建 |
| devtools socket 连到别的浏览器 | 带 pid 后缀的才是新实例；用 `/json/version` 的 `Android-Package` 确认 |
| `kiwi://extensions` 被重定向到 google | 走菜单（右上三点 → 扩展程序）最稳 |
| `chrome-extension://` URL intent 被屏蔽 | ERR_BLOCKED_BY_CLIENT 是 Kiwi 策略；用扩展详情页「检查视图 background.html」链接进入 |

---

## 桌面国产浏览器路线：Turbo / 百分（实测可行 ✅）

国产 Chromium 内核浏览器保留 MV2 支持，且 `--load-extension` **仍然有效**（Google Chrome 155 已移除）。适合桌面双端/多端 E2E。

### 启动模板（独立 profile，不污染日常数据）

```bash
# Turbo 154（D:/Software/Turbo/turbo.exe）
"D:/Software/Turbo/turbo.exe" --user-data-dir="<test-profile>" --no-first-run   --no-default-browser-check --load-extension="<扩展目录>"   --remote-debugging-port=9333 --window-size=1100,800

# 百分 5.3.1184.25 / Chromium 150（D:/Software/Cent/chrome.exe）
"D:/Software/Cent/chrome.exe" --user-data-dir="<test-profile>" ... 同上, port=9443
```

### 关键差异（Turbo/百分 各自的坑）

| 事项 | Turbo 154 | 百分 150 |
|---|---|---|
| 扩展初始状态 | 启用 | **DISABLED**（`--load-extension` 挂上但要求手动启用） |
| 启用方式 | 会话内 `chrome.management.setEnabled(id, true)`（CDP）即生效 | 同 API 报成功**但不生效**，必须走 UI 开关；且需先开右上角「开发者模式」 |
| 开发者模式默认 | 开 | **关** |
| 重启后状态 | 回 DISABLED（enabled 是会话级）；Preferences 无持久条目 | **Preferences 预写 `extensions.settings.<id>.state=1` 可持久启用**（百分无 HMAC 校验） |
| vAPI.defer | `onon` 调度回调静默不执行 → 用原生 setTimeout | 未测，同建议 |
| MV2 | 完整支持 | 完整支持 |

### 启用流程（百分，UI 自动化）

1. CDP `PUT /json/new?chrome://extensions/` 开扩展页
2. 鼠标点击「开发者模式」开关（右上角）→ 再点扩展卡片开关
3. 坐标从 PrintWindow 截图换算（窗口 1650×1200 物理 / 1.5 = 逻辑坐标）
4. **注意 strokeit 等鼠标手势工具会吞 SendInput/SetCursorPos**：点击后必须截图确认效果；失败就换 Preferences 预写法（更稳）

### Preferences 预写法（推荐，可持久化）

```
关闭浏览器 → 改 <profile>/Default/Preferences：
extensions.settings.<ext-id>.state = 1
→ 冷启动扩展即启用（百分验证通过；Turbo 无此条目、走会话内 setEnabled）
```

### E2E 同步测试骨架（CDP）

```python
# 1. bg target = /json 里 url 含 background.html 的 other 类型
# 2. 配置: chrome.storage.local.set({ davSyncConfig: {...} })   （键须 davSyncConfig）
# 3. 触发: 重启浏览器（startupSync 18s 后自动跑）或 chrome.alarms.create('davSyncAlarm', {delayInMinutes: 0.2})
# 4. 验证: vAPI.storage.get('davSyncState') → lastDirection/lastError
# 5. 云端: curl PROPFIND/GET <url>/<filePath> 比对内容
# 注意: pull 后 vAPI.app.restart 会杀掉 bg → 会话级 enabled 丢失（Turbo），需重新启用再读状态
#       或直接 grep profile/Default/Local Extension Settings/<id>/ 的 LevelDB（strings 可读）
```

---

## 本项目上下文备注

- 被测扩展：本仓库构建产物 `dist/build/uBlock0.davsync-*.zip`（解包目录 uBlock0.chromium/）。
- 测试 profile 与 CDP 端口：win-chrome/9222、turbo-chrome/9333、cent-chrome/9443、Kiwi forward 9444。
- 完整兼容性验证与 E2E 结论见 `docs/DAVSYNC-TESTING.md`。
- davsync 配置键：`davSyncConfig`（storage.local）；状态键：`davSyncState`。
- 修正（2026-10-22）：Turbo 亦可用 Preferences 预写法（本次双向测试未试，理论同百分；
  若 Turbo 有 HMAC 校验则回落会话内 setEnabled）。

### CRX3 打包与拖拽安装（实测可行 ✅）

**裸 zip/.xpi 拖到扩展页不触发安装**——Chromium 拖拽安装只认 CRX3 格式（`Cr24` magic + protobuf header + zip payload）。

打包（有私钥 pem 即可）：**`node tools/make-packages.cjs`**（一键出 .crx + .zip，
详见 `tools/make-packages.md`）。工具链：
```js
const writeCRX3 = require('<path>/node_modules/crx3/lib/writeCRX3File.js');
writeCRX3(recursiveFileList, {
  keyPath: '<key>.pem',
  crxPath: '<out>.crx',
  zipPath: '<tmp>.zip',
})
```
- manifest.json 带 `key` 字段（RSA 公钥 base64）→ 扩展 ID 固定可预测；
- CRX3 头结构：`Cr24` + u32 version(3) + u32 headerLen + protobuf{ field2: AsymmetricKeyProof{pubkey(1), sig(2)}, field10000: SignedData{crx_id(1)} }；sig = RSA-SHA256(SignedData 原始字节)；
- **安装前提：目标 profile 的「开发者模式」必须开启**，否则报 `CRX_SIGNATURE_VERIFICATION_FAILED`（未上架商店的自签 crx 被 InstallVerifier 拒）。

**⚠️ 企业策略白名单（ExtensionInstallAllowlist）对 Turbo 无效**：Turbo 构建剥离了
policy 服务（chrome://policy 页面为空），注册表策略一律不读。百分未验证策略路径，
但开发者模式开启即足够。

**程序化安装路径**（拖拽本身是浏览器 UI 行为，无法 CDP 模拟）：
把 crx 路径作为命令行参数传给浏览器 → 打开扩展页并弹标准确认框 → 点击「添加扩展程序」完成。
crx 正规安装后状态**持久 ENABLED**（区别于 --load-extension 的会话级 DISABLED），且 Preferences 有持久条目。

