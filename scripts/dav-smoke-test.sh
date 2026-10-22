#!/usr/bin/env bash
# 坚果云/通用 WebDAV 冒烟测试
# 用法: DAV_USER=you@example.com DAV_PASS=应用密码 bash dav-smoke-test.sh https://dav.jianguoyun.com/dav/ublock-davsync
# 退出码: 0=全部通过, 1=失败（会打印具体步骤）
set -euo pipefail

BASE="${1:?usage: dav-smoke-test.sh <webdav-dir-url>}"
USER="${DAV_USER:?need DAV_USER}"
PASS="${DAV_PASS:?need DAV_PASS}"
CURL="curl -s -u $USER:$PASS --max-time 15"

fail() { echo "FAIL: $1"; exit 1; }

# 1. 认证 + 服务可达（PROPFIND 根）
code=$($CURL -X PROPFIND "${BASE%/}/" -H "Depth: 0" -o /dev/null -w '%{http_code}')
[ "$code" = "207" ] || fail "PROPFIND -> $code (期望 207; 401=凭据错误, 404=路径不存在)"
echo "PROPFIND 207 OK"

# 2. 建目录（已存在返回 405 也算通过）
code=$($CURL -X MKCOL "$BASE" -o /dev/null -w '%{http_code}')
case "$code" in 201|405) echo "MKCOL $code OK";; *) fail "MKCOL -> $code";; esac

# 3. 写入（坚果云特性: 父目录必须已存在, 否则 409）
ts=$(date +%s)
code=$($CURL -X PUT "$BASE/davsync-smoke-$ts.txt" -d "smoke-$ts" -o /dev/null -w '%{http_code}')
[ "$code" = "201" ] || fail "PUT -> $code (409=父目录未建)"
echo "PUT 201 OK"

# 4. 读回
body=$($CURL "$BASE/davsync-smoke-$ts.txt" -w '\n%{http_code}')
code=$(echo "$body" | tail -1)
[ "$code" = "200" ] || fail "GET -> $code"
[ "$(echo "$body" | head -1)" = "smoke-$ts" ] || fail "GET 内容不一致"
echo "GET 200 OK (content verified)"

# 5. 清理
code=$($CURL -X DELETE "$BASE/davsync-smoke-$ts.txt" -o /dev/null -w '%{http_code}')
[ "$code" = "204" ] && echo "DELETE 204 OK"

echo "ALL PASS ✓"
