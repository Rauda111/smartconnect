import unittest
from experiments.webrtc_continuity.recording_collect import correlate

class CorrelationTests(unittest.TestCase):
    def test_only_matching_fingerprints_correlate_both_roles(self):
        rows = [{'role': role, 'directory': role, 'session_fingerprint_sha256': key}
                for role, key in [('A', 'a'*64), ('B', 'b'*64), ('B', 'a'*64)]]
        groups = correlate(rows)
        self.assertEqual([g['same_signaling_session_both_peers'] for g in groups], [True, False])
        self.assertTrue(all(g['physical_handover_verified'] is False for g in groups))
        self.assertNotIn('a'*64, str(groups))

    def test_missing_or_raw_identifiers_never_correlate(self):
        self.assertEqual(correlate([{'role': 'A', 'session_fingerprint_sha256': 'raw-secret-id'}]), [])
