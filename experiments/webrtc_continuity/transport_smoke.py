"""Opt-in loopback HTTP integration check; all network measurements are fixtures.

No external destination, browser, camera, microphone, ICE or probe is used.
This is software transport validation, never physical handover evidence.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import secrets
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler
from unittest.mock import patch

from .policy_bridge import BridgeError, Writer, run
from .server import Broker, Handler, LoopbackServer
from mac_hub.monitor import Measurement


def check(*, approved=False):
    if not approved:
        raise ValueError('Explicit approval for loopback HTTP integration check required')
    reader, writer = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    elapsed = 0.
    base = datetime.now(timezone.utc)
    broker = Broker(reader, policy_token=writer, clock=lambda: elapsed,
                    utcnow=lambda: base+timedelta(seconds=elapsed))
    server = LoopbackServer(('127.0.0.1', 0), Handler)
    server.broker = broker
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = 'http://127.0.0.1:' + str(server.server_address[1])
    opener = build_opener(ProxyHandler({}))
    session = None

    def peer(method, path, role='A', **extra):
        data = dict(role=role, client='software-fixture-client-'+role, **extra)
        if session:
            data['session_id'] = session
        body = json.dumps(data).encode() if method == 'POST' else None
        url = origin+path+('?' + urlencode(data) if method == 'GET' else '')
        req = Request(url, data=body, method=method,
                      headers={'Authorization': 'Bearer '+reader, 'Content-Type': 'application/json'})
        with opener.open(req, timeout=3) as response:
            return json.loads(response.read(262145))

    try:
        session = peer('POST', '/join')['session_id']
        assert peer('POST', '/join', 'B')['session_id'] == session
        sender = Writer(origin, writer, allow_loopback=True)

        def probe(interface, target, count):
            return Measurement(interface, 'reachable', latency=50 if interface=='en0' else 5,
                               loss=0, sent=count, received=count)

        def advance(_):
            nonlocal elapsed
            elapsed += 10

        # Probe subprocess execution is forbidden even though HTTP uses real sockets.
        with patch('subprocess.run', side_effect=AssertionError('Probes forbidden')):
            result = run(execute=True, send=sender, cycles=4, probe=probe,
                         clock=lambda: elapsed, sleep=advance,
                         utc=lambda:(base+timedelta(seconds=elapsed)).isoformat(), emit=lambda _:None)
        assert result['accepted_windows'] == 4
        policy = peer('GET', '/policy')
        assert policy['window'] == 4 and policy['recommended'] == 'cellular'
        assert policy['reason_code'] == 'qualified_change'
        assert peer('GET', '/policy', 'B')['recommended'] == 'cellular'
        offer = dict(mode='smartconnect', revision=1,
                     description=dict(type='offer', sdp='v=0\nsoftware-transport-fixture'))
        assert peer('POST', '/signal', message=offer)['accepted']
        first = peer('GET', '/signal', 'B', ack=0)['messages']
        assert len(first) == 1
        assert peer('GET', '/signal', 'B', ack=0)['messages'] == first
        assert peer('GET', '/signal', 'B', ack=first[0]['delivery_id'])['messages'] == []
        try:
            opener.open(Request(origin+'/policy/session', headers={'Authorization':'Bearer invalid'}), timeout=3)
            raise AssertionError('Unauthorized writer accepted')
        except HTTPError as error:
            assert error.code == 403
            error.close()
        assert peer('POST', '/leave')['left']
        try:
            sender('/policy/session')
            raise AssertionError('Closed room remained active')
        except BridgeError:
            pass
        return dict(status='passed', transport='actual_loopback_http',
                    measurements='test_fixtures', physical_handover_verified=False)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-loopback-check', action='store_true')
    args = parser.parse_args(argv)
    if not args.approved_loopback_check:
        parser.error('No listener started; --approved-loopback-check is required')
    try:
        print(json.dumps(check(approved=True)))
    except Exception:
        print('Loopback integration check failed; no raw request or credential details emitted.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
