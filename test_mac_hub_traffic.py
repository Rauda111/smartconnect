import csv
import hashlib
import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
from mac_hub.traffic.client import request, Target, IP_BOUND_IF
from mac_hub.traffic.capture import capture
from mac_hub.traffic.verify import packets, correlate, verify


def pcap(frames):
    data=struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,96,1)
    for timestamp,reverse,flags,payload in frames:
        src,dst=(bytes([192,0,2,1]),bytes([1,1,1,1]))
        sport,dport=50000,443
        if reverse:
            src,dst=dst,src
            sport,dport=dport,sport
        ip=struct.pack('!BBHHHBBH4s4s',0x45,0,40+len(payload),1,0,64,6,0,src,dst)
        tcp=struct.pack('!HHIIBBHHH',sport,dport,9000 if reverse else 1000,1001 if reverse else 0,0x50,flags,65535,0,0)
        frame=b'\x00'*12+b'\x08\x00'+ip+tcp+payload
        sec=int(timestamp)
        data+=struct.pack('<IIII',sec,round((timestamp-sec)*1e6),len(frame),len(frame))+frame
    return data


class TrafficTests(unittest.TestCase):
    def test_dry_run_has_no_socket_or_resolver(self):
        with patch('mac_hub.traffic.client.socket.socket') as factory,patch('socket.getaddrinfo') as dns:
            result=request('en6')
            factory.assert_not_called()
            dns.assert_not_called()
        self.assertEqual(result['status'],'dry_run')
        self.assertIsNone(result['request_duration_ms'])
        self.assertIsNone(result['verified_egress'])
        for target in (Target(address='127.0.0.1'),Target(path='/bad\r\nX: yes'),Target(timeout=float('nan'))):
            with self.assertRaises(ValueError):
                request('en0',target)
        with self.assertRaises(ValueError):
            request('en0;echo')

    def live_mocks(self):
        raw=MagicMock()
        raw.getsockopt.return_value=7
        raw.getsockname.return_value=('192.0.2.1',50000)
        tls=MagicMock()
        context=MagicMock()
        context.wrap_socket.return_value=tls
        response=MagicMock(status=200)
        response.read1.side_effect=[b'ok',b'']
        return raw,context,response

    def test_bound_tls_success_without_egress_claim(self):
        raw,context,response=self.live_mocks()
        with patch('mac_hub.traffic.client.platform.system',return_value='Darwin'),patch('socket.if_nametoindex',return_value=7),patch('socket.socket',return_value=raw),patch('ssl.create_default_context',return_value=context),patch('http.client.HTTPSConnection.getresponse',return_value=response),patch('socket.getaddrinfo') as dns:
            result=request('en6',execute=True)
            dns.assert_not_called()
        raw.setsockopt.assert_called_once_with(socket.IPPROTO_IP,IP_BOUND_IF,7)
        raw.connect.assert_called_once_with(('1.1.1.1',443))
        self.assertEqual(result['status'],'success')
        self.assertEqual(result['bytes_received'],2)
        self.assertIsNone(result['verified_egress'])
        self.assertEqual(result['egress_status'],'unverified')
        self.assertGreaterEqual(result['request_duration_ms'],0)

    def test_failed_binding_no_fallback(self):
        raw,context,response=self.live_mocks()
        for failure in ('setopt','readback','missing_interface'):
            raw.reset_mock()
            raw.setsockopt.side_effect=OSError('unsupported') if failure=='setopt' else None
            raw.getsockopt.return_value=8 if failure=='readback' else 7
            with patch('mac_hub.traffic.client.platform.system',return_value='Darwin'),patch('socket.if_nametoindex',side_effect=OSError('no path') if failure=='missing_interface' else None,return_value=7),patch('socket.socket',return_value=raw),patch('ssl.create_default_context',return_value=context):
                result=request('en6',execute=True)
            self.assertEqual(result['status'],'binding_failed')
            raw.connect.assert_not_called()

    def test_unavailable_timeout_recovery_and_cancel(self):
        for exception,status in [(OSError('unreachable'),'request_failed'),(TimeoutError('deadline'),'timeout')]:
            raw,context,response=self.live_mocks()
            raw.connect.side_effect=exception
            with patch('mac_hub.traffic.client.platform.system',return_value='Darwin'),patch('socket.if_nametoindex',return_value=7),patch('socket.socket',return_value=raw),patch('ssl.create_default_context',return_value=context):
                self.assertEqual(request('en6',execute=True)['status'],status)
        cancel=threading.Event()
        cancel.set()
        with patch('socket.socket') as factory:
            self.assertEqual(request('en6',execute=True,cancel=cancel)['status'],'cancelled')
            factory.assert_not_called()
        raw,context,response=self.live_mocks()
        with patch('mac_hub.traffic.client.platform.system',return_value='Darwin'),patch('socket.if_nametoindex',return_value=7),patch('socket.socket',return_value=raw),patch('ssl.create_default_context',return_value=context),patch('http.client.HTTPSConnection.getresponse',return_value=response):
            self.assertEqual(request('en6',execute=True)['status'],'success')
        raw,context,response=self.live_mocks()
        cancel.clear()
        def interrupted(*args):
            cancel.set()
            raise OSError('cancelled socket')
        raw.connect.side_effect=interrupted
        with patch('mac_hub.traffic.client.platform.system',return_value='Darwin'),patch('socket.if_nametoindex',return_value=7),patch('socket.socket',return_value=raw),patch('ssl.create_default_context',return_value=context):
            self.assertEqual(request('en6',execute=True,cancel=cancel)['status'],'cancelled')

    def test_capture_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp,patch('subprocess.Popen') as process:
            folder=Path(tmp)/'capture'
            self.assertEqual(capture(folder)['mode'],'dry_run')
            self.assertFalse(folder.exists())
            with self.assertRaises(PermissionError):
                capture(folder,execute=True)
            process.assert_not_called()

    def test_pcap_physical_correlation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'flow.pcap'
            path.write_bytes(pcap([(10.1,False,2,b''),(10.2,True,0x12,b''),(10.3,False,0x18,b'tls')]))
            parsed=list(packets(path))
            row=dict(request_id='r',requested_interface='en6',source='actual_https',local_ip='192.0.2.1',local_port='50000',destination_ip='1.1.1.1',destination_port='443',start_epoch='10',end_epoch='11')
            verified=correlate(row,{'en0':[],'en6':parsed})
            self.assertEqual(verified['verified_egress'],'en6')
            self.assertEqual(correlate(row,{'en0':parsed,'en6':parsed})['egress_status'],'mismatch_or_multiple_paths')
            self.assertEqual(correlate(row,{'en0':[],'en6':[]})['egress_status'],'unverified')
            self.assertEqual(correlate(row,{'en0':[],'en6':parsed[:2]})['egress_status'],'unverified')
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(ValueError):
                list(packets(path))

    def test_stage_a_gate_and_capture_drops(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rd,cd=root/'requests',root/'capture'
            rd.mkdir();cd.mkdir()
            rows=[]
            captures={'en0':[],'en6':[]}
            for i,n in enumerate(('en0','en6','en0','en6')):
                t=10+i*2
                captures[n].extend([(t+.1,False,2,b''),(t+.2,True,0x12,b''),(t+.3,False,0x18,b'tls')])
                rows.append(dict(request_id=str(i),requested_interface=n,source='actual_https',status='success',local_ip='192.0.2.1',local_port='50000',destination_ip='1.1.1.1',destination_port='443',start_epoch=t,end_epoch=t+1))
            with (rd/'requests.csv').open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            manifest=dict(status='complete',address='1.1.1.1',interfaces={},sha256={})
            for n,frames in captures.items():
                (cd/f'{n}.pcap').write_bytes(pcap(frames))
                (cd/f'{n}.stderr').write_text(f'listening on {n}, link-type EN10MB\n0 packets dropped by kernel\n')
                manifest['interfaces'][n]=dict(returncode=0,ready_epoch=9,stopped_epoch=20,command=['tcpdump','-i',n,'-p'])
                for path in (cd/f'{n}.pcap',cd/f'{n}.stderr'):
                    manifest['sha256'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            (cd/'capture.json').write_text(json.dumps(manifest))
            (rd/'manifest.json').write_text(json.dumps(dict(uid=501,source_sha256={'mac_hub/traffic/client.py':hashlib.sha256(Path('mac_hub/traffic/client.py').read_bytes()).hexdigest()})))
            self.assertTrue(verify(rd,cd,root/'verified')['stage_a_passed'])
            (cd/'en0.stderr').write_text('listening on en0, link-type EN10MB\n1 packets dropped by kernel\n')
            manifest['sha256']['en0.stderr']=hashlib.sha256((cd/'en0.stderr').read_bytes()).hexdigest()
            (cd/'capture.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                verify(rd,cd,root/'bad')

    def test_capture_start_failure_never_launches_requests(self):
        from io import StringIO
        with tempfile.TemporaryDirectory() as tmp,patch('os.geteuid',return_value=501),patch('subprocess.Popen') as launch:
            def fake(*args,**kwargs):
                process=MagicMock()
                process.stderr=StringIO('sudo: a password is required\n')
                process.poll.return_value=1
                process.returncode=1
                return process
            launch.side_effect=fake
            root=Path(tmp)
            with self.assertRaises(RuntimeError):
                capture(root/'capture',60,execute=True,approved=True,requests_dir=root/'requests')
            self.assertEqual(launch.call_count,2)
            self.assertFalse((root/'requests').exists())
            self.assertEqual(json.loads((root/'capture/capture.json').read_text())['status'],'failed')

    def test_outcome_report_and_read_only_dashboard(self):
        from mac_hub.traffic.report import summarize
        from streamlit.testing.v1 import AppTest
        from dataclasses import replace
        rows=[request('en0'),request('en6')]
        result=summarize(rows)
        self.assertTrue(all(r['actual_attempts']==0 and r['mean_success_duration_ms'] is None for r in result))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'requests.csv'
            with path.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            app=AppTest.from_file(str(Path('mac_hub/traffic/dashboard.py').resolve())).run(timeout=30)
            app.text_input[0].set_value(str(path)).run(timeout=30)
            self.assertFalse(list(app.exception))
            self.assertEqual(app.metric[0].value,'0')
            self.assertEqual(app.metric[3].value,'0')

    def test_capture_uses_concurrent_graceful_termination(self):
        # Both terminate signals must be sent before waiting on either child.
        from io import StringIO
        events=[]
        procs=[]
        with tempfile.TemporaryDirectory() as tmp,patch('os.geteuid',return_value=501),patch('subprocess.Popen') as launch:
            def make(cmd,**kwargs):
                name=cmd[cmd.index('-i')+1]
                p=MagicMock()
                p.stderr=StringIO(f'listening on {name}, link-type EN10MB\n0 packets dropped by kernel\n')
                p.poll.side_effect=lambda: None if not p.done else 0
                p.done=False
                def terminate():
                    events.append(('terminate',name));p.done=True;p.returncode=0
                p.terminate.side_effect=terminate
                p.wait.side_effect=lambda **_:events.append(('wait',name))
                procs.append(p)
                return p
            launch.side_effect=make
            # Drive duration without waiting five seconds.
            def immediate_thread(*args,**kwargs):
                thread=MagicMock()
                thread.start.side_effect=kwargs['target']
                return thread
            with patch('mac_hub.traffic.capture.threading.Thread',side_effect=immediate_thread),patch('mac_hub.traffic.capture.time.monotonic',side_effect=[0,0,10]):
                result=capture(Path(tmp)/'capture',5,execute=True,approved=True)
            self.assertEqual(result['status'],'complete')
            self.assertEqual(events[:2],[('terminate','en0'),('terminate','en6')])

    def test_gated_control_workload_dry_run_and_stability(self):
        from mac_hub.traffic.experiment import run
        with tempfile.TemporaryDirectory() as tmp,patch('socket.socket') as factory,patch('mac_hub.traffic.experiment.measure') as measure:
            output=Path(tmp)/'dry'
            run(output,mode='controlled',cycles=16,execute=False)
            factory.assert_not_called();measure.assert_not_called()
            with (output/'requests.csv').open() as stream:
                rows=list(csv.DictReader(stream))
            smart=[r for r in rows if r['policy']=='smartconnect']
            self.assertEqual(sum(r['recommended_change']=='True' for r in smart),2)
            self.assertEqual(smart[6]['requested_interface'],'en6')
            self.assertEqual(smart[12]['requested_interface'],'en0')
            self.assertTrue(all(r['source']=='dry_run' and not r['request_duration_ms'] for r in rows))
            self.assertEqual([r['policy'] for r in rows[:4]],['wifi_first','smartconnect','smartconnect','wifi_first'])
            with self.assertRaises(ValueError):
                run(Path(tmp)/'ungated',execute=True)
            self.assertFalse((Path(tmp)/'ungated').exists())

    def test_gate_rejects_stale_changed_binding_or_client(self):
        import time
        from mac_hub.traffic.experiment import gate
        with tempfile.TemporaryDirectory() as tmp,patch('socket.if_nametoindex',side_effect=lambda n:11 if n=='en0' else 21):
            path=Path(tmp)/'gate.json'
            valid=dict(stage_a_passed=True,verified_epoch=time.time(),capture_ended_epoch=time.time(),client_sha256=hashlib.sha256(Path('mac_hub/traffic/client.py').read_bytes()).hexdigest(),interface_indices={'en0':[11],'en6':[21]})
            path.write_text(json.dumps(valid));self.assertTrue(gate(path)['stage_a_passed'])
            for field,value in [('stage_a_passed',False),('client_sha256','wrong'),('capture_ended_epoch',0),('interface_indices',{'en0':[1],'en6':[21]})]:
                bad=dict(valid);bad[field]=value;path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    gate(path)

    def test_unavailable_input_and_failure_gap_metrics(self):
        from mac_hub.engine import Engine
        from mac_hub.monitor import Measurement
        from mac_hub.traffic.experiment import decide
        from mac_hub.traffic.compare import summarize
        m={'wifi':Measurement('en0',error='missing'),'cellular':Measurement('en6','reachable',30,0)}
        d,b=decide(Engine(),m,0)
        self.assertEqual((d['recommended'],b),('cellular','cellular'))
        m['cellular']=Measurement('en6',error='missing')
        d,b=decide(Engine(),m,0)
        self.assertEqual((d['recommended'],b),('none','none'))
        base=dict(policy='smartconnect',source='actual_https',recommended_change='False',request_duration_ms='100')
        rows=[dict(base,status='success',end_epoch='1'),dict(base,status='timeout',end_epoch='6'),dict(base,status='success',end_epoch='11')]
        result=summarize(rows)[1]
        self.assertEqual(result['successes'],2)
        self.assertEqual(result['timeouts'],1)
        self.assertEqual(result['max_bracketed_failure_gap_ms'],10000)
        self.assertIsNone(result['independently_confirmed_path_changes'])
        self.assertIsNone(result['confirmed_transition_delay_ms'])
        self.assertIsNone(summarize([rows[0],rows[2]])[1]['max_bracketed_failure_gap_ms'])

    def test_no_eligible_path_does_not_claim_an_http_attempt(self):
        from mac_hub.monitor import Measurement
        from mac_hub.traffic.experiment import run
        from mac_hub.traffic.client import target_dict
        from mac_hub.traffic.compare import summarize
        with tempfile.TemporaryDirectory() as tmp,patch('mac_hub.traffic.experiment.gate',return_value={'target':target_dict(Target())}),patch('mac_hub.traffic.experiment.measure',side_effect=lambda interface,*_:Measurement(interface,error='unavailable')),patch('socket.socket') as factory:
            root=Path(tmp);gatefile=root/'gate.json';gatefile.write_text('{}')
            out=root/'unavailable'
            run(out,mode='live',cycles=1,execute=True,stage_a=gatefile)
            factory.assert_not_called()
            with (out/'requests.csv').open() as stream:
                rows=list(csv.DictReader(stream))
            self.assertTrue(all(r['source']=='no_request' for r in rows))
            for r in summarize(rows):
                self.assertEqual(r['actual_attempts'],0)
                self.assertEqual(r['no_eligible_path_slots'],1)
                self.assertEqual(r['trailing_failure_streak'],1)

    def test_stage_b_dashboard_keeps_unverified_transitions_unknown(self):
        from mac_hub.traffic.experiment import run
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'dry'
            run(output,mode='controlled',cycles=16,execute=False,application='file_download')
            app=AppTest.from_file(str(Path('mac_hub/traffic/dashboard.py').resolve())).run(timeout=30)
            app.text_input[0].set_value(str(output/'requests.csv')).run(timeout=30)
            self.assertFalse(list(app.exception))
            self.assertTrue(any(m.label=='Recommended new-request path changes' and m.value=='2' for m in app.metric))
            self.assertTrue(any(m.label=='Independently confirmed path changes' and m.value=='Unverified' for m in app.metric))
