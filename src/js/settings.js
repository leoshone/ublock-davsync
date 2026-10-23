/*******************************************************************************

    uBlock Origin - a comprehensive, efficient content blocker
    Copyright (C) 2014-present Raymond Hill

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

    Home: https://github.com/gorhill/uBlock
*/

import { dom, qs$, qsa$ } from './dom.js';
import { setAccentColor, setTheme } from './theme.js';
import { i18n$ } from './i18n.js';

/******************************************************************************/

function handleImportFilePicker() {
    const file = this.files[0];
    if ( file === undefined || file.name === '' ) { return; }

    const reportError = ( ) => {
        window.alert(i18n$('aboutRestoreDataError'));
    };

    const expectedFileTypes = [
        'text/plain',
        'application/json',
    ];
    if ( expectedFileTypes.includes(file.type) === false ) {
        return reportError();
    }

    const filename = file.name;
    const fr = new FileReader();

    fr.onload = function() {
        let userData;
        try {
            userData = JSON.parse(this.result);
            if ( typeof userData !== 'object' ) {
                throw 'Invalid';
            }
            if ( typeof userData.userSettings !== 'object' ) {
                throw 'Invalid';
            }
            if (
                Array.isArray(userData.whitelist) === false &&
                typeof userData.netWhitelist !== 'string'
            ) {
                throw 'Invalid';
            }
            if (
                typeof userData.filterLists !== 'object' &&
                Array.isArray(userData.selectedFilterLists) === false
            ) {
                throw 'Invalid';
            }
        }
        catch {
            userData = undefined;
        }
        if ( userData === undefined ) {
            return reportError();
        }
        const time = new Date(userData.timeStamp);
        const msg = i18n$('aboutRestoreDataConfirm')
                        .replace('{{time}}', time.toLocaleString());
        const proceed = window.confirm(msg);
        if ( proceed !== true ) { return; }
        vAPI.messaging.send('dashboard', {
            what: 'restoreUserData',
            userData,
            file: filename,
        });
    };

    fr.readAsText(file);
}

/******************************************************************************/

function startImportFilePicker() {
    const input = qs$('#restoreFilePicker');
    // Reset to empty string, this will ensure an change event is properly
    // triggered if the user pick a file, even if it is the same as the last
    // one picked.
    input.value = '';
    input.click();
}

/******************************************************************************/

async function exportToFile() {
    const response = await vAPI.messaging.send('dashboard', {
        what: 'backupUserData',
    });
    if (
        response instanceof Object === false ||
        response.userData instanceof Object === false
    ) {
        return;
    }
    vAPI.download({
        'url': 'data:text/plain;charset=utf-8,' +
               encodeURIComponent(JSON.stringify(response.userData, null, '  ')),
        'filename': response.localData.lastBackupFile
    });
    onLocalDataReceived(response.localData);
}

/******************************************************************************/

