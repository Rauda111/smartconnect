"""Offline evidence, privacy and rendered Streamlit regression checks."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from mac_hub.competition.dashboard_data import recorded, request_table, project, REPORT
from mac_hub.competition.run import replay_rows
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent/'mac_hub/competition/dashboard.py')

class DashboardTests(unittest.TestCase):
    def test_exact_recording_and_missing_metrics(self):
        rows, requests = recorded()
        self.assertEqual([r['selected'] for r in rows], ['wifi']*6+['cellular']*2)
        self.assertEqual(rows[5]['selected_request_status'], 'timeout')
        self.assertIsNone(rows[6]['wifi_latency'])
        self.assertIsNone(rows[7]['wifi_latency'])
        self.assertEqual(rows[6]['wifi_received'], 0)
        self.assertIn('Availability exception', rows[6]['reason'])
        self.assertEqual(rows[6]['selected_request_ms'],224.69495807308704)
        self.assertEqual(rows[7]['selected_request_ms'],193.06245795451105)
        table = request_table(requests)
        self.assertEqual(sum(r['status']=='success' for r in table),20)
        self.assertEqual(sum(r['role']=='calibration' for r in table),16)
        self.assertEqual([r['completed_body_bytes'] for r in table if r['window']>=7 and r['role']=='selected_outcome'],[65536,65536])

    def test_tamper_missing_and_privacy(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            for name in ('package_sha256.json','windows.csv','requests.csv','provenance.json'):
                shutil.copy(REPORT/name,dest/name)
            (dest/'windows.csv').write_text('broken')
            with self.assertRaises(ValueError): recorded(dest)
        r = dict(window=1,role='PRIVATE 192.168.1.1',requested_interface='PRIVATE',status='PRIVATE',error='PRIVATE',local_ip='192.168.1.1')
        self.assertNotIn('PRIVATE',json.dumps(request_table([r])))
        self.assertNotIn('192.168',json.dumps(request_table([r])))

    def test_historical_changes(self):
        raw = list(replay_rows())
        self.assertEqual([r['window'] for r in raw if r['decision']['direct_recommendation_change']],[4,18])
        self.assertTrue(all(project(r)['selected_request_status']=='not_collected' for r in raw))

    def test_render_modes_and_windows_offline(self):
        with patch('socket.getaddrinfo',side_effect=AssertionError('No DNS')), patch('mac_hub.competition.run.request',side_effect=AssertionError('No HTTPS')), patch('mac_hub.competition.run.measure',side_effect=AssertionError('No probes')):
            app = AppTest.from_file(APP).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            for window in (6,7,8):
                app.slider[0].set_value(window).run()
                self.assertFalse(app.exception)
                if window==6: self.assertTrue(any('timeout' in e.value for e in app.error))
                else: self.assertTrue(any('Network unavailable' in e.value for e in app.error))
            app.radio[0].set_value('Historical policy replay').run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            app.selectbox[0].set_value('file_download').run()
            self.assertFalse(app.exception)
            app.radio[0].set_value('Live monitoring').run()
            self.assertTrue(any('Evidence unavailable' in e.value for e in app.error))

    def test_live_empty_malformed_fresh_stale_and_finished(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'events.jsonl'
            app=AppTest.from_file(APP).run(timeout=30)
            app.radio[0].set_value('Live monitoring').run()
            app.text_input[0].set_value(str(path)).run()
            path.write_text('')
            app.run()
            self.assertTrue(any('Waiting' in x.value for x in app.info))
            path.write_text('bad\n')
            app.run()
            self.assertTrue(any('Evidence unavailable' in x.value for x in app.error))
            raw=list(replay_rows())[0]
            from datetime import datetime, timezone
            raw.update(mode='live',event='completed_window',timestamp=datetime.now(timezone.utc).isoformat())
            path.write_text(json.dumps(raw)+'\n')
            app.run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            raw['timestamp']='2020-01-01T00:00:00+00:00'
            path.write_text(json.dumps(raw)+'\n')
            (path.parent/'manifest.json').write_text(json.dumps(dict(output_hashes={},run_error_type='PRIVATE')))
            app.run()
            self.assertTrue(any('Stale' in x.value for x in app.error))
            self.assertTrue(any('finished' in x.value for x in app.warning))
            self.assertTrue(any('stopped' in x.value for x in app.error))
            self.assertNotIn('PRIVATE',str(app))

if __name__=='__main__': unittest.main()
