# davsync 扩展打包说明（CRX3 / ZIP / XPI）

> 最终有效方案（2026-10-22 实测，2026-11-07 补订）：`node tools/make-packages.cjs` 一键出
> **.crx（点击 crx 链接安装）+ .zip（Kiwi 加载）**，Firefox 的 `.xpi` 另由
> `tools/make-firefox.sh` 构建后重打。
> **Turbo 与 Cent 都支持 crx 直接安装并自动更新**（2026-11-07 用户实测，见
> `docs/DAVSYNC-TESTING.md` §19.1）；本文件早期「Turbo 不能装 crx」的结论只适用于
> 「crx 作命令行参数」这一条路径。
> 早期手写 CRX3 protobuf 的方案已被废弃（原因见文末「踩坑记录」）。

## 一键打包

```bash
# 依赖（一次性）：crx3 npm 工具
npm install --prefix D:/AiSpaces/Work/2026-10-21-21-29-21/_tmp crx3

# 打包（在本仓库根目录）
node tools/make-packages.cjs [keyPath]
# keyPath 默认 D:/AiSpaces/Work/2026-10-21-21-29-21/_tmp/davsync-key.pem
```

产物（`dist/build/` 下，version 取自 manifest.json）：

| 文件 | 用途 | 实测 |
|---|---|---|
| `uBlock0.davsync_v<ver>.chromium.crx` | Turbo / Cent 点击 crx 链接安装 | ✅ 两者均安装成功（持久 ENABLED + 自动更新） |
| `uBlock0.davsync_v<ver>.chromium.zip` | Kiwi 扩展页「+ (from .zip)」加载 / 解包侧载 | ✅ Kiwi x86 加载成功 |
| `uBlock0.davsync_v<ver>.firefox.xpi` | Firefox 临时加载（web-ext） | ✅ 第 17 节三会话脚本化通过 |

> 三资产都由发版流程产出并上传 Release（xpi 走 `make-firefox.sh` 后重打）。
> Chromium 扩展页**不认裸 zip/xpi**，只有 CRX3 能触发安装。

## 各浏览器安装方式速查

| 浏览器 | 方式 | 前提 | 结果 |
|---|---|---|---|
| Cent（百分）150 | 点击 crx 链接 | **开发者模式开启**（必须） | 弹确认框 → 持久 ENABLED + 自动更新 |
| Turbo 154 | 点击 crx 链接（2026-11-07 实测） | **开发者模式开启** | ✅ 同上，持久 ENABLED + 自动更新 |
| Turbo 154 | crx 路径作命令行参数 | — | ❌ `CRX_REQUIRED_PROOF_MISSING`（被当更新请求，历史路径，见 TESTING §11.4） |
| Turbo / Cent | `--load-extension` + 会话内 `management.setEnabled` | CDP 调试端口 | 仅自动化测试用，会话级（重启丢失） |
| Kiwi x86 (Android) | zip 按钮加载 | 开发者模式默认开 | ✅ |
| Chrome 155+ | 无解 | MV2 已移除 | — |

注意：**点击 crx 链接 = 正规 INTERNAL 安装**，重启持久 ENABLED，且由
`docs/update.xml` 自动更新（见下节）；**`--load-extension` = 会话级 DISABLED 起点**，
需 setEnabled 且重启丢失。分发与日常安装一律用 crx，不要再走命令行传 crx 的路径。

## 扩展 ID 与 key

manifest.json 的 `key` 字段（RSA 公钥 base64）决定扩展 ID：
**`odecihgahfphabajblgnmopeibmkhifp`**（全平台一致，多端识别依赖它）。

扩展显示名（2026-10-22 起）：**uBlock Origin DavSync**（short_name 同为完整名，
不再使用上游的 "development build" 后缀）。

⚠️ 版本号策略：永远 fork 上游**正式 release**（不跟 beta）；版本号 = `<上游版本>.<100+迭代号>`，
如 `1.75.0.101`。详见 ARTIFACTS.md「版本策略」。

重新生成 key（仅在泄露时需要）：

```bash
openssl genrsa -out davsync-key.pem 2048
openssl rsa -in davsync-key.pem -pubout -outform DER -out davsync-pub.der
python -c "import base64,hashlib; der=open('davsync-pub.der','rb').read(); \
  print(base64.b64encode(der).decode()); \
  print(''.join(chr(ord('a')+int(c,16)) for c in hashlib.sha256(der).hexdigest()[:32]))"
```

把输出的 base64 写入 manifest.json 的 `key` 字段，第二行即新扩展 ID，
然后 `node tools/make-packages.cjs` 重新打包。
私钥 davsync-key.pem **勿入库**（.gitignore 已排除 *.pem）。

## 自动更新通道（2026-11-07 确认可用）

- `platform/chromium/manifest.json` 的 `update_url` 指向
  `https://raw.githubusercontent.com/leoshone/ublock-davsync/master/docs/update.xml`；
- Release 发布后 `.github/workflows/davsync-update-feed.yml` 自动把 feed 的
  `codebase` / `version` 改成最新版（历史手工改写已废弃）；
- feed 里的 `appid` **必须全小写** `odecihgahfphabajblgnmopeibmkhifp`，否则 Chromium
  静默不匹配、更新不生效；
- Turbo / Cent 已安装的 crx 会自动升级，无需重新安装或手工改 manifest。

## 踩坑记录（为什么废弃早期方案）

1. **裸 zip/.xpi 拖到 Chromium 扩展页不触发安装**——拖拽只认 CRX3 格式
   （`Cr24` magic + protobuf header + zip payload）。
2. **手写 CRX3 protobuf**（openssl 签名 + 手工构造 field2/field10000）：
   结构与原版 uBO crx 逐字段对齐、openssl 验签 Verified OK，但在 Turbo 154 的
   **命令行参数路径**上报 `CRX_REQUIRED_PROOF_MISSING`。换 crx3 npm 工具签名后
   百分安装走到确认弹窗——细节差异未深究，**结论：不要手写，统一用 crx3 工具**。
   crx3 签出的包在 Turbo 上点击 crx 链接安装同样可用（2026-11-07 实测）。
3. **CRX 安装的前提是开发者模式开启**，否则 `CRX_SIGNATURE_VERIFICATION_FAILED`
   （InstallVerifier 拒绝未上架商店的自签包）。Cent 的 dev-mode 可用 Preferences 预写
   `extensions.ui.developer_mode=true` 持久开启；Turbo 从扩展页手动打开即可。
4. Turbo 154 的 **crx 命令行参数**安装被策略拒绝（要求 Google 商店 proof），
   已提 issue：tbrowser/Turbo-Browser#724。但这是「把 crx 当启动参数」这条路径的
   限制，**点击 crx 链接安装没有问题**（2026-11-07 用户实测，见 TESTING §19.1）。
   Turbo 端现在同样用 Release 的 crx 安装 + 自动更新，不必再走 --load-extension。
