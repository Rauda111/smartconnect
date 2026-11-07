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
        if path != '/join': data.setdefault('session_id', self.broker.session_id)
        return self.broker.dispatch('POST', path, self.auth, json.dumps(data).encode())

    def signal(self, role='A', **overrides):
        message = dict(mode='smartconnect', revision=1, description=dict(type='offer' if role=='A' else 'answer', sdp='v=0\nfixture-private-sdp'))
        message.update(overrides)
        return self.post('/signal', role=role, client=self.clients[role], message=message)

    def get(self, role):
        return self.broker.dispatch('GET', '/signal?role='+role+'&client='+self.clients[role]+'&session_id='+str(self.broker.session_id), self.auth)

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
        self.assertEqual(self.broker.dispatch('GET', '/unknown?role=A&client='+self.clients['A']+'&session_id='+self.broker.session_id, self.auth)[0], 404)

    def test_queue_bound_and_leave(self):
        for revision in range(1, 65): self.assertEqual(self.signal(revision=revision)[0], 200)
        self.assertEqual(self.signal(revision=65)[0], 429)
        self.assertEqual(self.post('/leave', role='A', client=self.clients['A'])[0], 200)
        self.assertEqual(self.signal()[0], 403)

    def test_ack_delivery_survives_a_lost_poll_response_and_deduplicates_posts(self):
        def poll(ack):
            return self.broker.dispatch('GET', '/signal?role=B&client='+self.clients['B']+
                                       '&session_id='+self.broker.session_id+'&ack='+str(ack), self.auth)
        self.assertEqual(self.signal()[0], 200)
        self.assertEqual(self.signal()[0], 200)
        first = poll(0)[1]['messages']
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]['delivery_id'], 1)
        # The first response is deliberately discarded as if Wi-Fi failed in flight.
        self.assertEqual(poll(0)[1]['messages'], first)
        self.assertEqual(poll(2)[0], 400)
        self.assertEqual(poll(1)[1]['messages'], [])
        self.assertEqual(self.signal()[0], 200)
        self.assertEqual(poll(1)[1]['messages'][0]['delivery_id'], 2)
        # A delayed older cursor never rolls back a prior acknowledgement.
        self.assertEqual(len(poll(0)[1]['messages']), 1)
        self.assertEqual(poll(2)[1]['messages'], [])

    def test_ack_validation_and_expired_messages(self):
        self.signal()
        prefix = '/signal?role=B&client='+self.clients['B']+'&session_id='+self.broker.session_id+'&ack='
        for ack in ('-1', '01', '1.5', 'true', '', '9999999'):
            self.assertEqual(self.broker.dispatch('GET', prefix+ack, self.auth)[0], 400)
        self.clock = 121
        self.assertEqual(self.broker.dispatch('GET', prefix+'0', self.auth)[1]['messages'], [])

    def test_heartbeat_cannot_extend_absolute_call_lease(self):
        old = self.broker.session_id
        for elapsed in (120, 240, 359):
            self.clock = elapsed
            self.assertEqual(self.get('A')[0], 200)
            self.assertEqual(self.get('B')[0], 200)
        self.clock = 360
        self.assertEqual(self.get('A')[0], 403)
        self.assertIsNone(self.broker.session_id)
        code, joined = self.post('/join', role='A', client=self.clients['A'])
        self.assertEqual(code, 200)
        self.assertNotEqual(joined['session_id'], old)
        self.assertEqual(joined['expires_in_seconds'], 180)

    def test_invalid_and_ambiguous_requests_fail_without_side_effects(self):
        bodies = [b'{"role":"B","role":"A","client":"fixture-client-AAAA"}',
                  b'{"role":"A","client":"fixture-client-AAAA","value":NaN}',
                  b'[]', b'null']
        for body in bodies:
            self.assertEqual(self.broker.dispatch('POST', '/join', self.auth, body)[0], 400)
        self.assertEqual(self.broker.dispatch('GET', 'http://[broken', self.auth)[0], 400)
        self.assertEqual(self.broker.dispatch('GET', '/signal?role=A&role=B', self.auth)[0], 400)
        self.assertEqual(self.broker.dispatch('GET', '/policy', 'Bearer \u2603')[0], 403)
        self.assertEqual(self.broker.dispatch('POST', '/signal', self.auth, b'x'*(server.MAX_BODY+1))[0], 413)

    def test_local_writer_configuration_is_validated_before_listener(self):
        options = ['--approved-local-traffic', '--policy-token-from-env']
        for env in ({}, {'SMARTCONNECT_POLICY_TOKEN': 'weak'}):
            with patch.dict('os.environ', env, clear=True), patch.object(server, 'LoopbackServer') as listener, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit): server.main(options)
                listener.assert_not_called()
        with patch.dict('os.environ', {'SMARTCONNECT_POLICY_TOKEN': 'W'*48}), patch.object(server, 'LoopbackServer') as listener, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): server.main(options+['--policy-log', '/unused'])
            listener.assert_not_called()

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

    def test_http_body_limits_origin_and_partial_reads_precede_dispatch(self):
        def request(headers, body=b'', path='/policy'):
            handler = object.__new__(server.Handler)
            handler.server = type('Dummy', (), {'server_address': ('127.0.0.1', 8766),
                                              'broker': self.broker})()
            handler.headers = {'Host':'127.0.0.1:8766', 'Content-Type':'application/json', **headers}
            handler.rfile = io.BytesIO(body)
            handler.path = path
            responses = []
            handler.reply = lambda status, data: responses.append((status, data))
            with patch.object(self.broker, 'dispatch', side_effect=AssertionError('must not dispatch')):
                handler.do_POST()
            return responses
        self.assertEqual(request({'Content-Length':'16385'})[0][0], 400)
        self.assertEqual(request({'Content-Length':'2', 'Transfer-Encoding':'chunked'}, b'{}')[0][0], 400)
        self.assertEqual(request({'Content-Length':'2'}, b'{')[0][0], 400)
        self.assertEqual(request({'Content-Length':'2', 'Origin':'https://foreign.invalid'}, b'{}')[0][0], 403)

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
