"""Pure offline tests for Render cloud signaling; no listening socket or network."""
import unittest
from experiments.webrtc_continuity.cloud_server import CloudHandler, cloud_config

HOST = 'smartconnect-signaling.onrender.com'
TOKEN = 'A' * 48  # test fixture, never a live credential


class CloudServerTests(unittest.TestCase):
    def test_environment_gate(self):
        valid = {'RENDER': 'true', 'RENDER_EXTERNAL_HOSTNAME': HOST,
                 'SMARTCONNECT_SIGNAL_TOKEN': TOKEN, 'PORT': '10000'}
        self.assertEqual(cloud_config(valid), (HOST, TOKEN, 10000))
        for key, value in [('RENDER', 'false'), ('RENDER_EXTERNAL_HOSTNAME', 'attacker.invalid'),
                           ('SMARTCONNECT_SIGNAL_TOKEN', 'weak'), ('PORT', '80')]:
            broken = dict(valid, **{key: value})
            with self.assertRaises(ValueError): cloud_config(broken)

    def test_host_and_origin(self):
        handler = object.__new__(CloudHandler)
        handler.server = type('Server', (), {'public_hostname': HOST})()
        for headers, expected in [
            ({'Host': HOST}, True),
            ({'Host': HOST, 'Origin': 'https://' + HOST}, True),
            ({'Host': 'attacker.invalid'}, False),
            ({'Host': HOST, 'Origin': 'https://attacker.invalid'}, False),
            ({'Host': HOST, 'Origin': 'http://' + HOST}, False),
            ({'Host': HOST, 'Sec-Fetch-Site': 'cross-site'}, False),
        ]:
            handler.headers = headers
            self.assertEqual(handler.allowed_origin(), expected)


if __name__ == '__main__':
    unittest.main()
