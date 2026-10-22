#!/usr/bin/env python3
"""Chrome 137+（实测 155）未打包扩展侧载自动化。

--load-extension 已被 Google 移除，唯一通道是:
  chrome://extensions 页 -> 开发者模式 toggle -> 「加载未打包的扩展程序」
  -> Windows 原生目录对话框（UIA + WM_SETTEXT + SendInput 真实点击）

用法:
  python ublock-sideload.py <chrome_hwnd|auto> <扩展目录绝对路径>
  python ublock-sideload.py auto "D:/path/to/uBlock0.chromium"

依赖: pip install comtypes（UIA）; 截图验证需 Pillow。
注意: RDP 后台会话下鼠标注入受限，须前台会话执行。
"""
import sys, time, ctypes
import ctypes.wintypes as wt

sys.path.insert(0, r'C:/Users/xiongbin/.workbuddy/binaries/python/envs/default/site-packages')
import comtypes.client  # noqa: E402
import comtypes.gen.UIAutomationClient as UIA  # noqa: E402

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

# ---------- SendInput 真实鼠标点击（BM_CLICK / UIA Invoke 对 Chrome 按钮与 IFileDialog 均无效） ----------
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long), ('mouseData', ctypes.c_ulong),
                ('dwFlags', ctypes.c_ulong), ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.c_void_p)]

class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [('mi', MOUSEINPUT)]
    _anonymous_ = ['i']
    _fields_ = [('type', ctypes.c_ulong), ('i', _I)]

def real_click(cx, cy):
    user32.SetCursorPos(cx, cy)
    time.sleep(0.3)
    d = INPUT(type=0); d.mi = MOUSEINPUT(0, 0, 0, 2, 0, None)
    u = INPUT(type=0); u.mi = MOUSEINPUT(0, 0, 0, 4, 0, None)
    user32.SendInput(1, ctypes.byref(d), ctypes.sizeof(INPUT))
    time.sleep(0.05)
    user32.SendInput(1, ctypes.byref(u), ctypes.sizeof(INPUT))

def click_btn_center(iuia, btn):
    r = btn.CurrentBoundingRectangle
    real_click((r.left + r.right) // 2, (r.top + r.bottom) // 2)

# ---------- 工具 ----------
def find_chrome_hwnd():
    hits = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, l):
        b = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, b, 256)
        if 'Chrome' in b.value and user32.IsWindowVisible(h):
            hits.append(h)
        return True
    user32.EnumWindows(cb, 0)
    return hits[0] if hits else None

def find_dialog():
    hits = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, l):
        b = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, b, 256)
        if '选择扩展程序目录' in b.value and user32.IsWindowVisible(h):
            hits.append(h)
        return True
    user32.EnumWindows(cb, 0)
    return hits[0] if hits else None

def main():
    hwnd_arg = 'auto' if len(sys.argv) < 2 else sys.argv[1]
    ext_path = sys.argv[2] if len(sys.argv) > 2 else sys.exit(__doc__)
    hwnd = find_chrome_hwnd() if hwnd_arg == 'auto' else int(hwnd_arg)
    if not hwnd:
        sys.exit('未找到 Chrome 窗口；先手动打开 chrome://extensions')

    iuia = comtypes.client.CreateObject(UIA.CUIAutomation._reg_clsid_, interface=UIA.IUIAutomation)

    def elements():
        # COM 指针易失效，每次调用前重新获取
        return iuia.ElementFromHandle(hwnd)

    user32.SetForegroundWindow(hwnd)
    time.sleep(1.5)

    # 1. 开发者模式 toggle（Name=开发者模式 的 Button，ControlType=50000）
    cond_btn = iuia.CreatePropertyCondition(30003, 50000)
    devbtn = None
    btns = elements().FindAll(7, cond_btn)
    for i in range(btns.Length):
        b = btns.GetElement(i)
        if (b.CurrentName or '') == '开发者模式':
            devbtn = b
            break
    if devbtn is None:
        sys.exit('未找到「开发者模式」按钮——确认当前 tab 是 chrome://extensions')
    user32.SetForegroundWindow(hwnd); time.sleep(1)
    click_btn_center(iuia, devbtn)
    time.sleep(3)
    print('开发者模式已点击')

    # 2. 「加载未打包的扩展程序」
    cond_name = iuia.CreatePropertyCondition(30005, '加载未打包的扩展程序')
    load_btn = elements().FindFirst(7, cond_name)
    if load_btn is None:
        sys.exit('「加载未打包的扩展程序」未出现——dev mode 可能没开成，重跑一次')
    user32.SetForegroundWindow(hwnd); time.sleep(1)
    click_btn_center(iuia, load_btn)
    time.sleep(4)

    # 3. 目录对话框
    dlg_h = find_dialog()
    if not dlg_h:
        sys.exit('目录对话框未弹出')
    dlg = iuia.ElementFromHandle(dlg_h)
    cond_edit = iuia.CreatePropertyCondition(30003, 50004)  # Edit
    edits = dlg.FindAll(7, cond_edit)
    folder_edit = None
    for i in range(edits.Length):
        e = edits.GetElement(i)
        if (e.CurrentName or '') == '文件夹:' and e.CurrentBoundingRectangle.top > 300:
            folder_edit = e
            break
    if folder_edit is None:
        sys.exit('未找到「文件夹:」输入框')
    hwnd_edit = folder_edit.CurrentNativeWindowHandle
    # WM_SETTEXT 写路径（UIA ValuePattern 跨进程会被拒；键盘注入在后台会话不可靠）
    WM_SETTEXT, WM_GETTEXT = 0x000C, 0x000D
    user32.SendMessageW(hwnd_edit, WM_SETTEXT, 0, ext_path)
    val = ctypes.create_unicode_buffer(600)
    user32.SendMessageW(hwnd_edit, WM_GETTEXT, 600, val)
    assert ext_path in val.value, f'路径写入失败: {val.value!r}'
    print('路径已写入:', val.value)

    # 4. 「选择文件夹」确认（SendInput 真实点击）
    cond_btn2 = iuia.CreatePropertyCondition(30003, 50000)
    btns = dlg.FindAll(7, cond_btn2)
    for i in range(btns.Length):
        b = btns.GetElement(i)
        if '选择文件夹' in (b.CurrentName or ''):
            user32.SetForegroundWindow(dlg_h); time.sleep(0.5)
            click_btn_center(iuia, b)
            break
    time.sleep(10)
    print('已提交。验证: curl http://127.0.0.1:9222/json 查 chrome-extension:// targets；'
          '若弹「不受支持的清单版本」= MV2 被拒，需换载体浏览器。')

if __name__ == '__main__':
    main()
