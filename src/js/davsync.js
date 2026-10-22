/*******************************************************************************

    uBlock Origin DAV-Sync fork
    Copyright (C) 2026 xiongbin

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see {http://www.gnu.org/licenses/}.

    WebDAV-backed auto-sync for uBO user data.

    Design (key decisions):
    - Data format mirrors messaging.js `backupUserData()`: one JSON file on
      the WebDAV server, fully compatible with uBO's "Restore from file".
    - Sync strategy is pull-first with an upload guard:
        * Remote newer AND no local dirty changes  -> apply remote, restart.
        * Local dirty changes AND remote unchanged -> push local.
        * Both changed                             -> keep local, push
          (last-writer-wins; user data size is small and conflict windows
          are rare; a merge of arbitrary filter lists is not attempted).
    - An ETag + local-snapshot hash is recorded after every push/pull so we
      can tell "local changed since last sync" from "same as last sync",
      which prevents sync self-oscillation.

    Home: https://github.com/gorhill/uBlock

*/

'use strict';

import { onBroadcast } from './broadcast.js';

/******************************************************************************/

const DAV_FILE_PATH_DEFAULT = 'ublock-davsync/ublock-backup.json';

const SYNC_ALARM_NAME = 'davSyncAlarm';
const SYNC_PERIOD_MIN = 30;          // periodic sync every 30 minutes
const SYNC_INITIAL_DELAY_MIN = 2;    // first sync 2 min after launch

/******************************************************************************/
// WebDAV client (fetch-based; Basic Auth only -- Jianguoyun/Nutstore,
// Nextcloud, Apache/Nginx DAV all work with this).

const davRequest = async function(config, method, filePath, details = {}) {
    const base = config.url.replace(/\/+$/, '');
    const url = `${base}/${filePath.split('/').map(encodeURIComponent).join('/')}`;
    const headers = Object.assign({}, details.headers);
    if ( config.username !== '' ) {
        headers.Authorization = 'Basic ' + btoa(
            `${config.username}:${config.password}`
        );
    }
    if ( details.body !== undefined ) {
        headers['Content-Type'] = 'application/json; charset=utf-8';
    }
    let response;
    try {
        response = await fetch(url, {
            method,
            headers,
            body: details.body,
            credentials: 'omit',
            cache: 'no-store',
            // Floccus-style hardening: a 302 (e.g. captive portal, expired
            // session HTML login page) would silently drop the Authorization
            // header and return an HTML body that fails JSON.parse -- much
            // harder to diagnose than an explicit redirect error.
            redirect: 'manual',
        });
    } catch (reason) {
        return { ok: false, error: `network: ${reason}` };
    }
    // Redirects are not followed (see above): report them explicitly.
    if ( response.status >= 300 && response.status < 400 ) {
        return { ok: false, status: response.status, error: `redirect ${response.status} (check server URL)` };
    }
    // 404 is a normal condition on first sync (file not yet created).
    if ( response.status === 404 && details.allowNotFound === true ) {
        return { ok: true, notFound: true, status: 404 };
    }
    if ( response.ok === false ) {
        return { ok: false, status: response.status, error: `HTTP ${response.status}` };
    }
    const etag = response.headers.get('ETag') || response.headers.get('Etag') || '';
    const text = details.wantBody === false ? '' : await response.text();
    return { ok: true, status: response.status, etag, text };
};

const davGet = function(config) {
    return davRequest(config, 'GET', config.filePath, {
        allowNotFound: true,
    });
};

const davPut = function(config, text, ifMatch = '') {
    const headers = {};
    // Conditional PUT: only overwrite if we saw this exact version last.
    // Guards against two devices clobbering each other blind-folded.
    if ( ifMatch !== '' ) { headers['If-Match'] = ifMatch; }
    return davRequest(config, 'PUT', config.filePath, {
        body: text,
        headers,
    });
};

// Floccus-style upload verification: re-read the file size via PROPFIND and
// compare against what we sent. Catches silent server-side truncation
// (observed on flaky WebDAV providers) before we record a good sync state.
const PUT_VERIFY_RETRIES = 2;

