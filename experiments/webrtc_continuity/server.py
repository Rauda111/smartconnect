"""Approval-gated, loopback-only controlled-call signaling. Import is offline."""
import argparse
from collections import deque
from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
from threading import Lock
from time import monotonic
from urllib.parse import parse_qs, urlsplit

try:
    from .policy_channel import validate_policy
except ImportError:  # Portable standalone local server.
    from policy_channel import validate_policy

ROOT = Path(__file__).resolve().parent
MAX_BODY = 262144
POLICY_MAX_BODY = 16384
SESSION_SECONDS = 360
PEER_IDLE_SECONDS = 180
SIGNAL_SECONDS = 120


def strict_json(body):
    """Reject ambiguous duplicate keys and non-JSON numeric constants."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate_key')
            result[key] = value
        return result

    def invalid(_):
        raise ValueError('invalid_number')

    return json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)


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
    """One bounded call; role/session ownership and a separate policy publisher."""
    def __init__(self, token, policy_log=None, clock=monotonic, policy_token=None, utcnow=None):
        if policy_token is not None and (not isinstance(policy_token, str) or
                not re.fullmatch(r'[A-Za-z0-9_-]{40,256}', policy_token) or policy_token == token):
            raise ValueError('Policy token must be strong and separate from signaling')
        self.token, self.policy_token, self.policy_log = token, policy_token, policy_log
        self.clock = clock
        self.utcnow = utcnow or (lambda: datetime.now(timezone.utc))
        self.lock = Lock()
        self._reset()

    def _reset(self):
        self.owners, self.seen = {}, {}
        self.queues = {'A': deque(), 'B': deque()}
        self.session_id = None
        self.session_started = None
        self.delivery = {'A': 0, 'B': 0}
        self.delivered = {'A': 0, 'B': 0}
        self.acknowledged = {'A': 0, 'B': 0}
        self.policy = None
        self.policy_received = None
        self.policy_window = 0
        self.policy_attempt = -float('inf')

    def _expire(self):
        if self.session_id and self._remaining() <= 0:
            self._reset()

    def _remaining(self):
        if self.session_started is None:
            return 0
        now = self.clock()
        return max(0, min(SESSION_SECONDS - (now-self.session_started),
                          *(PEER_IDLE_SECONDS-(now-seen) for seen in self.seen.values())))

    def _absolute_remaining(self):
        return max(0, SESSION_SECONDS-(self.clock()-self.session_started)) if self.session_started is not None else 0

    @staticmethod
    def _authorized(authorization, token):
        return bool(token and isinstance(authorization, str) and
                    authorization.isascii() and
                    hmac.compare_digest(authorization, 'Bearer '+token))

    def _policy_route(self, method, path, authorization, body):
        if not self._authorized(authorization, self.policy_token):
            return 403, {'error': 'not_authorized'}
        with self.lock:
            self._expire()
            if not self.session_id or 'A' not in self.owners:
                return 409, {'error': 'no_active_session'}
            if method == 'GET':
                return 200, {'status': 'active', 'session_id': self.session_id, 'application': 'video_call',
                             'policy_window': self.policy_window, 'expires_in_seconds': self._remaining(),
                             'absolute_expires_in_seconds': self._absolute_remaining()}
            if len(body) > POLICY_MAX_BODY:
                return 413, {'error': 'policy_too_large'}
            if self.clock()-self.policy_attempt < .25:
                return 429, {'error': 'policy_rate_limited'}
            self.policy_attempt = self.clock()
            try:
                data = strict_json(body)
                safe = validate_policy(data, self.session_id, self.policy_window, self.utcnow())
                # Do not allow a newer sequence to replay an older observation.
                if self.policy and datetime.fromisoformat(safe['timestamp']) <= datetime.fromisoformat(self.policy['timestamp']):
                    return 409, {'error': 'replayed_policy'}
                self.policy, self.policy_window = safe, safe['window']
                self.policy_received = self.clock()
                return 200, {'status': 'accepted'}
            except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
                return 400, {'error': 'invalid_or_stale_policy'}

    def _read_policy(self):
        if self.policy is None:
            return {'status': 'unavailable' if self.policy_token else 'not_configured',
                    'session_id': self.session_id, 'physical_interface': 'unverified'}
        # Monotonic age prevents a wall-clock adjustment from rejuvenating old data.
        age = max(self.policy['age_seconds'] + self.clock()-self.policy_received,
                  (self.utcnow()-datetime.fromisoformat(self.policy['timestamp'])).total_seconds())
        return dict(self.policy, age_seconds=age, status='fresh' if 0 <= age <= 45 else 'stale')

    def dispatch(self, method, path, authorization, body=b''):
        if not isinstance(path, str) or len(path) > 2048 or not isinstance(body, bytes):
            return 400, {'error': 'invalid_request'}
        try:
            url = urlsplit(path)
        except ValueError:
            return 400, {'error': 'invalid_request'}
        if (method == 'GET' and url.path == '/policy/session') or (method == 'POST' and url.path == '/policy'):
            if url.query:
                return 400, {'error': 'invalid_request'}
            return self._policy_route(method, url.path, authorization, body)
        if not self._authorized(authorization, self.token):
            return 403, {'error': 'not_authorized'}
        if len(body) > MAX_BODY:
            return 413, {'error': 'body_too_large'}
        try:
            # Explicit local file mode remains available for private manual calls.
            if method == 'GET' and url.path == '/policy' and not url.query and self.policy_log is not None:
                return 200, policy_snapshot(self.policy_log)
            query = parse_qs(url.query, keep_blank_values=True, max_num_fields=8)
            if any(len(values) != 1 for values in query.values()):
                return 400, {'error': 'invalid_request'}
            data = strict_json(body) if method == 'POST' else {k: v[0] for k,v in query.items()}
            role, client = data.get('role'), data.get('client')
            if role not in ('A', 'B') or not isinstance(client, str) or not re.fullmatch(r'[A-Za-z0-9-]{16,64}', client):
                return 400, {'error': 'invalid_peer'}
            with self.lock:
                self._expire()
                if method == 'POST' and url.path == '/join':
                    if role in self.owners and self.owners[role] != client:
                        return 409, {'error': 'role_already_owned'}
                    if not self.session_id:
                        self.session_id = secrets.token_urlsafe(24)
                        self.session_started = self.clock()
                    self.owners[role], self.seen[role] = client, self.clock()
                    return 200, {'joined': True, 'session_id': self.session_id,
                                 'expires_in_seconds': self._remaining(),
                                 'absolute_expires_in_seconds': self._absolute_remaining()}
                if self.owners.get(role) != client:
                    return 403, {'error': 'peer_not_joined'}
                if data.get('session_id') != self.session_id:
                    return 409, {'error': 'session_mismatch'}
                self.seen[role] = self.clock()
                if method == 'POST' and url.path == '/leave':
                    self._reset()
                    return 200, {'left': True}
                if method == 'GET' and url.path == '/policy':
                    if self.policy_log is not None and self.policy_token is None:
                        return 200, dict(policy_snapshot(self.policy_log), session_id=self.session_id)
                    return 200, self._read_policy()
                if method == 'GET' and url.path == '/signal':
                    queue = self.queues[role]
                    while queue and self.clock()-queue[0][0] > SIGNAL_SECONDS:
                        queue.popleft()
                    if 'ack' in data:
                        ack = data['ack']
                        if not isinstance(ack, str) or not re.fullmatch(r'0|[1-9][0-9]{0,5}', ack):
                            return 400, {'error': 'invalid_ack'}
                        ack = int(ack)
                        if ack > self.delivered[role]:
                            return 400, {'error': 'invalid_ack'}
                        self.acknowledged[role] = max(ack, self.acknowledged[role])
                        while queue and queue[0][1] <= self.acknowledged[role]:
                            queue.popleft()
                        messages = [dict(message, delivery_id=sequence) for _, sequence, message in queue]
                        if queue:
                            self.delivered[role] = max(self.delivered[role], queue[-1][1])
                    else:
                        # Compatibility for older controlled clients; the integrated
                        # browser always uses acknowledgement-based delivery.
                        messages = [message for _, _, message in queue]
                        queue.clear()
                    return 200, {'messages': messages, 'session_id': self.session_id}
                if method == 'POST' and url.path == '/signal':
                    message = data['message']
                    description = message['description']
                    expected = 'offer' if role == 'A' else 'answer'
                    if message.get('mode') not in ('baseline', 'smartconnect') or type(message.get('revision')) is not int or not 1 <= message['revision'] <= 100:
                        return 400, {'error': 'invalid_signal'}
                    if description['type'] != expected or not isinstance(description['sdp'], str) or not description['sdp'].startswith('v=0') or len(description['sdp']) > 131072:
                        return 400, {'error': 'invalid_signal'}
                    safe_message = dict(mode=message['mode'], revision=message['revision'], session_id=self.session_id,
                                        description=dict(type=expected, sdp=description['sdp']))
                    recipient = 'B' if role == 'A' else 'A'
                    queue = self.queues[recipient]
                    while queue and self.clock()-queue[0][0] > SIGNAL_SECONDS:
                        queue.popleft()
                    # Idempotent retransmission does not fill the bounded queue.
                    # Once acknowledged/dequeued, a repeated offer can be delivered
                    # again so the answerer may resend its cached answer.
                    if any(queued == safe_message for _, _, queued in queue):
                        return 200, {'accepted': True}
                    if len(queue) >= 64:
                        return 429, {'error': 'signaling_queue_full'}
                    self.delivery[recipient] += 1
                    queue.append((self.clock(), self.delivery[recipient], safe_message))
                    return 200, {'accepted': True}
            return 404, {'error': 'not_found'}
        except Exception:
            return 400, {'error': 'invalid_signal'}

class LoopbackServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # Suppress raw request exceptions/addresses, including disconnects.


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

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
        self.send_header('Permissions-Policy', 'camera=(self), microphone=(self), display-capture=(self)')
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
                  '/core.js': ('core.js','application/javascript'), '/app.js': ('app.js','application/javascript'), '/style.css': ('style.css','text/css'),
                  '/jury.js': ('jury.js','application/javascript'), '/recording.js': ('recording.js','application/javascript')}
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
            maximum = POLICY_MAX_BODY if urlsplit(self.path).path == '/policy' else MAX_BODY
            if (not 0 <= length <= maximum or self.headers.get('Content-Type') != 'application/json'
                    or self.headers.get('Transfer-Encoding')):
                return self.reply(400, {'error': 'invalid_body'})
            raw = self.rfile.read(length)
            if len(raw) != length:
                return self.reply(400, {'error': 'invalid_body'})
            status, body = self.server.broker.dispatch('POST', self.path, self.headers.get('Authorization'), raw)
            self.reply(status, body)
        except Exception:
            self.reply(400, {'error': 'invalid_body'})


def main(argv=None):
    parser = argparse.ArgumentParser(description='Isolated controlled WebRTC experiment; never starts the competition collector.')
    parser.add_argument('--approved-local-traffic', action='store_true', help='Only after explicit approval to serve the two controlled local clients. Call/media approval remains separate.')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--policy-log', type=Path, help='Approved existing Video-profile events.jsonl; read-only. No collector is started.')
    parser.add_argument('--policy-token-from-env', action='store_true',
                        help='Enable the local live bridge with separate SMARTCONNECT_POLICY_TOKEN; never starts probes.')
    args = parser.parse_args(argv)
    if not args.approved_local_traffic:
        parser.error('Explicit approval required before starting even the local signaling server; no listener was created.')
    if not 1024 <= args.port <= 65535:
        parser.error('Use an unprivileged port in 1024..65535')
    token = secrets.token_urlsafe(32)
    if args.policy_token_from_env and args.policy_log:
        parser.error('Choose the live bridge or a read-only policy log, not both')
    writer_token = os.environ.get('SMARTCONNECT_POLICY_TOKEN') if args.policy_token_from_env else None
    if args.policy_token_from_env and not writer_token:
        parser.error('SMARTCONNECT_POLICY_TOKEN is required for the live bridge')
    try:
        broker = Broker(token, args.policy_log, policy_token=writer_token)
    except ValueError as error:
        parser.error(str(error))
    server = LoopbackServer(('127.0.0.1', args.port), Handler)
    server.broker = broker
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
