# ARTIFACTS 产物清单

> 本文件是工作区产物索引。**已同步到 GitHub**：源码与文档在 `master` 分支，构建包/密钥/工具在 `artifacts` 分支。
> 换电脑恢复：`git clone https://github.com/leoshone/ublock-davsync` 后按「重建命令」一节操作即可。

## 仓库布局（github.com/leoshone/ublock-davsync，私有）

| 分支 | 内容 |
|---|---|
| `master` | 完整 fork 源码（基于 gorhill/uBlock 1.75.1.16，上游 commit `1e6f82b`）+ `docs/` 验证文档 |
| `artifacts` | 可复用产物：构建 zip、扩展密钥、侧载脚本、WebDAV 冒烟测试、WorkBuddy skill |

## master 分支关键改动（相对上游 gorhill/uBlock）

| 产物 | 路径 | 说明 |
|---|---|---|
| fork 提交 | `22efe91` | 全部 fork 改动（git log 可查） |
| 核心模块 | `src/js/davsync.js` | WebDAV 客户端 + 自动同步调度 + 数据快照/应用（+577 行） |
| 云路由 | `src/js/dav-cloud.js` | 把 vAPI.cloud 路由到 WebDAV（+145 行） |
| 设置 UI | `src/settings.html` + `src/js/settings.js` | WebDAV 配置区块（URL/账号/密码/设备名/立即同步） |
| 消息通道 | `src/js/messaging.js` + `src/js/start.js` | davSyncGetStatus / davSyncSetConfig / davSyncNow + 变更广播 |
| 验证文档 | `docs/DAVSYNC-HOST-COMPATIBILITY-AND-SIDELOAD.md` | 载体兼容性验证 + Chrome 侧载方法（持续迭代，文末 changelog） |

## artifacts 分支内容

| 产物 | 路径 | 说明 |
|---|---|---|
| 构建包 | `build/uBlock0.davsync-1.75.1.16.zip` | MV2 包，解压后可"加载已解压的扩展程序" |
| 扩展密钥 | `build/ublock-davsync.key` | RSA 私钥（PEM）。**保持不变则扩展 ID 恒定**（`mggocpoejajooeoecednjapaeafnhiie`）。敏感：仓库转公开前须移走 |
| 侧载脚本 | `scripts/ublock-sideload.py` | Chrome 137+（实测 155）未打包扩展自动化加载（UIA + SendInput + WM_SETTEXT） |
| 冒烟测试 | `scripts/dav-smoke-test.sh` | 坚果云/通用 WebDAV 连通性五步测试 |
| WorkBuddy skill | `skill/SKILL.md` | `chrome-unpacked-sideload` 项目级 skill（本工作区 `.workbuddy/skills/` 同源） |

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
```

注意：重新构建后若要保持扩展 ID 不变，需把 `artifacts/build/ublock-davsync.key` 的公钥写进新 manifest 的 `key` 字段（换密钥 = 换 ID = 丢已装扩展的配置）。

## 本地临时目录（未入 GitHub，可随时重建）

`_tmp/davtest/`：测试 profile（win-chrome）、dialog 自动化中间产物、chrome 日志。全部可弃，有价值的内容均已沉淀到上述两分支。