const davGetRemoteFileSize = async function(config) {
    const result = await davRequest(config, 'PROPFIND', config.filePath, {
        headers: { Depth: '0' },
    });
    if ( result.ok === false ) { return null; }
    const m = result.text.match(/<[\w-]*:?getcontentlength[^>]*>(\d+)</);
    return m ? parseInt(m[1], 10) : null;
};

const davPutVerified = async function(config, text, ifMatch = '') {
    const expected = new TextEncoder().encode(text).length;
    for ( let attempt = 0; ; attempt++ ) {
        const put = await davPut(config, text, ifMatch);
        if ( put.ok === false ) { return put; }
        const remoteSize = await davGetRemoteFileSize(config);
        if ( remoteSize === null ) {
            // Server does not expose getcontentlength: trust the 2xx.
            return put;
        }
        if ( remoteSize === expected ) { return put; }
        if ( attempt >= PUT_VERIFY_RETRIES ) {
            return { ok: false, error: `upload size mismatch after ${attempt + 1} attempts (${remoteSize} != ${expected})` };
        }
    }
};

// Ensure the remote folder exists (Jianguoyun returns 409 Conflict on
// PUT into a missing collection).
const davMkdirp = async function(config) {
    const parts = config.filePath.split('/');
    parts.pop(); // file name itself is not a collection
    let base = config.url.replace(/\/+$/, '');
    for ( const part of parts ) {
        base += `/${encodeURIComponent(part)}`;
        try {
            await fetch(base, {
                method: 'MKCOL',
                headers: config.username !== ''
                    ? { Authorization: 'Basic ' + btoa(`${config.username}:${config.password}`) }
                    : {},
                credentials: 'omit',
                redirect: 'manual',
            });
        } catch {
        }
    }
};

/******************************************************************************/
// Floccus-style lock file: prevents two devices from syncing simultaneously
// and clobbering each other (our If-Match guard only protects single-PUT
// races; a full sync cycle is read-modify-write and needs mutual exclusion).

const DAV_LOCK_PATH = 'ublock-davsync/ublock-sync.lock';
const LOCK_TTL_MS = 5 * 60 * 1000;   // stale after 5 minutes (crashed device)

const davLockPath = function(config) {
    // Lock lives next to the data file, honouring a custom filePath.
    const dir = config.filePath.split('/').slice(0, -1).join('/');
    return dir !== '' ? `${dir}/ublock-sync.lock` : DAV_LOCK_PATH.split('/').pop();
};

// Returns true if the lock was acquired.
const davLockAcquire = async function(config) {
    const lockPath = davLockPath(config);
    // Read existing lock: if fresh, somebody else is syncing right now.
    const existing = await davRequest(config, 'GET', lockPath, {
        allowNotFound: true,
    });
    if ( existing.ok === true && existing.notFound !== true ) {
        try {
            const info = JSON.parse(existing.text);
            if ( Date.now() - (info.timeStamp || 0) < LOCK_TTL_MS ) {
                return false;   // someone else holds a live lock
            }
        } catch {
            // Unparseable lock: treat as stale and take over.
        }
    }
    const put = await davRequest(config, 'PUT', lockPath, {
        body: JSON.stringify({
            timeStamp: Date.now(),
            deviceName: config.deviceName || '',
        }, null, 1),
    });
    return put.ok === true;
};

const davLockRelease = async function(config) {
    await davRequest(config, 'DELETE', davLockPath(config), {
        allowNotFound: true,
    });
};

/******************************************************************************/
// Config persisted in vAPI.storage (storage.local) -- never leaves the
// device except as Basic-Auth headers to the configured server.

const configDefault = {
    enabled: false,          // auto-sync on/off (the toggle in settings pane)
    url: '',                 // e.g. https://dav.jianguoyun.com/dav/
    username: '',
    password: '',
    filePath: DAV_FILE_PATH_DEFAULT,
    deviceName: '',          // reported in remote metadata for diagnostics
};

let config = Object.assign({}, configDefault);

