# ARTIFACTS 产物清单

> 本文件是工作区产物索引。**已同步到 GitHub**：源码与文档在 `master` 分支，构建包/密钥/工具在 `artifacts` 分支，发行包在 [Releases](https://github.com/leoshone/ublock-davsync/releases/tag/v1.75.1.16)。
> 换电脑恢复：`git clone https://github.com/leoshone/ublock-davsync` 后按「重建命令」一节操作即可。
> 工作区副本与仓库副本（`ublock-davsync/ARTIFACTS.md`）内容一致，更新时同步改两处。

## 仓库布局（github.com/leoshone/ublock-davsync，私有）

| 分支/页 | 内容 |
|---|---|
| `master` | 完整 fork 源码（基于 gorhill/uBlock 1.75.1.16）+ `docs/` 验证文档 + `tools/` 打包脚本 |
| `artifacts` | 可复用产物：crx/zip/xpi 构建包、扩展密钥、侧载脚本、WebDAV 冒烟测试 |
| `Releases` | v1.75.1.16 正式发行（crx / zip / firefox.xpi 三件套 + 说明），日常下载用这个 |

## master 分支关键文件

| 路径 | 说明 |
|---|---|
| `src/js/davsync.js` | WebDAV 客户端 + lock/size 校验 + 启动同步/定时调度 + 快照/应用 |
| `src/js/dav-cloud.js` | 把 vAPI.cloud 路由到 WebDAV |
| `src/settings.html` + `src/js/settings.js` | 设置页 DAV-Sync 配置区块（URL/账号/密码/设备名/立即同步） |
| `src/js/messaging.js` + `src/js/start.js` | davSyncGetStatus / davSyncSetConfig / davSyncNow + 变更广播 |
| `tools/make-packages.cjs` | 一键打包 .crx + .zip（crx3 npm 工具签名） |
| `tools/make-packages.md` | 打包说明、各浏览器安装速查、踩坑记录 |
| `docs/DAVSYNC-TESTING.md` | 全平台载体验证 + 侧载方法 + E2E 记录（1-12 节） |
| `scripts/dav-e2e.py` | CDP E2E 同步测试骨架（连 bg → 注配置 → 触发 → 轮询 state → 判定） |

## artifacts 分支内容（`build/`）

| 产物 | 说明 |
|---|---|
| `uBlock0.davsync-1.75.1.16.crx` | CRX3（crx3 工具签名）。百分等拖拽/命令行安装（需开发者模式开） |
| `uBlock0.davsync-1.75.1.16.zip` | Kiwi zip 按钮加载 / 手工解压 --load-extension |
| `uBlock0.davsync-1.75.1.16.firefox.xpi` | Firefox/gecko 构建。web-ext 临时加载（会话级） |
| `secrets/davsync-key.pem.enc` | RSA 私钥的 **AES-256 加密密文**（密文可公开；口令自存密码管理器）。解密/重加密方法见 artifacts 分支 `secrets/README.md`。**保持 key 不变则扩展 ID 恒定 = `odecihgahfphabajblgnmopeibmkhifp`** |

> ⚠️ 2026-10-22 换过一次 key：旧 ID `mggocpoe...` 已废弃，现 ID `odecihgahfphabajblgnmopeibmkhifp`。
> manifest.json 已内嵌公钥（`key` 字段），重打包用 `node tools/make-packages.cjs` 即可。

## scripts/

| 脚本 | 说明 |
|---|---|
| `dav-smoke-test.sh` | 坚果云/通用 WebDAV 连通性五步测试 |
| `ublock-sideload.py` | Chrome 137+ 未打包扩展自动化加载（UIA + SendInput + WM_SETTEXT） |
| `dav-e2e.py`（master `scripts/` 与 artifacts `scripts/` 各一份） | CDP E2E 同步测试骨架：注入配置 → 触发 → 轮询 state → 判定 PASS/FAIL |

## 重建命令（换电脑后从源码重构建）

```bash
git clone https://github.com/leoshone/ublock-davsync
cd ublock-davsync
bash tools/pull-assets.sh          # 拉取 uAssets（仅需一次）
mkdir -p dist/build/uBlock0.chromium
bash tools/copy-common-files.sh dist/build/uBlock0.chromium
cp platform/chromium/*.js  dist/build/uBlock0.chromium/js/
cp platform/chromium/*.html dist/build/uBlock0.chromium/
cp platform/chromium/*.json dist/build/uBlock0.chromium/
cp -R dist/build/uBlock0.chromium/_locales/nb dist/build/uBlock0.chromium/_locales/no
python3 tools/make-chromium-meta.py dist/build/uBlock0.chromium

# 打包（需 manifest 带 key 字段；私钥见 artifacts/build/ublock-davsync.key）
npm install --prefix ../_tmp crx3
node tools/make-packages.cjs
```

## 本地临时目录（未入 GitHub，可随时重建）

`_tmp/davtest/`：各浏览器测试 profile（win/turbo/cent-chrome）、crx3 npm 工具链、对话框自动化中间产物。全部可弃，有价值的内容均已沉淀到分支与文档。
