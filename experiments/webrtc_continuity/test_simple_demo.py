import importlib.util,json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from experiments.webrtc_continuity.prepare_simple_demo import private_form,windows_launcher,ORIGIN,mac_app
from experiments.webrtc_continuity.jury_live_watch import approved_grant
from experiments.webrtc_continuity.policy_bridge import active_session,BridgeError
class SimpleDemoTests(unittest.TestCase):
    def test_launch_file_uses_post_body_not_credential_url(self):
        for role in ('A','B'):
            page=private_form(ORIGIN,'R'*48,role)
            self.assertIn('method="post"',page);self.assertIn('action="'+ORIGIN+'/launch"',page)
            self.assertIn('type="hidden" name="reader"',page);self.assertNotIn('#token=',page);self.assertNotIn('?token=',page)
            self.assertNotIn('getUserMedia',page);self.assertNotIn('RTCPeerConnection',page)
    def test_launcher_avoids_security_bypass_and_secret_command_arguments(self):
        cmd=windows_launcher()
        self.assertIn('Invoke-WebRequest',cmd);self.assertIn('PRIVATE-Windows-Launch.html',cmd)
        for forbidden in ['ExecutionPolicy','Bypass','Disable','ignore-certificate','--disable-web-security','SMARTCONNECT_POLICY_TOKEN']:
            self.assertNotIn(forbidden,cmd)
        self.assertEqual(cmd.count('\n'),cmd.count('\r\n'))
    def test_mac_launcher_is_a_native_bundle_with_no_token_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);mac_app(root,'Mac demo','mac','/opt/anaconda3/bin/python')
            executable=root/'Mac demo.app/Contents/MacOS/SmartConnect';self.assertTrue(executable.stat().st_mode&0o100)
            script=executable.read_text();self.assertIn('jury_launch.py',script);self.assertNotIn('token=',script)
    def test_missing_or_expired_probe_grant_never_authorizes_work(self):
        now=datetime.now(timezone.utc)
        grant={'approved':True,'grant_id':'fixture','max_sessions':2,'expires_at':(now+timedelta(minutes=20)).isoformat(),'max_echoes_per_session':360,'max_probe_seconds':270,'max_call_seconds':300,'target':'1.1.1.1','interfaces':['en0','en6']}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'approval.json';self.assertIsNone(approved_grant(p,now))
            p.write_text(json.dumps(grant));p.chmod(0o600);self.assertIsNotNone(approved_grant(p,now))
            for key,value in [('approved',False),('max_sessions',3),('expires_at',(now+timedelta(seconds=200)).isoformat()),('target','example.invalid')]:
                p.write_text(json.dumps(dict(grant,**{key:value})));self.assertIsNone(approved_grant(p,now))
    def test_absolute_call_budget_is_distinct_from_rolling_idle_expiry(self):
        base={'status':'active','application':'video_call','session_id':'fixture','policy_window':0,'expires_in_seconds':180,'absolute_expires_in_seconds':350}
        result=active_session(lambda _:base,initial=True);self.assertEqual(result['absolute_expires_in_seconds'],350);self.assertEqual(result['expires_in_seconds'],180)
        for absolute in [361,100,None]:
            with self.assertRaises(BridgeError):active_session(lambda _:dict(base,absolute_expires_in_seconds=absolute))
if __name__=='__main__':unittest.main()
