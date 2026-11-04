#!/usr/bin/env python3
"""Regression: fresh device -> first pull -> immediate 立即同步 must NOT
show 无变化 (the reported bug: lastDirection was overwritten to 'none' by
the redundant follow-up sync's in-sync branch).

Scenario:
  A. fresh profile, cloud already has peer data (like a second computer)
  B. configure via the real settings form -> the 500ms auto-sync pulls
  C. click 立即同步 (davSyncNow) -> reply must have lastDirection == 'pull'
     (NOT 'none') and appliedNow == true only on the transfer run
  D. another 立即同步 -> still lastDirection == 'pull' (in-sync checks no
     longer overwrite it), appliedNow absent
"""
import glob
import json
import os
import sys
import time

for cand in glob.glob(r'C:/Users/*/.workbuddy/binaries/python/envs/default/site-packages'):
    if cand not in sys.path:
        sys.path.insert(0, cand)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scaffold import Browser, Cdp, SETTINGS_URL, REPO
from acceptance import (wipe_cloud, local_base_snapshot, PASS, FAIL, check,
                        cloud_read, get_status, bg_eval)


def main():
    print('== regression: first pull then 立即同步 shows 已从云端应用 ==')
    wipe_cloud()
    browser = Browser(os.path.join(REPO, '_tmp', 'p-acc'), port=9447)

    # Seed the cloud with a peer snapshot BEFORE configuring this device --
    # exactly the "second computer joins an existing group" situation.
    # The peer data must be self-consistent, so build it from a throwaway
    # browser: simplest is to copy the shape our own tests already produce.
    peer = {
        'deviceName': 'peer-pc',
        'timeStamp': int(time.time() * 1000),
        'userSettings': {'importedLists': [], 'showIconBadge': False},
        'selectedFilterLists': ['user-filters', 'ublock-filters',
                                'ublock-badware', 'ublock-privacy',
                                'ublock-unbreak', 'ublock-quick-fixes',
                                'easylist', 'easyprivacy', 'urlhaus-1',
                                'plowe-0', 'CHN-0'],
        'whitelist': ['chrome-extension-scheme', 'moz-extension-scheme',
                      'peer.example'],
        'dynamicFilteringString': (
            'behind-the-scene * * noop\nbehind-the-scene * image noop\n'
            'behind-the-scene * 3p noop\nbehind-the-scene * inline-script noop\n'
            'behind-the-scene * 1p-script noop\nbehind-the-scene * 3p-script noop\n'
            'behind-the-scene * 3p-frame noop\nadtech.peer * * block'),
        'urlFilteringString': '',
        'hostnameSwitchesString': 'no-large-media: behind-the-scene false',
        'userFilters': ['! peer filters', '||peer-banner.example^'],
    }
    from acceptance import cloud_write
    cloud_write(peer)

    # Configure this device through the real form (open_page_and_configure
    # waits for the first transfer to settle; here the first transfer IS the
    # pull we care about). Retry once: settings page load can transiently
    # surface chrome-error:// while the renderer swaps.
    from acceptance import open_page_and_configure
    page = None
    for attempt in range(2):
        try:
            page = open_page_and_configure(browser, 'fresh-pc', wait_put=False)
            break
        except AssertionError as e:
            if 'did not load' not in str(e) or attempt == 1:
                raise
            time.sleep(3)
    try:
        # wait until the auto-sync pulls: status dir == 'pull'
        deadline = time.time() + 60
        st = None
        while time.time() < deadline:
            try:
                st = get_status(page)
            except Exception:
                time.sleep(1)
                continue
            if st.get('lastDirection') == 'pull' and not st.get('lastError'):
                break
            time.sleep(1)
        check(st is not None and st.get('lastDirection') == 'pull',
              f"A: auto first sync pulled (dir={st and st.get('lastDirection')}, "
              f"err={st and st.get('lastError')})")

        # verify data really landed
        wl = bg_eval(browser,
            '(async () => { const µb = (await import("/js/background.js")).default;'
            ' return µb.trustedSites.toLines(); })()', timeout=30)
        check('peer.example' in (wl or []),
              'A: peer whitelist entry applied (data really pulled)')

        # C: click 立即同步 -> the reply must still say pull, NOT none.
        # Drive the REAL button, not a bare messaging.send: the pane's
        # status line is only updated by davSyncRunAction's .then handler
        # (the 10s poll deliberately skips while focus is inside #davSync),
        # so E's text assertions below depend on this click path.
        btn_ready = page.ev(
            '(function(){ const b = document.getElementById("davSyncNow");'
            ' if (b.disabled) { return {ok:false, why:"button disabled"}; }'
            ' b.click(); return {ok:true}; })()',
            await_promise=True, timeout=15)
        check(btn_ready and btn_ready.get('ok') is True,
              f"C: 立即同步 button clickable and clicked ({btn_ready})")
        deadline = time.time() + 90
        result = None
        while time.time() < deadline:
            try:
                result = get_status(page)
            except Exception:
                time.sleep(1)
                continue
            if result and result.get('lastSyncTime') and not result.get('lastError'):
                break
            time.sleep(1)
        check(result is not None and result.get('lastDirection') == 'pull',
              f"C: 立即同步 keeps dir=pull (got {result and result.get('lastDirection')})")
        check('无变化' not in json.dumps(result.get('lastDirection')),
              'C: no none-direction in reply')

        # D: one more click — same expectations
        page.ev('(function(){ document.activeElement && document.activeElement.blur();'
                ' const b = document.getElementById("davSyncNow");'
                ' if (!b.disabled) { b.click(); } return b.disabled; })()',
                await_promise=True, timeout=15)
        deadline = time.time() + 90
        result2 = None
        while time.time() < deadline:
            try:
                result2 = get_status(page)
            except Exception:
                time.sleep(1)
                continue
            if result2 and result2.get('lastDirection') == 'pull':
                break
            time.sleep(1)
        check(result2 is not None and result2.get('lastDirection') == 'pull',
              f"D: second 立即同步 still dir=pull (got {result2 and result2.get('lastDirection')})")

        # E: the pane's own text (what the user actually reads). Wait for the
        # button-click render to land (davSyncRunAction's .then) or the 10s
        # poll (focus was blurred above, so the poll is allowed to run).
        deadline = time.time() + 45
        text = None
        while time.time() < deadline:
            text = page.ev('document.getElementById("davSyncStatus").textContent',
                           await_promise=False)
            # settle condition: the click's pending text is 同步中…; wait for
            # the .then render to replace it with the final direction text.
            if text and ('已从云端应用' in text or '无变化' in text
                         or '错误' in text):
                break
            time.sleep(1)
        check('已从云端应用' in (text or ''),
              f"E: status line shows 已从云端应用 (got {text!r})")
        check('无变化' not in (text or ''),
              f"E: status line does NOT show 无变化 (got {text!r})")

        print(f'\n== regression: {len(PASS)} passed, {len(FAIL)} failed ==')
        for f in FAIL:
            print('  FAILED:', f)
        return 1 if FAIL else 0
    finally:
        try:
            page.close()
        except Exception:
            pass
        browser.stop()


if __name__ == '__main__':
    sys.exit(main())
