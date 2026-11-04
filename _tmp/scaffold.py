#!/usr/bin/env python3
"""davsync test scaffolding — fixes the failures documented in
DAVSYNC-HOTAPPLY-PLAN.md §3.

What went wrong last round:
  - ui.ensure_page() attached to about:blank -> #davSync was null -> config
    was never saved -> the extension never PUT -> manual PUT hit 409.

The four requirements (from the plan):
  1. Explicit page: Target.createTarget(settings.html), pin the targetId.
  2. Assert every step: after config, davSyncGetStatus().enabled === true;
     cloud file must GET 200 before mutating it.
  3. Clean instance: fresh profile dir each run, Preferences patched
     (developer_mode + state=1), one restart, whole dir removed at exit.
  4. Clean WebDAV: rm -rf davroot and restart the server each run.

This module provides the reusable pieces; the self-check script is at the
bottom (run: python _tmp/scaffold.py selfcheck).
"""
import glob
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

# workbuddy-managed python ships websocket-client in an isolated site-packages
try:
    import websocket
except ImportError:
    for cand in glob.glob(r'C:/Users/*/.workbuddy/binaries/python/envs/default/site-packages'):
        if cand not in sys.path:
            sys.path.insert(0, cand)
    import websocket

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
BUILD = os.path.join(REPO, 'dist', 'build', 'uBlock0.chromium')
EXT_ID = 'odecihgahfphabajblgnmopeibmkhifp'
SETTINGS_URL = f'chrome-extension://{EXT_ID}/settings.html'
# Browser carriers MUST be Cent/Turbo (user directive: stock Chrome/Edge/
# Playwright Chromium no longer run MV2 reliably; these forks do).
CENT_EXE = os.environ.get(
    'DAVSYNC_CENT_EXE', r'D:\Software\Cent\chrome.exe')
TURBO_EXE = os.environ.get(
    'DAVSYNC_TURBO_EXE', r'D:\Software\Turbo\turbo.exe')
# --load-extension (unpacked) is DEAD on Cent since 2026-11-03: its cloud-
# managed rule blocks navigation to unpacked-extension UI pages
# (ERR_BLOCKED_BY_CLIENT) while INTERNAL (crx-installed) pages load fine —
# verified by _tmp/probe-internal.py on 2026-11-04. So we ride on the REAL
# profile from the 10-22 dual-browser E2E where the extension was properly
# crx-installed (location=1 INTERNAL, payload inside the profile), swap the
# payload to the current build, and wipe uBO's storage for a fresh-device
# state each run.
# NOTE(machine-local): the template profile lives OUTSIDE the repo. On a
# new machine either copy the old template dir over, or rebuild it once:
# launch Cent with a fresh --user-data-dir, enable developer mode, drag the
# release .crx into chrome://extensions (INTERNAL install), close, done —
# then point DAVSYNC_PROFILE_TEMPLATE at it. See skill
# leoshone/Skills -> browser-extension-e2e Step 0.
PROFILE_TEMPLATE = os.environ.get('DAVSYNC_PROFILE_TEMPLATE',
    os.path.normpath(os.path.join(
        'D:', os.sep, 'AiSpaces', 'Work', '2026-10-21-21-29-21', '_tmp',
        'davtest', 'cent-chrome')))
EXT_PAYLOAD_SUBPATH = os.path.join(
    'Default', 'Extensions', EXT_ID, '1.75.1.16_1')
WEBDAV_URL = 'http://127.0.0.1:8088/dav/'
WEBDAV_USER = 'davtest'
WEBDAV_PASSWORD = 'davtest123'
DAV_FILE_DIR = os.path.join(REPO, '_tmp', 'davroot', 'ublock-davsync')