function onLocalDataReceived(details) {
    let v, unit;
    if ( typeof details.storageUsed === 'number' ) {
        v = details.storageUsed;
        if ( v < 1e3 ) {
            unit = 'genericBytes';
        } else if ( v < 1e6 ) {
            v /= 1e3;
            unit = 'KB';
        } else if ( v < 1e9 ) {
            v /= 1e6;
            unit = 'MB';
        } else {
            v /= 1e9;
            unit = 'GB';
        }
    } else {
        v = '?';
        unit = '';
    }
    dom.text(
        '#storageUsed',
        i18n$('storageUsed')
            .replace('{{value}}', v.toLocaleString(undefined, { maximumSignificantDigits: 3 }))
            .replace('{{unit}}', unit && i18n$(unit) || '')
    );

    const timeOptions = {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: 'numeric',
        minute: 'numeric',
        timeZoneName: 'short'
    };

    const lastBackupFile = details.lastBackupFile || '';
    if ( lastBackupFile !== '' ) {
        const dt = new Date(details.lastBackupTime);
        const text = i18n$('settingsLastBackupPrompt');
        const node = qs$('#settingsLastBackupPrompt');
        node.textContent = text + '\xA0' + dt.toLocaleString('fullwide', timeOptions);
        node.style.display = '';
    }

    const lastRestoreFile = details.lastRestoreFile || '';
    if ( lastRestoreFile !== '' ) {
        const dt = new Date(details.lastRestoreTime);
        const text = i18n$('settingsLastRestorePrompt');
        const node = qs$('#settingsLastRestorePrompt');
        node.textContent = text + '\xA0' + dt.toLocaleString('fullwide', timeOptions);
        node.style.display = '';
    }

    if ( details.cloudStorageSupported === false ) {
        dom.attr('[data-setting-name="cloudStorageEnabled"]', 'disabled', '');
    }

    if ( details.privacySettingsSupported === false ) {
        dom.attr('[data-setting-name="prefetchingDisabled"]', 'disabled', '');
        dom.attr('[data-setting-name="hyperlinkAuditingDisabled"]', 'disabled', '');
        dom.attr('[data-setting-name="webrtcIPAddressHidden"]', 'disabled', '');
    }
}

/******************************************************************************/

function resetUserData() {
    const msg = i18n$('aboutResetDataConfirm');
    const proceed = window.confirm(msg);
    if ( proceed !== true ) { return; }
    vAPI.messaging.send('dashboard', {
        what: 'resetUserData',
    });
}

/******************************************************************************/

function synchronizeDOM() {
    dom.cl.toggle(
        dom.body,
        'advancedUser',
        qs$('[data-setting-name="advancedUserEnabled"]').checked === true
    );
}

/******************************************************************************/

function changeUserSettings(name, value) {
    vAPI.messaging.send('dashboard', {
        what: 'userSettings',
        name,
        value,
    });

    // Maybe reflect some changes immediately
    switch ( name ) {
    case 'uiTheme':
        setTheme(value, true);
        break;
    case 'uiAccentCustom':
    case 'uiAccentCustom0':
        setAccentColor(
            qs$('[data-setting-name="uiAccentCustom"]').checked,
            qs$('[data-setting-name="uiAccentCustom0"]').value,
            true
        );
        break;
    default:
        break;
    }
}

/******************************************************************************/

function onValueChanged(ev) {
    const input = ev.target;
    const name = dom.attr(input, 'data-setting-name');
    let value = input.value;
    // Maybe sanitize value
    switch ( name ) {
    case 'largeMediaSize':
        value = Math.min(Math.max(Math.floor(parseInt(value, 10) || 0), 0), 1000000);
        break;
    default:
        break;
    }
    if ( value !== input.value ) {
        input.value = value;
    }

    changeUserSettings(name, value);
}

/******************************************************************************/

// TODO: use data-* to declare simple settings

function onUserSettingsReceived(details) {
    const checkboxes = qsa$('[data-setting-type="bool"]');
    const onchange = ev => {
        const checkbox = ev.target;
        const name = checkbox.dataset.settingName || '';
        changeUserSettings(name, checkbox.checked);
        synchronizeDOM();
    };
    for ( const checkbox of checkboxes ) {
        const name = dom.attr(checkbox, 'data-setting-name') || '';
        if ( details[name] === undefined ) {
            dom.attr(checkbox.closest('.checkbox'), 'disabled', '');
            dom.attr(checkbox, 'disabled', '');
            continue;
        }
        checkbox.checked = details[name] === true;
        dom.on(checkbox, 'change', onchange);
    }

    if ( details.canLeakLocalIPAddresses === true ) {
        qs$('[data-setting-name="webrtcIPAddressHidden"]')
            .closest('div.li')
            .style.display = '';
    }

    qsa$('[data-setting-type="value"]').forEach(function(elem) {
        elem.value = details[dom.attr(elem, 'data-setting-name')];
        dom.on(elem, 'change', onValueChanged);
    });

    dom.on('#export', 'click', ( ) => { exportToFile(); });
    dom.on('#import', 'click', startImportFilePicker);
    dom.on('#reset', 'click', resetUserData);
    dom.on('#restoreFilePicker', 'change', handleImportFilePicker);

    synchronizeDOM();
}

