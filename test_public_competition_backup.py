"""Offline checks for committed sanitized evidence, without private originals."""
import csv
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import unittest

ROOT=Path('mac_hub/competition/reports/20261104-final')

class PublicBackupTests(unittest.TestCase):
    def test_package_hashes_and_counts(self):
        m=json.loads((ROOT/'provenance.json').read_text())
        for name,h in m['output_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),h)
        with (ROOT/'windows.csv').open(newline='') as f:rows=list(csv.DictReader(f))
        with (ROOT/'requests.csv').open(newline='') as f:req=list(csv.DictReader(f))
        self.assertEqual(len(rows),46);self.assertEqual(len(req),44)
        natural=[r for r in rows if r['run'].startswith('smartconnect-natural-')]
        self.assertEqual(len(natural),6)
        self.assertTrue(all(r['selected']=='wifi' for r in natural))

    def test_no_private_identifiers_in_public_report_text(self):
        for p in ROOT.iterdir():
            if p.suffix not in ('.json','.csv','.md'):continue
            text=p.read_text()
            self.assertIsNone(re.search(r'\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b',text))
            for addr in re.findall(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])',text):
                try:ip=ipaddress.ip_address(addr)
                except ValueError:continue
                self.assertTrue(ip.is_global)
            for word in ('local_ip','local_port','binding_index','raw_output','/Users/','PRIVATE KEY'):
                self.assertNotIn(word,text)

    def test_download_outcomes_and_missingness(self):
        with (ROOT/'requests.csv').open(newline='') as f:all_rows=list(csv.DictReader(f))
        rows=[r for r in all_rows if r['run'].startswith('smartconnect-download-')]
        self.assertEqual(len(rows),24)
        self.assertEqual(sum(r['status']=='success' for r in rows),20)
        selected=[r for r in rows if r['role']=='selected_outcome']
        self.assertEqual([r['requested_interface'] for r in selected],['en0']*6+['en6']*2)
        self.assertEqual(selected[5]['status'],'timeout')
        self.assertEqual(selected[5]['completed_body_bytes'],'')
        self.assertEqual(selected[5]['bounded_goodput_Mbps'],'')
        self.assertTrue(all(r['physical_egress']=='unverified' for r in rows))

if __name__=='__main__':unittest.main()
