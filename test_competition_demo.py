"""Offline EDGE integration tests; real networking is mocked or forbidden."""
import json
from pathlib import Path
import ssl
import tempfile
import threading
import unittest
from unittest.mock import patch

from mac_hub.monitor import Measurement
from mac_hub.competition.run import Session, replay_rows, live, diagnostic
from mac_hub.competition.dashboard import safe_view, read_events


def paths(w=20., c=35., loss=0.):
    return {'wifi': Measurement('en0', 'reachable', w, loss),
            'cellular': Measurement('en6', 'reachable', c, 0.)}

PROBES = {n: {'status': 'not_measured'} for n in ('wifi', 'cellular')}


class CompetitionTests(unittest.TestCase):
    def test_historical_replay_no_network(self):
        with patch('socket.socket', side_effect=AssertionError('network')), patch('socket.getaddrinfo', side_effect=AssertionError('DNS')), patch('mac_hub.competition.run.measure', side_effect=AssertionError('probe')), patch('mac_hub.competition.run.request', side_effect=AssertionError('request')):
            a = list(replay_rows()); b = list(replay_rows())
        self.assertEqual(a, b)
        self.assertEqual(len(a), 18)
        self.assertEqual([r['window'] for r in a if r['decision']['direct_recommendation_change']], [4, 18])
        self.assertTrue(all(r['outcome'] is None and r['location_stage'] is None for r in a))
        self.assertTrue(a[14]['diagnostics']['wifi']['rtt_reply_count_mismatch'])

    def test_hold_dwell_recovery_and_flapping(self):
        s = Session('video_call')
        self.assertEqual(s.decide(paths(), PROBES, 1)['recommended'], 'wifi')
        for t in (2,3,4):
            self.assertEqual(s.decide(paths(100.), PROBES, t)['recommended'], 'wifi')
        self.assertEqual(s.decide(paths(100.), PROBES, 31)['recommended'], 'cellular')
        for i,t in enumerate(range(32,40)):
            s.decide(paths(20. if i%2 else 100.), PROBES, t)
        self.assertEqual(s.controller.engine.current, 'cellular')
        for t in (61,62,63): d=s.decide(paths(), PROBES,t)
        self.assertEqual(d['recommended'],'wifi')

    def test_unavailable_and_missing_metrics(self):
        for bad in (Measurement('en0', 'no_reply', None,100.), Measurement('en0','error'), Measurement('en0','reachable',None,0.)):
            s=Session('video_call'); m=paths();m['wifi']=bad
            self.assertEqual(s.decide(m,PROBES,1)['recommended'],'cellular')
        s=Session('video_call');m={n:Measurement(i,'error') for n,i in [('wifi','en0'),('cellular','en6')]}
        self.assertEqual(s.decide(m,PROBES,1)['recommended'],'none')

    def test_new_flow_evidence_never_claims_physical_handover(self):
        s=Session('video_call')
        def r(i,status='success'): return dict(requested_interface=i,status=status,binding_index=7)
        self.assertFalse(s.outcome(r('en0'))['successful_bound_request_interface_change'])
        self.assertFalse(s.outcome(r('en6','timeout'))['successful_bound_request_interface_change'])
        d=s.outcome(r('en6'))
        self.assertTrue(d['successful_bound_request_interface_change'])
        self.assertIsNone(d['physical_new_flow_change']);self.assertIsNone(d['existing_session_handover'])

    def test_live_mocked_binding_failure_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.competition.run.resolve', return_value=['1.1.1.1']), patch('mac_hub.competition.run.measure',side_effect=lambda i,*_:paths()['wifi' if i=='en0' else 'cellular']), patch('mac_hub.competition.run.request',return_value=dict(status='binding_failed',source='actual_https',requested_interface='en0',binding_index=None)) as req:
            out=Path(tmp)/'run';live(out,cycles=1)
            self.assertEqual(req.call_count,1)
            self.assertEqual(req.call_args.args[0],'en0')
            self.assertEqual(read_events(out/'events.jsonl')[-1]['outcome']['status'],'binding_failed')
            with self.assertRaises(FileExistsError):live(out,cycles=1)

    def test_tls_blocked_and_cancelled_no_fallback(self):
        from mac_hub.traffic.client import request, BoundHTTPS
        for error in (ssl.SSLCertVerificationError('bad certificate'),TimeoutError('blocked')):
            with patch.object(BoundHTTPS,'connect',side_effect=error),patch('socket.socket',side_effect=AssertionError('real socket')):
                r=request('en6',execute=True)
                self.assertNotEqual(r['status'],'success');self.assertEqual(r['requested_interface'],'en6')
        cancel=threading.Event();cancel.set()
        with patch('socket.socket',side_effect=AssertionError('socket')):
            self.assertEqual(request('en0',execute=True,cancel=cancel)['status'],'cancelled')

    def test_bounds_and_cancellation_manifest(self):
        for kwargs in [dict(cycles=31),dict(count=31),dict(pause=float('nan')),dict(size=9999999)]:
            with self.assertRaises(ValueError):live('/unused',**kwargs)
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.competition.run.resolve',side_effect=TimeoutError('DNS preparation')):
            out=Path(tmp)/'run'
            with self.assertRaises(TimeoutError):live(out,cycles=1)
            self.assertEqual(json.loads((out/'manifest.json').read_text())['run_error_type'],'TimeoutError')

    def test_public_display_allowlist(self):
        r=list(replay_rows())[0];r['inputs']['wifi']['raw_output']='SECRET 192.168.0.1'
        r['outcome']=dict(status='request_failed',error='SECRET',local_ip='192.168.0.1')
        self.assertNotIn('SECRET',json.dumps(safe_view([r])))
        self.assertNotIn('192.168',json.dumps(safe_view([r])))

    def test_partial_append_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'events.jsonl';p.write_text('{"ok":1}\n{"par')
            self.assertEqual(read_events(p),[{'ok':1}])
            p.write_text('{bad}\n')
            with self.assertRaises(ValueError):read_events(p)
            p.write_text('{bad}\n{"ok":1}\n')
            with self.assertRaises(ValueError):read_events(p)

    def test_runner_cancellation_preserves_outcome(self):
        def cancel_request(interface, target, execute, cancel):
            cancel.set()
            return dict(status='cancelled', source='actual_https', requested_interface=interface, binding_index=7)
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.competition.run.resolve', return_value=['1.1.1.1']), patch('mac_hub.competition.run.measure', side_effect=lambda i,*_:paths()['wifi' if i=='en0' else 'cellular']), patch('mac_hub.competition.run.request', side_effect=cancel_request) as req:
            out=Path(tmp)/'run';live(out, cycles=6)
            self.assertEqual(req.call_count,1)
            m=json.loads((out/'manifest.json').read_text())
            self.assertTrue(m['cancelled'])
            self.assertEqual(m['completed_windows'],1)
            self.assertEqual(read_events(out/'events.jsonl')[-1]['outcome']['status'],'cancelled')

    def test_no_eligible_path_sends_no_request(self):
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.competition.run.resolve',return_value=['1.1.1.1']), patch('mac_hub.competition.run.measure',side_effect=lambda i,*_:Measurement(i,'error')), patch('mac_hub.competition.run.request',side_effect=AssertionError('request')):
            out=Path(tmp)/'run';live(out,cycles=1)
            self.assertEqual(read_events(out/'events.jsonl')[-1]['outcome']['status'],'no_request')
            self.assertEqual((out/'requests.jsonl').read_text(),'')

    def test_download_actual_mocked_calibration_and_state(self):
        def fake(interface,target,execute,cancel):
            return dict(status='success',source='actual_https',requested_interface=interface,
                        binding_index=7,bytes_received=target.max_bytes,request_duration_ms=100.)
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.competition.run.resolve',return_value=['1.1.1.1']), patch('mac_hub.competition.run.measure',side_effect=lambda i,*_:paths()['wifi' if i=='en0' else 'cellular']), patch('mac_hub.competition.run.request',side_effect=fake) as req:
            out=Path(tmp)/'run';live(out,application='file_download',cycles=1)
            self.assertEqual(req.call_count,3)
            row=read_events(out/'events.jsonl')[-1]
            self.assertEqual(row['decision']['scoring_basis'],'bounded_goodput_utility_and_loss')
            self.assertTrue(row['flow_evidence']['successful_bound_request'])

    def test_certificate_failure_after_binding(self):
        from test_mac_hub_traffic import TrafficTests
        from mac_hub.traffic.client import request
        raw, context, response = TrafficTests().live_mocks()
        context.wrap_socket.return_value.do_handshake.side_effect=ssl.SSLCertVerificationError('untrusted')
        with patch('mac_hub.traffic.client.platform.system',return_value='Darwin'), patch('socket.if_nametoindex',return_value=7), patch('socket.socket',return_value=raw), patch('ssl.create_default_context',return_value=context):
            result=request('en6',execute=True)
        self.assertEqual(result['phase'],'tls')
        self.assertEqual(result['status'],'request_failed')
        self.assertEqual(raw.connect.call_count,1)
        self.assertEqual(result['requested_interface'],'en6')

    def test_live_dashboard_failure_and_privacy(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as tmp, patch('mac_hub.competition.run.resolve',return_value=['1.1.1.1']), patch('mac_hub.competition.run.measure',side_effect=lambda i,*_:paths()['wifi' if i=='en0' else 'cellular']), patch('mac_hub.competition.run.request',return_value=dict(status='request_failed',source='actual_https',requested_interface='en0',binding_index=7,local_ip='192.168.7.1',error='SECRET')):
            out=Path(tmp)/'run';live(out,cycles=1)
            app=AppTest.from_file('mac_hub/competition/dashboard.py').run(timeout=30)
            app.sidebar.radio[0].set_value('Live monitoring').run(timeout=30)
            app.sidebar.text_input[0].set_value(str(out/'events.jsonl')).run(timeout=30)
            self.assertEqual(list(app.exception),[])
            self.assertTrue(any('Selected request failed' in x.value for x in app.error))
            display=' '.join(x.value for kind in [app.markdown,app.error,app.info,app.caption] for x in kind)
            self.assertNotIn('SECRET',display)
            self.assertNotIn('192.168.7.1',display)

    def test_dashboard_historical(self):
        from streamlit.testing.v1 import AppTest
        with patch('mac_hub.competition.run.request',side_effect=AssertionError('network')):
            app=AppTest.from_file('mac_hub/competition/dashboard.py').run(timeout=30)
        self.assertEqual(list(app.exception),[])
        app.sidebar.radio[0].set_value('Historical policy replay').run(timeout=30)
        self.assertTrue(any('HISTORICAL' in x.value for x in app.caption))
        app.slider[0].set_value(18).run(timeout=30)
        self.assertEqual(list(app.exception),[])
        self.assertTrue(any(x.label=='Recommendation changes' and x.value=='2' for x in app.metric))

if __name__=='__main__': unittest.main()
