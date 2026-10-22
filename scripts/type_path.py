import ctypes, time
user32 = ctypes.windll.user32
user32.SetForegroundWindow(601890390)
time.sleep(1)
# Alt+D 聚焦文件对话框地址栏
user32.keybd_event(0x12, 0, 0, 0)
user32.keybd_event(0x44, 0, 0, 0)
user32.keybd_event(0x44, 0, 2, 0)
user32.keybd_event(0x12, 0, 2, 0)
time.sleep(0.8)

path = 'D:\\AiSpaces\\Work\\2026-10-21-21-29-21\\_tmp\\davtest\\ublock0-davsync\\uBlock0.chromium'
for ch in path:
    if ch.isalpha():
        vk = ord(ch.upper())
        shift = ch.islower()
    elif ch.isdigit():
        vk = 0x30 + int(ch)
        shift = False
    elif ch == '\\':
        vk = 0xE2
        shift = False
    elif ch == ':':
        vk = 0xBA
        shift = True
    elif ch == '_':
        vk = 0xBD
        shift = True
    elif ch == '-':
        vk = 0xBD
        shift = False
    else:
        continue
    if shift:
        user32.keybd_event(0x10, 0, 0, 0)
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 2, 0)
    if shift:
        user32.keybd_event(0x10, 0, 2, 0)
    time.sleep(0.02)
time.sleep(0.5)
user32.keybd_event(0x0D, 0, 0, 0)
user32.keybd_event(0x0D, 0, 2, 0)
print('path typed + enter')
time.sleep(12)
print('done')
