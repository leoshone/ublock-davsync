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
    enabled: false,
    url: '',
    username: '',
    password: '',
    passwordDirty: false,
    deviceName: '',
    syncIntervalMinutes: 30,
};

// 已保存密码时输入框里放的占位掩码：真实密码不下发到页面，但空着会让人
// 以为没保存。输入框本身是 type=password，所以这里放什么都会被渲染成圆点，
// 内容不会被提交（只有 passwordDirty 为真时才发送该字段）。
const DAV_PWD_MASK = '••••••••';

let davSyncHasPassword = false;   // 后台是否已存密码（明文不下发）
let davSyncPwdMasked = false;     // 输入框当前显示的只是掩码，不是用户输入

const davSyncReadForm = function() {
    const interval = parseFloat(qs$('#davSyncInterval').value);
    return {
        enabled: qs$('#davSyncEnabled').checked,
        url: qs$('#davSyncUrl').value.trim(),
        username: qs$('#davSyncUsername').value.trim(),
        password: qs$('#davSyncPassword').value,
        deviceName: qs$('#davSyncDeviceName').value.trim(),
        syncIntervalMinutes: isNaN(interval) ? 30 : interval,
    };
};

// 配置是否完整（启用同步所需的最低要求）
// 必填项按页面从上到下的顺序检查，只返回第一个缺失的字段名（空串表示都齐了）。
// 设备名称也在其中：云端靠它区分数据来源，空名字会让其他设备看到「未知设备」。
// 密码：页面上不回填明文，只要后台已存过（davSyncHasPassword）就算有。
const DAV_REQUIRED_FIELDS = [
    { label: '服务器 URL', selector: '#davSyncUrl',
      missing: cfg => cfg.url === '' },
    { label: '用户名', selector: '#davSyncUsername',
      missing: cfg => cfg.username === '' },
    { label: '应用密码', selector: '#davSyncPassword',
      missing: cfg => cfg.password === '' && davSyncHasPassword !== true },
    { label: '设备名称', selector: '#davSyncDeviceName',
      missing: cfg => cfg.deviceName === '' },
];

const davSyncMissingField = function(cfg) {
    for ( const field of DAV_REQUIRED_FIELDS ) {
        if ( field.missing(cfg) ) { return field; }
    }
    return null;
};

const davSyncConfigComplete = function(cfg) {
    return davSyncMissingField(cfg) === null;
};

