# 扩展签名私钥

私钥**不在本仓库**。存放在私有仓库 [leoshone/secrets](https://github.com/leoshone/secrets)（需登录你的 GitHub 账号访问）：

    ublock-davsync/davsync-key.pem      # RSA 2048 打包签名私钥

## 换电脑后重打包

    git clone https://github.com/leoshone/secrets
    node <本项目>/tools/make-packages.cjs secrets/ublock-davsync/davsync-key.pem

扩展 ID 由该 key 公钥派生：odecihgahfphabajblgnmopeibmkhifp（manifest key 字段已内嵌公钥）。
换 key = 换 ID = 用户需重装。
