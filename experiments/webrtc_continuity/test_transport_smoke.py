"""Default tests never start the opt-in loopback transport check."""
import unittest
from unittest.mock import patch
from experiments.webrtc_continuity import transport_smoke


class TransportApprovalTests(unittest.TestCase):
    def test_api_without_approval_never_constructs_listener(self):
        with patch.object(transport_smoke, 'LoopbackServer') as listener:
            with self.assertRaises(ValueError):
                transport_smoke.check()
            listener.assert_not_called()

    def test_cli_without_approval_never_constructs_listener(self):
        with patch.object(transport_smoke, 'LoopbackServer') as listener, patch('sys.stderr'):
            with self.assertRaises(SystemExit):
                transport_smoke.main([])
            listener.assert_not_called()