const configReady = (async ( ) => {
    const bin = await vAPI.storage.get('davSyncConfig');
    if ( bin instanceof Object && bin.davSyncConfig instanceof Object ) {
        config = Object.assign(configDefault, bin.davSyncConfig);
    }
    return config;
})();

const saveConfig = function( ) {
    return vAPI.storage.set({ davSyncConfig: config });
};

/******************************************************************************/
// Local user-data snapshot (same shape as official backup file).

const collectLocalData = async function( ) {
    // Imported lazily to avoid module-load order issues: this module is
    // loaded after ublock.js/messaging.js at runtime (ES module graph).
    // µBlock instance lives in background.js; user-facing helpers live in
    // ublock.js (which extends the instance).
    const µb = (await import('./background.js')).default;
    const ub = await import('./ublock.js');
    const { permanentFirewall, permanentSwitches, permanentURLFiltering } =
        await import('./filtering-engines.js');

    const userFilters = await µb.loadUserFilters();

    return {
        timeStamp: Date.now(),
        deviceName: config.deviceName || '',
        userSettings: µb.getModifiedSettings(
            µb.userSettings,
            µb.userSettingsDefault
        ),
        selectedFilterLists: µb.selectedFilterLists,
        whitelist: µb.trustedSites.toLines(),
        dynamicFilteringString: permanentFirewall.toString(),
        urlFilteringString: permanentURLFiltering.toString(),
        hostnameSwitchesString: permanentSwitches.toString(),
        userFilters: userFilters.content.split('\n'),
    };
};

// Cheap fingerprint of user-relevant data: settings strings + filters.
// Filter-list *contents* are not fingerprinted (they auto-update on their
// own schedule on every device; only the selection matters, which is
// covered by selectedFilterLists).
const fingerprintLocalData = function(data) {
    return [
        JSON.stringify(data.userSettings || {}),
        JSON.stringify(data.selectedFilterLists || []),
        data.whitelist || '',
        data.dynamicFilteringString || '',
        data.urlFilteringString || '',
        data.hostnameSwitchesString || '',
        (data.userFilters || []).join('\n'),
    ].join('\u0000');
};

/******************************************************************************/
// Sync state persisted locally.

let syncState = {
    lastEtag: '',            // ETag of remote file as of last sync
    lastLocalFingerprint: '',// fingerprint captured at last successful sync
    lastSyncTime: 0,
    lastError: '',
    lastDirection: '',       // 'push' | 'pull' | 'none'
};

const stateReady = (async ( ) => {
    const bin = await vAPI.storage.get('davSyncState');
    if ( bin instanceof Object && bin.davSyncState instanceof Object ) {
        syncState = Object.assign(syncState, bin.davSyncState);
    }
    return syncState;
})();

const saveSyncState = function( ) {
    return vAPI.storage.set({ davSyncState: syncState });
};

/******************************************************************************/
// Core sync algorithm. Returns a short human-readable status string.

const runSyncOnce = async function( ) {
    if ( config.enabled !== true ) { return 'disabled'; }
    if ( config.url === '' ) { return 'no-url'; }

    await Promise.all([ configReady, stateReady ]);

    // 0. Mutual exclusion: another device may be mid-sync. One retry after
    // a short wait covers the common "both devices hit the periodic alarm"
    // case without complicating the caller.
    let locked = await davLockAcquire(config);
    if ( locked === false ) {
        await new Promise(resolve => setTimeout(resolve, 8000));
        locked = await davLockAcquire(config);
        if ( locked === false ) {
            syncState.lastError = 'locked-by-other-device';
            saveSyncState();
            return syncState.lastError;
        }
    }

    try {
        return await runSyncOnceLocked();
    } finally {
        davLockRelease(config);
    }
};