/******************************************************************************/

self.wikilink = 'https://github.com/gorhill/uBlock/wiki/Dashboard:-Settings';

self.hasUnsavedData = function() {
    return false;
};

/******************************************************************************/

vAPI.messaging.send('dashboard', { what: 'userSettings' }).then(result => {
    onUserSettingsReceived(result);
});

vAPI.messaging.send('dashboard', { what: 'getLocalData' }).then(result => {
    onLocalDataReceived(result);
});

// https://github.com/uBlockOrigin/uBlock-issues/issues/591
dom.on(
    '[data-i18n-title="settingsAdvancedUserSettings"]',
    'click',
    self.uBlockDashboard.openOrSelectPage
);

/******************************************************************************/
// WebDAV auto-sync configuration pane (DAV-Sync fork)

const davSyncFields = [
    '#davSyncUrl',
    '#davSyncUsername',
    '#davSyncPassword',
    '#davSyncDeviceName',
    '#davSyncInterval',
];

// 当前已保存的配置快照：用于判断表单是否有未保存的变更。
// password 保存密码框是否处于「已填但未保存」状态：密码不入库不下发，
// 保存后输入框保留用户输入，仅当用户再次修改时才算有变更。
let davSyncSaved = {
    url: '',
    username: '',
    password: '',
    passwordDirty: false,
    deviceName: '',
    syncIntervalMinutes: 30,
};

const davSyncReadForm = function() {
    const interval = parseFloat(qs$('#davSyncInterval').value);
    return {
        url: qs$('#davSyncUrl').value.trim(),
        username: qs$('#davSyncUsername').value.trim(),
        password: qs$('#davSyncPassword').value,
        deviceName: qs$('#davSyncDeviceName').value.trim(),
        syncIntervalMinutes: isNaN(interval) ? 30 : interval,
    };
};

// 配置是否完整（启用同步所需的最低要求）
const davSyncConfigComplete = function(cfg) {
    return cfg.url !== '' && cfg.username !== '';
};

// 表单相对已保存快照是否有变化
const davSyncFormChanged = function(cfg) {
    return cfg.url !== davSyncSaved.url
        || cfg.username !== davSyncSaved.username
        || davSyncSaved.passwordDirty
        || cfg.deviceName !== davSyncSaved.deviceName
        || cfg.syncIntervalMinutes !== davSyncSaved.syncIntervalMinutes;
};

// 依据启用状态与表单状态刷新：字段可用性、保存/同步按钮可用性
const davSyncUpdateUI = function() {
    const enabled = qs$('#davSyncEnabled').checked;
    const cfg = davSyncReadForm();
    for ( const sel of davSyncFields ) {
        qs$(sel).disabled = enabled === false;
    }
    // 保存按钮：有变化才可点（参考「应用更改」按钮的行为）
    qs$('#davSyncSave').disabled = davSyncFormChanged(cfg) === false;
    // 立即同步：配置完整且已保存（无未保存变更）才可点
    qs$('#davSyncNow').disabled =
        davSyncConfigComplete(cfg) === false || davSyncFormChanged(cfg) === true;
};

const davStatusText = status => {
    if ( status.enabled !== true ) { return '未启用'; }
    if ( status.conflict === true ) { return '冲突：自动同步已暂停，请选择「上传」或「下载」'; }
    if ( status.lastError ) {
        return `错误：${status.lastError}`;
    }
    if ( status.lastSyncTime === 0 ) { return '尚未同步'; }
    const t = new Date(status.lastSyncTime).toLocaleString();
    const dir = {
        push: '已上传',
        pull: '已从云端应用',
        none: '无变化',
    }[status.lastDirection] || '';
    return `${dir} · ${t}`;
};

