"""Full bridge -> broker policy flow without network or probe subprocesses."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch
from mac_hub.monitor import Measurement
from experiments.webrtc_continuity.server import Broker
from experiments.webrtc_continuity import policy_bridge, cloud_server


class PolicyChannelTests(unittest.TestCase):
    def setUp(self):
        self.elapsed = 0.
        self.base = datetime(2026, 11, 7, tzinfo=timezone.utc)
        self.writer = 'W'*48
        self.reader = 'R'*48
        self.broker = Broker(self.reader, policy_token=self.writer,
                             clock=lambda: self.elapsed, utcnow=lambda: self.base+timedelta(seconds=self.elapsed))
        self.clients = {'A': 'fixture-client-AAAA', 'B': 'fixture-client-BBBB'}
        self.session = None
        for role in self.clients:
            status, body = self.peer('POST', '/join', role)
            self.assertEqual(status, 200)
            self.session = body['session_id']
        for name in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo', 'subprocess.run'):
            p = patch(name, side_effect=AssertionError('Offline test forbids network/probes'))
            p.start(); self.addCleanup(p.stop)

    def peer(self, method, path, role='A', **extra):
        data = dict(role=role, client=self.clients[role], session_id=self.session, **extra)
        if method == 'GET':
            return self.broker.dispatch(method, path+'?'+'&'.join(k+'='+str(v) for k,v in data.items()), 'Bearer '+self.reader)
        return self.broker.dispatch(method, path, 'Bearer '+self.reader, json.dumps(data).encode())

    def payload(self, window=1):
        row = dict(status='reachable', latency_ms=10, loss_percent=0, sent=10, received=10,
                   score=.9, adjusted_score=.9, trend='Stable')
        return dict(session_id=self.session, window=window,
                    timestamp=(self.base+timedelta(seconds=self.elapsed)).isoformat(),
                    application='video_call', source='measured_icmp', recommended='wifi', reason_code='hold',
                    measurements={'wifi': dict(row), 'cellular': dict(row)},
                    stability=dict(hold_count=0, hold_required=3, dwell_seconds=30, margin=.05), coverage=.6)

    def post(self, payload=None, auth=None):
        return self.broker.dispatch('POST', '/policy', auth or 'Bearer '+self.writer,
                                   json.dumps(payload or self.payload()).encode())

    def test_fresh_both_peers_receive_same_scoped_policy_and_monotonic_expiry(self):
        self.assertEqual(self.post()[0], 200)
        for role in ('A', 'B'):
            code, p = self.peer('GET', '/policy', role)
            self.assertEqual(code, 200)
            self.assertEqual(p['session_id'], self.session)
            self.assertEqual(p['status'], 'fresh')
            self.assertEqual(p['physical_interface'], 'unverified')
        self.elapsed = 46
        self.broker.utcnow = lambda: self.base  # clock rollback cannot freshen it
        self.assertEqual(self.peer('GET', '/policy')[1]['status'], 'stale')

    def test_separate_credentials_and_peer_scope(self):
        self.assertEqual(self.post(auth='Bearer '+self.reader)[0], 403)
        self.assertEqual(self.broker.dispatch('GET', '/policy/session', 'Bearer '+self.reader)[0], 403)
        self.assertEqual(self.broker.dispatch('GET', '/policy?role=A', 'Bearer '+self.writer)[0], 403)
        self.assertEqual(self.broker.dispatch('GET', '/policy', 'Bearer '+self.reader)[0], 400)
        self.assertEqual(self.broker.dispatch('GET', '/policy?role=A&client='+self.clients['A']+'&session_id=wrong', 'Bearer '+self.reader)[0], 409)
        self.assertEqual(self.post(dict(self.payload(), session_id='wrong'))[0], 400)

    def test_replay_duplicate_window_old_timestamp_and_rate_limit(self):
        p = self.payload()
        self.assertEqual(self.post(p)[0], 200)
        self.assertEqual(self.post(p)[0], 429)
        self.elapsed += 1
        self.assertEqual(self.post(p)[0], 400)
        self.elapsed += 1
        self.assertEqual(self.post(dict(p, window=2))[0], 409)
        self.elapsed += 1
        self.assertEqual(self.post(self.payload(2))[0], 200)

    def test_strict_schema_stale_future_wrong_profile_and_private_fields(self):
        cases = [dict(self.payload(), timestamp=(self.base-timedelta(seconds=46)).isoformat()),
                 dict(self.payload(), timestamp=(self.base+timedelta(seconds=60)).isoformat()),
                 dict(self.payload(), application='file_download'),
                 dict(self.payload(), source='simulated'), dict(self.payload(), raw_output='PRIVATE'),
                 dict(self.payload(), window=True), dict(self.payload(), coverage=float('nan'))]
        broken = self.payload(); broken['measurements']['wifi']['latency_ms'] = None; cases.append(broken)
        broken = self.payload(); broken['measurements']['wifi']['raw_address'] = 'PRIVATE'; cases.append(broken)
        for item in cases:
            self.elapsed += 1
            self.assertEqual(self.post(item)[0], 400)
        self.assertEqual(self.peer('GET', '/policy')[1]['status'], 'unavailable')

    def test_leave_invalidates_all_policy_signals_and_old_session(self):
        self.assertEqual(self.post()[0], 200)
        old = self.session
        self.assertEqual(self.peer('POST', '/leave')[0], 200)
        self.assertEqual(self.peer('GET', '/policy', 'B')[0], 403)
        self.assertEqual(self.broker.dispatch('GET', '/policy/session', 'Bearer '+self.writer)[0], 409)
        self.session = self.peer('POST', '/join')[1]['session_id']
        self.assertNotEqual(old, self.session)
        self.assertEqual(self.peer('GET', '/policy')[1]['status'], 'unavailable')
        self.elapsed += 1
        self.assertEqual(self.post(dict(self.payload(), session_id=old))[0], 400)

    def test_expired_peer_and_policy_payload_size_bound(self):
        self.assertEqual(self.broker.dispatch('POST', '/policy', 'Bearer '+self.writer, b'x'*16385)[0], 413)
        self.elapsed = 181
        self.assertEqual(self.broker.dispatch('GET', '/policy/session', 'Bearer '+self.writer)[0], 409)
        self.assertEqual(self.peer('GET', '/signal')[0], 403)

    def test_policy_lease_is_read_only_and_writer_cannot_keep_call_alive(self):
        code, first = self.broker.dispatch('GET', '/policy/session', 'Bearer '+self.writer)
        self.assertEqual(code, 200)
        self.assertEqual(first['expires_in_seconds'], 180)
        self.elapsed = 100
        self.assertEqual(self.broker.dispatch('GET', '/policy/session', 'Bearer '+self.writer)[1]['expires_in_seconds'], 80)
        self.elapsed = 180
        self.assertEqual(self.broker.dispatch('GET', '/policy/session', 'Bearer '+self.writer)[0], 409)

    def test_inconsistent_values_and_duplicate_json_are_rejected(self):
        cases = []
        for change in ({'coverage': 1}, {'recommended': 'none'}, {'reason_code': 'no_eligible_path'}):
            cases.append(dict(self.payload(), **change))
        bad = self.payload(); bad['measurements']['wifi']['loss_percent'] = 20; cases.append(bad)
        bad = self.payload(); bad['measurements']['wifi']['sent'] = True; cases.append(bad)
        bad = self.payload(); bad['measurements']['cellular'].update(status='error', score=None, adjusted_score=None, trend='Unavailable'); bad['recommended'] = 'cellular'; cases.append(bad)
        bad = self.payload(); bad['stability']['hold_required'] = True; cases.append(bad)
        bad = self.payload(); bad['stability']['margin'] = .01; cases.append(bad)
        bad = self.payload(); bad['timestamp'] = '2026-11-07T00:00:00'; cases.append(bad)
        for payload in cases:
            self.elapsed += 1
            self.assertEqual(self.post(payload)[0], 400)
        self.elapsed += 1
        raw = json.dumps(self.payload()).replace('"window": 1', '"window": 2, "window": 1').encode()
        self.assertEqual(self.broker.dispatch('POST', '/policy', 'Bearer '+self.writer, raw)[0], 400)
        self.assertEqual(self.peer('GET', '/policy')[1]['status'], 'unavailable')

    def test_new_sequence_cannot_resubmit_older_timestamp(self):
        self.elapsed = 5
        old = self.payload()
        self.assertEqual(self.post(old)[0], 200)
        self.elapsed = 10
        replay = self.payload(3)
        replay['timestamp'] = (self.base+timedelta(seconds=4)).isoformat()
        self.assertEqual(self.post(replay)[0], 409)
        self.assertEqual(self.peer('GET', '/policy')[1]['window'], 1)

    def test_engine_explanations_are_preserved_but_arbitrary_text_is_rejected(self):
        explanation = 'Hold: superiority 2/3; elapsed dwell 19.0/30s'
        self.assertEqual(self.post(dict(self.payload(), explanation=explanation))[0], 200)
        self.assertEqual(self.peer('GET', '/policy')[1]['explanation'], explanation)
        for explanation in ('PRIVATE address or exception', 'Availability reset: recommend usable path immediately',
                            'Hold: superiority 2/3; elapsed dwell NaN/30s',
                            'Hold: superiority 2/3; elapsed dwell 19.0/30s\nPRIVATE'):
            self.elapsed += 1
            self.assertEqual(self.post(dict(self.payload(2), explanation=explanation))[0], 400)

    def test_cloud_invalid_writer_configuration_fails_before_listener(self):
        env = dict(RENDER='true', RENDER_EXTERNAL_HOSTNAME='fixture.onrender.com',
                   SMARTCONNECT_SIGNAL_TOKEN=self.reader, SMARTCONNECT_POLICY_TOKEN=self.reader, PORT='10000')
        for token in (self.reader, '', 'weak'):
            env['SMARTCONNECT_POLICY_TOKEN'] = token
            with patch.dict('os.environ', env, clear=True), patch.object(cloud_server, 'QuietCloudServer') as listener, patch('sys.stderr'):
                with self.assertRaises(SystemExit): cloud_server.main()
                listener.assert_not_called()

    def test_actual_engine_bridge_to_authenticated_channel_offline(self):
        def send(path, payload=None):
            code, result = self.broker.dispatch('POST' if payload else 'GET', path, 'Bearer '+self.writer,
                                               json.dumps(payload).encode() if payload else b'')
            self.assertEqual(code, 200, result)
            return result
        def probe(interface, target, count):
            return Measurement(interface, 'reachable', latency=50 if interface=='en0' else 5,
                               loss=0, sent=count, received=count, raw_output='PRIVATE RAW')
        def pause(seconds):
            self.elapsed += 10
            # The already-running browser keeps its scope alive; no socket involved.
            self.peer('GET', '/signal', 'A'); self.peer('GET', '/signal', 'B')
        policy_bridge.run(execute=True, send=send, cycles=4, probe=probe, clock=lambda:self.elapsed,
                          sleep=pause, utc=lambda:(self.base+timedelta(seconds=self.elapsed)).isoformat(), emit=lambda _:None)
        code, result = self.peer('GET', '/policy')
        self.assertEqual(code, 200)
        self.assertEqual(result['recommended'], 'cellular')
        self.assertEqual(result['reason_code'], 'qualified_change')
        self.assertEqual(result['window'], 4)
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_unavailable_cellular_and_both_paths_keep_null_metrics(self):
        p = self.payload()
        unavailable = dict(status='no_reply', latency_ms=None, loss_percent=100, sent=10, received=0,
                           score=None, adjusted_score=None, trend='Unavailable')
        p['measurements']['cellular'] = dict(unavailable)
        self.assertEqual(self.post(p)[0], 200)
        self.elapsed += 1
        p = self.payload(2); p['measurements'] = {n:dict(unavailable) for n in ('wifi','cellular')}
        p.update(recommended='none', reason_code='no_eligible_path')
        self.assertEqual(self.post(p)[0], 200)
        self.assertIsNone(self.peer('GET', '/policy')[1]['measurements']['wifi']['latency_ms'])


if __name__ == '__main__': unittest.main()
