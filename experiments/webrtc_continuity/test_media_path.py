"""Offline path-evidence tests: fixture addresses are documentation-only."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.webrtc_continuity import media_path


class MediaPathTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = dict(schema=1, captured_at='2026-11-07T12:00:00Z',
                             candidate_pair_generation=2, role='A',
                             connection_state='connected', ice_state='completed',
                             selected_pair={'state': 'succeeded', 'nominated': True},
                             local_candidate={'candidate_type': 'host', 'address': '2001:db8:6::2'})
        self.interfaces = dict(schema=1, captured_at='2026-11-07T12:00:01Z', ifconfig='''en0: flags=8863
\tinet 192.0.2.2 netmask 0xffffff00
\tinet6 2001:db8:0::2 prefixlen 64
\tstatus: active
en6: flags=8863
\tinet6 2001:0db8:0006:0:0:0:0:2 prefixlen 64
\tinet6 fe80::2%en6 prefixlen 64 scopeid 0x7
\tstatus: active
''')

    def test_exact_ipv6_match_is_not_physical_handover(self):
        with patch('socket.socket', side_effect=AssertionError('network')), patch('subprocess.run', side_effect=AssertionError('process')):
            result = media_path.compare(self.snapshot, self.interfaces)
        self.assertEqual(result['status'], 'candidate_interface_match')
        self.assertEqual(result['interface'], 'en6')
        self.assertEqual(result['network'], 'cellular')
        self.assertFalse(result['physical_egress_verified'])
        self.assertFalse(result['same_session_handover_verified'])
        self.assertNotIn('2001:', json.dumps(result))
        self.assertNotIn('192.0.', json.dumps(result))

    def test_ipv4_and_scoped_ipv6_match(self):
        for addr, expected in [('192.0.2.2', 'en0'), ('fe80::2%en6', 'en6')]:
            self.snapshot['local_candidate']['address'] = addr
            self.assertEqual(media_path.compare(self.snapshot, self.interfaces)['interface'], expected)

    def test_obscured_nat_relay_and_unmatched_never_verify(self):
        for kind, addr in [('host', 'example.local'), ('host', '192.0.2.99'), ('relay', '2001:db8:6::2'), ('srflx', '192.0.2.2'), ('host', '127.0.0.1'), ('host', 'fe80::2%en0')]:
            self.snapshot['local_candidate'].update(candidate_type=kind, address=addr)
            result = media_path.compare(self.snapshot, self.interfaces)
            self.assertEqual(result['status'], 'unverified')
            self.assertIsNone(result['interface'])

    def test_stale_disconnected_missing_or_other_peer_evidence(self):
        for update in [dict(captured_at='2026-11-07T11:00:00Z'), dict(connection_state='disconnected'), dict(ice_state='failed'), dict(role='B'), dict(selected_pair=None), dict(candidate_pair_generation=None)]:
            result = media_path.compare(dict(self.snapshot, **update), self.interfaces)
            self.assertEqual(result['status'], 'unverified')

    def test_inactive_and_ambiguous_interfaces(self):
        self.interfaces['ifconfig'] = self.interfaces['ifconfig'].replace('status: active', 'status: inactive')
        self.assertEqual(media_path.compare(self.snapshot, self.interfaces)['status'], 'unverified')
        self.interfaces['ifconfig'] = self.interfaces['ifconfig'].replace('status: inactive', 'status: active')
        self.interfaces['ifconfig'] += 'en8: flags=8863\n\tinet6 2001:db8:6::2 prefixlen 64\n\tstatus: active\n'
        self.assertEqual(media_path.compare(self.snapshot, self.interfaces)['reason'], 'address_ambiguous')

    def test_invalid_timestamp_and_schema_rejected(self):
        for update in [dict(schema=2), dict(captured_at='2026-11-07T12:00:00'), dict(candidate_pair_generation=True)]:
            with self.assertRaises(ValueError):
                media_path.compare(dict(self.snapshot, **update), self.interfaces)

    def test_cli_compare_private_files_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media_path.save_private(root/'path.json', self.snapshot)
            media_path.save_private(root/'interfaces.json', self.interfaces)
            args = ['compare', '--path-snapshot', str(root/'path.json'), '--interfaces', str(root/'interfaces.json'), '--output', str(root/'result.json')]
            with patch('socket.socket', side_effect=AssertionError('network')), patch('subprocess.run', side_effect=AssertionError('process')):
                self.assertEqual(media_path.main(args), 0)
                self.assertEqual(media_path.main(args), 1)
            self.assertEqual((root/'path.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads((root/'result.json').read_text())['interface'], 'en6')

    def test_capture_is_only_explicit_local_read(self):
        with patch('subprocess.run') as process:
            process.return_value.stdout = self.interfaces['ifconfig']
            result = media_path.capture_interfaces()
        self.assertEqual(process.call_args.args[0], ['/sbin/ifconfig', '-a'])
        self.assertEqual(result['ifconfig'], self.interfaces['ifconfig'])


if __name__ == '__main__':
    unittest.main()