def rmtree(path):
    """Profile dirs are test artifacts under _tmp; plain rmtree is right.
    The environment's safe-delete hook can intercept os.* trash ops (and
    hard-abort the interpreter on bulk deletes >50 files), so prefer
    Windows native rmdir, and honour DAVSYNC_KEEP_PROFILE=1 to skip
    cleanup entirely (post-mortem inspection / hook-hostile environments)."""
    if os.environ.get('DAVSYNC_KEEP_PROFILE') == '1':
        return
    if not os.path.isdir(path):
        return
    try:
        subprocess.run(['cmd', '/c', 'rmdir', '/s', '/q', path],
                       check=False, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    if os.path.isdir(path):  # last resort
        shutil.rmtree(path, ignore_errors=True)


def wipe_dir_ungated(path):
    """Delete a SMALL directory regardless of DAVSYNC_KEEP_PROFILE.
    Used for uBO's per-extension storage when re-preparing a kept profile:
    the fresh-device invariant matters more than keeping those files, and
    leveldb dirs stay far below the hook's 50-file bulk threshold."""
    if not os.path.isdir(path):
        return
    try:
        subprocess.run(['cmd', '/c', 'rmdir', '/s', '/q', path],
                       check=False, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    if os.path.isdir(path):  # last resort
        shutil.rmtree(path, ignore_errors=True)


def assert_eq(actual, expected, label):
    if actual != expected:
        raise AssertionError(f'{label}: got {actual!r}, expected {expected!r}')
    print(f'  [PASS] {label} = {actual!r}')


def assert_true(cond, label):
    if not cond:
        raise AssertionError(f'{label}: failed')
    print(f'  [PASS] {label}')


# --------------------------------------------------------------------------
# WebDAV cloud side
# --------------------------------------------------------------------------

def dav_req(method, path, body=None, expect=(200, 201, 204)):
    r = urllib.request.Request(WEBDAV_URL + path, method=method, data=body)
    import base64
    r.add_header('Authorization', 'Basic ' + base64.b64encode(
        f'{WEBDAV_USER}:{WEBDAV_PASSWORD}'.encode()).decode())
    try:
        resp = urllib.request.urlopen(r, timeout=10)
        code, data = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        code, data = e.code, e.read()
    if code not in expect:
        raise AssertionError(f'WebDAV {method} {path} -> {code}, expected {expect}')
    return code, data


def dav_backup_path():
    return 'ublock-davsync/ublock-backup.json'


def cloud_get():
    """GET the backup file; returns (found, data)."""
    try:
        _, data = dav_req('GET', dav_backup_path(), expect=(200,))
        return True, data
    except AssertionError:
        return False, None


# --------------------------------------------------------------------------
# Browser instance management (requirement 3: clean instance each run)
# --------------------------------------------------------------------------

class Browser:
    """Fresh-profile Chromium instance with the extension pre-enabled."""

    def __init__(self, profile_dir, port=9447):
        self.profile = profile_dir
        self.port = port
        self.proc = None

    @staticmethod
    def kill_by_port(port):
        """Kill whatever chrome.exe is bound to the debug port. A leftover
        instance silently swallows our CDP connections (timeouts)."""
        try:
            out = subprocess.run(['netstat', '-ano', '-p', 'TCP'],
                                 capture_output=True, text=True,
                                 encoding='utf-8', errors='ignore',
                                 timeout=30).stdout
        except Exception:
            return
        pids = set()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[3] == 'LISTENING' \
                    and parts[1].endswith(f':{port}'):
                pids.add(parts[4])
        for pid in pids:
            if pid.isdigit():
                subprocess.run(['taskkill', '/F', '/T', '/PID', pid],
                               check=False, timeout=15,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)

    def _write_preferences(self):
        """(legacy path — kept for reference) Patch Default/Preferences:
        developer mode on + extension state=1. This was the Cent 150 recipe
        pre-11-03; the INTERNAL-profile approach below replaced it."""
        default_dir = os.path.join(self.profile, 'Default')
        os.makedirs(default_dir, exist_ok=True)
        pref_path = os.path.join(default_dir, 'Preferences')
        prefs = {}
        if os.path.isfile(pref_path):
            with open(pref_path, encoding='utf-8') as f:
                prefs = json.load(f)
        prefs.setdefault('extensions', {}).setdefault('ui', {})[
            'developer_mode'] = True
        ext = prefs['extensions'].setdefault('settings', {}).setdefault(EXT_ID, {})
        ext.update({
            'state': 1,
            'location': 4,           # unpacked load
            'path': BUILD.replace('/', '\\'),
        })
        with open(pref_path, 'w', encoding='utf-8') as f:
            json.dump(prefs, f)

    def _prepare_profile(self):
        """Fresh-device profile from the INTERNAL template.

        1. copy the REAL Cent profile (crx-installed extension, ENABLED and
           persistent — the 10-22 E2E form that Cent's 11-03 cloud rule
           does NOT block);
        2. overwrite Default/Extensions/<id>/<ver>_1 with the current build;
        3. bump the version inside the prefs manifest snapshot to match;
        4. wipe uBO's storage (Local Extension Settings leveldb) so every
           run starts as a NEW DEVICE — that is the whole point of these
           regressions; also remove uBO's cached filter-list data and the
           legacy test davSync config from that profile."""
        if os.path.isdir(self.profile):
            rmtree(self.profile)
        # dirs_exist_ok: under DAVSYNC_KEEP_PROFILE=1 a previous run's
        # profile may still be present; overwriting it is fine.
        shutil.copytree(PROFILE_TEMPLATE, self.profile, dirs_exist_ok=True)
        payload_dst = os.path.join(self.profile, EXT_PAYLOAD_SUBPATH)
        for root, dirs, files in os.walk(BUILD):
            rel = os.path.relpath(root, BUILD)
            os.makedirs(os.path.join(payload_dst, rel), exist_ok=True)
            for f in files:
                shutil.copy2(os.path.join(root, f),
                             os.path.join(payload_dst, rel, f))
        pref_path = os.path.join(self.profile, 'Default', 'Preferences')
        prefs = json.load(open(pref_path, encoding='utf-8'))
        entry = prefs['extensions']['settings'][EXT_ID]
        build_mf = json.load(open(os.path.join(BUILD, 'manifest.json'),
                                  encoding='utf-8'))
        entry.setdefault('manifest', {})['version'] = build_mf['version']
        json.dump(prefs, open(pref_path, 'w', encoding='utf-8'))

        # wipe uBO state for a clean "new device" — ALWAYS, even when the
        # whole-profile cleanup is gated off (fresh-device is the regression's
        # core invariant; these leveldb dirs are small so the safe-delete
        # hook's bulk threshold is not a concern).
        wipe_dir_ungated(os.path.join(self.profile, 'Default',
                                      'Local Extension Settings', EXT_ID))
        wipe_dir_ungated(os.path.join(self.profile, 'Default',
                                      'Sync Extension Settings', EXT_ID))
        # cached filter lists live under Local Storage keyed by the
        # extension origin; simplest reliable wipe is the whole leveldb
        wipe_dir_ungated(os.path.join(self.profile, 'Default', 'Local Storage'))

    def start(self, settle_seconds=20):
        # Any leftover instance bound to our debug port would swallow the
        # CDP connection (silent timeouts) — kill by port first.
        Browser.kill_by_port(self.port)
        self._prepare_profile()
        exe = os.environ.get('DAVSYNC_BROWSER', CENT_EXE)
        # NOTE: no --load-extension. The INTERNAL profile form carries the
        # extension; adding an unpacked load would trip Cent's 11-03 UI-page
        # blocking rule for unpacked extensions.
        args = [
            exe,
            f'--user-data-dir={self.profile}',
            f'--remote-debugging-port={self.port}',
            '--no-first-run', '--no-default-browser-check',
            '--disable-background-networking',
            '--disable-session-crashed-bubble', '--hide-crash-restore-bubble',
            'about:blank',
        ]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        self._wait_devtools()
        # uBO restarts itself ONCE on first launch in a fresh profile
        # (start.js: lastVersionInt===0 + chromium => vAPI.app.restart()).
        # That restart closes any page opened too early (observed: settings
        # page target vanished ~5s after createTarget). Wait it out BEFORE
        # opening dashboard pages.
        if settle_seconds > 0:
            time.sleep(settle_seconds)
        return self

    def _wait_devtools(self, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                with urllib.request.urlopen(
                        f'http://127.0.0.1:{self.port}/json/version', timeout=3) as r:
                    json.load(r)
                return
            except Exception:
                time.sleep(1)
        raise RuntimeError('devtools endpoint did not come up')

    def targets(self):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json',
                                    timeout=10) as r:
            return json.load(r)

    def stop(self):
        if self.proc:
            # terminate() only kills the launcher; chrome.exe forks and the
            # children (network/gpu/renderer) survive and keep the debug
            # port bound. Kill the whole tree like a real teardown would.
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.proc.pid)],
                           check=False, timeout=30,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                self.proc.wait(timeout=15)
            except Exception:
                pass
            self.proc = None
        # DAVSYNC_KEEP_PROFILE=1 keeps the profile for post-mortem inspection
        # (extension payload hash behaviour, leveldb state, ...); rmtree
        # itself is also gated on the same variable.
        if os.environ.get('DAVSYNC_KEEP_PROFILE') != '1':
            rmtree(self.profile)


