# 扩展签名私钥（加密存储）

davsync-key.pem.enc = 扩展打包签名私钥（RSA 2048）经 openssl AES-256-CBC 加密后的密文。
公开无害，没有口令解不开。口令请自行保存在密码管理器（勿入库）。

## 解密（换电脑后）

    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000       -in secrets/davsync-key.pem.enc -out davsync-key.pem -pass pass:<你的口令>

解出的 davsync-key.pem 交给 node tools/make-packages.cjs <pem路径> 即可重打包。

## 重新加密（换口令/换 key 时）

    openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt       -in davsync-key.pem -out secrets/davsync-key.pem.enc -pass pass:<新口令>

扩展 ID 由该 key 公钥派生：odecihgahfphabajblgnmopeibmkhifp（manifest key 字段已内嵌公钥）。换 key = 换 ID = 用户需重装。
