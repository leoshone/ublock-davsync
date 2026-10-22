---
name: chrome-unpacked-sideload
description: 在本机 Windows Chrome（137+，含 155）上自动侧载未打包扩展的唯一可靠方法。当需要在 Chrome 中加载本地扩展目录做测试、而 --load-extension 已失效时使用。涵盖：开发者模式开启、加载未打包对话框自动化、MV2 兼容性判断、屏幕截图验证。触发词：侧载、加载扩展、load-extension、加载未打包、chrome://extensions、扩展测试。
---

# Chrome 未打包扩展侧载（Windows 自动化）

> 适用：本机 Windows Chrome ≥ 137（验证于 Chrome 155.0.8059.85）。
> 范围：**项目级 skill**——仅在本工作区（uBlock DAV-Sync fork）扩展测试场景下加载，勿入全局。

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

## 本项目上下文备注

- 被测扩展：本仓库构建产物 `dist/build/uBlock0.davsync-*.zip` 解包目录（uBlock0.chromium/）。
- 测试 profile：`_tmp/davtest/win-chrome/`；CDP 端口 9222。
- 完整兼容性验证与侧载结论见 `docs/DAVSYNC-HOST-COMPATIBILITY-AND-SIDELOAD.md`。
