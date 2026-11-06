"""Approval-gated, loopback-only controlled-call signaling. Import is offline."""
import argparse
from collections import deque
from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
from threading import Lock
from time import monotonic
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
MAX_BODY = 262144


def policy_snapshot(path, now=None):
    """Read an existing Video policy result; never collect or recompute metrics."""
    unavailable = {'status': 'unavailable', 'recommended': 'none', 'physical_interface': 'unverified'}
    if path is None:
        return dict(unavailable, status='not_configured')
    try:
        path = Path(path)
        if path.stat().st_size > 5*1024*1024:
            return unavailable
        text = path.read_text()
        rows = []
        lines = text.splitlines()
        for i, line in enumerate(lines):
            try:
                row = json.loads(line)
            except ValueError:
                if i == len(lines)-1 and not text.endswith('\n'):
                    break
                return unavailable
            if not isinstance(row, dict) or row.get('mode') != 'live':
                return unavailable
            if row.get('event') == 'completed_window':
                rows.append(row)
        if not rows:
            return unavailable
        row = rows[-1]
        if row['application'] != 'video_call':
            return dict(unavailable, status='wrong_profile')
        stamp = datetime.fromisoformat(row['timestamp'])
        age = ((now or datetime.now(timezone.utc))-stamp).total_seconds()
        window = row['window']
        recommendation = row['decision']['recommended']
        if type(window) is not int or window < 1 or recommendation not in ('wifi', 'cellular', 'none'):
            return unavailable
        # A finished run cannot masquerade as a current controller input.
        if path.with_name('manifest.json').exists():
            return dict(unavailable, status='finished')
        if not 0 <= age <= 45:
            return dict(unavailable, status='stale')
        return dict(status='fresh', application='video_call', window=window,
                    recommended=recommendation, age_seconds=age, physical_interface='unverified')
    except Exception:
        return unavailable


class Broker:
    """Private SDP exists in bounded in-memory queues, never logs or files."""
    def __init__(self, token, policy_log=None, clock=monotonic):
        self.token = token
        self.policy_log = policy_log
        self.clock = clock
        self.owners = {}
        self.queues = {'A': deque(), 'B': deque()}
        self.lock = Lock()

    def dispatch(self, method, path, authorization, body=b''):
        if not isinstance(authorization, str) or not hmac.compare_digest(authorization, 'Bearer '+self.token):
            return 403, {'error': 'not_authorized'}
        try:
            url = urlsplit(path)
            if method == 'GET' and url.path == '/policy':
                return 200, policy_snapshot(self.policy_log)
            data = json.loads(body) if method == 'POST' else {k: v[0] for k,v in parse_qs(url.query).items()}
            role, client = data.get('role'), data.get('client')
            if role not in ('A', 'B') or not isinstance(client, str) or not re.fullmatch(r'[A-Za-z0-9-]{16,64}', client):
                return 400, {'error': 'invalid_peer'}
            with self.lock:
                if method == 'POST' and url.path == '/join':
                    if role in self.owners and self.owners[role] != client:
                        return 409, {'error': 'role_already_owned'}
                    self.owners[role] = client
                    return 200, {'joined': True}
                if self.owners.get(role) != client:
                    return 403, {'error': 'peer_not_joined'}
                if method == 'POST' and url.path == '/leave':
                    del self.owners[role]
                    self.queues[role].clear()
                    return 200, {'left': True}
                if method == 'GET' and url.path == '/signal':
                    queue = self.queues[role]
                    messages = []
                    while queue:
                        created, message = queue.popleft()
                        if self.clock()-created <= 120:
                            messages.append(message)
                    return 200, {'messages': messages}
                if method == 'POST' and url.path == '/signal':
                    message = data['message']
                    description = message['description']
                    expected = 'offer' if role == 'A' else 'answer'
                    if message.get('mode') not in ('baseline', 'smartconnect') or type(message.get('revision')) is not int or not 1 <= message['revision'] <= 100:
                        return 400, {'error': 'invalid_signal'}
                    if description['type'] != expected or not isinstance(description['sdp'], str) or not description['sdp'].startswith('v=0') or len(description['sdp']) > 131072:
                        return 400, {'error': 'invalid_signal'}
                    # Forward only protocol fields; never arbitrary supplied metadata.
                    safe_message = dict(mode=message['mode'], revision=message['revision'], description=dict(type=expected, sdp=description['sdp']))
                    queue = self.queues['B' if role == 'A' else 'A']
                    while queue and self.clock()-queue[0][0] > 120:
                        queue.popleft()
                    if len(queue) >= 64:
                        return 429, {'error': 'signaling_queue_full'}
                    queue.append((self.clock(), safe_message))
                    return 200, {'accepted': True}
            return 404, {'error': 'not_found'}
        except Exception:
            return 400, {'error': 'invalid_signal'}


class LoopbackServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # Suppress raw request exceptions/addresses, including disconnects.


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # No paths, SDP, tokens, request logs or credentials on stdout/disk.

    def reply(self, status, body, content_type='application/json'):
        if not isinstance(body, bytes):
            body = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self' blob:; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'")
        self.send_header('Permissions-Policy', 'camera=(self), microphone=(self)')
        self.end_headers()
        self.wfile.write(body)

    def allowed_origin(self):
        port = self.server.server_address[1]
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        return (self.headers.get('Host') in hosts
                and self.headers.get('Sec-Fetch-Site') != 'cross-site'
                and (not self.headers.get('Origin') or self.headers['Origin'] in {'http://'+h for h in hosts}))

    def do_GET(self):
        if not self.allowed_origin():
            return self.reply(403, {'error': 'origin_not_allowed'})
        assets = {'/': ('index.html','text/html; charset=utf-8'), '/index.html': ('index.html','text/html; charset=utf-8'),
                  '/core.js': ('core.js','application/javascript'), '/app.js': ('app.js','application/javascript'), '/style.css': ('style.css','text/css')}
        if self.path in assets:
            name, mime = assets[self.path]
            return self.reply(200, (ROOT/name).read_bytes(), mime)
        status, body = self.server.broker.dispatch('GET', self.path, self.headers.get('Authorization'))
        self.reply(status, body)

    def do_POST(self):
        if not self.allowed_origin():
            return self.reply(403, {'error': 'origin_not_allowed'})
        try:
            length = int(self.headers.get('Content-Length', '-1'))
            if not 0 <= length <= MAX_BODY or self.headers.get('Content-Type') != 'application/json':
                return self.reply(400, {'error': 'invalid_body'})
            status, body = self.server.broker.dispatch('POST', self.path, self.headers.get('Authorization'), self.rfile.read(length))
            self.reply(status, body)
        except Exception:
            self.reply(400, {'error': 'invalid_body'})


def main(argv=None):
    parser = argparse.ArgumentParser(description='Isolated controlled WebRTC experiment; never starts the competition collector.')
    parser.add_argument('--approved-local-traffic', action='store_true', help='Only after explicit approval to serve the two controlled local clients. Call/media approval remains separate.')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--policy-log', type=Path, help='Approved existing Video-profile events.jsonl; read-only. No collector is started.')
    args = parser.parse_args(argv)
    if not args.approved_local_traffic:
        parser.error('Explicit approval required before starting even the local signaling server; no listener was created.')
    if not 1024 <= args.port <= 65535:
        parser.error('Use an unprivileged port in 1024..65535')
    token = secrets.token_urlsafe(32)
    server = LoopbackServer(('127.0.0.1', args.port), Handler)
    server.broker = Broker(token, args.policy_log)
    print('PRIVATE CONTROL URLs: do not project, publish or save these access tokens.')
    print(f'Client A: http://127.0.0.1:{args.port}/#role=A&token={token}')
    print(f'Client B: http://127.0.0.1:{args.port}/#role=B&token={token}')
    print('No media starts until each client explicitly confirms approval and starts its camera/microphone.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