const runSyncOnceLocked = async function( ) {
    // 1. Fetch remote
    let remote = await davGet(config);
    if ( remote.ok === false ) {
        syncState.lastError = remote.error;
        saveSyncState();
        return remote.error;
    }

    const local = await collectLocalData();
    const localFp = fingerprintLocalData(local);
    const localDirty = localFp !== syncState.lastLocalFingerprint;

    // 2. Remote empty -> first push
    if ( remote.notFound === true ) {
        const put = await davMkdirp(config).then(( ) =>
            davPutVerified(config, JSON.stringify(local, null, 1))
        );
        if ( put.ok === false ) {
            syncState.lastError = put.error;
            saveSyncState();
            return put.error;
        }
        syncState.lastEtag = put.etag || '';
        syncState.lastLocalFingerprint = localFp;
        syncState.lastSyncTime = Date.now();
        syncState.lastDirection = 'push';
        syncState.lastError = '';
        saveSyncState();
        return 'pushed-init';
    }

    // 3. Parse remote
    let remoteData;
    try {
        remoteData = JSON.parse(remote.text);
    } catch {
        syncState.lastError = 'remote-parse-failed';
        saveSyncState();
        return syncState.lastError;
    }

    const remoteFp = fingerprintLocalData(remoteData);
    const remoteSameAsLocal = remoteFp === localFp;
    const remoteMatchesLastEtag = remote.etag !== '' &&
        remote.etag === syncState.lastEtag;

    // 4. Nothing changed anywhere
    if ( remoteSameAsLocal && localDirty === false ) {
        syncState.lastSyncTime = Date.now();
        syncState.lastError = '';
        saveSyncState();
        return 'in-sync';
    }

    // 5. Local dirty & remote unchanged since we last saw it -> push
    if ( localDirty && ( remoteMatchesLastEtag || remoteFp === syncState.lastLocalFingerprint ) ) {
        const put = await davPutVerified(
            config,
            JSON.stringify(local, null, 1),
            syncState.lastEtag
        );
        // If-Match failed (someone else pushed) -> fall through to pull-apply
        if ( put.ok === true ) {
            syncState.lastEtag = put.etag || '';
            syncState.lastLocalFingerprint = localFp;
            syncState.lastSyncTime = Date.now();
            syncState.lastDirection = 'push';
            syncState.lastError = '';
            saveSyncState();
            return 'pushed';
        }
        if ( put.status !== 412 ) {
            syncState.lastError = put.error;
            saveSyncState();
            return put.error;
        }
        // 412 Precondition Failed: remote moved on; re-read and apply remote
        remote = await davGet(config);
        if ( remote.ok === false || remote.notFound === true ) {
            syncState.lastError = remote.ok ? 'remote-vanished' : remote.error;
            saveSyncState();
            return syncState.lastError;
        }
        try {
            remoteData = JSON.parse(remote.text);
        } catch {
            syncState.lastError = 'remote-parse-failed';
            saveSyncState();
            return syncState.lastError;
        }
    }

    // 6. Remote has changes we do not have -> apply remote (pull wins)
    if ( remoteSameAsLocal === false ) {
        await applyRemoteData(remoteData);
        const localNow = await collectLocalData();
        syncState.lastEtag = remote.etag || '';
        syncState.lastLocalFingerprint = fingerprintLocalData(localNow);
        syncState.lastSyncTime = Date.now();
        syncState.lastDirection = 'pull';
        syncState.lastError = '';
        saveSyncState();
        return 'pulled';
    }

    // 7. Only fingerprint bookkeeping was stale
    syncState.lastEtag = remote.etag || '';
    syncState.lastLocalFingerprint = localFp;
    syncState.lastSyncTime = Date.now();
    syncState.lastError = '';
    saveSyncState();
    return 'in-sync';
};

/******************************************************************************/
// Apply remote data locally. Deliberately conservative: writes everything
// through the same storage paths the official "Restore from file" uses,
// then restarts the extension so all engines reload cleanly.