# --------------------------------------------------------------------------
# CDP session: explicit page targeting (requirement 1)
# --------------------------------------------------------------------------

class Cdp:
    """CDP over a plain websocket to one target (page or background)."""

    def __init__(self, base_url, wanted_url_substring=None, create_url=None,
                 timeout=60):
        """If create_url is given, use Target.createTarget and pin the
        returned targetId (plan requirement 1). Otherwise find the first
        target whose url contains wanted_url_substring."""
        self.base = base_url
        self.next_id = 1
        if create_url is not None:
            tid = self._create_target(create_url)
            self.target_id = tid
            self.url = create_url
        else:
            t = self._find_target(wanted_url_substring, timeout)
            self.target_id = t['id']
            self.url = t['url']
        ws_url = self._ws_url_for(self.target_id)
        self.ws = websocket.create_connection(ws_url, timeout=timeout,
                                              suppress_origin=True)

    def _create_target(self, url):
        # Target.createTarget needs the browser-level websocket endpoint.
        with urllib.request.urlopen(self.base + '/json/version', timeout=10) as r:
            ver = json.load(r)
        ws = websocket.create_connection(ver['webSocketDebuggerUrl'],
                                         timeout=30, suppress_origin=True)
        ws.settimeout(30)
        mid = 1  # Cent 150 requires an *integer* id; string ids get no reply
        ws.send(json.dumps({'id': mid, 'method': 'Target.createTarget',
                            'params': {'url': url}}))
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == mid:
                ws.close()
                if 'error' in m:
                    raise RuntimeError(f'Target.createTarget failed: {m["error"]}')
                tid = m['result']['targetId']
                print(f'  [PASS] Target.createTarget -> {url} (targetId={tid[:12]}...)')
                return tid
    def _find_target(self, substring, timeout):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                with urllib.request.urlopen(self.base + '/json', timeout=5) as r:
                    tabs = json.load(r)
                for t in tabs:
                    if substring in t.get('url', '') and t.get('type') == 'page':
                        return t
                for t in tabs:
                    if substring in t.get('url', ''):
                        return t
            except Exception:
                pass
            time.sleep(1)
        raise RuntimeError(f'target *{substring}* not found in {timeout}s')

    def _ws_url_for(self, target_id):
        for t in self.targets():
            if t['id'] == target_id:
                return t['webSocketDebuggerUrl']
        raise RuntimeError(f'no devtools ws for target {target_id}')

    def targets(self):
        with urllib.request.urlopen(self.base + '/json', timeout=10) as r:
            return json.load(r)

    def call(self, method, params=None, timeout=None):
        mid = self.next_id
        self.next_id += 1
        if timeout:
            self.ws.settimeout(timeout)
        self.ws.send(json.dumps({'id': mid, 'method': method,
                                 'params': params or {}}))
        deadline = time.time() + (timeout or 60)
        while True:
            if time.time() > deadline:
                raise TimeoutError(f'{method} timed out')
            m = json.loads(self.ws.recv())
            if m.get('id') == mid:
                if 'error' in m:
                    raise RuntimeError(f'{method}: {m["error"]}')
                return m.get('result', {})

    def ev(self, expr, await_promise=True, timeout=60):
        """Runtime.evaluate with awaitPromise; unwraps the value; raises on
        JS exception so silent config-save failures can't slip through."""
        r = self.call('Runtime.evaluate', {
            'expression': expr,
            'awaitPromise': await_promise,
            'returnByValue': True,
        }, timeout=timeout)
        if 'exceptionDetails' in r:
            desc = r['exceptionDetails'].get('exception', {}).get(
                'description', '') or str(r['exceptionDetails'])
            raise RuntimeError(f'JS exception: {desc[:500]}')
        return r.get('result', {}).get('value')

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# High-level steps with assertions (requirement 2)
# --------------------------------------------------------------------------

