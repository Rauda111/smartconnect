import json
from pathlib import Path
import tempfile
import unittest
from experiments.webrtc_continuity.jury_inventory import snapshot,write_current

class JuryInventoryTests(unittest.TestCase):
    def test_inventory_is_os_data_not_network_measurement(self):
        raw='en0: flags=1\n\tinet 192.0.2.20 netmask 0xffffff00\n\tstatus: active\nen6: flags=1\n\tinet 192.0.2.21 netmask 0xffffff00\n\tstatus: inactive\n'
        result=snapshot(raw);self.assertEqual(result['role'],'A');self.assertTrue(result['interfaces'][0]['active']);self.assertFalse(result['interfaces'][1]['active']);self.assertEqual(result['interfaces'][0]['addresses'],['192.0.2.20'])
    def test_file_handle_path_and_inode_survive_refresh(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'current.json';write_current(path,{'a':1});inode=path.stat().st_ino
            write_current(path,{'a':2});self.assertEqual(path.stat().st_ino,inode);self.assertEqual(json.loads(path.read_text()),{'a':2});self.assertEqual(path.stat().st_mode&0o777,0o600)
