# ARTIFACTS 产物清单

> 本文件是工作区产物索引。**已同步到 GitHub**：源码与文档在 `master` 分支，构建包/密钥/工具在 `artifacts` 分支，发行包在 [Releases](https://github.com/leoshone/ublock-davsync/releases)（**当前最新 v1.75.4.103**；v1.75.1.16 为历史首版）。
> 换电脑恢复：`git clone https://github.com/leoshone/ublock-davsync` 后按「重建命令」一节操作即可。
> 工作区副本（`D:/AiSpaces/Work/2026-10-21-21-29-21/ARTIFACTS.md`）是历史快照，最新以本文件为准；重大变更同步改两处。

## ⚠️ 版本策略（重要原则）

1. **以后永远 fork 上游正式 release，不跟 beta**（正式版经完整验证且与商店版本对照一致）。
2. **版本号 = `<fork 基线版本>.<100 + DavSync 迭代号>`**：
   - 当前 `1.75.4.103` = 基于上游 1.75.4 正式版（2026-11-03 merge，含元素拾取器 secret-token 安全加固）的第 3 次 DavSync 迭代（102 修首 pull 状态回弹，103 修冲突 badge 被拦截计数覆盖）；
   - 第 4 段 ≥101 即 DavSync 迭代（上游 beta 序号 ≤99，空间隔离不撞车）；
   - 上游出新正式版（如 1.76.0）→ merge 上游新 tag，版本号变 `1.76.0.101` 重新计数；
   - 历史基线：1.75.1.101–1.75.1.122 基于 1.75.1 beta 线（1.75.1b16+3，commit 1e6f82b）——当时 1.75.1 尚未出正式版，属既成事实；122 之后 rebase 到正式版，此后基线均为正式 release；
3. Chromium manifest version 最多 4 段、每段 ≤65535，禁止 5 段；
4. 每次发版：`dist/version` 改新版本号 → `make-chromium-meta.py` → `make-packages.cjs` → `make-firefox.sh` + 重打 xpi → Release（资产名 `uBlock0.davsync_v<版本>.<平台>.*`）→ GitHub Actions 自动更新 docs/update.xml。Chromium 包 manifest 的 `update_url` 指向该 feed，**Turbo / Cent 已装的 crx 会自动升级**（2026-11-07 实测可用）。

## 仓库布局（github.com/leoshone/ublock-davsync，私有）

| 分支/页 | 内容 |
|---|---|
| `master` | 完整 fork 源码（已 rebase 到上游 1.75.4 正式版，当前 1.75.4.103）+ `docs/` 验证文档 + `tools/` 打包脚本 |
| `artifacts` | 可复用产物：crx/zip/xpi 构建包、扩展密钥、侧载脚本、WebDAV 冒烟测试 |
| `Releases` | 最新 v1.75.4.103（crx / zip / firefox.xpi 三件套 + 自动更新 feed），日常下载用这个；历史首版 v1.75.1.16 仅存档 |

## master 分支关键文件

| 路径 | 说明 |
|---|---|
| `src/js/davsync.js` | WebDAV 客户端 + lock/size 校验 + 启动同步/定时调度 + 快照/应用 |
| `src/js/tab.js` | 冲突期间强制红「!」badge 覆盖 uBO 拦截计数、冲突翻转时重算全 tab badge（v1.75.4.103） |
| `src/js/dav-cloud.js` | 把 vAPI.cloud 路由到 WebDAV |
| `src/settings.html` + `src/js/settings.js` | 设置页 DAV-Sync 配置区块（URL/账号/密码/设备名/立即同步） |
| `src/js/messaging.js` + `src/js/start.js` | davSyncGetStatus / davSyncSetConfig / davSyncNow + 变更广播 |
| `tools/make-packages.cjs` | 一键打包 .crx + .zip（crx3 npm 工具签名） |
| `tools/make-packages.md` | 打包说明、各浏览器安装速查、踩坑记录 |
| `docs/DAVSYNC-TESTING.md` | 全平台载体验证 + 安装/侧载方法 + E2E 记录 + 各版本修复记录（1-19 节；§19 为现行 crx 安装结论） |
| `scripts/dav-e2e.py` | CDP E2E 同步测试骨架（连 bg → 注配置 → 触发 → 轮询 state → 判定） |
| **通用 skill** | **扩展安装/E2E 测试方法已沉淀到私有库 [leoshone/Skills](https://github.com/leoshone/Skills) → `browser-extension-e2e`**（Cent/Turbo INTERNAL profile + CDP 驱动 + 陷阱速查 + 可复用 cdp_driver.py，2026-11-04）。本仓库旧目录 `.agents/skills/chrome-unpacked-sideload/` 为其前身，2026-11-07 已删除，内容并入上述通用 skill |

## artifacts 分支内容（`build/`）

| 产物 | 说明 |
|---|---|
| `uBlock0.davsync_v1.75.1.16.chromium.crx` | ⚠️ 历史首版产物，仅存档；**现行安装一律用 Releases 最新版 crx**（Turbo / Cent 点击 crx 链接或拖入 crx 文件，需开发者模式，支持自动更新） |
| `uBlock0.davsync_v1.75.1.16.chromium.zip` | Kiwi zip 按钮加载 / 手工解压 --load-extension |
| `uBlock0.davsync_v1.75.1.16.firefox.xpi` | Firefox/gecko 构建。web-ext 临时加载（会话级） |
| `v1.75.4.103`（Releases） | 当前发行：crx 6.06MB / zip 6.06MB / firefox.xpi 6.10MB；crx 为推荐安装方式 |
| `secrets/README.md` | 签名私钥存放在**私有仓库 [leoshone/secrets](https://github.com/leoshone/secrets)**（`ublock-davsync/davsync-key.pem`），公开库只放指向说明。**key 不变则扩展 ID 恒定 = `odecihgahfphabajblgnmopeibmkhifp`** |

> ⚠️ 2026-10-22 换过一次 key：旧 ID `mggocpoe...` 已废弃，现 ID `odecihgahfphabajblgnmopeibmkhifp`。
> manifest.json 已内嵌公钥（`key` 字段），重打包用 `node tools/make-packages.cjs` 即可。

## scripts/

| 脚本 | 说明 |
|---|---|
| `dav-smoke-test.sh` | 坚果云/通用 WebDAV 连通性五步测试 |
| `ublock-sideload.py` | Chrome 137+ 未打包扩展自动化加载（UIA + SendInput + WM_SETTEXT） |
| `dav-e2e.py`（master `scripts/` 与 artifacts `scripts/` 各一份） | CDP E2E 同步测试骨架：注入配置 → 触发 → 轮询 state → 判定 PASS/FAIL |

## test/ 测试脚手架（v1.75.1.122 起长期复用；2026-11-07 从 _tmp/ 迁入 test/）

脚本入库于 `test/`；**运行产物**（profile `p-*`、云端根 `davroot`、日志）仍在 `_tmp/`，随时可删。

| 文件 | 说明 |
|---|---|
| `test/webdav.py` | 本地 WebDAV 测试服务（8088，davtest/davtest123，纯标准库；If-Match 412 / 无鉴权 /log 回传口） |
| `test/webdav-test.py` | 服务自测（14 项动词/状态码断言） |
| `test/scaffold.py` | 测试脚手架：Cent INTERNAL 模板 profile + payload 覆盖 + createTarget 显式开设置页 + 断言工具；`python test/scaffold.py` 跑三关自检 |
| `test/acceptance.py` | 计划 §3 验收表 Chromium 用例 1-7（21 断言），`python test/acceptance.py all`；v1.75.4.103 发版前重跑全绿，确认 badge 修复无回归 |
| `test/firstpull-status.py` | 针对性回归（8 断言）：新设备首 pull 后「立即同步」状态不被覆盖（v1.75.4.102 修复的复现场景） |
| `test/case8-firefox.py` | 用例 8：Firefox 日志钩子构建 + web-ext 三会话（push/pull/none）自动判定 |
| `test/epicker-smoke.py` | 元素拾取器密码握手冒烟（rebase 上游后跑） |

### 换机重建（2026-11-04 起）

脚本入库后，测试环境重建只需四步：
1. 装 Cent（`D:\Software\Cent`）或 Turbo——仅浏览器本体；
2. **重建 INTERNAL 模板 profile**（一次性）：Cent 带 `--user-data-dir=<模板目录>` 启动 → 开发者模式 → 拖入 Release 的 .crx → 关闭。然后把模板路径写入环境变量 `DAVSYNC_PROFILE_TEMPLATE`（浏览器路径可同样用 `DAVSYNC_CENT_EXE` 覆盖默认值）；
3. key pem 从 leoshone/secrets 私有库取（`ublock-davsync/davsync-key.pem`）；
4. `python test/scaffold.py selfcheck` 三关全绿即环境就绪。

通用方法论（载体选择、CDP 驱动、陷阱）见私有库 [leoshone/Skills](https://github.com/leoshone/Skills) → `browser-extension-e2e`。

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
