#!/usr/bin/env python3
"""Minimal WebDAV server for davsync E2E testing.

Listens on 127.0.0.1:8088, account davtest / davtest123.
Root directory: _tmp/davroot (served at /dav/).

Supports the verbs davsync.js actually uses:
    OPTIONS / PROPFIND / GET / PUT / DELETE / MKCOL
Conditional PUT via If-Match header -> 412 on mismatch (conflict path).
Plus a /log/<msg> sink used by the Firefox log-hook build (TESTING.md §17).

Pure stdlib (no wsgidav dependency). Run from repo root:
    python _tmp/webdav.py
"""
import base64
import json
import os
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = '127.0.0.1'
PORT = 8088
USER = 'davtest'
PASSWORD = 'davtest123'
# davroot is relative to repo root regardless of CWD
ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), 'davroot'))
DAV_PREFIX = '/dav/'

os.makedirs(ROOT, exist_ok=True)

_log_lock = threading.Lock()


def log(msg):
    line = f'{msg}'
    with _log_lock:
        print(line, flush=True)


def dav_path(url_path):
    """Map /dav/foo/bar -> ROOT/foo/bar, refusing escapes."""
    rel = url_path[len(DAV_PREFIX):]
    rel = urllib.parse.unquote(rel)
    full = os.path.normpath(os.path.join(ROOT, rel))
    if full != ROOT and not full.startswith(ROOT + os.sep):
        raise PermissionError(rel)
    return full


class DavHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    # ---- helpers ----------------------------------------------------------

    def _auth_ok(self):
        h = self.headers.get('Authorization', '')
        if h.startswith('Basic '):
            try:
                cred = base64.b64decode(h[6:]).decode('utf-8')
            except Exception:
                return False
            return cred == f'{USER}:{PASSWORD}'
        return False

    def _deny(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="davtest"')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _read_body(self):
        length = int(self.headers.get('Content-Length') or 0)
        return self.rfile.read(length) if length > 0 else b''

    def _reply(self, code, body=b'', ctype='text/plain; charset=utf-8',
               extra=None):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD' and body:
            self.wfile.write(body)

    def _propfind_body(self, full, is_dir, depth_one):
        """Minimal 207 multistatus; includes getetag + getcontentlength."""
        def entry(path, dir_flag):
            rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
            href = DAV_PREFIX + ('' if rel == '.' else rel)
            quoted = urllib.parse.quote(href)
            if dir_flag:
                res = '<D:resourcetype><D:collection/></D:resourcetype>'
                props = ''
            else:
                size = os.path.getsize(path)
                etag = f'"w/{size}-{int(os.path.getmtime(path))}"'
                res = '<D:resourcetype/>'
                props = (f'<D:getcontentlength>{size}</D:getcontentlength>'
                         f'<D:getetag>{etag}</D:getetag>')
            return (f'<D:response><D:href>{quoted}</D:href>'
                    f'<D:propstat><D:prop>{props}{res}</D:prop>'
                    f'<D:status>HTTP/1.1 200 OK</D:status></D:propstat>'
                    f'</D:response>')

        parts = [entry(full, is_dir)]
        if depth_one and is_dir:
            for name in sorted(os.listdir(full)):
                p = os.path.join(full, name)
                parts.append(entry(p, os.path.isdir(p)))
        body = ('<?xml version="1.0" encoding="utf-8"?>'
                '<D:multistatus xmlns:D="DAV:">'
                + ''.join(parts) + '</D:multistatus>')
        return body

    # ---- verbs ------------------------------------------------------------

    def do_OPTIONS(self):
        if not self._auth_ok():
            return self._deny()
        self._reply(200, '', extra={
            'DAV': '1,2',
            'Allow': 'OPTIONS,GET,PUT,DELETE,PROPFIND,MKCOL',
        })

    def do_MKCOL(self):
        if not self._auth_ok():
            return self._deny()
        try:
            full = dav_path(self.path)
        except PermissionError:
            return self._reply(403, 'forbidden')
        if os.path.exists(full):
            return self._reply(405, 'already exists')
        os.makedirs(full, exist_ok=True)
        log(f'[{self.command}] {self.path} -> 201')
        self._reply(201, 'created')

    def do_PROPFIND(self):
        if not self._auth_ok():
            return self._deny()
        try:
            full = dav_path(self.path)
        except PermissionError:
            return self._reply(403, 'forbidden')
        if not os.path.exists(full):
            return self._reply(404, 'not found')
        depth = self.headers.get('Depth', '0')
        body = self._propfind_body(full, os.path.isdir(full), depth == '1')
        log(f'[{self.command}] {self.path} depth={depth} -> 207')
        self._reply(207, body, ctype='application/xml; charset=utf-8')

    def do_GET(self):
        # /log/<msg> sink for the Firefox hook build: no auth (hook fetch
        # is fire-and-forget and carries no credentials).
        if self.path.startswith('/log/'):
            msg = urllib.parse.unquote(self.path[len('/log/'):])
            log(f'[FF-LOG] {msg}')
            return self._reply(200, 'ok')
        if not self._auth_ok():
            return self._deny()
        try:
            full = dav_path(self.path)
        except PermissionError:
            return self._reply(403, 'forbidden')
        if not os.path.isfile(full):
            return self._reply(404, 'not found')
        with open(full, 'rb') as f:
            data = f.read()
        size = len(data)
        etag = f'"w/{size}-{int(os.path.getmtime(full))}"'
        log(f'[{self.command}] {self.path} -> 200 ({size}B)')
        self._reply(200, data, ctype='application/json', extra={
            'ETag': etag, 'Last-Modified': self.date_time_string(
                int(os.path.getmtime(full))),
        })

    def do_PUT(self):
        if not self._auth_ok():
            return self._deny()
        try:
            full = dav_path(self.path)
        except PermissionError:
            return self._reply(403, 'forbidden')
        body = self._read_body()

        # Ancestors check: parent must exist (davsync does MKCOL first, but
        # assert the 409 path anyway so tests can rely on it).
        parent = os.path.dirname(full)
        if not os.path.isdir(parent):
            log(f'[{self.command}] {self.path} -> 409 (no collection)')
            return self._reply(409, 'ancestors not found')

        # If-Match: conflict detection must behave like a real server.
        im = self.headers.get('If-Match')
        if im is not None:
            cur = None
            if os.path.isfile(full):
                size = os.path.getsize(full)
                cur = f'"w/{size}-{int(os.path.getmtime(full))}"'
            if cur is None or im not in ('*', cur):
                log(f'[{self.command}] {self.path} -> 412 (if-match {im} vs {cur})')
                return self._reply(412, 'precondition failed')

        existed = os.path.isfile(full)
        with open(full, 'wb') as f:
            f.write(body)
        size = len(body)
        etag = f'"w/{size}-{int(os.path.getmtime(full))}"'
        code = 204 if existed else 201
        log(f'[{self.command}] {self.path} -> {code} ({size}B)')
        self._reply(code, '', extra={'ETag': etag})

    def do_DELETE(self):
        if not self._auth_ok():
            return self._deny()
        try:
            full = dav_path(self.path)
        except PermissionError:
            return self._reply(403, 'forbidden')
        if os.path.isdir(full):
            import shutil
            shutil.rmtree(full, ignore_errors=True)
            log(f'[{self.command}] {self.path} -> 204 (dir)')
            return self._reply(204, '')
        if not os.path.isfile(full):
            return self._reply(404, 'not found')
        os.remove(full)
        log(f'[{self.command}] {self.path} -> 204')
        self._reply(204, '')

    def do_HEAD(self):
        if not self._auth_ok():
            return self._deny()
        try:
            full = dav_path(self.path)
        except PermissionError:
            return self._reply(403, 'forbidden')
        if not os.path.isfile(full):
            return self._reply(404, '')
        size = os.path.getsize(full)
        self._reply(200, '', extra={
            'Content-Length': str(size),
            'ETag': f'"w/{size}-{int(os.path.getmtime(full))}"',
        })

    def log_message(self, fmt, *args):  # silence default stderr chatter
        pass


if __name__ == '__main__':
    srv = ThreadingHTTPServer((HOST, PORT), DavHandler)
    log(f'webdav-test-server on http://{HOST}:{PORT}{DAV_PREFIX} root={ROOT} '
        f'({USER}/{PASSWORD})')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
