"""Private Mac launcher backend. No camera/microphone or recording APIs."""
import argparse,json,os,socket,subprocess,sys,time
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parent
ORIGIN='https://smartconnect-prototype2-staging-4b5e878.onrender.com'
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def get(url,timeout=10):
    op=build_opener(ProxyHandler({}),NoRedirect())
    try:r=op.open(Request(url),timeout=timeout)
    except HTTPError as e:r=e
    with r:return r.code,r.read(1048576)
def staging_ready(attempts=4):
    for attempt in range(attempts):
        try:
            code,body=get(ORIGIN+'/launch.js',15)
            if code==200 and b'smartconnect.reader' in body and b'location.replace' in body:return True
            if code in (403,404):return False
        except Exception:pass
        if attempt+1<attempts:time.sleep(2)
    return False
def browser():
    for name in ['Google Chrome','Microsoft Edge']:
        if Path('/Applications',name+'.app').is_dir():return name
    raise RuntimeError('supported_browser_missing')
def open_browser(target):
    subprocess.run(['/usr/bin/open','-a',browser(),str(target)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def prototype_one():
    state=ROOT/'.state';state.mkdir(mode=0o700,exist_ok=True);receipt=state/'prototype1.json'
    try:
        old=json.loads(receipt.read_text());port=old['port'];pid=old['pid'];os.kill(pid,0)
        command=subprocess.check_output(['/bin/ps','-p',str(pid),'-o','command='],text=True)
        if str(ROOT/'runtime/mac_hub/competition/dashboard.py') in command and str(port) in command and get(f'http://127.0.0.1:{port}/_stcore/health')[0]==200:return f'http://127.0.0.1:{port}/'
    except Exception:pass
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    command=[sys.executable,'-B','-m','streamlit','run',str(ROOT/'runtime/mac_hub/competition/dashboard.py'),'--server.address','127.0.0.1','--server.port',str(port),'--browser.gatherUsageStats','false','--server.headless','true']
    proc=subprocess.Popen(command,cwd=ROOT/'runtime',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    receipt.write_text(json.dumps({'pid':proc.pid,'port':port}));receipt.chmod(0o600)
    for _ in range(40):
        if proc.poll() is not None:break
        try:
            if get(f'http://127.0.0.1:{port}/_stcore/health',1)[0]==200:return f'http://127.0.0.1:{port}/'
        except Exception:pass
        time.sleep(.25)
    raise RuntimeError('prototype1_unavailable')
def alert(message):
    # Fixed non-sensitive messages only; never show raw exception details.
    subprocess.run(['/usr/bin/osascript','-e','display alert "SmartConnect" message '+json.dumps(message)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('action',choices=['mac','prototype1','offline']);p.add_argument('--check-only',action='store_true');p.add_argument('--prepare-only',action='store_true');a=p.parse_args(argv);os.umask(0o077)
    if a.action=='mac':
        browser()
        if not staging_ready():
            if a.check_only:print(json.dumps({'staging_supports_new_launcher':False,'media_or_probes_started':False}));return 1
            alert('The prepared staging update is not available yet, or staging is waking. No call started. Try again after the approved deployment is complete.');return 1
        if a.check_only:print(json.dumps({'staging_supports_new_launcher':True,'browser_available':True,'media_or_probes_started':False}));return 0
        # The watcher exits immediately if no separate current probe grant exists.
        subprocess.Popen([sys.executable,str(ROOT/'jury_live_watch.py')],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        open_browser(ROOT/'PRIVATE-Mac-Launch.html')
    elif a.action=='prototype1':
        if a.check_only:
            import importlib.util
            print(json.dumps({'dashboard_present':(ROOT/'runtime/mac_hub/competition/dashboard.py').is_file(),'dependencies_available':all(importlib.util.find_spec(x) is not None for x in ['streamlit','numpy','pandas','altair'])}));return 0
        url=prototype_one()
        if a.prepare_only:print(json.dumps({'local_dashboard_url':url,'read_only':True,'probes_started':False}));return 0
        open_browser(url)
    else:
        movie=ROOT/'Offline-Demo/video/SmartConnect-Evidence-Edition.mp4'
        if a.check_only:print(json.dumps({'offline_video_present':movie.is_file()}));return 0
        subprocess.run(['/usr/bin/open',str(movie)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except Exception:
        alert('SmartConnect could not open this item. No new media or measurements were started. The existing demonstration and evidence are unchanged.');raise SystemExit(1)
