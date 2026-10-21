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

    vAPI.cloud route-over for WebDAV.

    Replaces the browser-sync backend of vAPI.cloud with the WebDAV server
    configured in davsync.js. Each dashboard pane's datakey becomes a
    separate file on the server: <filePath-dir>/<datakey>.json.

    The default vAPI.cloud (browser storage.sync) is preserved as fallback:
    if DAV sync is not configured/enabled, cloud widget behaves exactly
    like upstream (uses browser sync).

    Home: https://github.com/gorhill/uBlock

*/

'use strict';

import davSync from './davsync.js';

/******************************************************************************/
// One-time wrapper installation. vAPI.cloud is created by
// platform/common/vapi-background.js using browser storage.sync; we wrap
// its push/pull/used with a router that delegates to WebDAV when DAV sync
// is configured and enabled.

const installCloudRouter = (async ( ) => {
    if ( vAPI.cloud instanceof Object === false ) { return; }

    const upstream = vAPI.cloud;

    // Encode/decode are supplied per-call by messaging.js (they handle the
    // s14e serialization + lz4 compression). We just store/retrieve the
    // resulting string, exactly like the chunked browser backend would.

    const davEntryPath = datakey => `ublock-davsync/${datakey}.json`;

    const davConfig = ( ) => davSync.getCloudConfig();

    const davGet = async function(datakey) {
        const cfg = davConfig();
        if ( cfg === null ) { return undefined; }
        const bin = await davSync.davReadJson(davEntryPath(datakey));
        return bin; // { source, tstamp, data } or undefined
    };

    const davPut = async function(datakey, item) {
        const cfg = davConfig();
        if ( cfg === null ) { return 'dav-not-configured'; }
        return davSync.davWriteJson(davEntryPath(datakey), item);
    };

    vAPI.cloud = {
        async push(details) {
            const { datakey, data, encode } = details;
            const cfg = davConfig();
            if ( cfg === null ) {
                return upstream.push(details);
            }
            if ( data === undefined || typeof data === 'string' && data === '' ) {
                return davSync.davDelete(davEntryPath(datakey));
            }
            const item = {
                source: cfg.deviceName || 'unknown device',
                tstamp: Date.now(),
                data,
            };
            const encoded = encode instanceof Function
                ? await encode(item)
                : JSON.stringify(item);
            // Store the encoded string as JSON-safe wrapper
            return davPut(datakey, { encoded });
        },

        async pull(details) {
            const { datakey, decode } = details;
            const cfg = davConfig();
            if ( cfg === null ) {
                return upstream.pull(details);
            }
            const bin = await davGet(datakey);
            if ( bin instanceof Object === false ) { return null; }
            let entry = null;
            try {
                if ( decode instanceof Function ) {
                    entry = await decode(bin.encoded) || null;
                }
                if ( typeof entry === 'string' ) {
                    entry = JSON.parse(entry);
                }
            } catch {
            }
            return entry;
        },

        async used(datakey) {
            const cfg = davConfig();
            if ( cfg === null ) {
                return upstream.used(datakey);
            }
            const bin = await davGet(datakey);
            if ( bin instanceof Object === false ) { return; }
            const size = JSON.stringify(bin).length;
            // DAV has no meaningful quota; report against a nominal 1 MB.
            const total = 1024 * 1024;
            return { used: size, total, max: total };
        },

        getOptions(callback) {
            if ( typeof callback !== 'function' ) { return; }
            upstream.getOptions(options => {
                const cfg = davConfig();
                callback(Object.assign({}, options, {
                    davEnabled: cfg !== null,
                }));
            });
        },

        setOptions(details, callback) {
            upstream.setOptions(details, callback);
        },
    };
})();

/******************************************************************************/

export default installCloudRouter;

/******************************************************************************/