const refreshDavStatus = function(status) {
    qs$('#davSyncEnabled').checked = status.enabled === true;
    qs$('#davSyncUrl').value = status.url || '';
    qs$('#davSyncUsername').value = status.username || '';
    // 密码不回填（服务端不下发），保持输入框为空
    qs$('#davSyncDeviceName').value = status.deviceName || '';
    if ( typeof status.syncIntervalMinutes === 'number' ) {
        qs$('#davSyncInterval').value = status.syncIntervalMinutes;
    }
    // 记录已保存快照（密码不入库不下发：输入框保留用户输入，
    // 仅当用户再次修改时才算有变更）
    davSyncSaved = {
        url: status.url || '',
        username: status.username || '',
        password: '',
        passwordDirty: false,
        deviceName: status.deviceName || '',
        syncIntervalMinutes: typeof status.syncIntervalMinutes === 'number'
            ? status.syncIntervalMinutes : 30,
    };
    // Conflict banner: show row + details, or hide it when resolved.
    const row = qs$('#davSyncConflictRow');
    if ( status.conflict === true ) {
        row.style.display = '';
        const meta = status.conflictRemoteMeta || {};
        const when = meta.timeStamp
            ? new Date(meta.timeStamp).toLocaleString() : '未知时间';
        dom.text('#davSyncConflictMeta',
            `云端版本来自「${meta.deviceName || '未知设备'}」· 更新于 ${when}`);
    } else {
        row.style.display = 'none';
    }
    dom.text('#davSyncStatus', davStatusText(status));
    davSyncUpdateUI();
};

vAPI.messaging.send('dashboard', { what: 'davSyncGetStatus' }).then(status => {
    if ( status instanceof Object ) { refreshDavStatus(status); }
});

for ( const sel of [ '#davSyncEnabled', ...davSyncFields ] ) {
    dom.on(sel, 'input', ( ) => {
        if ( sel === '#davSyncPassword' ) { davSyncSaved.passwordDirty = true; }
        davSyncUpdateUI();
    });
    dom.on(sel, 'change', ( ) => { davSyncUpdateUI(); });
}

dom.on('#davSyncSave', 'click', ( ) => {
    const cfg = davSyncReadForm();
    const status = vAPI.messaging.send('dashboard', {
        what: 'davSyncSetConfig',
        enabled: qs$('#davSyncEnabled').checked,
        url: cfg.url,
        username: cfg.username,
        password: cfg.password,
        deviceName: cfg.deviceName,
        syncIntervalMinutes: cfg.syncIntervalMinutes,
    }).then(result => {
        if ( result instanceof Object ) {
            refreshDavStatus(result);
            // 密码框保留用户输入（服务端不下发密码，清空会让用户误以为没保存）
            davSyncSaved.passwordDirty = false;
            davSyncUpdateUI();
        }
    });
});

dom.on('#davSyncNow', 'click', ( ) => {
    dom.text('#davSyncStatus', '同步中…');
    vAPI.messaging.send('dashboard', { what: 'davSyncNow' }).then(result => {
        if ( result instanceof Object ) { refreshDavStatus(result); }
    });
});

// Conflict resolution: 上传 keeps local, 下载 applies remote (then restarts).
dom.on('#davSyncForceUpload', 'click', ( ) => {
    dom.text('#davSyncStatus', '正在用本地覆盖云端…');
    vAPI.messaging.send('dashboard', {
        what: 'davSyncResolveConflict', direction: 'push',
    }).then(result => {
        if ( result instanceof Object ) { refreshDavStatus(result); }
    });
});

dom.on('#davSyncForceDownload', 'click', ( ) => {
    dom.text('#davSyncStatus', '正在应用云端版本…');
    vAPI.messaging.send('dashboard', {
        what: 'davSyncResolveConflict', direction: 'pull',
    }).then(result => {
        if ( result instanceof Object ) { refreshDavStatus(result); }
    });
});

/******************************************************************************/
