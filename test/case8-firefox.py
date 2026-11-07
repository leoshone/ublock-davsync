#!/usr/bin/env python3
"""Case 8 (Firefox): pull -> restart -> sync -> dir=none, cloud intact.

Follows the proven recipe from docs/DAVSYNC-TESTING.md §17:
- a log-hook build copy (self-config + /log/<msg> reporting), engine code
  identical to the release build;
- web-ext run (temporary add-on), two browser sessions:
    session A: boot -> push   (deviceName=firefox-ff)
    (we mutate the cloud file to look like a peer)
    session B: boot -> pull (restart) -> boot -> dir=none, cloud NOT overwritten
- verdict read from the WebDAV server log (/log/ entries).

Pure subprocess orchestration; no BiDi needed (UI assertions are not
possible on Firefox per §17.2b, and none are required here).
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse

for cand in glob.glob(r'C:/Users/*/.workbuddy/binaries/python/envs/default/site-packages'):
    if cand not in sys.path:
        sys.path.insert(0, cand)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scaffold import REPO, WEBDAV_URL, WEBDAV_USER, WEBDAV_PASSWORD, rmtree
from acceptance import (check, wipe_cloud, cloud_read, cloud_write, PASS,
                        FAIL, make_remote_variant)

# fingerprintData is module-private; expose it for the Firefox log hook only.
# (A test-only export in the hook build copy, not in the release build.)


# NOTE(machine-local): FF_EXE / NPX point at this machine's installs.
# On a new machine, install Firefox anywhere and `npm i -g web-ext`
# (or adjust NPX to any node>=20), then update these two paths.
FF_EXE = r'D:\AiSpaces\Work\2026-10-21-21-29-21\_tmp\davtest\firefox\firefox.exe'
NPX = r'C:\Users\xiongbin\.workbuddy\binaries\node\versions\22.22.2-6\npx.cmd'
SRC_BUILD = os.path.join(REPO, 'dist', 'build', 'uBlock0.firefox')
HOOK_BUILD = os.path.join(REPO, '_tmp', 'uBlock0.firefox-hook')
PROFILE = os.path.join(REPO, '_tmp', 'p-ff')
WEBDAV_LOG = os.path.join(REPO, '_tmp', 'webdav-server.log')

HOOK_JS = '''
const ffLog = msg => { try { fetch('http://127.0.0.1:8088/log/' + encodeURIComponent(msg)).catch(()=>{}); } catch {} };
( async () => {
    await configReady;
    if ( config.url === '' ) {
        config.url = '__WEBDAV_URL__';
        config.username = '__WEBDAV_USER__';
        config.password = '__WEBDAV_PASS__';
        config.deviceName = 'firefox-ff';
        config.enabled = true;
        await saveConfig();
    }
    ffLog('boot');
    setTimeout(async () => {
        try {
            const local = await (async () => {
                const µb = (await import('./background.js')).default;
                const { permanentFirewall, permanentSwitches, permanentURLFiltering } =
                    await import('./filtering-engines.js');
                const userFilters = await µb.loadUserFilters();
                return {
                    userSettings: µb.getModifiedSettings(µb.userSettings, µb.userSettingsDefault),
                    selectedFilterLists: µb.selectedFilterLists,
                    whitelist: µb.trustedSites.toLines(),
                    dynamicFilteringString: permanentFirewall.toString(),
                    urlFilteringString: permanentURLFiltering.toString(),
                    hostnameSwitchesString: permanentSwitches.toString(),
                    userFilters: userFilters.content.split('\\n'),
                };
            })();
            ffLog('local wl=' + JSON.stringify(local.whitelist));
            ffLog('local us=' + JSON.stringify(local.userSettings));
            ffLog('local lists=' + local.selectedFilterLists.length +
                  ' dyn=' + local.dynamicFilteringString.length +
                  ' uf=' + local.userFilters.length);
            const m = await import('./davsync.js');
            const lfp = await m.fingerprintData(local);
            const bin = await vAPI.storage.get('davSyncState');
            const st = bin.davSyncState || {};
            ffLog('fp local=' + lfp.length +
                  ' lastLocal=' + (st.lastLocalFingerprint || '').length +
                  ' lastApplied=' + (st.lastAppliedRemoteFp || '').length +
                  ' localEqLastLocal=' + (lfp === st.lastLocalFingerprint) +
                  ' lastLocalEqApplied=' +
                  (st.lastLocalFingerprint === st.lastAppliedRemoteFp));
        } catch (e) { ffLog('dump err ' + e.message); }
        davSync.syncNow().then(st => ffLog('sync dir=' + st.lastDirection + ' err=' + (st.lastError || '-')));
    }, 3000);
})();
'''.replace('__WEBDAV_URL__', WEBDAV_URL) \
   .replace('__WEBDAV_USER__', WEBDAV_USER) \
   .replace('__WEBDAV_PASS__', WEBDAV_PASSWORD)


def make_hook_build():
    if os.path.isdir(HOOK_BUILD):
        rmtree(HOOK_BUILD)
    shutil.copytree(SRC_BUILD, HOOK_BUILD)
    p = os.path.join(HOOK_BUILD, 'js', 'davsync.js')
    with open(p, encoding='utf-8') as f:
        src = f.read()
    marker = 'export default davSync;'
    assert marker in src, 'export marker not found in davsync.js'
    # Diagnostic: log the fingerprint decision inside the hook build so the
    # C-pull mystery can be read straight from the server log.
    fp_probe = ("try { ffLog('fp local=' + localFp.length + ' remote=' + "
                "remoteFp.length + ' eq=' + (localFp === remoteFp) + "
                "' lastApplied_eq_remote=' + (syncState.lastAppliedRemoteFp "
                "=== remoteFp) + ' localDirty=' + localDirty); } catch {}")
    anchor = "    // 4. Nothing changed anywhere"
    assert anchor in src, 'step-4 anchor not found'
    src = src.replace(anchor, '    ' + fp_probe + '\n' + anchor)
    src = src.replace(marker,
                      HOOK_JS + '\nexport { fingerprintData };\n' + marker)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(src)


def run_ff_session(timeout_s=75, wipe_profile=True):
    """One web-ext run; the hook build self-syncs; kill after timeout.
    wipe_profile=False reuses the previous session's profile (needed for
    the no-bounce check: a fresh profile is a new device that legitimately
    pulls)."""
    if wipe_profile:
        rmtree(PROFILE)
    os.makedirs(PROFILE, exist_ok=True)
    cmd = [NPX, '--yes', 'web-ext', 'run',
           '--source-dir', HOOK_BUILD,
           '--firefox', FF_EXE,
           '--firefox-profile', PROFILE,
           '--keep-profile-changes',
           '--no-input', '--no-reload']
    proc = subprocess.Popen(cmd, cwd=REPO, shell=False,
                            stdout=open(os.path.join(REPO, '_tmp',
                                                   'webext.log'), 'w'),
                            stderr=subprocess.STDOUT)
    time.sleep(timeout_s)
    subprocess.run(['taskkill', '/F', '/IM', 'firefox.exe'],
                   capture_output=True)
    try:
        proc.terminate()
        proc.wait(timeout=15)
    except Exception:
        proc.kill()


def log_entries_since(n):
    """Read /log/ entries from the webdav server log (newest at end)."""
    entries = []
    try:
        with open(WEBDAV_LOG, encoding='utf-8', errors='ignore') as f:
            for line in f:
                if '[FF-LOG]' in line:
                    entries.append(line.split('[FF-LOG]', 1)[1].strip())
    except FileNotFoundError:
        pass
    return entries[n:]


def main():
    print('== case 8: Firefox pull -> restart -> sync -> dir=none ==')
    wipe_cloud()
    make_hook_build()

    # Session A: first boot pushes (deviceName=firefox-ff)
    n0 = len([l for l in open(WEBDAV_LOG, encoding='utf-8', errors='ignore')
              if '[FF-LOG]' in l]) if os.path.isfile(WEBDAV_LOG) else 0
    run_ff_session()
    entries = log_entries_since(n0)
    print('session A log:', entries)
    a_boot = any(e == 'boot' for e in entries)
    a_push = any(e.startswith('sync dir=push') for e in entries)
    check(a_boot, 'case8-A: boot logged')
    check(a_push, 'case8-A: sync dir=push')
    cloud = cloud_read()
    check(cloud is not None and cloud.get('deviceName') == 'firefox-ff',
          f"case8-A: cloud deviceName=firefox-ff (got {cloud and cloud.get('deviceName')})")

    # Peer mutation: add a marker whitelist entry + different device name
    remote = make_remote_variant(cloud,
                                 whitelist=(cloud.get('whitelist') or [])
                                           + ['ff-case8.example'])
    cloud_write(remote)

    # Session B: fresh boot -> pull (hot path: no restart, single boot;
    # restart path would show boot -> pull -> boot -> none) -> later sync
    # settles at dir=none. Accept both shapes; forbid a push.
    n1 = len([l for l in open(WEBDAV_LOG, encoding='utf-8', errors='ignore')
              if '[FF-LOG]' in l])
    run_ff_session(timeout_s=150)
    entries = log_entries_since(n1)
    print('session B log:', entries)
    b_pulls = [e for e in entries if e.startswith('sync dir=pull')]
    b_none = [e for e in entries if e.startswith('sync dir=none')]
    b_push = [e for e in entries if e.startswith('sync dir=push')]
    check(len(b_pulls) >= 1, f'case8-B: pull happened ({b_pulls})')
    # Hot path: the pull is applied in place, no restart, and no local-change
    # broadcast fires -- so no immediate follow-up sync is scheduled. The
    # no-bounce contract is proven by session C: the next boot must sync
    # with dir=none (pre-hot-apply bug: it pulled or pushed again).
    check(len(b_push) == 0, f'case8-B: NO spurious push (got {b_push})')

    # Session C: SAME profile, next boot must be dir=none (no bounce,
    # cloud untouched). A fresh profile would be a new device that
    # legitimately pulls -- so reuse B's profile here.
    n2 = len([l for l in open(WEBDAV_LOG, encoding='utf-8', errors='ignore')
              if '[FF-LOG]' in l])
    run_ff_session(timeout_s=75, wipe_profile=False)
    entries = log_entries_since(n2)
    print('session C log:', entries)
    c_none = [e for e in entries if e.startswith('sync dir=none')]
    c_pull = [e for e in entries if e.startswith('sync dir=pull')]
    c_push = [e for e in entries if e.startswith('sync dir=push')]
    check(len(c_none) >= 1, f'case8-C: boot sync dir=none ({c_none})')
    check(len(c_pull) == 0 and len(c_push) == 0,
          f'case8-C: no re-pull/re-push on next boot '
          f'(pull={c_pull}, push={c_push})')

    # Cloud must NOT have been overwritten
    cloud2 = cloud_read()
    check(cloud2 is not None and cloud2.get('deviceName') == 'peer-device',
          f"case8-B: cloud still peer's (got {cloud2 and cloud2.get('deviceName')})")

    print(f'\n== case8: {len(PASS)} passed, {len(FAIL)} failed ==')
    for f in FAIL:
        print('  FAILED:', f)
    if not FAIL:
        rmtree(PROFILE)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