// 表单相对已保存快照是否有变化
// 注意包含 enabled：只勾选/取消「启用」也必须让「保存」可用，
// 否则这个开关根本存不下去（曾经就是这样）。
const davSyncFormChanged = function(cfg) {
    return cfg.enabled !== davSyncSaved.enabled
        || cfg.url !== davSyncSaved.url
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

// 状态文案统一入口：为空时整行隐藏，避免「保存 / 立即同步」下方
// 多出一条空白；文案长时在独立一行换行，不会再把按钮撑高。
const davSyncSetStatus = function(text) {
    const value = text || '';
    dom.text('#davSyncStatus', value);
    const row = qs$('#davSyncStatusRow');
    if ( row !== null ) {
        row.style.display = value === '' ? 'none' : '';
    }
};

const davStatusText = status => {
    if ( status.enabled !== true ) { return '未启用'; }
    // 冲突时上方红色横幅已经把情况说清楚了，状态行不再重复一遍。
    if ( status.conflict === true ) { return ''; }
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
    // 已保存过密码时显示掩码，避免「看起来没填」
    const pwdEl = qs$('#davSyncPassword');
    const hasPassword = status.hasPassword === true;
    davSyncHasPassword = hasPassword;
    if ( hasPassword === true && pwdEl.value === '' ) {
        pwdEl.value = DAV_PWD_MASK;
        davSyncPwdMasked = true;
    }

    davSyncSaved = {
        enabled: status.enabled === true,
        url: status.url || '',
        username: status.username || '',
        password: '',
        passwordDirty: false,
        deviceName: status.deviceName || '',
        syncIntervalMinutes: typeof status.syncIntervalMinutes === 'number'
            ? status.syncIntervalMinutes : 30,
    };
    davSyncApplyBanner(status);
    davSyncSetStatus(davStatusText(status));
    davSyncUpdateUI();
};

// 冲突横幅：只关心 conflict / conflictRemoteMeta，供「整表刷新」与
// 「状态行轮询」共用（轮询不能重填表单，否则会打断用户正在输入的内容）。
const davSyncApplyBanner = function(status) {
    const row = qs$('#davSyncConflictRow');
    if ( status.conflict === true ) {
        // 显式 block：.li 的默认 display 是 flex，靠 '' 回退会把内部各块排成一行。
        row.style.display = 'block';
        const meta = status.conflictRemoteMeta || {};
        const when = meta.timeStamp
            ? new Date(meta.timeStamp).toLocaleString() : '未知时间';
        dom.text('#davSyncConflictMeta',
            `云端版本来自「${meta.deviceName || '未知设备'}」· 更新于 ${when}`);
    } else {
        row.style.display = 'none';
    }
};

// 动作执行：先显示「进行中」，收到回复再落状态。
// 拉取成功会让扩展在 600ms 后重新加载，届时本页的消息端口失效——
// 所以这里要么正常收尾，要么把页面刷新掉，绝不停在「同步中…」。
const davSyncRunAction = function(payload, pendingText) {
    davSyncSetStatus(pendingText);
    let settled = false;
    const timeoutMs = 30000;
    const bail = function(text) {
        if ( settled ) { return; }
        settled = true;
        davSyncSetStatus(text);
        setTimeout(( ) => { location.reload(); }, 1200);
    };
    const guard = setTimeout(
        ( ) => { bail('同步仍在后台进行，正在刷新页面确认结果…'); },
        timeoutMs
    );
    vAPI.messaging.send('dashboard', payload).then(result => {
        clearTimeout(guard);
        if ( settled ) { return; }
        settled = true;
        if ( result instanceof Object === false ) { return; }
        refreshDavStatus(result);
        if ( result.pendingRestart === true ) {
            // 云端数据已应用，扩展马上重新加载；刷新一次让本页重新连上新实例。
            davSyncSetStatus('已从云端应用，扩展正在重新加载…');
            setTimeout(( ) => { location.reload(); }, 1600);
        }
    }).catch(( ) => {
        clearTimeout(guard);
        bail('扩展已重新加载，正在刷新页面…');
    });
};

vAPI.messaging.send('dashboard', { what: 'davSyncGetStatus' }).then(status => {
    if ( status instanceof Object ) { refreshDavStatus(status); }
});

for ( const sel of [ '#davSyncEnabled', ...davSyncFields ] ) {
    dom.on(sel, 'input', ( ) => {
        if ( sel === '#davSyncPassword' ) {
            davSyncSaved.passwordDirty = true;
            davSyncPwdMasked = false;
        }
        davSyncUpdateUI();
    });
    dom.on(sel, 'change', ( ) => { davSyncUpdateUI(); });
}

// 掩码只是「已保存」的视觉提示：聚焦时清空，让用户直接输入新密码；
// 失焦且什么都没输入时再放回掩码。
dom.on('#davSyncPassword', 'focus', ( ) => {
    if ( davSyncPwdMasked !== true ) { return; }
    qs$('#davSyncPassword').value = '';
    davSyncPwdMasked = false;
});
dom.on('#davSyncPassword', 'blur', ( ) => {
    const el = qs$('#davSyncPassword');
    if ( el.value !== '' ) { return; }
    if ( davSyncSaved.passwordDirty === true ) { return; }
    if ( davSyncHasPassword !== true ) { return; }
    el.value = DAV_PWD_MASK;
    davSyncPwdMasked = true;
});

dom.on('#davSyncSave', 'click', ( ) => {
    const cfg = davSyncReadForm();
    if ( cfg.enabled ) {
        const missing = davSyncMissingField(cfg);
        if ( missing !== null ) {
            davSyncSetStatus(`请先填写${missing.label}`);
            qs$(missing.selector).focus();
            return;
        }
    }
    const payload = {
        what: 'davSyncSetConfig',
        enabled: qs$('#davSyncEnabled').checked,
        url: cfg.url,
        username: cfg.username,
        deviceName: cfg.deviceName,
        syncIntervalMinutes: cfg.syncIntervalMinutes,
    };
    // 只在用户这次确实改过密码时才发送：设置页不回填密码，若无条件发送空串，
    // 改个设备名就会把已保存的密码清掉。
    if ( davSyncSaved.passwordDirty ) {
        payload.password = cfg.password;
    }
    vAPI.messaging.send('dashboard', payload).then(result => {
        if ( result instanceof Object ) {
            refreshDavStatus(result);
            // 密码框保留用户输入（服务端不下发密码，清空会让用户误以为没保存）
            davSyncSaved.passwordDirty = false;
            davSyncUpdateUI();
        }
    }).catch(( ) => {
        // 保存后可能立刻触发一次拉取，扩展重启会把回复掐断；刷新一次即可。
        if ( davSyncRecover() ) { location.reload(); }
    });
});

dom.on('#davSyncNow', 'click', ( ) => {
    davSyncRunAction({ what: 'davSyncNow' }, '同步中…');
});

// Conflict resolution: 上传 keeps local, 下载 applies remote (then restarts).
dom.on('#davSyncForceUpload', 'click', ( ) => {
    davSyncRunAction(
        { what: 'davSyncResolveConflict', direction: 'push' },
        '正在用本地覆盖云端…'
    );
});

dom.on('#davSyncForceDownload', 'click', ( ) => {
    davSyncRunAction(
        { what: 'davSyncResolveConflict', direction: 'pull' },
        '正在应用云端版本…'
    );
});

// 扩展重新加载后，本页的消息端口会失效，而且不是所有内核都会自动重载
// chrome-extension:// 页面（实测 Kiwi 不会，页面 DOM 直接冻在旧状态）。
// 这里做一次带节流的自愈刷新：一分钟内最多 3 次，避免扩展真的坏掉时死循环。
const davSyncRecover = function() {
    try {
        const now = Date.now();
        const hist = JSON.parse(sessionStorage.getItem('__davReloads') || '[]')
            .filter(t => typeof t === 'number' && now - t < 60000);
        if ( hist.length >= 3 ) { return false; }
        hist.push(now);
        sessionStorage.setItem('__davReloads', JSON.stringify(hist));
        return true;
    } catch {
        return true;
    }
};

// 状态行自动刷新：后台定时同步、启动同步、其他标签页的操作都会改变状态，
// 而设置页不会重载。这里只刷新状态文字与冲突横幅，绝不重填表单——
// 否则会打断用户正在输入的内容。
const davSyncPollStatus = function() {
    if ( document.hidden ) { return; }
    if ( davSyncFormChanged(davSyncReadForm()) ) { return; }
    const active = document.activeElement;
    if ( active instanceof HTMLElement && active.closest('#davSync') !== null ) { return; }
    vAPI.messaging.send('dashboard', { what: 'davSyncGetStatus' }).then(status => {
        if ( status instanceof Object === false ) { return; }
        if ( davSyncFormChanged(davSyncReadForm()) ) { return; }
        davSyncApplyBanner(status);
        davSyncSetStatus(davStatusText(status));
        davSyncUpdateUI();
    }).catch(( ) => {
        // 端口已死 = 扩展重启过：刷新一次拿到新实例的状态。
        if ( davSyncRecover() ) { location.reload(); }
    });
};
setInterval(davSyncPollStatus, 10000);

/******************************************************************************/
