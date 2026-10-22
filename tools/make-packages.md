# davsync 扩展打包说明（CRX3 / ZIP / XPI）

> 最终有效方案（2026-10-22 实测验证）：`node tools/make-packages.cjs` 一键出
> **.crx（拖拽/命令行安装）+ .zip（Kiwi 加载）**。
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
| `uBlock0.davsync-<ver>.crx` | 百分等浏览器拖拽安装 / crx 路径作命令行参数 | ✅ 百分 150 安装成功（持久 ENABLED） |
| `uBlock0.davsync-<ver>.zip` | Kiwi 扩展页「+ (from .zip)」加载 | ✅ Kiwi x86 加载成功 |
| ~~`.xpi`~~ | Firefox 系用；Chromium 系拖拽**不认**，已不产出 | — |

## 各浏览器安装方式速查

| 浏览器 | 方式 | 前提 | 结果 |
|---|---|---|---|
| 百分 150 | crx 拖入扩展页 / crx 路径作命令行参数 | **开发者模式开启**（必须） | 弹确认框 → 持久 ENABLED |
| Turbo 154 | --load-extension + 会话内 `management.setEnabled` | CDP 调试端口 | 会话级（重启丢失） |
| Turbo 154 | crx 拖拽 / 命令行参数 | ❌ | `CRX_REQUIRED_PROOF_MISSING`（策略拒绝，已提 issue tbrowser/Turbo-Browser#724） |
| Kiwi x86 (Android) | zip 按钮加载 | 开发者模式默认开 | ✅ |
| Chrome 155+ | 无解 | MV2 已移除 | — |

注意：**crx 拖拽/命令行安装 = 持久 ENABLED**（普通安装，Preferences 有持久条目）；
**--load-extension = 会话级 DISABLED 起点**，需 setEnabled 且重启丢失。优先用 crx。

## 扩展 ID 与 key

manifest.json 的 `key` 字段（RSA 公钥 base64）决定扩展 ID：
**`odecihgahfphabajblgnmopeibmkhifp`**（全平台一致，多端识别依赖它）。

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

## 踩坑记录（为什么废弃早期方案）

1. **裸 zip/.xpi 拖到 Chromium 扩展页不触发安装**——拖拽只认 CRX3 格式
   （`Cr24` magic + protobuf header + zip payload）。
2. **手写 CRX3 protobuf**（openssl 签名 + 手工构造 field2/field10000）：
   结构与原版 uBO crx 逐字段对齐、openssl 验签 Verified OK，但在 Turbo 154 上
   报 `CRX_REQUIRED_PROOF_MISSING`。换 crx3 npm 工具签名后百分安装走到确认弹窗——
   细节差异未深究，**结论：不要手写，统一用 crx3 工具**。
3. **CRX 安装的前提是开发者模式开启**，否则 `CRX_SIGNATURE_VERIFICATION_FAILED`
   （InstallVerifier 拒绝未上架商店的自签包）。百分的 dev-mode 可用 Preferences 预写
   `extensions.ui.developer_mode=true` 持久开启。
4. Turbo 154 的 crx 命令行/拖拽安装被策略拒绝（要求 Google 商店 proof），
   已提 issue：tbrowser/Turbo-Browser#724。Turbo 端用 --load-extension 方案。
