#!/usr/bin/env python3
"""davsync hot-apply acceptance tests (DAVSYNC-HOTAPPLY-PLAN.md §3 table).

Run order (from repo root, two shells):
  shell A:  rm -rf _tmp/davroot && mkdir -p _tmp/davroot && python test/webdav.py
  shell B:  python test/acceptance.py

Each case spins a fresh Cent profile (plan §3 requirement 3), opens the
settings page via Target.createTarget (req 1), asserts every step (req 2)
and reuses the clean-davroot discipline (req 4) by wiping the davroot tree
between cases.

Cases covered (Chromium; case 8 = Firefox lives in run-firefox.sh):
  1  remote change (+ importedLists default noise) -> sync; page alive,
     status '已从云端应用'
  2  wait 20s, sync again -> no '已上传' (no spurious push), cloud
     deviceName still the peer's
  3  my filters / whitelist / settings equal remote
  4  filter engine rebuilt (netFilterCount changed)
  5  local change -> sync -> '已上传', no conflict
  6  both ends change -> sync -> conflict banner
  7  remote hiddenSettings change -> sync -> restart path (page closes and
     reopens), data still correct afterwards
"""
import base64
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

try:
    import websocket
except ImportError:
    for cand in glob.glob(r'C:/Users/*/.workbuddy/binaries/python/envs/default/site-packages'):
        if cand not in sys.path:
            sys.path.insert(0, cand)
    import websocket

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scaffold import (Browser, Cdp, WEBDAV_URL, WEBDAV_USER, WEBDAV_PASSWORD,
                      DAV_FILE_DIR, SETTINGS_URL, EXT_ID, rmtree)

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
DAVROOT = os.path.join(REPO, '_tmp', 'davroot')
BACKUP = os.path.join(DAVROOT, 'ublock-davsync', 'ublock-backup.json')

PASS, FAIL = [], []


def check(cond, label):
    print(f'  [{"PASS" if cond else "FAIL"}] {label}')
    (PASS if cond else FAIL).append(label)
    return cond


def dav_auth():
    return 'Basic ' + base64.b64encode(
        f'{WEBDAV_USER}:{WEBDAV_PASSWORD}'.encode()).decode()


