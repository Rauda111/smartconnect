"""Offline preparation tests: no real HTTP, subprocesses, media or probes."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock,patch
from experiments.webrtc_continuity import jury_live_watch as watch

READY={'credentials_valid':True,'engine_ready':True,'wifi_available':True,'cellular_available':True,'media_or_probes_started':False,'http_sent':False}
class BridgePreparationTests(unittest.TestCase):
    def operator(self):
        return SimpleNamespace(credentials=Mock(return_value={'SMARTCONNECT_POLICY_TOKEN':'W'*48}),
            get=Mock(return_value=(409,b'{"error":"no_active_session"}')),collect=Mock())
    def grant(self,root):
        data={'approved':True,'grant_id':'offline-fixture','max_sessions':1,
            'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=20)).isoformat(),
            'max_echoes_per_session':360,'max_probe_seconds':270,'max_call_seconds':300,
            'target':'1.1.1.1','interfaces':['en0','en6']}
        p=root/'approved-demo.json';p.write_text(json.dumps(data));p.chmod(0o600)
    def test_arm_without_fresh_approval_is_inert(self):
        with patch.object(watch,'readiness') as checks,patch.object(watch,'load_operator') as operator,patch.object(watch.subprocess,'Popen') as child:
            with self.assertRaisesRegex(ValueError,'approval'):watch.arm_one_call()
            checks.assert_not_called();operator.assert_not_called();child.assert_not_called()
    def test_watcher_without_a_grant_does_not_touch_credentials_or_network(self):
        with tempfile.TemporaryDirectory() as d,patch.object(watch,'ROOT',Path(d)),patch.object(watch,'load_operator') as operator:
            self.assertEqual(watch.main(),0);operator.assert_not_called();self.assertFalse((Path(d)/'.state').exists())
    def test_approved_arm_requires_idle_room_and_starts_only_existing_watcher(self):
        with tempfile.TemporaryDirectory() as d,patch.object(watch,'ROOT',Path(d)),patch.object(watch,'readiness',return_value=READY),patch.object(watch,'load_operator',return_value=self.operator()) as loader,patch.object(watch.subprocess,'Popen') as child:
            result=watch.arm_one_call(True);grant=watch.approved_grant(Path(d)/'approved-demo.json')
            self.assertEqual(grant['max_sessions'],1);self.assertTrue(result['waiting_for_one_call'])
            self.assertFalse(result['browser_tabs_reopened']);self.assertEqual(grant['max_echoes_per_session'],360)
            command=child.call_args.args[0];self.assertIn('--kit-dir',command);self.assertFalse(any('open'==x or '.html' in x for x in command))
            loader.return_value.collect.assert_not_called()
    def test_busy_room_or_missing_interface_never_creates_a_grant(self):
        for ready in [READY,dict(READY,cellular_available=False)]:
            with tempfile.TemporaryDirectory() as d,patch.object(watch,'ROOT',Path(d)),patch.object(watch,'readiness',return_value=ready),patch.object(watch,'load_operator',return_value=self.operator()) as loader,patch.object(watch.subprocess,'Popen') as child:
                loader.return_value.get.return_value=(200,b'{"status":"active"}')
                with self.assertRaises(ValueError):watch.arm_one_call(True)
                self.assertFalse((Path(d)/'approved-demo.json').exists());child.assert_not_called()
    def test_spawn_failure_removes_unconsumed_approval(self):
        with tempfile.TemporaryDirectory() as d,patch.object(watch,'ROOT',Path(d)),patch.object(watch,'readiness',return_value=READY),patch.object(watch,'load_operator',return_value=self.operator()),patch.object(watch.subprocess,'Popen',side_effect=OSError):
            with self.assertRaises(OSError):watch.arm_one_call(True)
            self.assertFalse((Path(d)/'approved-demo.json').exists())
    def test_one_call_is_consumed_once_without_reopening_browser(self):
        with tempfile.TemporaryDirectory() as d,patch.object(watch,'ROOT',Path(d)),patch.object(watch,'load_operator',return_value=self.operator()) as loader,patch.object(watch.time,'sleep'):
            self.grant(Path(d));loader.return_value.get.return_value=(200,b'{"session_id":"fixture-session-private","policy_window":0}')
            self.assertEqual(watch.main(),0);self.assertEqual(watch.main(),0)
            loader.return_value.collect.assert_called_once_with(approved=True,wait_for_export=False)
            receipt=(Path(d)/'.state/approved-calls.json').read_text();self.assertNotIn('fixture-session-private',receipt)
    def test_invalid_receipt_fails_closed_before_collection(self):
        with tempfile.TemporaryDirectory() as d,patch.object(watch,'ROOT',Path(d)),patch.object(watch,'load_operator',return_value=self.operator()) as loader:
            root=Path(d);self.grant(root);(root/'.state').mkdir();(root/'.state/approved-calls.json').write_text('broken')
            self.assertEqual(watch.main(),1);loader.return_value.collect.assert_not_called();loader.return_value.get.assert_not_called()
if __name__=='__main__':unittest.main()
