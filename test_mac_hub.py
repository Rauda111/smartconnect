import csv
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from mac_hub.monitor import Measurement, parse_ping, ping_command, measure
from mac_hub.engine import Engine
from mac_hub.scenarios import scenario, NAMES
from mac_hub.run import record
from mac_hub.compare import summarize


def output(lines, sent=5, received=3):
    return '\n'.join(lines)+f'\n{sent} packets transmitted, {received} packets received, 40.0% packet loss\n'


class MacHubTests(unittest.TestCase):
    def test_parser_adjacent_only_and_missing(self):
        m=parse_ping(output(['64 bytes: icmp_seq=0 ttl=50 time=10.0 ms',
                             '64 bytes: icmp_seq=1 ttl=50 time=14.0 ms',
                             '64 bytes: icmp_seq=4 ttl=50 time=99.0 ms']), 'en0')
        self.assertEqual(m.loss,40)
        self.assertEqual(m.latency,41)
        self.assertEqual(m.rtt_variation,4)
        self.assertEqual(m.adjacent_pairs,1)
        m=parse_ping(output(['64 bytes: icmp_seq=0 ttl=50 time=10.0 ms'],1,1),'en0')
        self.assertIsNone(m.rtt_variation)
        m=parse_ping(output([],10,0),'en6')
        self.assertEqual((m.status,m.loss,m.latency),('no_reply',100,None))
        m=parse_ping('ping: bad interface','en6')
        self.assertIsNone(m.loss)
        self.assertEqual(m.status,'error')

    def test_bound_command_and_failures(self):
        command=ping_command('en6','1.1.1.1',10)
        self.assertEqual(command[:4],['/sbin/ping','-n','-b','en6'])
        self.assertNotIn('-I',command)
        for interface,target,count in [('en0;echo','1.1.1.1',10),('en0','-foo',10),('en0','1.1.1.1',0)]:
            with self.assertRaises(ValueError):
                ping_command(interface,target,count)
        with patch('mac_hub.monitor.platform.system',return_value='Darwin'), patch('mac_hub.monitor.subprocess.run',side_effect=subprocess.TimeoutExpired('ping',10)):
            self.assertIsNone(measure('en6').loss)
        result=subprocess.CompletedProcess([],1,'','permission denied')
        with patch('mac_hub.monitor.platform.system',return_value='Darwin'),patch('mac_hub.monitor.subprocess.run',return_value=result):
            self.assertEqual(measure('en6').status,'error')

    def test_scenarios_profiles_and_coverage(self):
        for app,coverage in [('video_call',.6),('file_download',.3)]:
            results={}
            for name in NAMES:
                engine=Engine(app)
                results[name]=[record(m,t,app,engine,'synthetic_fixture') for t,m in scenario(name)]
                self.assertTrue(all(abs(r['coverage']-coverage)<1e-9 for r in results[name]))
            self.assertEqual(set(r['recommended'] for r in results['stable']),{'wifi'})
            self.assertEqual(results['deteriorating_wifi'][-1]['recommended'],'cellular')
            self.assertEqual(results['wifi_recovery'][-1]['recommended'],'wifi')
            self.assertIn('cellular',[r['recommended'] for r in results['cellular_degradation'][:20]])
            self.assertEqual(results['cellular_degradation'][-1]['recommended'],'wifi')
            self.assertEqual(results['unavailable_paths'][25]['recommended'],'none')
            self.assertEqual(results['unavailable_paths'][15]['baseline'],'cellular')
            summary=summarize(pd.DataFrame(results['unavailable_paths']))
            self.assertEqual(summary.iloc[0].no_recommendation_cycles,10)
            self.assertLess(summary.iloc[1].latency_observed_cycles,60)

    def test_hold_dwell_outage_and_causality(self):
        m={'wifi':Measurement('en0','reachable',50,0), 'cellular':Measurement('en6','reachable',10,0)}
        e=Engine(dwell=30)
        self.assertEqual(e.step(m,0)['recommended'],'wifi')
        self.assertEqual(e.step(m,10)['recommended'],'wifi')
        self.assertEqual(e.step(m,20)['recommended'],'wifi')
        self.assertEqual(e.step(m,30)['recommended'],'cellular')
        with self.assertRaises(ValueError):
            e.step(m,30)
        m['cellular']=Measurement('en6',error='missing')
        self.assertEqual(e.step(m,31)['recommended'],'wifi')
        a,b=Engine(),Engine()
        full=list(scenario('wifi_recovery'))
        prefix=[a.step(m,t) for t,m in full[:20]]
        self.assertEqual(prefix,[b.step(m,t) for t,m in full][:20])

    def test_csv_roundtrip_and_dashboard(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.csv'
            e=Engine()
            records=[record(m,t,'video_call',e,'synthetic_fixture') for t,m in scenario('stable')]
            pd.DataFrame(records).to_csv(path,index=False)
            frame=pd.read_csv(path)
            self.assertTrue(frame.wifi_throughput.isna().all())
            self.assertEqual(summarize(frame).iloc[0].latency_mean,20)
            app=AppTest.from_file(str(Path('mac_hub/dashboard.py').resolve())).run()
            app.sidebar.text_input[0].set_value(str(path)).run()
            self.assertFalse(list(app.exception))
            self.assertTrue(any(m.value=='wifi' for m in app.metric))


if __name__=='__main__':
    unittest.main()
