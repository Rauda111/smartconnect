"""Offline server/policy contracts. No listener, DNS, media, or socket traffic."""
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from experiments.webrtc_continuity import server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.clock = 0
        self.broker = server.Broker('test-only-authorization', clock=lambda: self.clock)
        self.auth = 'Bearer test-only-authorization'
        self.clients = {'A': 'fixture-client-AAAA', 'B': 'fixture-client-BBBB'}
        for role, client in self.clients.items():
            self.assertEqual(self.post('/join', role=role, client=client)[0], 200)
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo'):
            patcher = patch(name, side_effect=AssertionError('Network forbidden'))
            patcher.start()
            self.addCleanup(patcher.stop)

    def post(self, path, **data):
        return self.broker.dispatch('POST', path, self.auth, json.dumps(data).encode())

    def signal(self, role='A', **overrides):
        message = dict(mode='smartconnect', revision=1, description=dict(type='offer' if role=='A' else 'answer', sdp='v=0\nfixture-private-sdp'))
        message.update(overrides)
        return self.post('/signal', role=role, client=self.clients[role], message=message)

    def get(self, role):
        return self.broker.dispatch('GET', '/signal?role='+role+'&client='+self.clients[role], self.auth)

    def test_signaling_roundtrip_dequeue_and_allowed_fields(self):
        self.assertEqual(self.signal(private_extra='MUST_NOT_FORWARD')[0], 200)
        code, response = self.get('B')
        self.assertEqual(code, 200)
        self.assertEqual(len(response['messages']), 1)
        self.assertNotIn('MUST_NOT_FORWARD', json.dumps(response))
        self.assertEqual(self.get('B')[1]['messages'], [])
        self.assertEqual(self.signal('B')[0], 200)
        self.assertEqual(self.get('A')[1]['messages'][0]['description']['type'], 'answer')

    def test_authorization_conflicts_invalid_signaling_and_expiry(self):
        self.assertEqual(self.broker.dispatch('GET', '/policy', None)[0], 403)
        self.assertEqual(self.post('/join', role='A', client='different-client-AAAA')[0], 409)
        self.assertEqual(self.signal(revision=-1)[0], 400)
        self.assertEqual(self.signal(description=dict(type='answer',sdp='v=0'))[0], 400)
        self.assertEqual(self.broker.dispatch('POST', '/signal', self.auth, b'not-json')[0], 400)
        self.signal(); self.clock=121
        self.assertEqual(self.get('B')[1]['messages'], [])
        self.assertEqual(self.broker.dispatch('GET', '/unknown?role=A&client='+self.clients['A'], self.auth)[0], 404)

    def test_queue_bound_and_leave(self):
        for _ in range(64): self.assertEqual(self.signal()[0], 200)
        self.assertEqual(self.signal()[0], 429)
        self.assertEqual(self.post('/leave', role='A', client=self.clients['A'])[0], 200)
        self.assertEqual(self.signal()[0], 403)

    def test_server_requires_approval_before_creating_listener(self):
        with patch.object(server, 'LoopbackServer') as listener, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): server.main([])
            listener.assert_not_called()
            with self.assertRaises(SystemExit): server.main(['--approved-local-traffic','--port','80'])
            listener.assert_not_called()

    def test_host_origin_and_static_asset_allowlist(self):
        handler = object.__new__(server.Handler)
        handler.server = type('Dummy', (), {'server_address': ('127.0.0.1', 8766)})()
        for headers, expected in [({'Host':'127.0.0.1:8766'},True),
                                  ({'Host':'attacker.invalid:8766'},False),
                                  ({'Host':'127.0.0.1:8766','Origin':'https://attacker.invalid'},False),
                                  ({'Host':'127.0.0.1:8766','Sec-Fetch-Site':'cross-site'},False)]:
            handler.headers = headers
            self.assertEqual(handler.allowed_origin(), expected)
        self.assertEqual(self.broker.dispatch('GET','/../../PRIVATE',self.auth)[0],400)

    def test_transport_errors_do_not_print_private_addresses_or_exceptions(self):
        instance = object.__new__(server.LoopbackServer)
        output = io.StringIO()
        with redirect_stderr(output):
            instance.handle_error(None, ('PRIVATE-ADDRESS', 12345))
        self.assertEqual(output.getvalue(), '')

    def test_policy_fresh_stale_wrong_profile_finished_and_privacy(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'events.jsonl'
            row = dict(mode='live',event='completed_window',application='video_call',timestamp=now.isoformat(),window=7,
                       decision={'recommended':'cellular'},local_ip='PRIVATE-ADDRESS',error='PRIVATE-ERROR')
            path.write_text(json.dumps(row)+'\n')
            result = server.policy_snapshot(path, now)
            self.assertEqual(result['status'],'fresh')
            self.assertEqual(result['recommended'],'cellular')
            self.assertNotIn('PRIVATE',json.dumps(result))
            self.assertEqual(server.policy_snapshot(path,now+timedelta(seconds=46))['status'],'stale')
            row['application']='file_download';path.write_text(json.dumps(row)+'\n')
            self.assertEqual(server.policy_snapshot(path,now)['status'],'wrong_profile')
            row['application']='video_call';path.write_text(json.dumps(row)+'\n')
            path.with_name('manifest.json').write_text('{}')
            self.assertEqual(server.policy_snapshot(path,now)['status'],'finished')

    def test_policy_invalid_and_partial_input(self):
        self.assertEqual(server.policy_snapshot(None)['status'],'not_configured')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'events.jsonl'
            for text in ('', 'bad\n', '[]\n', '{"incomplete":'):
                path.write_text(text)
                self.assertEqual(server.policy_snapshot(path)['status'],'unavailable')
            path.write_text(json.dumps(dict(mode='live',event='completed_window',application='video_call',timestamp='PRIVATE',window=1,decision={'recommended':'wifi'}))+'\n')
            self.assertEqual(server.policy_snapshot(path)['status'],'unavailable')


if __name__ == '__main__': unittest.main()
