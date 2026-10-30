"""Offline Phase 4 contracts, fairness and failure behavior."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import pandas as pd
from mac_hub.monitor import Measurement
from mac_hub.phase4.policy import Controller, goodput
from mac_hub.phase4.run import run
from mac_hub.phase4.report import audit, summarize

class Phase4Tests(unittest.TestCase):
    def test_goodput_and_missing(self):
        self.assertEqual(goodput(dict(status='success',bytes_received=250000,request_duration_ms=200)),10)
        for status in ['timeout','binding_failed','cancelled','dry_run']:
            self.assertIsNone(goodput(dict(status=status,bytes_received=250000,request_duration_ms=200)))
        self.assertIsNone(goodput(dict(status='success',bytes_received=None,request_duration_ms=10)))

    def test_profiles_different_with_measured_goodput(self):
        m = {n: Measurement(interface=i,status='reachable',latency=20,loss=0) for n,i in [('wifi','en0'),('cellular','en6')]}
        p = {n: dict(status='success',bytes_received=250000,request_duration_ms=duration) for n,duration in [('wifi',2000),('cellular',200)]}
        video, download = Controller('video_call'), Controller('file_download')
        for now in [1,16,31,46]:
            v,d = video.step(m,p,now),download.step(m,p,now)
        self.assertEqual(v['recommended'],'wifi')
        self.assertEqual(d['recommended'],'cellular')
        p['wifi']['status']='timeout'
        d=download.step(m,p,47)
        self.assertEqual(d['scoring_basis'],'icmp_rtt_and_loss')
        self.assertEqual(d['utility'],{})
        m['wifi'].latency=None
        self.assertEqual(download.step(m,p,48)['recommended'],'cellular')
        m['cellular'].status='error'
        self.assertEqual(download.step(m,p,49)['recommended'],'none')

    def test_dry_run_no_network_and_balanced_pairs(self):
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.phase4.run.socket.getaddrinfo',side_effect=AssertionError('DNS')), patch('mac_hub.phase4.run.measure',side_effect=AssertionError('ping')):
            path=run(Path(tmp)/'dry',trials=2,cycles=2)
            manifest, rows, rounds=audit(path)
            self.assertEqual(manifest['mode'],'dry_run')
            self.assertFalse(rows.source.eq('actual_https').any())
            self.assertEqual(len(rounds),8)
            summarize(path)
            self.assertTrue((path/'outcomes.png').exists())
            # Evidence corruption must be detected, not silently displayed.
            with (path/'requests.csv').open('a') as f:
                f.write('corruption\n')
            with self.assertRaises(ValueError):
                audit(path)

    def test_bounds(self):
        for kw in [dict(trials=3),dict(size=0),dict(trials=8,cycles=12),dict(interval=0)]:
            with self.assertRaises(ValueError):
                run('/unused',**kw)

    def test_actual_mock_failure_recovery_and_timing(self):
        def fake(interface,target,execute,cancel):
            import time
            now=time.time()
            return dict(request_id=str(now),source='actual_https',status='timeout' if interface=='en6' else 'success',
                        requested_interface=interface,start_epoch=now,end_epoch=now+.001,request_duration_ms=1.,
                        bytes_received=target.max_bytes if interface=='en0' else None,egress_status='unverified')
        def monitor(interface,*args):
            return Measurement(interface=interface,status='reachable',latency=10,loss=0)
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.phase4.run.request',side_effect=fake), patch('mac_hub.phase4.run.measure',side_effect=monitor):
            # Use real wall completion in mock to preserve causal ordering.
            def wrapped(*args):
                row=fake(*args)
                import time
                row['end_epoch']=time.time()
                return row
            with patch('mac_hub.phase4.run.request',side_effect=wrapped):
                path=run(Path(tmp)/'mock',execute=True,trials=2,cycles=1,address='1.1.1.1')
            audit(path)
            summary, contrasts=summarize(path)
            self.assertEqual(summary.actual_attempts.sum(),8)
            self.assertEqual(summary.successes.sum(),8)
            self.assertTrue(contrasts.cluster_bootstrap_low.isna().all())

    def test_cancellation_preserves_partial_evidence(self):
        def cancelled(interface,target,execute,cancel):
            import time
            cancel.set()
            now=time.time()
            return dict(source='actual_https',status='cancelled',start_epoch=now,end_epoch=now,
                        requested_interface=interface,request_duration_ms=0.,bytes_received=None,
                        egress_status='unverified')
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.phase4.run.request',side_effect=cancelled), patch('mac_hub.phase4.run.measure',return_value=Measurement('en0')):
            path=run(Path(tmp)/'cancel',execute=True,trials=2,cycles=1,address='1.1.1.1')
            manifest,rows,rounds=audit(path)
            self.assertTrue(manifest['cancelled'])
            self.assertEqual(len(rows),1)
            self.assertTrue(rounds.empty)

    def test_dashboard_offline(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file('mac_hub/phase4/dashboard.py').run(timeout=15)
        self.assertFalse(list(app.exception))
        self.assertEqual(app.metric[2].value,'0')

    def test_recovery_hold_dwell_and_timing_validation(self):
        measurements={n:Measurement(i,status='reachable',latency=20,loss=0) for n,i in [('wifi','en0'),('cellular','en6')]}
        probes={n:dict(status='timeout') for n in measurements}
        c=Controller('video_call')
        self.assertEqual(c.step(measurements,probes,1)['recommended'],'wifi')
        measurements['wifi'].latency=130
        for t in [6,11,16]:
            self.assertEqual(c.step(measurements,probes,t)['recommended'],'wifi')
        self.assertEqual(c.step(measurements,probes,31)['recommended'],'cellular')
        measurements['cellular'].status='error'
        measurements['wifi'].latency=20
        self.assertEqual(c.step(measurements,probes,32)['recommended'],'wifi')
        with self.assertRaises(ValueError):
            c.step(measurements,probes,32)

    def test_summary_failure_gap_changes_and_signed_contrasts(self):
        rows=[]
        for trial in range(4):
            for cycle,network in enumerate(['wifi','cellular','none','wifi']):
                for policy in ['smartconnect','wifi_first']:
                    status='success' if cycle in (0,3) else 'timeout' if cycle==1 else 'no_eligible_path'
                    rows.append(dict(trial=trial,cycle=cycle,application='file_download',policy=policy,
                                     role='outcome',network=network,status=status,source='no_request' if cycle==2 else 'actual_https',
                                     end_epoch=trial*100+cycle*10+1,request_duration_ms=(100 if policy=='wifi_first' else 110) if status=='success' else None,
                                     goodput_mbps=(2 if policy=='wifi_first' else 3) if status=='success' else None))
        data=pd.DataFrame(rows)
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.phase4.report.audit',return_value=({'mode':'actual_requests','condition':'test'},data,pd.DataFrame())):
            summary,contrasts=summarize(tmp)
            smart=summary[summary.policy.eq('smartconnect')].iloc[0]
            self.assertEqual(smart.recommended_path_changes,4)
            self.assertEqual(smart.availability_transitions,8)
            self.assertEqual(smart.max_failed_slot_streak,2)
            self.assertEqual(smart.max_bracketed_failure_gap_ms,30000)
            self.assertEqual(smart.failures,4)
            self.assertEqual(smart.no_eligible_slots,4)
            self.assertEqual(contrasts.iloc[0].smart_minus_wifi_mean,10)
            self.assertEqual(contrasts.iloc[1].smart_minus_wifi_mean,1)
            self.assertTrue(contrasts.cluster_bootstrap_low.notna().all())

    def test_committed_observation_and_report_audit(self):
        from mac_hub.phase4.report import audit_products
        path=Path('mac_hub/phase4/evidence/stable_observation')
        manifest,rows,rounds=audit_products(path)
        self.assertEqual(len(rows),128)
        self.assertTrue(rows.status.eq('success').all())
        self.assertEqual(rows.bytes_received.sum(),13107200)
        self.assertEqual(len(rounds),32)
        self.assertTrue(rounds.smartconnect.eq('wifi').all())
        self.assertTrue(rounds.wifi_first.eq('wifi').all())
        self.assertTrue(rows.egress_status.eq('unverified').all())
        self.assertEqual(len(rows[rows.role.eq('probe')]),64)

    def test_dns_preparation_cancelled_and_timeout(self):
        from mac_hub.phase4.run import resolve
        cancel=threading.Event()
        cancel.set()
        with patch('mac_hub.phase4.run.socket.getaddrinfo',return_value=[]):
            with self.assertRaises(TimeoutError):
                resolve(cancel)
        blocked=threading.Event()
        with patch('mac_hub.phase4.run.socket.getaddrinfo',side_effect=lambda *args: blocked.wait(.2)):
            with self.assertRaises(TimeoutError):
                resolve(threading.Event(),timeout=.01)
            blocked.set()

    def test_published_result_tampering_detected(self):
        from mac_hub.phase4.report import audit_products
        with tempfile.TemporaryDirectory() as tmp:
            path=run(Path(tmp)/'plan',trials=2,cycles=1)
            summarize(path)
            with (path/'REPORT.md').open('a') as f:
                f.write('Fabricated improvement\n')
            with self.assertRaises(ValueError):
                audit_products(path)

if __name__=='__main__':
    unittest.main()
