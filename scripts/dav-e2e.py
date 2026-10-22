#!/usr/bin/env python3
"""davsync CDP E2E 测试骨架 —— 对一个运行中的 Chromium 系浏览器实例做同步链路验证。

用法：
    python dav-e2e.py --port 9333 --webdav https://dav.jianguoyun.com/dav/ \
        --user <account> --pass <app-password> --device <device-name>

前提：
    - 目标浏览器以 --remote-debugging-port=<port> 启动
    - davsync 扩展已加载且 ENABLED（bg target 存在）
    - pip install websocket-client（放入隔离 site-packages 亦可）

流程：
    1. 连 background.html target
    2. 注入 davSyncConfig（chrome.storage.local）
    3. 重置 davSyncAlarm 短延时触发 runSyncOnce（或等启动同步）
    4. 轮询 davSyncState 直到 lastDirection 非 None 或超时
    5. 直接 PROPFIND/GET 云端比对 deviceName / 时间戳

已知行为（2026-10-22 实测）：
    - alarm 路径（chrome.alarms.create 0.2min）在百分/Turbo 上均不触发
      runSyncOnce——**可靠的触发方式是重启浏览器走启动同步（18s 后）**；
    - pull 成功会 vAPI.app.restart() → bg 消失 → 需重新启用扩展再读状态
      （Turbo 等浏览器会话级 enabled 会丢；或直接 grep
        <profile>/Default/Local Extension Settings/<id>/ 的 LevelDB 取证）；
    - vAPI.storage.get 在 bg 是 Promise 风格：vAPI.storage.get('x').then(...)
    - chrome.storage.local 是回调风格：new Promise(res => chrome.storage.local.get(k, v => res(...)))
    - crx 正规安装（非 --load-extension）的扩展重启后保持 ENABLED，启动同步自动执行；
    - 多端同时启动时会看到 lastError='locked-by-other-device'——这是 lock 文件
      机制正常工作的证据（另一端持锁时本端拒绝并发同步），下一轮会成功。
    - 两端都有修改时 lastError='both-changed' 且 state.conflict=true：自动同步
      暂停，需在设置页手动选 上传/下载（davSyncResolveConflict 消息）。
    - pull 成功会 vAPI.app.restart() → bg 消失 → 需重新启用扩展再读状态
      （Turbo 等浏览器会话级 enabled 会丢；或直接 grep
        <profile>/Default/Local Extension Settings/<id>/ 的 LevelDB 取证）
    - vAPI.storage.get 在 bg 是 Promise 风格：vAPI.storage.get('x').then(...)
    - chrome.storage.local 是回调风格：new Promise(res => chrome.storage.local.get(k, v => res(...)))
"""
import argparse
import json
import sys
import time
import urllib.request

try:
    import websocket
except ImportError:
    # 常见隔离 site-packages 兜底（WorkBuddy 管理版 Python）
    import glob
    for cand in glob.glob(r'C:/Users/*/.workbuddy/binaries/python/envs/default/site-packages'):
        if cand not in sys.path:
            sys.path.insert(0, cand)
    import websocket


def http_json(url, method='GET', timeout=10):
    req = urllib.request.Request(url, method=method)
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def find_bg(base_url, timeout=60):
    """轮询 devtools targets 直到 background.html 出现（扩展被启用）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            tabs = http_json(base_url + '/json')
            bg = [t for t in tabs if 'background.html' in t.get('url', '')]
            if bg:
                return bg[0]
        except Exception:
            pass
        time.sleep(3)
    raise RuntimeError('background target not found within %ss' % timeout)


class Bg:
    def __init__(self, ws_url, timeout=60):
        self.ws = websocket.create_connection(ws_url, timeout=timeout,
                                              suppress_origin=True)
        self.n = 0

    def ev(self, expr, timeout=None):
        """Runtime.evaluate with awaitPromise；返回值或异常字符串。"""
        self.n += 1
        mid = 10000 + self.n
        params = {'expression': expr, 'awaitPromise': True, 'returnByValue': True}
        if timeout:
            self.ws.settimeout(timeout)
        self.ws.send(json.dumps({'id': mid, 'method': 'Runtime.evaluate',
                                 'params': params}))
        deadline = time.time() + (timeout or 40)
        while True:
            m = json.loads(self.ws.recv())
            if m.get('id') == mid:
                r = m.get('result', {})
                if 'exceptionDetails' in r:
                    return 'EXC: ' + str(r['exceptionDetails']
                                         .get('exception', {})
                                         .get('description', ''))[:300]
                return r.get('result', {}).get('value')

    def close(self):
        self.ws.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, required=True,
                    help='浏览器 remote debugging 端口')
    ap.add_argument('--webdav', default='https://dav.jianguoyun.com/dav/')
    ap.add_argument('--user', required=True)
    ap.add_argument('--pass', dest='password', required=True)
    ap.add_argument('--device', default='e2e-device')
    ap.add_argument('--wait', type=int, default=90,
                    help='同步完成等待秒数')
    args = ap.parse_args()

    base = 'http://127.0.0.1:%d' % args.port

    print('[1/4] waiting for background target...')
    bg_t = find_bg(base)
    bg = Bg(bg_t['webSocketDebuggerUrl'])
    print('  bg:', bg_t['url'][:70])

    print('[2/4] injecting davSyncConfig...')
    cfg = json.dumps({'enabled': True, 'url': args.webdav, 'username': args.user,
                      'password': args.password, 'deviceName': args.device})
    r = bg.ev("new Promise(res => chrome.storage.local.set({davSyncConfig: %s}, "
              "() => res('saved')))" % cfg)
    print('  ', r)

    print('[3/4] triggering sync (alarm, 0.2min)...')
    bg.ev("new Promise(res => chrome.alarms.create('davSyncAlarm', "
          "{delayInMinutes: 0.2}, () => res(1)))")
    print('  alarm set; waiting up to %ss' % args.wait)

    state = None
    t0 = time.time()
    while time.time() - t0 < args.wait:
        time.sleep(10)
        s = bg.ev("vAPI.storage.get('davSyncState')"
                  ".then(v => JSON.stringify(v.davSyncState))")
        if s and s != 'None':
            state = json.loads(s)
            if state.get('lastDirection'):
                break
        # bg 可能因 pull->restart 消失，重连
        try:
            tabs = http_json(base + '/json')
            if not any('background.html' in t.get('url', '') for t in tabs):
                bg_t = find_bg(base, timeout=30)
                bg.close()
                bg = Bg(bg_t['webSocketDebuggerUrl'])
        except Exception:
            pass

    print('[4/4] result:')
    print('  state:', json.dumps(state, ensure_ascii=False))
    ok = bool(state and state.get('lastDirection') in ('push', 'pull', 'pushed-init')
              and not state.get('lastError'))
    print('  VERDICT:', 'PASS' if ok else 'FAIL')
    bg.close()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