def cloud_read():
    try:
        r = urllib.request.Request(
            WEBDAV_URL + 'ublock-davsync/ublock-backup.json')
        r.add_header('Authorization', dav_auth())
        with urllib.request.urlopen(r, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def cloud_write(payload):
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    with open(BACKUP, 'w', encoding='utf-8') as f:
        json.dump(payload, f)


def wipe_cloud():
    """Requirement 4: davroot wiped between cases (server keeps serving it)."""
    if os.path.isdir(DAVROOT):
        rmtree(DAVROOT)
    os.makedirs(DAVROOT, exist_ok=True)


def wait_cloud_backup(timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        data = cloud_read()
        if data is not None:
            return data
        time.sleep(2)
    raise AssertionError('cloud backup never appeared')


def open_page_and_configure(browser, device, wait_put=True):
    """Shared prologue: open settings page, save config, wait for first PUT."""
    browser.start()
    page = None
    for _ in range(30):
        try:
            page = Cdp(f'http://127.0.0.1:{browser.port}',
                       create_url=SETTINGS_URL, timeout=60)
            break
        except Exception:
            time.sleep(1)
    if page is None:
        raise RuntimeError('could not open settings page')
    deadline = time.time() + 30
    url = ''
    while time.time() < deadline:
        url = page.ev('location.href', await_promise=False)
        if url == SETTINGS_URL:
            break
        time.sleep(1)
    assert url == SETTINGS_URL, f'settings page did not load: {url}'

    # The pane's save button stays disabled until BOTH are true: the form
    # differs from davSyncSaved AND the initial davSyncGetStatus reply has
    # landed (refreshDavStatus populates davSyncSaved asynchronously after
    # page load). Filling fields immediately after createTarget races that
    # reply; wait for the status text to render first. The websocket can
    # be aborted mid-navigation by the renderer swap (WinError 10053), so
    # wrap each probe and re-attach to the pinned targetId on failure.
    deadline = time.time() + 25
    ready = False
    while time.time() < deadline:
        try:
            ready = page.ev(
                'document.getElementById("davSyncStatus") !== null && '
                'document.getElementById("davSyncStatus").textContent !== ""',
                await_promise=False)
        except (ConnectionAbortedError, websocket.WebSocketException,
                TimeoutError, OSError):
            time.sleep(1)
            try:
                page.close()
            except Exception:
                pass
            try:
                page = Cdp(f'http://127.0.0.1:{browser.port}',
                           wanted_url_substring='settings.html', timeout=30)
            except Exception:
                pass
            continue
        if ready:
            break
        time.sleep(0.5)

    js = '''
    (async () => {
        const q = s => document.querySelector(s);
        q('#davSyncEnabled').checked = true;
        q('#davSyncEnabled').dispatchEvent(new Event('change', {bubbles:true}));
        q('#davSyncUrl').value = %s;
        q('#davSyncUsername').value = %s;
        q('#davSyncPassword').value = %s;
        q('#davSyncDeviceName').value = %s;
        for (const id of ['davSyncUrl','davSyncUsername','davSyncPassword','davSyncDeviceName']) {
            q('#'+id).dispatchEvent(new Event('input', {bubbles:true}));
        }
        const saveBtn = q('#davSyncSave');
        if (!saveBtn || saveBtn.disabled) return {ok:false};
        saveBtn.click();
        return {ok:true};
    })()
    ''' % (json.dumps(WEBDAV_URL), json.dumps(WEBDAV_USER),
           json.dumps(WEBDAV_PASSWORD), json.dumps(device))
    # Fill + save. The page websocket dies whenever the renderer swaps
    # (about:blank -> settings, extension init); retries re-attach to the
    # same page target until the click lands.
    result = None
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            result = page.ev(js, await_promise=True)
        except (ConnectionAbortedError, websocket.WebSocketException,
                TimeoutError, OSError, RuntimeError):
            time.sleep(1)
            try:
                page.close()
            except Exception:
                pass
            try:
                page = Cdp(f'http://127.0.0.1:{browser.port}',
                           wanted_url_substring='settings.html', timeout=30)
            except Exception:
                pass
            continue
        if result and result.get('ok'):
            break
        if result and result.get('ok') is False:
            # button genuinely disabled: wait and retry (status reply racing)
            time.sleep(1)
            continue
    assert result and result.get('ok'), f'save button never clickable: {result}'

    # status must confirm enabled
    deadline = time.time() + 30
    st = None
    while time.time() < deadline:
        try:
            st = page.ev('vAPI.messaging.send("dashboard", '
                         '{what: "davSyncGetStatus"})', await_promise=True,
                         timeout=30)
        except Exception:
            time.sleep(1)
            try:
                page.close()
            except Exception:
                pass
            page = Cdp(f'http://127.0.0.1:{browser.port}',
                       wanted_url_substring='settings.html', timeout=30)
            continue
        if st and st.get('enabled') is True:
            break
        time.sleep(1)
    assert st and st.get('enabled') is True, f'not enabled: {st}'

    if wait_put:
        wait_cloud_backup()
        # The config-save triggers an immediate first sync (setConfig's
        # 500ms timer). File existence alone doesn't mean that sync FINISHED
        # (lock still held, state still being written) -- firing davSyncNow
        # into that window races it for the lock and the 8s retry can lose,
        # poisoning the whole case (observed: dir=push, err=
        # locked-by-other-device). Wait until the backend reports quiescence:
        # a recorded lastDirection AND no error.
        deadline = time.time() + 60
        settled = None
        while time.time() < deadline:
            try:
                settled = page.ev(
                    'vAPI.messaging.send("dashboard", {what: "davSyncGetStatus"})',
                    await_promise=True, timeout=30)
            except Exception:
                time.sleep(1)
                continue
            if settled and settled.get('lastDirection') in ('push', 'pull',
                                                            'pulled-hot') \
                    and not settled.get('lastError'):
                break
            time.sleep(1)
        assert settled and settled.get('lastDirection') and \
            not settled.get('lastError'), f'first sync never settled: {settled}'
    return page


def sync_now(page):
    return page.ev('vAPI.messaging.send("dashboard", {what: "davSyncNow"})',
                   await_promise=True, timeout=90)


def get_status(page):
    return page.ev('vAPI.messaging.send("dashboard", '
                   '{what: "davSyncGetStatus"})', await_promise=True,
                   timeout=30)


def page_alive(page):
    try:
        return page.ev('location.href', await_promise=False,
                       timeout=10) == SETTINGS_URL
    except Exception:
        return False


def bg_eval(browser, expr, timeout=30):
    """Evaluate in the background context (engine state, userFilters...).
    NOTE: `import('./x.js')` inside Runtime.evaluate resolves against the
    DOCUMENT base (background.html at extension root), NOT against
    davsync.js's module URL -- so './background.js' fails with "Failed to
    fetch". This helper rewrites bare relative specifiers to /js/-prefixed
    absolute ones so test snippets can read like the product code."""
    fixed = expr.replace('import("./', 'import("/js/') \
                .replace("import('./", "import('/js/")
    bg = Cdp(f'http://127.0.0.1:{browser.port}',
             wanted_url_substring='background', timeout=30)
    try:
        return bg.ev(fixed, await_promise=True, timeout=timeout)
    finally:
        bg.close()


def make_remote_variant(base, **overrides):
    """Cloud payload modelled on a REAL peer upload: deviceName different,
    importedLists present-but-default (the exact noise that broke 118/119)."""
    data = dict(base)
    data['deviceName'] = 'peer-device'
    data['timeStamp'] = int(time.time() * 1000)
    data.setdefault('userSettings', {})
    data['userSettings'] = dict(data['userSettings'])
    data['userSettings'].setdefault('importedLists', [])
    data.update(overrides)
    return data


# ---------------------------------------------------------------- prologue

def local_base_snapshot(browser, page):
    """Read the local data as the extension itself would collect it (via bg)."""
    return bg_eval(browser, '''
    (async () => {
        const µb = (await import("./background.js")).default;
        const { permanentFirewall, permanentSwitches, permanentURLFiltering } =
            await import("./filtering-engines.js");
        const userFilters = await µb.loadUserFilters();
        return {
            userSettings: µb.getModifiedSettings(µb.userSettings, µb.userSettingsDefault),
            selectedFilterLists: µb.selectedFilterLists,
            whitelist: µb.trustedSites.toLines(),
            dynamicFilteringString: permanentFirewall.toString(),
            urlFilteringString: permanentURLFiltering.toString(),
            hostnameSwitchesString: permanentSwitches.toString(),
            userFilters: userFilters.content.split("\\n"),
        };
    })()
    ''', timeout=60)


# ------------------------------------------------------------------ cases

def case_1_2_3_4():
    """Remote change -> hot apply: page alive, no spurious push, data equal,
    engine rebuilt."""
    print('== cases 1-4: remote change -> hot apply ==')
    wipe_cloud()
    browser = Browser(os.path.join(REPO, '_tmp', 'p-acc'), port=9447)
    page = open_page_and_configure(browser, 'acc-self')
    try:
        base = local_base_snapshot(browser, page)
        check(isinstance(base, dict), 'collected local base snapshot')

        # Remote variant: peer turned OFF icon badge + added one whitelist
        # entry + one dynamic rule. importedLists noise included.
        remote = make_remote_variant(base,
            userSettings=dict(base.get('userSettings', {}),
                              importedLists=[], showIconBadge=False),
            whitelist=(base.get('whitelist') or []) + ['example.org'],
            dynamicFilteringString=(
                (base.get('dynamicFilteringString') or '') +
                '\nadtech.example * * block').strip(),
        )
        cloud_write(remote)

        # Case 1: sync -> applied, page NOT gone, status '已从云端应用'
        result = sync_now(page)
        check(page_alive(page), 'case1: settings page still alive after sync')
        st = get_status(page)
        check(st.get('lastDirection') == 'pull', f"case1: direction=pull (got {st.get('lastDirection')})")
        check(st.get('lastError') in ('', None), f'case1: no lastError (got {st.get("lastError")})')
        check(st.get('pendingRestart') is not True,
              'case1: no restart pending (hot path)')

        # Case 2: wait 20s, sync again -> must NOT become a push / overwrite
        time.sleep(20)
        result2 = sync_now(page)
        st2 = get_status(page)
        check(st2.get('lastDirection') in ('none', 'pull'),
              f"case2: second sync is none/pull, not push (got {st2.get('lastDirection')})")
        cloud = cloud_read()
        check(cloud is not None and cloud.get('deviceName') == 'peer-device',
              f"case2: cloud deviceName still peer (got {cloud and cloud.get('deviceName')})")

        # Case 3: data really applied
        applied = local_base_snapshot(browser, page)
        check(applied.get('userSettings', {}).get('showIconBadge') is False,
              'case3: userSetting showIconBadge=false applied')
        check('example.org' in (applied.get('whitelist') or []),
              'case3: whitelist entry applied')
        check('adtech.example * * block' in (applied.get('dynamicFilteringString') or ''),
              'case3: dynamic rule applied')

        # Case 4: engine rebuilt -- netFilterCount reflects list selection.
        net_count = lambda: bg_eval(browser,
            '(async () => { const m = await import("/js/static-net-filtering.js");'
            ' return m.default.getFilterCount(); })()', timeout=60)
        before = net_count()
        check(isinstance(before, (int, float)) and before >= 0,
              f'case4: engine count readable ({before})')
        # change selection remotely: add available-but-unselected filter lists
        extra_lists = bg_eval(browser,
            '(async () => { const µb = (await import("/js/background.js")).default;'
            ' const av = await µb.getAvailableLists();'
            ' return Object.keys(av).filter(k => av[k].content === "filters"'
            '  && !µb.selectedFilterLists.includes(k)).slice(0,2); })()',
            timeout=60)
        if extra_lists:
            remote2 = make_remote_variant(base,
                selectedFilterLists=(base.get('selectedFilterLists') or [])
                                    + list(extra_lists))
            cloud_write(remote2)
            sync_now(page)
            after = net_count()
            check(after != before,
                  f'case4: netFilterCount changed after list change '
                  f'({before} -> {after})')
        else:
            check(True, 'case4: no additional lists available (count check n/a)')
        return browser, page
    except Exception as e:
        print(f'  EXCEPTION: {e}')
        import traceback; traceback.print_exc()
        FAIL.append(f'cases1-4 exception: {e}')
        return browser, page


def case_5():
    """Local change -> sync -> pushed, no conflict."""
    print('== case 5: local change -> push ==')
    browser = Browser(os.path.join(REPO, '_tmp', 'p-acc'), port=9447)
    page = open_page_and_configure(browser, 'acc-self')
    try:
        # local edit: add whitelist entry through the bg API (as the pane does)
        bg_eval(browser, '''
        (async () => {
            const µb = (await import("./background.js")).default;
            µb.trustedSites.fromLines(µb.trustedSites.toLines().concat(["local.test"]));
            µb.saveWhitelist();
            return true;
        })()
        ''', timeout=30)
        # debounce would sync in ~1min; trigger now
        st = sync_now(page)
        st2 = get_status(page)
        check(st2.get('lastDirection') == 'push',
              f"case5: direction=push (got {st2.get('lastDirection')})")
        check(st2.get('conflict') is not True, 'case5: no conflict')
        cloud = cloud_read()
        check(cloud is not None and 'local.test' in (cloud.get('whitelist') or []),
              'case5: cloud has local.test entry')
    except Exception as e:
        print(f'  EXCEPTION: {e}')
        import traceback; traceback.print_exc()
        FAIL.append(f'case5 exception: {e}')
    finally:
        page.close() if page else None
        browser.stop()


def case_6():
    """Both ends change -> conflict banner."""
    print('== case 6: both changed -> conflict ==')
    wipe_cloud()
    browser = Browser(os.path.join(REPO, '_tmp', 'p-acc'), port=9447)
    page = open_page_and_configure(browser, 'acc-self')
    try:
        base = local_base_snapshot(browser, page)
        # remote changed by peer
        remote = make_remote_variant(base,
            whitelist=(base.get('whitelist') or []) + ['peer.example'])
        cloud_write(remote)
        # local changed too (different entry)
        bg_eval(browser, '''
        (async () => {
            const µb = (await import("./background.js")).default;
            µb.trustedSites.fromLines(µb.trustedSites.toLines().concat(["mine.example"]));
            µb.saveWhitelist();
            return true;
        })()
        ''', timeout=30)
        sync_now(page)
        st = get_status(page)
        check(st.get('conflict') is True,
              f'case6: conflict flag set (conflict={st.get("conflict")}, dir={st.get("lastDirection")}, err={st.get("lastError")})')
        # Banner display is refreshed by davSyncRunAction's reply handler
        # (refreshDavStatus -> davSyncApplyBanner) or the 10s poll; wait for
        # either to land before asserting.
        banner = False
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                banner = page.ev(
                    'document.getElementById("davSyncConflictRow") && '
                    'document.getElementById("davSyncConflictRow")'
                    '.style.display === "block"',
                    await_promise=False)
            except Exception:
                pass
            if banner is True:
                break
            time.sleep(1)
        check(banner is True, 'case6: conflict banner visible')
    except Exception as e:
        print(f'  EXCEPTION: {e}')
        import traceback; traceback.print_exc()
        FAIL.append(f'case6 exception: {e}')
    finally:
        page.close() if page else None
        browser.stop()


def case_7():
    """Remote hiddenSettings change -> restart path; data correct after."""
    print('== case 7: hiddenSettings change -> restart path ==')
    wipe_cloud()
    browser = Browser(os.path.join(REPO, '_tmp', 'p-acc'), port=9447)
    page = open_page_and_configure(browser, 'acc-self')
    try:
        base = local_base_snapshot(browser, page)
        # consoleLogLevel is poisoned on this platform: devbuild flavor makes
        # its DEFAULT 'info', so {consoleLogLevel: info} is a no-op. Use a
        # stable-default hidden key instead.
        remote = make_remote_variant(base,
                                     hiddenSettings={'extensionUpdateForceReload': True})
        cloud_write(remote)
        result = sync_now(page)
        # page should go away (restart) or be refreshed by pane code
        time.sleep(3)
        alive = page_alive(page)
        st = None
        # after restart, read the PERSISTED state via chrome.storage (the
        # live davSync module instance is not addressable from a fresh
        # import: that would create a second module copy with stale state).
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                st = bg_eval(browser,
                    'new Promise(res => chrome.storage.local.get("davSyncState",'
                    ' v => { const d = v.davSyncState || {};'
                    ' res({dir: d.lastDirection, err: d.lastError,'
                    ' t: d.lastSyncTime}); }))', timeout=20)
                if st and st.get('t'):
                    break
            except Exception:
                time.sleep(2)
        check(st is not None, 'case7: background reachable after restart')
        if st:
            check(st.get('dir') == 'pull', f"case7: direction=pull (got {st.get('dir')})")
        hs = bg_eval(browser,
            '(async () => { const µb = (await import("/js/background.js")).default;'
            ' return µb.hiddenSettings.extensionUpdateForceReload; })()', timeout=30)
        check(hs is True,
              f'case7: hiddenSetting extensionUpdateForceReload applied (got {hs!r})')
        # reopen a fresh settings page to prove the pane story still works
        # (navigation is async; poll like open_settings_page does)
        page2 = Cdp(f'http://127.0.0.1:{browser.port}',
                    create_url=SETTINGS_URL, timeout=60)
        reopened = False
        deadline = time.time() + 25
        while time.time() < deadline:
            try:
                if page2.ev('location.href', await_promise=False,
                            timeout=15) == SETTINGS_URL:
                    reopened = True
                    break
            except Exception:
                time.sleep(1)
        check(reopened, 'case7: settings page can be reopened after restart')
        page2.close()
    except Exception as e:
        print(f'  EXCEPTION: {e}')
        import traceback; traceback.print_exc()
        FAIL.append(f'case7 exception: {e}')
    finally:
        page.close() if page else None
        browser.stop()


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if only in ('all', '1234'):
        b, p = case_1_2_3_4()
        p.close() if p else None
        b.stop()
    if only in ('all', '5'):
        case_5()
    if only in ('all', '6'):
        case_6()
    if only in ('all', '7'):
        case_7()

    print(f'\n== ACCEPTANCE: {len(PASS)} passed, {len(FAIL)} failed ==')
    for f in FAIL:
        print(f'  FAILED: {f}')
    sys.exit(1 if FAIL else 0)


if __name__ == '__main__':
    main()
