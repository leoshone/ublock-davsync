#!/usr/bin/env node
/**
 * davsync 扩展打包脚本：CRX3 + ZIP（可拖拽安装 / Kiwi zip 加载）
 *
 * 用法（在本仓库根目录执行）：
 *   node tools/make-packages.js [keyPath]
 *   keyPath 默认 D:/AiSpaces/Work/2026-10-21-21-29-21/_tmp/davsync-key.pem
 *
 * 依赖（一次性）：
 *   npm install --prefix D:/AiSpaces/Work/2026-10-21-21-29-21/_tmp crx3
 *
 * 产物（dist/build/ 下）：
 *   uBlock0.davsync_v<ver>.chromium.crx — 百分等浏览器拖拽/命令行安装（需开发者模式开启）
 *   uBlock0.davsync_v<ver>.chromium.zip — Kiwi 扩展页「+ (from .zip)」加载
 *   crx3tool-zip.zip           — crx3 工具的中间产物（可删）
 *
 * 注意：
 * - manifest.json 必须带 "key" 字段（RSA 公钥 base64），否则扩展 ID 不固定。
 *   当前 ID: odecihgahfphabajblgnmopeibmkhifp
 * - 手写 CRX3 protobuf（openssl dgst -sha256 -sign 签 signed_header_data）格式上
 *   与本工具产物一致，但实测在 Turbo 154 上被拒（CRX_REQUIRED_PROOF_MISSING），
 *   百分 150 则接受。原因未深究——**统一用本脚本（crx3 npm 工具）打包**。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const writeCRX3 = require(process.env.CRX3_LIB ||
    'D:/AiSpaces/Work/2026-10-21-21-29-21/_tmp/node_modules/crx3/lib/writeCRX3File.js');

const ROOT = path.resolve(__dirname, '..');
const BUILD = path.join(ROOT, 'dist', 'build', 'uBlock0.chromium');
const OUTDIR = path.join(ROOT, 'dist', 'build');
const keyPath = process.argv[2] ||
    'D:/AiSpaces/Work/2026-10-21-21-29-21/_tmp/davsync-key.pem';

const mfPath = path.join(BUILD, 'manifest.json');
const mf = JSON.parse(fs.readFileSync(mfPath, 'utf-8'));
if (!mf.key) {
    // 构建脚本不会注入 key，手工补一步很容易忘（忘了就 FATAL 中断）。
    // 直接从签名私钥推导公钥写回 manifest：扩展 ID = 公钥 SHA256 前 128 位
    // 转 a-z，所以同一把 pem 永远得到同一个 ID。
    const { createPublicKey } = require('crypto');
    mf.key = createPublicKey(fs.readFileSync(keyPath, 'utf-8'))
        .export({ type: 'spki', format: 'der' })
        .toString('base64');
    fs.writeFileSync(mfPath, JSON.stringify(mf, null, 2) + '\n');
    console.log('manifest.json 缺少 key，已从', keyPath, '推导并写入');
}

// 递归收集文件（crx3 工具要求文件路径列表，zip 内相对路径 = 相对 BUILD）
const files = [];
(function walk(dir) {
    for (const f of fs.readdirSync(dir)) {
        const full = path.join(dir, f);
        if (fs.statSync(full).isDirectory()) walk(full);
        else files.push(full);
    }
})(BUILD);
console.log('files:', files.length);

const crxPath = path.join(OUTDIR, `uBlock0.davsync_v${mf.version}.chromium.crx`);
const zipPath = path.join(OUTDIR, `uBlock0.davsync_v${mf.version}.chromium.zip`);

writeCRX3(files, {
    keyPath,
    crxPath,
    zipPath,
}).then(() => {
    // zipPath is written directly by writeCRX3 (self-contained zip build);
    // do NOT copy any cached external zip over it.
    for (const f of [crxPath, zipPath]) {
        console.log('OK', f, fs.existsSync(f) ? fs.statSync(f).size + ' bytes' : 'MISSING');
    }
}).catch(e => {
    console.error('FAILED:', e.message);
    process.exit(1);
});
