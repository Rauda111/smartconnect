"""Offline preservation, independent arithmetic and anti-tampering checks."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from mac_hub.phase4.pilot_audit import audit

EVIDENCE=Path('mac_hub/phase4/evidence/location_pilot_20261030T175502Z')

class PilotAuditTests(unittest.TestCase):
    def test_preserved_negative_result(self):
        result=audit(EVIDENCE)
        self.assertEqual(result,json.loads((EVIDENCE/'audit.json').read_text()))
        self.assertEqual(result['icmp_received'],240)
        self.assertEqual(result['actual_http_requests'],24)
        self.assertFalse(result['checks']['wifi_rtt_deterioration'])
        self.assertFalse(result['checks']['wifi_goodput_deterioration'])
        self.assertFalse(result['checks']['cellular_B_rtt_stable'])
        self.assertTrue(result['checks']['wifi_return_goodput'])

    def test_raw_corruption_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'evidence'
            shutil.copytree(EVIDENCE,dest)
            with (dest/'raw'/'B-icmp.csv').open('a') as stream:
                stream.write('corruption')
            with self.assertRaisesRegex(ValueError,'checksum'):
                audit(dest)

    def test_rehashed_false_summary_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'evidence'
            shutil.copytree(EVIDENCE,dest)
            summary=dest/'raw'/'pilot_summary.csv'
            with summary.open(newline='') as stream:
                reader=csv.DictReader(stream)
                fields=reader.fieldnames
                rows=list(reader)
            rows[2]['median_window_rtt_ms']='150'
            with summary.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=fields)
                writer.writeheader();writer.writerows(rows)
            preservation=dest/'preservation.json'
            metadata=json.loads(preservation.read_text())
            metadata['files']['pilot_summary.csv']=hashlib.sha256(summary.read_bytes()).hexdigest()
            preservation.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError,'Numerical mismatch'):
                audit(dest)

if __name__=='__main__':
    unittest.main()