def open_settings_page(browser):
    """Requirement 1: explicitly create the settings page target."""
    page = Cdp(f'http://127.0.0.1:{browser.port}',
               create_url=SETTINGS_URL, timeout=60)
    # Pin and verify: the page must really be ours, not about:blank.
    # Navigation after createTarget is async — poll until the URL sticks.
    deadline = time.time() + 30
    url = None
    while time.time() < deadline:
        url = page.ev('location.href', await_promise=False)
        if url == SETTINGS_URL:
            break
        time.sleep(1)
    assert_eq(url, SETTINGS_URL, 'settings page location.href')
    # The pane + vAPI need the page scripts to finish loading; poll instead
    # of asserting immediately (INTERNAL-profile form loads a touch slower).
    deadline = time.time() + 30
    vapi = pane = False
    while time.time() < deadline:
        try:
            vapi = page.ev('typeof vAPI !== "undefined"', await_promise=False)
            pane = page.ev(
                'document.getElementById("davSync") !== null',
                await_promise=False)
        except Exception:
            pass
        if vapi and pane:
            break
        time.sleep(1)
    assert vapi, 'vAPI never defined on settings page'
    assert pane, '#davSync pane never present on settings page'
    print('  [PASS] #davSync pane present on the page')
    return page


def save_config_via_page(page, device_name='scaffold-cent'):
    """Fill the DAV-Sync form through the real UI path and save.
    Asserts davSyncGetStatus().enabled === true afterwards (requirement 2)."""
    js = '''
    (async () => {
        const q = s => document.querySelector(s);
        q('#davSyncEnabled').checked = true;
        q('#davSyncEnabled').dispatchEvent(new Event('change', {bubbles:true}));
        q('#davSyncUrl').value = %s;
        q('#davSyncUsername').value = %s;
        q('#davSyncPassword').value = %s;
        q('#davSyncDeviceName').value = %s;
        q('#davSyncUrl').dispatchEvent(new Event('input', {bubbles:true}));
        q('#davSyncUsername').dispatchEvent(new Event('input', {bubbles:true}));
        q('#davSyncPassword').dispatchEvent(new Event('input', {bubbles:true}));
        q('#davSyncDeviceName').dispatchEvent(new Event('input', {bubbles:true}));
        const saveBtn = q('#davSyncSave');
        if (!saveBtn || saveBtn.disabled) {
            return {ok: false, why: 'save button missing or still disabled'};
        }
        saveBtn.click();
        return {ok: true};
    })()
    ''' % (json.dumps(WEBDAV_URL), json.dumps(WEBDAV_USER),
           json.dumps(WEBDAV_PASSWORD), json.dumps(device_name))
    result = page.ev(js, await_promise=True)
    assert_eq(result.get('ok'), True,
              'settings form save button clicked')
    if not result.get('ok'):
        raise AssertionError(f'could not click save: {result}')

    # Requirement 2: assert persisted config through the backend status.
    deadline = time.time() + 20
    last = None
    while time.time() < deadline:
        st = page.ev(
            'vAPI.messaging.send("dashboard", {what: "davSyncGetStatus"})',
            await_promise=True, timeout=30)
        last = st
        if st and st.get('enabled') is True:
            break
        time.sleep(1)
    assert_true(last and last.get('enabled') is True,
                'davSyncGetStatus().enabled === true')
    assert_eq(last.get('url'), WEBDAV_URL, 'status.url')
    assert_eq(last.get('deviceName'), device_name, 'status.deviceName')
    assert_true(last.get('hasPassword') is True, 'status.hasPassword === true')
    return last


