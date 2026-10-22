# XPI/ZIP 打包说明（含固定扩展 ID）

## 为什么需要 key
manifest.json 无 `key` 字段时：
- `--load-extension`/拖拽安装的扩展 ID 由浏览器随机或按路径 hash 生成 → 每台机器/每个 profile 都不同
- davsync 依赖稳定 ID 做存储分区和多端识别

注入 RSA 公钥（`key` 字段）后，扩展 ID = SHA256(DER SPKI) 派生，全平台一致：
**odecihgahfphabajblgnmopeibmkhifp**

## 重新生成 key（仅在泄露时需要）
```bash
openssl genrsa -out davsync-key.pem 2048
openssl rsa -in davsync-key.pem -pubout -outform DER -out davsync-pub.der
python -c "import base64,hashlib; der=open('davsync-pub.der','rb').read(); \
  print(base64.b64encode(der).decode()); \
  print(''.join(chr(ord('a')+int(c,16)) for c in hashlib.sha256(der).hexdigest()[:32]))"
```
把输出的 base64 写入 manifest.json 的 `key` 字段，第二行即新扩展 ID。
私钥 davsync-key.pem **勿入库**（.gitignore 已排除 *.pem）。

## 打包
```bash
python -c "import zipfile,os; root='dist/build/uBlock0.chromium'; out='dist/build/uBlock0.davsync-1.75.1.16.xpi'; \
  z=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED); \
  [z.write(os.path.join(dp,f), os.path.relpath(os.path.join(dp,f), root)) for dp,_,fs in os.walk(root) for f in fs]; z.close()"
```
（把 .xpi 后缀换 .zip 即 zip 包；两者内容相同，仅扩展名不同）
