#!/usr/bin/env python3
"""Smoke test for _tmp/webdav.py — exercises every verb davsync.js uses.

Run with the server already up:
    python _tmp/webdav-test.py
Exits 0 only if all checks pass.
"""
import base64
import sys
import urllib.request
import urllib.error

BASE = 'http://127.0.0.1:8088'
AUTH = 'Basic ' + base64.b64encode(b'davtest:davtest123').decode()


def req(method, path, body=None, headers=None, expect=None, label=''):
    r = urllib.request.Request(BASE + path, method=method,
                               data=body, headers=headers or {})
    r.add_header('Authorization', AUTH)
    try:
        resp = urllib.request.urlopen(r, timeout=10)
        code, data, hdrs = resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        code, data, hdrs = e.code, e.read(), dict(e.headers)
    ok = expect is None or code == expect
    tag = 'PASS' if ok else 'FAIL'
    print(f'[{tag}] {label or method} {path} -> {code}'
          + ('' if ok else f' (expected {expect})'))
    return ok, code, data, hdrs


def main():
    results = []

    # bad credentials -> 401
    r = urllib.request.Request(BASE + '/dav/', method='PROPFIND')
    try:
        urllib.request.urlopen(r, timeout=10)
        print('[FAIL] no-auth PROPFIND passed auth (expected 401)')
        results.append(False)
    except urllib.error.HTTPError as e:
        print(f'[{"PASS" if e.code == 401 else "FAIL"}] no-auth -> {e.code}')
        results.append(e.code == 401)

    results.append(req('OPTIONS', '/dav/', expect=200, label='options')[0])
    results.append(req('MKCOL', '/dav/ublock-davsync/', expect=201,
                       label='mkcol parent')[0])
    results.append(req('MKCOL', '/dav/ublock-davsync/', expect=405,
                       label='mkcol dup')[0])
    # PUT without collection -> 409
    results.append(req('PUT', '/dav/nosuchdir/file.json', b'{}', expect=409,
                       label='put no-collection 409')[0])

    body = json_body = b'{"hello": "world"}'
    ok, code, data, hdrs = req('PUT', '/dav/ublock-davsync/t.json', body,
                               expect=201, label='put first 201')
    results.append(ok)
    etag = hdrs.get('ETag')

    ok, code, data, hdrs = req('GET', '/dav/ublock-davsync/t.json',
                               expect=200, label='get back 200')
    results.append(ok and data == body)
    print(f'      body round-trip: {"PASS" if data == body else "FAIL"}')

    # conditional PUT with stale etag -> 412
    results.append(req('PUT', '/dav/ublock-davsync/t.json', b'{"v":2}',
                       headers={'If-Match': '"stale-etag"'}, expect=412,
                       label='if-match stale -> 412')[0])
    # conditional PUT with current etag -> 204
    results.append(req('PUT', '/dav/ublock-davsync/t.json', b'{"v":2}',
                       headers={'If-Match': etag}, expect=204,
                       label='if-match current -> 204')[0])

    ok, _, data, _ = req('PROPFIND', '/dav/ublock-davsync/t.json',
                         expect=207, label='propfind file 207')
    results.append(ok and b'getcontentlength' in data)

    ok, _, data, _ = req('PROPFIND', '/dav/ublock-davsync/',
                         headers={'Depth': '1'}, expect=207,
                         label='propfind dir depth1 207')
    results.append(ok and b't.json' in data)

    results.append(req('DELETE', '/dav/ublock-davsync/t.json', expect=204,
                       label='delete 204')[0])
    results.append(req('GET', '/dav/ublock-davsync/t.json', expect=404,
                       label='get after delete 404')[0])

    # log sink
    results.append(req('GET', '/log/hello', expect=200,
                       label='log sink')[0])

    n_fail = len([x for x in results if not x])
    print(f'\n== webdav-test: {len(results) - n_fail}/{len(results)} passed ==')
    sys.exit(1 if n_fail else 0)


if __name__ == '__main__':
    main()
