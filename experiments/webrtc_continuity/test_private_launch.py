"""Offline route security tests; synthetic credentials, no listeners or media."""
import io,json,unittest
from urllib.parse import urlencode
from experiments.webrtc_continuity.server import Handler,Broker
from experiments.webrtc_continuity.cloud_server import CloudHandler
READER='R'*48
WRITER='W'*48
HOST='smartconnect-fixture.onrender.com'
class LaunchTests(unittest.TestCase):
    def request(self,*,body=None,headers=None,route='/launch',method='POST',cloud=True):
        h=object.__new__(CloudHandler if cloud else Handler)
        h.server=type('Server',(),{'public_hostname':HOST,'server_address':('127.0.0.1',8766),'broker':Broker(READER,policy_token=WRITER)})()
        origin='https://'+HOST if cloud else 'http://127.0.0.1:8766'
        raw=urlencode(body or {'reader':READER,'role':'B'}).encode()
        h.headers={'Host':HOST if cloud else '127.0.0.1:8766','Origin':'null','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'document','Sec-Fetch-Site':'cross-site','Content-Type':'application/x-www-form-urlencoded','Content-Length':str(len(raw))}
        h.headers.update(headers or {});h.path=route;h.rfile=io.BytesIO(raw);result=[]
        h.reply=lambda status,body,content_type='application/json':result.append((status,body,content_type))
        (h.do_POST if method=='POST' else h.do_GET)()
        return result[0],h.server.broker
    def test_private_file_form_authenticates_without_a_secret_url_or_session(self):
        for cloud in (False,True):
            (status,body,kind),broker=self.request(cloud=cloud)
            self.assertEqual(status,200);self.assertEqual(kind,'text/html; charset=utf-8')
            self.assertIn(b'privateLaunch',body);self.assertIn(b'/launch.js',body)
            self.assertNotIn(b'#token=',body);self.assertNotIn(WRITER.encode(),body)
            self.assertIsNone(broker.session_id)
    def test_public_navigation_does_not_relax_api_origin_checks(self):
        for route in ('/','/index.html'):
            (status,_,_),_=self.request(route=route,method='GET');self.assertEqual(status,200)
        for route,method in [('/signal','GET'),('/policy/session','GET'),('/join','POST'),('/leave','POST'),('/policy','POST')]:
            (status,body,_),_=self.request(route=route,method=method);self.assertEqual(status,403);self.assertEqual(body['error'],'origin_not_allowed')
    def test_authentication_and_top_level_destination_are_required(self):
        for headers in ({'Host':'attacker.invalid'},{'Origin':'https://attacker.invalid'},{'Sec-Fetch-Dest':'iframe'},{'Sec-Fetch-Mode':'cors'},{'Origin':''}):
            (status,_,_),_=self.request(headers=headers);self.assertEqual(status,403)
        for reader in ('bad',WRITER):
            (status,body,_),_=self.request(body={'reader':reader,'role':'A'});self.assertEqual(status,403);self.assertNotIn(reader,json.dumps(body))
    def test_invalid_form_does_not_return_credentials(self):
        for data in ({'reader':READER,'role':'Z'},{'reader':[READER,READER],'role':'A'},{'reader':READER,'role':'B','extra':'x'}):
            (status,body,_),_=self.request(body=data);self.assertIn(status,(400,403));self.assertNotIn(READER,str(body))
        (status,_,_),_=self.request(headers={'Transfer-Encoding':'chunked'});self.assertEqual(status,400)
    def test_same_origin_form_also_works(self):
        (status,_,_),_=self.request(headers={'Origin':'https://'+HOST,'Sec-Fetch-Site':'same-origin'});self.assertEqual(status,200)
if __name__=='__main__':unittest.main()