const applyRemoteData = async function(data) {
    const µb = (await import('./background.js')).default;
    const cacheStorage = (await import('./cachestorage.js')).default;
    const io = (await import('./assets.js')).default;
    const { FilteringContext } = await import('./filtering-context.js');

    // Normalize shapes exactly like restoreUserData() does.
    if ( Array.isArray(data.userFilters) === false && typeof data.userFilters === 'string' ) {
        data.userFilters = data.userFilters.split('\n');
    }
    if ( Array.isArray(data.externalLists) ) {
        data.externalLists = data.externalLists.join('\n');
    }

    // Flush caches + wipe local storage, mirroring restoreUserData().
    io.rmrf();
    await Promise.all([
        cacheStorage.clear(),
        vAPI.storage.clear(),
    ]);

    µb.saveLocalSettings();

    // Careful: vAPI.storage.clear() wiped our own config/state. Rewrite them.
    await saveConfig();
    await saveSyncState();

    // Whitelist may be array or string depending on producer version.
    let whitelist = data.whitelist;
    if (
        Array.isArray(whitelist) === false &&
        typeof data.netWhitelist === 'string' &&
        data.netWhitelist !== ''
    ) {
        whitelist = data.netWhitelist.split('\n');
    }

    // Advanced settings (hiddenSettings).
    let hiddenSettings = data.hiddenSettings;
    if ( hiddenSettings instanceof Object === false ) {
        hiddenSettings = µb.hiddenSettingsFromString(data.hiddenSettingsString || '');
    }
    for ( const key in hiddenSettings ) {
        if (
            Object.hasOwn(µb.hiddenSettingsDefault, key) === false ||
            hiddenSettings[key] === µb.hiddenSettingsDefault[key]
        ) {
            delete hiddenSettings[key];
        }
    }

    vAPI.storage.set(Object.assign({}, data.userSettings || {}, {
        hiddenSettings,
        netWhitelist: whitelist || [],
        dynamicFilteringString: data.dynamicFilteringString || '',
        urlFilteringString: data.urlFilteringString || '',
        hostnameSwitchesString: data.hostnameSwitchesString || '',
    }));

    const userFilters = Array.isArray(data.userFilters)
        ? data.userFilters.join('\n')
        : data.userFilters;
    await µb.saveUserFilters(userFilters || '');

    if ( Array.isArray(data.selectedFilterLists) ) {
        await µb.saveSelectedFilterLists(data.selectedFilterLists);
    }

    // Keep the filtering-context import referenced so bundlers/linters do
    // not complain; it also documents the dependency on engine modules
    // being reloadable (vAPI.app.restart performs the actual reload).
    void FilteringContext;
};

/******************************************************************************/
// Scheduling: alarm-driven periodic sync + post-change debounced sync.
// uBO already owns the 'davSyncAlarm' name space is fresh -- prefix avoids
// collisions with 'assetUpdater'/'createSelfie'/etc.

const schedulePeriodicSync = function( ) {
    if ( config.enabled !== true ) {
        vAPI.alarms.clear(SYNC_ALARM_NAME);
        return;
    }
    // Unconditional create: alarms persist across browser restarts in the
    // profile, so createIfNotPresent would keep the stale schedule forever
    // and the "first sync 2 min after launch" promise would never hold.
    // Recreating on every launch resets the initial delay while keeping the
    // same 30-minute period. Same (name, ...args) shape the vAPI wrapper uses.
    vAPI.alarms.create(SYNC_ALARM_NAME, {
        delayInMinutes: SYNC_INITIAL_DELAY_MIN,
        periodInMinutes: SYNC_PERIOD_MIN,
    });
};

// Debounced sync shortly after a local change is detected. The dashboard
// fires broadcast messages on user edits; we listen for the ones that
// indicate user data changed.
const debounceTimer = vAPI.defer.create(( ) => {
    runSyncOnce();
});
const syncSoon = function( ) {
    if ( config.enabled !== true ) { return; }
    debounceTimer.offon({ min: 1 });
};

/******************************************************************************/
// Public API consumed by messaging.js and dav-cloud.js

const isDavConfigured = function( ) {
    return config.enabled === true && config.url !== '';
};

const davReadJson = async function(filePath) {
    const result = await davRequest(config, 'GET', filePath, {
        allowNotFound: true,
    });
    if ( result.ok === false || result.notFound === true ) { return undefined; }
    try {
        return JSON.parse(result.text);
    } catch {
        return undefined;
    }
};

