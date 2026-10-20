"""Checks performed before a Burp tool call is forwarded; no network access here."""
from fnmatch import fnmatchcase
from pathlib import Path
import posixpath
import re
import sqlite3
import time
from urllib.parse import unquote, urlsplit

from burp_common import PROFILES, SEND_TOOLS, TAB_TOOLS


class Denied(ValueError):
    pass


def request_target(name, args):
    host, port, https = args.get('targetHostname'), args.get('targetPort'), args.get('usesHttps')
    if not isinstance(host, str) or type(port) is not int or type(https) is not bool:
        raise Denied('Explicit targetHostname, targetPort and usesHttps are required')
    scheme = 'https' if https else 'http'
    if name.endswith('http2') or name == 'send_http2_request':
        pseudo = args.get('pseudoHeaders')
        if not isinstance(pseudo, dict) or any(not isinstance(v, str) for v in pseudo.values()):
            raise Denied('HTTP/2 pseudoHeaders must be a string map')
        normalized = {}
        for key, value in pseudo.items():
            key = key.removeprefix(':')
            if key in normalized:
                raise Denied('Duplicate HTTP/2 pseudo-header aliases')
            normalized[key] = value
        if set(normalized) != {'method', 'path', 'authority', 'scheme'}:
            raise Denied('HTTP/2 requires method, path, authority and scheme only')
        if normalized['scheme'] != scheme:
            raise Denied('HTTP/2 scheme differs from target service')
        method, path, authority = (normalized[k] for k in ('method', 'path', 'authority'))
        headers = args.get('headers', {})
        if not isinstance(headers, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) or k.startswith(':')
            or '\r' in k + v or '\n' in k + v or k.lower() == 'host'
            for k, v in headers.items()
        ):
            raise Denied('Invalid HTTP/2 headers or conflicting Host/pseudo-header')
    else:
        content = args.get('content')
        if not isinstance(content, str):
            raise Denied('HTTP/1.1 content is required')
        # Require real line endings; do not reinterpret escaped text inside bodies.
        prelude = content.replace('\r\n', '\n').split('\n\n', 1)[0]
        lines = prelude.split('\n')
        match = re.fullmatch(r'([A-Z]+) (\S+) HTTP/1\.[01]', lines[0])
        if not match:
            raise Denied('Invalid HTTP/1 request line; use actual CRLF/LF separators')
        method, path = match.groups()
        hosts = []
        for line in lines[1:]:
            if ':' not in line or line[:1].isspace() or '\r' in line:
                raise Denied('Invalid or folded HTTP/1 header')
            key, value = line.split(':', 1)
            if key.lower() == 'host':
                hosts.append(value.strip())
        if len(hosts) != 1:
            raise Denied('Exactly one Host header is required')
        authority = hosts[0]
    if not path.startswith('/') or path.startswith('//') or '#' in path or '\\' in path:
        raise Denied('Only origin-form paths without fragments are supported')
    parsed = urlsplit(scheme + '://' + authority)
    try:
        authority_port = parsed.port or (443 if https else 80)
    except ValueError as exc:
        raise Denied('Invalid request authority') from exc
    if (parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
            or parsed.hostname != host.lower() or authority_port != port):
        raise Denied('Request authority differs from the explicit target service')
    return host.lower(), port, https, method, path


class Policy:
    def __init__(self, config, profile):
        self.config, self.profile = config, profile
        self.tools = set(PROFILES[profile])
        state = Path(config['state_path'])
        state.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(state, timeout=30, isolation_level=None)
        self.db.execute('CREATE TABLE IF NOT EXISTS budget (engagement TEXT PRIMARY KEY, requests INTEGER NOT NULL, polls INTEGER NOT NULL, last_dispatch REAL NOT NULL)')
        self.db.execute('INSERT OR IGNORE INTO budget VALUES (?, 0, 0, 0)', (config['engagement_id'],))

    def validate(self, name, args):
        if name not in self.tools:
            raise Denied(f'Tool is not allowed in the {self.profile} profile')
        if not isinstance(args, dict):
            raise Denied('Tool arguments must be an object')
        if name in SEND_TOOLS + TAB_TOOLS:
            host, port, https, method, path = request_target(name, args)
            if not any((t['host'].lower(), t['port'], t['https']) == (host, port, https)
                       for t in self.config['targets']):
                raise Denied('Target service is outside engagement scope')
            if method not in self.config['allowed_methods']:
                raise Denied('HTTP method is outside the engagement allowlist')
            path = path.split('?', 1)[0]
            for _ in range(4):
                decoded = unquote(path)
                if decoded == path:
                    break
                path = decoded
            else:
                raise Denied('Excessively nested path encoding')
            if '\\' in path or any(ord(c) < 32 for c in path):
                raise Denied('Ambiguous path encoding')
            normalized = '/' + posixpath.normpath(path).lstrip('/')
            candidates = (path, normalized, normalized.rstrip('/') or '/')
            if any(fnmatchcase(p, pattern) for p in candidates for pattern in self.config['excluded_paths']):
                raise Denied('Request path is excluded from this engagement')
        if name.startswith('get_') and name != 'get_collaborator_interactions':
            count, offset = args.get('count'), args.get('offset')
            if type(count) is not int or not 1 <= count <= self.config['limits']['max_history_count']:
                raise Denied('History/issue batch count exceeds configured bounds')
            if type(offset) is not int or offset < 0:
                raise Denied('A nonnegative pagination offset is required')
        if name == 'get_collaborator_interactions' and (
                not isinstance(args.get('payloadId'), str) or not args['payloadId'].strip()):
            raise Denied('A payloadId is required for correlated polling')

    def reserve(self, name):
        """Reserve at dispatch, sharing counts and pacing across gateway processes.

        An attempted send consumes budget even if Burp rejects it or the transport fails.
        All active calls are paced, including tab creation and Collaborator operations.
        """
        if name not in set(PROFILES['active']) - set(PROFILES['analysis']):
            return
        limits = self.config['limits']
        while True:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                sent, polls, last = self.db.execute(
                    'SELECT requests, polls, last_dispatch FROM budget WHERE engagement=?',
                    (self.config['engagement_id'],)).fetchone()
                if name in SEND_TOOLS and sent >= limits['max_requests']:
                    raise Denied('Engagement request budget exhausted')
                if name == 'get_collaborator_interactions' and polls >= limits['max_polls']:
                    raise Denied('Engagement poll budget exhausted')
                now = time.time()
                delay = limits['min_interval_seconds'] - (now - last)
                if delay <= 0:
                    self.db.execute('UPDATE budget SET requests=?, polls=?, last_dispatch=? WHERE engagement=?',
                                    (sent + (name in SEND_TOOLS), polls + (name == 'get_collaborator_interactions'),
                                     now, self.config['engagement_id']))
                    self.db.execute('COMMIT')
                    return
                self.db.execute('ROLLBACK')
            except BaseException:
                if self.db.in_transaction:
                    self.db.execute('ROLLBACK')
                raise
            time.sleep(min(delay, 1))
