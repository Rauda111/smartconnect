"""Offline download data-flow and explicit public decision-display contracts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mac_hub.competition.run import live, replay_rows, Session
from mac_hub.competition.dashboard import decision_view, public_requests, safe_view
from mac_hub.monitor import Measurement


class DownloadDisplayTests(unittest.TestCase):
    def collect(self, folder, profile='file_download', failed=None, cycles=4):
        clock=[0.]; order=[]
        def measure(interface,*args):
            return Measurement(interface,'reachable',20.,0., sent=10,received=10)
        def request(interface,target,execute,cancel):
            order.append(interface)
            start=clock[0];clock[0]+=.1
            return dict(status=failed if interface=='en6' and failed else 'success',source='actual_https',
                        requested_interface=interface,binding_index=11 if interface=='en0' else 21,
                        bytes_received=target.max_bytes,request_duration_ms=1000. if interface=='en0' else 100.,
                        start_epoch=start,end_epoch=clock[0],error='PRIVATE 192.168.0.1',local_ip='192.168.0.1')
        def wait(cancel,seconds):clock[0]+=seconds;return False
        with patch('mac_hub.competition.run.resolve',return_value=['1.1.1.1']),patch('mac_hub.competition.run.measure',side_effect=measure),patch('mac_hub.competition.run.request',side_effect=request),patch('mac_hub.competition.run.time.monotonic',side_effect=lambda:clock[0]),patch('mac_hub.competition.run.wait_for',side_effect=wait):
            live(folder,application=profile,cycles=cycles,pause=15)
        events=[json.loads(x) for x in (folder/'events.jsonl').read_text().splitlines()]
        rows=[r for r in events if r['event']=='completed_window']
        requests=[json.loads(x) for x in (folder/'requests.jsonl').read_text().splitlines()]
        return rows,requests

    def test_equal_predecision_transfers_bindings_units_and_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows,requests=self.collect(Path(tmp)/'download')
        self.assertEqual(len(requests),12)
        for row in rows:
            probes=row['calibration']
            self.assertEqual({x['bytes_received'] for x in probes.values()},{65536})
            self.assertEqual({x['requested_interface'] for x in probes.values()},{'en0','en6'})
            self.assertTrue(all(x['binding_index'] and x['source']=='actual_https' for x in probes.values()))
            self.assertAlmostEqual(probes['wifi']['goodput_mbps'],.524288)
            self.assertAlmostEqual(probes['cellular']['goodput_mbps'],5.24288)
            self.assertLessEqual(max(x['end_epoch'] for x in probes.values()),row['elapsed_seconds'])
            self.assertEqual(row['decision']['scoring_basis'],'bounded_goodput_utility_and_loss')
            for n in probes:
                quality=1-(20-1)/149
                utility=.8*min(1,probes[n]['goodput_mbps']/10)+.2*quality
                self.assertAlmostEqual(row['decision']['utility'][n],utility)
                self.assertAlmostEqual(row['decision']['details'][n]['score'],.5*utility+.5)
        self.assertEqual(rows[-1]['decision']['recommended'],'cellular')
        self.assertEqual(rows[-1]['outcome']['requested_interface'],'en6')
        for window in range(1,5):
            cal=[r['requested_interface'] for r in requests if r['window']==window and r['role']=='calibration']
            self.assertEqual(cal,['en0','en6'] if window%2 else ['en6','en0'])

    def test_video_and_download_rank_differently_on_same_icmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            video,req=self.collect(Path(tmp)/'video','video_call')
            download,_=self.collect(Path(tmp)/'download')
        self.assertEqual(len(req),4)
        self.assertTrue(all(r['decision']['recommended']=='wifi' for r in video))
        self.assertEqual(download[-1]['decision']['recommended'],'cellular')
        self.assertNotEqual(video[-1]['decision']['details']['cellular']['score'],download[-1]['decision']['details']['cellular']['score'])

    def test_failed_and_invalid_length_calibration_disable_goodput(self):
        for failure in ('timeout','binding_failed','request_failed'):
            with tempfile.TemporaryDirectory() as tmp:
                rows,requests=self.collect(Path(tmp)/'run',failed=failure,cycles=1)
            self.assertEqual(len(requests),3)  # two planned probes + selected outcome, no retry
            self.assertIsNone(rows[0]['calibration']['cellular']['goodput_mbps'])
            self.assertEqual(rows[0]['decision']['scoring_basis'],'icmp_rtt_and_loss')
            self.assertEqual(rows[0]['decision']['utility'],{})
        def wrong(interface,target,**kwargs):
            return dict(status='success',requested_interface=interface,binding_index=7,bytes_received=1,request_duration_ms=10.)
        with tempfile.TemporaryDirectory() as tmp,patch('mac_hub.competition.run.resolve',return_value=['1.1.1.1']),patch('mac_hub.competition.run.measure',side_effect=lambda i,*_:Measurement(i,'reachable',20.,0.)),patch('mac_hub.competition.run.request',side_effect=wrong):
            out=Path(tmp)/'run';live(out,application='file_download',cycles=1)
            requests=[json.loads(x) for x in (out/'requests.jsonl').read_text().splitlines()]
            self.assertTrue(all(r['status']=='invalid_body_length' and r['goodput_mbps'] is None for r in requests))

    def test_decision_inspector_hold_reset_and_privacy(self):
        rows=list(replay_rows())
        self.assertEqual(decision_view(rows[2])['qualifying'],'2/3')
        self.assertEqual(decision_view(rows[3])['qualifying'],'3/3')
        self.assertEqual(decision_view(rows[3])['candidate'],'cellular')
        self.assertEqual(decision_view(rows[2])['eligibility']['wifi'],'Observed breach')
        self.assertEqual(decision_view(rows[2])['margin'],.05)
        table=public_requests([dict(window=1,role='calibration',status='request_failed',requested_interface='en6',binding_index=21,error='PRIVATE',local_ip='192.168.0.1')])
        self.assertEqual(table[0]['requested_interface'],'en6')
        self.assertNotIn('PRIVATE',json.dumps(table));self.assertNotIn('192.168',json.dumps(table))
        s=Session('video_call');m={n:Measurement(i,'error') for n,i in [('wifi','en0'),('cellular','en6')]}
        row=rows[0].copy();row['decision']=s.decide(m,{n:{'status':'not_measured'} for n in m},1)
        self.assertEqual(set(decision_view(row)['eligibility'].values()),{'Unavailable / incomplete'})

    def test_requested_change_is_distinct_from_successful_bound_change(self):
        rows=list(replay_rows())[:3]
        for row,interface,status in zip(rows,['en0','en6','en0'],['success','timeout','success']):
            row['outcome']=dict(requested_interface=interface,status=status,binding_index=11)
        table=safe_view(rows)
        self.assertEqual([r['requested_interface_change'] for r in table],[False,True,True])
        self.assertTrue(all(not r['bound_request_interface_change'] for r in table))

    def test_live_download_binding_table_and_decision_inspection(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run';self.collect(out)
            with patch('mac_hub.competition.run.resolve',side_effect=AssertionError('DNS')), patch('mac_hub.competition.run.request',side_effect=AssertionError('network')):
                app=AppTest.from_file('mac_hub/competition/dashboard.py').run(timeout=30)
                app.sidebar.radio[0].set_value('Live monitoring').run(timeout=30)
                app.sidebar.text_input[0].set_value(str(out/'events.jsonl')).run(timeout=30)
                self.assertEqual(list(app.exception),[])
                metrics={x.label:x.value for x in app.metric}
                self.assertTrue(any('Cellular' in x.value and 'SELECTED INTERFACE' in x.value for x in app.markdown))
                self.assertEqual(metrics['Qualifying hold'],'3 / 3')
                self.assertEqual(metrics['Recommendation changes'],'1')
                requests=app.dataframe[-1].value
                self.assertEqual(len(requests),12)
                self.assertEqual(set(requests.interface),{'Wi-Fi','Cellular'})
                self.assertTrue(requests.binding_readback.all())
                self.assertNotIn('192.168',requests.to_string())
                app.slider[0].set_value(2).run(timeout=30)
                self.assertEqual(list(app.exception),[])
                self.assertEqual(next(x.value for x in app.metric if x.label=='Qualifying hold'),'1 / 3')

    def test_streamlit_decision_displays(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file('mac_hub/competition/dashboard.py').run(timeout=30)
        app.sidebar.radio[0].set_value('Historical policy replay').run(timeout=30)
        app.slider[0].set_value(3).run(timeout=30)
        self.assertEqual(list(app.exception),[])
        metrics={x.label:x.value for x in app.metric}
        self.assertEqual(metrics['Qualifying hold'],'2 / 3')
        self.assertEqual(metrics['Switching margin'],'0.050')
        self.assertTrue(any('Wi-Fi adjusted score' in x.value.columns for x in app.dataframe))
        self.assertIn('Candidate advantage',metrics)

if __name__=='__main__':unittest.main()