const davWriteJson = async function(filePath, obj) {
    await davMkdirp(config);
    const result = await davRequest(config, 'PUT', filePath, {
        body: JSON.stringify(obj, null, 1),
    });
    return result.ok === true ? '' : result.error;
};

const davDelete = async function(filePath) {
    const result = await davRequest(config, 'DELETE', filePath, {
        allowNotFound: true,
    });
    return result.ok === true ? '' : result.error;
};

const davSync = {
    async getStatus() {
        await Promise.all([ configReady, stateReady ]);
        return {
            enabled: config.enabled,
            url: config.url,
            username: config.username,
            filePath: config.filePath,
            deviceName: config.deviceName,
            lastSyncTime: syncState.lastSyncTime,
            lastError: syncState.lastError,
            lastDirection: syncState.lastDirection,
        };
    },

    async setConfig(details) {
        await configReady;
        for ( const key of [ 'url', 'username', 'password', 'filePath', 'deviceName' ] ) {
            if ( typeof details[key] === 'string' ) {
                config[key] = details[key].trim();
            }
        }
        if ( config.filePath === '' ) {
            config.filePath = DAV_FILE_PATH_DEFAULT;
        }
        if ( typeof details.enabled === 'boolean' ) {
            config.enabled = details.enabled;
        }
        await saveConfig();
        schedulePeriodicSync();
        if ( config.enabled ) {
            // Immediate first sync so the user sees feedback right away.
            setTimeout(( ) => { runSyncOnce(); }, 500);
        }
        return this.getStatus();
    },

    async syncNow() {
        const status = await runSyncOnce();
        // 'pulled' means remote data was applied and the extension is about
        // to restart; respond before restart via callback ordering is fine.
        if ( status === 'pulled' ) {
            vAPI.app.restart();
        }
        return this.getStatus();
    },

    // Called from ublock.js when user settings change (hook below).
    onLocalChange() {
        syncSoon();
    },

    // --- Used by dav-cloud.js (vAPI.cloud router) ---
    getCloudConfig() {
        return isDavConfigured()
            ? { deviceName: config.deviceName || 'device' }
            : null;
    },
    davReadJson,
    davWriteJson,
    davDelete,
};

/******************************************************************************/

// React to alarm ticks (browser-level timers survive page suspends).
vAPI.alarms.onAlarm.addListener(alarm => {
    if ( alarm.name !== SYNC_ALARM_NAME ) { return; }
    runSyncOnce().then(status => {
        if ( status === 'pulled' ) { vAPI.app.restart(); }
    });
});

// React to in-memory broadcasts about user edits (dashboard panes etc.).
{
    onBroadcast(msg => {
        switch ( msg.what ) {
        case 'hiddenSettingsChanged':    // broadcast by ublock.js
        case 'davLocalDataChanged':      // broadcast by messaging.js hooks
            davSync.onLocalChange();
            break;
        }
    });
}

// Kick scheduling once config is loaded.
configReady.then(( ) => { schedulePeriodicSync(); });

// Startup sync, independent of the alarm system. The periodic alarm covers
// long-running sessions, but MV2 background pages can be started at any time
// (browser launch, extension reload) and the alarm path has proven flaky on
// some Chromium forks (Turbo 154: alarm fires but the packaged listener does
// not run). A short timer here guarantees an attempt per launch; the
// ETag/fingerprint bookkeeping makes redundant attempts harmless no-ops.
const startupSync = ( ) => {
    runSyncOnce().then(status => {
        if ( status === 'pulled' ) { vAPI.app.restart(); }
    }).catch(reason => {
    });
};
configReady.then(( ) => {
    if ( config.enabled !== true ) { return; }
    // Native setTimeout on purpose: vAPI.defer proved unreliable across
    // Chromium forks (works in Kiwi 137, misbehaves in Turbo 154 where the
    // scheduled callback silently never fires). No wrapper needed for a
    // one-shot 18-second delay.
    setTimeout(startupSync, 18000);
});

/******************************************************************************/

export default davSync;

/******************************************************************************/
