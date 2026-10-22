# uBlock DAV-Sync 测试产物与可复用工具

> 主仓库：[leoshone/ublock-davsync](https://github.com/leoshone/ublock-davsync)（fork 源码 + 兼容性验证与侧载方法 `docs/DAVSYNC-COMPAT-AND-SIDELOAD-2026-10-22.md`）
> 本目录：真机测试过程中沉淀的**可复用产物**——构建包、密钥、自动化脚本、WorkBuddy skill。

## 目录

| 路径 | 内容 |
|---|---|
| `build/uBlock0.davsync-1.75.1.16.zip` | DAV-Sync fork 构建产物（MV2，可解压后作为未打包扩展加载） |
| `build/ublock-davsync.key` | 扩展 RSA 私钥（PEM）。manifest 中的 `key` 公钥由此派生，**保持此密钥不变则扩展 ID 恒定**（`mggocpoejajooeoecednjapaeafnhiie`）。勿泄露、勿提交到公共仓库 |
| `scripts/ublock-sideload.py` | Chrome 137+（实测 155）未打包扩展侧载自动化：UIA 开开发者模式 → SendInput 点「加载未打包」→ WM_SETTEXT 填路径 → 真实点击确认 |
| `scripts/dav-smoke-test.sh` | 坚果云 WebDAV 连通性冒烟测试（PROPFIND/MKCOL/PUT/GET） |
| `skill/SKILL.md` | WorkBuddy 项目级 skill：`chrome-unpacked-sideload`（完整方法论 + 失败速查表） |

## 快速使用

### 1. 加载扩展（需 MV2 载体浏览器，如百分浏览器）

```
浏览器 → 扩展管理 → 开发者模式 → 加载已解压 → 选择 build 解压后的 uBlock0.chromium 目录
```

或直接运行自动化脚本（Windows + Python 3.13 + comtypes）：

```bash
python scripts/ublock-sideload.py "<chrome窗口句柄或自动查找>" "D:/path/to/uBlock0.chromium"
```

### 2. WebDAV 冒烟测试

```bash
DAV_USER=you@example.com DAV_PASS=应用密码 bash scripts/dav-smoke-test.sh https://dav.jianguoyun.com/dav/ublock-davsync
```

### 3. 重建扩展包

在主仓库执行 `make chromium`（uBO 官方构建链），产物即 `uBlock0.davsync-<版本>.zip`。

## 关键结论速查（详见主仓库兼容性验证文档）

- Chrome 137+ 已移除 `--load-extension`；MV2 扩展在 Chrome 155 弹窗明示「不受支持的清单版本」；
- 侧载唯一通道 = `chrome://extensions` 页内开发者模式 + 原生目录对话框自动化；
- x86_64 模拟器（MuMu/houdini 翻译）跑不了任何带扩展的 Android Chromium（渲染进程被 SIGSYS 全灭）；
- 坚果云 WebDAV 全通；PUT 前必须先 MKCOL 父目录（409 AncestorsNotFound）。