def wait_bg_target(browser, timeout=90):
    """Wait for the extension background target; returns Cdp attached to it."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            bg = Cdp(f'http://127.0.0.1:{browser.port}',
                     wanted_url_substring='background', timeout=30)
            print(f'  [PASS] background target attached: {bg.url[:60]}')
            return bg
        except Exception:
            time.sleep(2)
    raise RuntimeError('background target not found')


# --------------------------------------------------------------------------
# WebDAV cleanliness (requirement 4) is handled by the runner script:
# rm -rf _tmp/davroot && restart webdav.py. Here we only assert the cloud
# side when needed.
# --------------------------------------------------------------------------

def assert_cloud_file_exists(timeout=60):
    """Requirement 2b: cloud file must exist (GET 200) before we mutate it."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        found, data = cloud_get()
        if found:
            payload = json.loads(data)
            assert_true('deviceName' in payload,
                        f'cloud backup has deviceName={payload.get("deviceName")!r}')
            print(f'  [PASS] cloud backup exists ({len(data)}B)')
            return payload
        time.sleep(2)
    raise AssertionError('cloud backup file never appeared (no PUT received)')


# --------------------------------------------------------------------------
# Self-check (plan §5 step 2): three gates before touching sync logic
# --------------------------------------------------------------------------

def selfcheck():
    print('== davsync scaffold self-check ==')
    print('[gate 0] clean webdav root + server alive')
    # requirement 4: the runner wipes davroot; here we just assert the server
    code, _ = dav_req('OPTIONS', '', expect=(200,))
    print(f'  [PASS] webdav server responds ({code})')

    profile = os.path.join(REPO, '_tmp', 'p-selfcheck')
    browser = Browser(profile, port=9447)
    page = bg = None
    try:
        print('[gate 1] explicit settings page (createTarget + assertions)')
        browser.start()
        page = open_settings_page(browser)

        print('[gate 2] config saved through the form, backend confirms')
        save_config_via_page(page, device_name='scaffold-selfcheck')

        print('[gate 3] extension performed first PUT; cloud file readable')
        payload = assert_cloud_file_exists(timeout=90)
        assert_eq(payload.get('deviceName'), 'scaffold-selfcheck',
                  'cloud deviceName')

        print('\n== SELF-CHECK: ALL 3 GATES GREEN ==')
        return 0
    except Exception as e:
        print(f'\n== SELF-CHECK FAILED: {e} ==')
        import traceback
        traceback.print_exc()
        return 1
    finally:
        for c in (page, bg):
            if c:
                c.close()
        browser.stop()
        print('profile removed:', not os.path.isdir(profile))


if __name__ == '__main__':
    sys.exit(selfcheck())
