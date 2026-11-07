"""Offline collector/transport tests; sockets, probes, and listeners are forbidden."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from mac_hub.monitor import Measurement
from experiments.webrtc_continuity import policy_bridge as bridge


class FakeClock:
    def __init__(self):
        self.now = 0.

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds

    def utc(self):
        return (datetime(2026, 11, 7, tzinfo=timezone.utc) + timedelta(seconds=self.now)).isoformat()


class BridgeTests(unittest.TestCase):
    def setUp(self):
        # These fail closed if any test accidentally escapes its offline fixtures.
        self.addCleanup(patch.stopall)
        patch('socket.socket', side_effect=AssertionError('Unexpected real socket')).start()
        patch('subprocess.run', side_effect=AssertionError('Unexpected probe subprocess')).start()
        self.posts = []
        self.calls = []
        self.probes = []
        self.clock = FakeClock()
        self.remote_window = 0

    def session(self, **kwargs):
        return dict(session_id='call_A', application='video_call', status='active',
                    policy_window=self.remote_window, expires_in_seconds=300, **kwargs)

    def send(self, path, payload=None):
        self.calls.append(path)
        if path == '/policy':
            self.posts.append(payload)
            self.remote_window = payload['window']
            return {'status': 'accepted'}
        return self.session()

    def probe(self, interface, target, count):
        self.probes.append((interface, target, count))
        if interface == 'en0':
            self.clock.sleep(10)
        return Measurement(interface, 'reachable', latency=50 if interface == 'en0' else 5,
                           loss=0, sent=count, received=count,
                           raw_output='PRIVATE RAW ADDRESS', error='PRIVATE ERROR')

    def run_bridge(self, **kwargs):
        args = dict(execute=True, send=self.send, probe=self.probe, cycles=4,
                    clock=self.clock, sleep=self.clock.sleep,
                    utc=self.clock.utc, emit=lambda _: None)
        args.update(kwargs)
        return bridge.run(**args)

    def test_collector_restart_rejected_before_probes(self):
        self.remote_window = 4
        with self.assertRaisesRegex(bridge.BridgeError, 'new call'):
            self.run_bridge()
        self.assertEqual(self.probes, [])

    def test_ongoing_session_allows_accepted_policy_windows(self):
        result = self.run_bridge()
        self.assertEqual(result, dict(accepted_windows=4, discarded_windows=0))
        self.assertEqual([p['window'] for p in self.posts], [1, 2, 3, 4])
        self.assertEqual({row[:2] for row in self.probes}, {('en0', '1.1.1.1'), ('en6', '1.1.1.1')})

    def test_session_sequence_requires_nonnegative_integer(self):
        for window in (None, -1, True, '0', 1.5, 10001):
            self.remote_window = window
            with self.subTest(window=window), self.assertRaises(bridge.BridgeError):
                self.run_bridge()
        self.assertEqual(self.probes, [])

    def test_session_lease_is_required_and_bounded(self):
        for lease in (None, 0, -1, True, '300', 361, float('nan')):
            def send(*_):
                return {**self.session(), 'expires_in_seconds': lease}
            with self.subTest(lease=lease), self.assertRaises(bridge.BridgeError):
                self.run_bridge(send=send)
        self.assertEqual(self.probes, [])

    def test_writer_requires_strong_urlsafe_token(self):
        for token in (None, '', 'short', 't' * 257, 't' * 40 + ' ', 't' * 40 + ':'):
            with self.subTest(token_length=len(token or '')), self.assertRaises(bridge.BridgeError):
                bridge.Writer('https://demo.onrender.com', token)

    def test_gate_blocks_session_fetch_probes_and_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'events.jsonl'
            with self.assertRaises(bridge.BridgeError):
                self.run_bridge(execute=False, output=output)
            self.assertFalse(output.exists())
        self.assertEqual(self.calls, [])
        self.assertEqual(self.probes, [])

    def test_invalid_bounds_stop_before_network(self):
        for setting in (dict(duration=301), dict(duration=True), dict(duration=float('nan')),
                        dict(cycles=31), dict(cycles=True), dict(count=31),
                        dict(pause=True), dict(pause=0), dict(retries=4), dict(cellular='en0')):
            with self.subTest(setting=setting), self.assertRaises(bridge.BridgeError):
                self.run_bridge(**setting)
        self.assertEqual(self.calls, [])

    def test_real_engine_persists_three_observation_hold_and_dwell(self):
        self.run_bridge()
        self.assertEqual([p['recommended'] for p in self.posts], ['wifi'] * 3 + ['cellular'])
        self.assertEqual([p['stability']['hold_count'] for p in self.posts], [0, 1, 2, 0])
        self.assertEqual(self.posts[-1]['reason_code'], 'qualified_change')
        self.assertNotIn('PRIVATE', json.dumps(self.posts))
        self.assertEqual(self.posts[0]['stability']['dwell_seconds'], 30)
        self.assertEqual(self.posts[0]['stability']['margin'], .05)

    def test_dwell_retains_wifi_even_after_three_qualifying_observations(self):
        def fast_probe(*args):
            result = self.probe(*args)
            if args[0] == 'en0':
                self.clock.sleep(-9)
            return result
        self.run_bridge(probe=fast_probe, pause=1)
        self.assertTrue(all(p['recommended'] == 'wifi' for p in self.posts))
        self.assertEqual(self.posts[-1]['stability']['hold_count'], 3)

    def test_timestamp_marks_window_start_not_end(self):
        self.run_bridge(cycles=1)
        self.assertEqual(self.posts[0]['timestamp'], '2026-11-07T00:00:00+00:00')
        self.assertEqual(self.clock.now, 10)

    def test_repeated_or_naive_timestamp_stops_before_next_probes(self):
        for stamp in ('2026-11-07T00:00:00', 'not-a-date'):
            with self.subTest(stamp=stamp), self.assertRaisesRegex(bridge.BridgeError, 'clock invalid'):
                self.run_bridge(utc=lambda: stamp)
        self.assertEqual(self.probes, [])
        with self.assertRaisesRegex(bridge.BridgeError, 'clock invalid'):
            self.run_bridge(utc=lambda: '2026-11-07T00:00:00+00:00')
        self.assertEqual(len(self.probes), 2)

    def test_no_cellular_preserves_unavailable_values_and_wifi(self):
        def probe(interface, target, count):
            return Measurement(interface) if interface == 'en6' else self.probe(interface, target, count)
        self.run_bridge(probe=probe)
        cell = self.posts[0]['measurements']['cellular']
        self.assertEqual(cell['status'], 'error')
        for metric in ('latency_ms', 'loss_percent', 'score', 'adjusted_score'):
            self.assertIsNone(cell[metric])
        self.assertEqual(cell['trend'], 'Unavailable')
        self.assertTrue(all(p['recommended'] == 'wifi' for p in self.posts))

    def test_wifi_loss_uses_actual_availability_exception(self):
        def probe(interface, target, count):
            if interface == 'en0' and self.posts:
                self.clock.sleep(10)
                return Measurement(interface, 'no_reply', loss=100, sent=count, received=0)
            return self.probe(interface, target, count)
        self.run_bridge(probe=probe, cycles=2)
        self.assertEqual(self.posts[1]['recommended'], 'cellular')
        self.assertEqual(self.posts[1]['reason_code'], 'availability')

    def test_both_unavailable_reports_none(self):
        self.run_bridge(probe=lambda *args: Measurement(args[0]), cycles=1)
        self.assertEqual(self.posts[0]['recommended'], 'none')
        self.assertEqual(self.posts[0]['reason_code'], 'no_eligible_path')

    def test_probe_error_never_exposes_raw_exception(self):
        def probe(*_):
            raise RuntimeError('PRIVATE ERROR ADDRESS')
        self.run_bridge(probe=probe, cycles=1)
        self.assertNotIn('PRIVATE', json.dumps(self.posts))
        self.assertEqual(self.posts[0]['recommended'], 'none')

    def test_session_change_after_probes_discards_results(self):
        sessions = iter(['call_A', 'call_B'])
        def send(path, payload=None):
            self.assertEqual(path, '/policy/session')
            return {**self.session(), 'session_id': next(sessions)}
        with self.assertRaisesRegex(bridge.BridgeError, 'session changed'):
            self.run_bridge(send=send)
        self.assertEqual(self.posts, [])

    def test_auth_failure_prevents_probe_and_retry(self):
        attempts = []
        def failed(*args):
            attempts.append(args)
            raise bridge.BridgeError('unauthorized')
        with self.assertRaises(bridge.BridgeError):
            self.run_bridge(send=failed)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(self.probes, [])

    def test_rejected_post_is_fatal_without_retry(self):
        def send(path, payload=None):
            if path == '/policy':
                self.posts.append(payload)
                return {'status': 'rejected'}
            return self.send(path, payload)
        with self.assertRaises(bridge.BridgeError):
            self.run_bridge(send=send)
        self.assertEqual(len(self.posts), 1)

    def test_brief_session_outage_retries_without_resetting_engine(self):
        failed = False
        def send(path, payload=None):
            nonlocal failed
            if path == '/policy/session' and self.remote_window == 2 and not failed:
                failed = True
                raise bridge.TransientBridgeError('temporary')
            return self.send(path, payload)
        self.run_bridge(send=send)
        self.assertEqual([p['recommended'] for p in self.posts], ['wifi'] * 3 + ['cellular'])
        self.assertEqual([p['stability']['hold_count'] for p in self.posts], [0, 1, 2, 0])

    def test_post_lost_before_acceptance_is_not_replayed(self):
        def send(path, payload=None):
            if path == '/policy' and payload['window'] == 2:
                self.posts.append(payload)
                raise bridge.TransientBridgeError('temporary')
            return self.send(path, payload)
        result = self.run_bridge(send=send)
        self.assertEqual([p['window'] for p in self.posts], [1, 2, 3, 4])
        self.assertEqual(result, dict(accepted_windows=3, discarded_windows=1))
        self.assertEqual(self.posts[-1]['recommended'], 'cellular')

    def test_post_ack_lost_after_acceptance_reconciles_without_replay(self):
        def send(path, payload=None):
            result = self.send(path, payload)
            if path == '/policy' and payload['window'] == 2:
                raise bridge.TransientBridgeError('temporary')
            return result
        result = self.run_bridge(send=send)
        self.assertEqual([p['window'] for p in self.posts], [1, 2, 3, 4])
        self.assertEqual(result, dict(accepted_windows=4, discarded_windows=0))

    def test_stale_window_after_outage_is_discarded_before_engine(self):
        failed = False
        def send(path, payload=None):
            nonlocal failed
            if path == '/policy/session' and self.probes and not failed:
                failed = True
                self.clock.sleep(40)
                raise bridge.TransientBridgeError('temporary')
            return self.send(path, payload)
        result = self.run_bridge(send=send, cycles=2)
        self.assertEqual([p['window'] for p in self.posts], [2])
        self.assertEqual(self.posts[0]['stability']['hold_count'], 0)
        self.assertEqual(result, dict(accepted_windows=1, discarded_windows=1))

    def test_transport_retries_have_fixed_ceiling(self):
        attempts = []
        def send(*args):
            attempts.append(args)
            raise bridge.TransientBridgeError('temporary')
        with self.assertRaisesRegex(bridge.BridgeError, 'bounded retries'):
            self.run_bridge(send=send)
        self.assertEqual(len(attempts), 4)
        self.assertEqual(self.probes, [])
        self.assertEqual(self.clock.now, 7)

    def test_no_probe_without_enough_approval_or_session_time(self):
        with self.assertRaisesRegex(bridge.BridgeError, 'Insufficient approved time'):
            self.run_bridge(duration=10)
        self.assertEqual(self.probes, [])
        with self.assertRaisesRegex(bridge.BridgeError, 'Insufficient approved time'):
            self.run_bridge(send=lambda *_: {**self.session(), 'expires_in_seconds': 10})
        self.assertEqual(self.probes, [])

    def test_approval_duration_does_not_renew_with_session_polls(self):
        with self.assertRaisesRegex(bridge.BridgeError, 'Insufficient approved time'):
            self.run_bridge(duration=30)
        self.assertEqual(len(self.probes), 2)
        self.assertEqual(len(self.posts), 1)

    def test_session_expiry_during_network_retry_stops_requests_and_probes(self):
        attempts = []
        def send(*_):
            attempts.append(self.clock.now)
            if len(attempts) == 1:
                return {**self.session(), 'expires_in_seconds': 30}
            self.clock.sleep(19)
            raise bridge.TransientBridgeError('temporary')
        with self.assertRaisesRegex(bridge.BridgeError, 'expired'):
            self.run_bridge(send=send)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(len(self.probes), 2)
        self.assertEqual(self.posts, [])

    def test_changed_or_reset_remote_sequence_stops(self):
        for value in (0, 5):
            self.posts, self.calls, self.probes = [], [], []
            self.clock, self.remote_window = FakeClock(), 0
            def send(path, payload=None):
                if path == '/policy/session' and self.posts:
                    return {**self.session(), 'policy_window': value}
                return self.send(path, payload)
            with self.subTest(value=value), self.assertRaisesRegex(bridge.BridgeError, 'sequence changed'):
                self.run_bridge(send=send)
            self.assertEqual(len(self.posts), 1)

    def test_optional_journal_is_fresh_private_and_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'events.jsonl'
            self.run_bridge(output=output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            decisions = [r for r in rows if r['event'] == 'decision']
            self.assertEqual(len(decisions), 4)
            self.assertTrue(decisions[-1]['recommendation_change'])
            self.assertEqual(decisions[-1]['reason_code'], 'qualified_change')
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            for private in ('PRIVATE', 'call_A', 'Authorization', '1.1.1.1'):
                self.assertNotIn(private, output.read_text())
            calls_before = len(self.calls)
            with self.assertRaisesRegex(bridge.BridgeError, 'fresh file'):
                self.run_bridge(output=output)
            self.assertEqual(len(self.calls), calls_before)

    def test_origin_rejects_redirect_targets_credentials_and_other_hosts(self):
        for value in ('http://demo.onrender.com', 'https://demo.onrender.com/private',
                      'https://demo.onrender.com.evil.example', 'https://user:secret@demo.onrender.com',
                      'https://demo.onrender.com:443', 'https://demo.onrender.com:bad', 'https://[broken', 'https://example.org'):
            with self.subTest(value=value), self.assertRaises(bridge.BridgeError):
                bridge.server_origin(value)
        self.assertEqual(bridge.server_origin('https://demo.onrender.com/'), 'https://demo.onrender.com')
        self.assertIsNone(bridge.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere'))

    def test_loopback_requires_explicit_flag_and_literal_loopback_host(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.server_origin('http://127.0.0.1:8765')
        self.assertEqual(bridge.server_origin('http://127.0.0.1:8765', allow_loopback=True), 'http://127.0.0.1:8765')
        for value in ('http://localhost:8765', 'http://192.168.1.2:8765', 'http://127.0.0.1:80',
                      'http://127.0.0.1:8765/path', 'http://127.0.0.2:8765'):
            with self.subTest(value=value), self.assertRaises(bridge.BridgeError):
                bridge.server_origin(value, allow_loopback=True)

    def test_writer_errors_are_sanitized_and_timeout_bounded(self):
        writer = bridge.Writer('https://demo.onrender.com', 't' * 48)
        for error, expected in ((HTTPError('PRIVATE', 401, 'PRIVATE', {}, None), bridge.BridgeError),
                                (HTTPError('PRIVATE', 503, 'PRIVATE', {}, None), bridge.TransientBridgeError),
                                (URLError('PRIVATE'), bridge.TransientBridgeError)):
            with patch.object(writer.opener, 'open', side_effect=error) as opened:
                with self.assertRaises(expected) as caught:
                    writer('/policy/session', timeout=3)
                self.assertNotIn('PRIVATE', str(caught.exception))
                self.assertEqual(opened.call_args.kwargs['timeout'], 3)

    def test_main_without_execute_does_not_prompt_or_construct_writer(self):
        with patch.object(bridge, 'Writer', side_effect=AssertionError('writer created')), \
             patch.object(bridge.getpass, 'getpass', side_effect=AssertionError('prompt started')), patch('builtins.print'):
            self.assertEqual(bridge.main(['--server', 'https://demo.onrender.com', '--prompt-token']), 1)

    def test_main_hidden_prompt_passes_secret_to_writer_only(self):
        token = 's' * 48
        with patch.object(bridge, 'Writer') as writer, patch.object(bridge, 'run') as run, \
             patch.object(bridge.getpass, 'getpass', return_value=token):
            self.assertEqual(bridge.main(['--server', 'http://127.0.0.1:8765', '--allow-loopback',
                                          '--execute', '--prompt-token']), 0)
            writer.assert_called_once_with('http://127.0.0.1:8765', token, allow_loopback=True)
            self.assertEqual(run.call_args.kwargs['duration'], 300)


if __name__ == '__main__':
    unittest.main()
