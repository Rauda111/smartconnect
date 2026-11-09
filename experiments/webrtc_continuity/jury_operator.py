"""Private competition operator wrapper. Import and check without --staging never send traffic."""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parent
RUNTIME=ROOT/'runtime'
sys.path.insert(0,str(RUNTIME))
ORIGIN='https://smartconnect-prototype2-staging-4b5e878.onrender.com'

def utc():return datetime.now(timezone.utc).isoformat()
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(data,f,indent=2);f.write('\n')

def credentials():
    config=dict(line.split('=',1) for line in (ROOT/'.env').read_text().splitlines() if line and not line.startswith('#'))
    if set(config)!={'SMARTCONNECT_SIGNAL_TOKEN','SMARTCONNECT_POLICY_TOKEN'} or any(not re.fullmatch('[A-Za-z0-9_-]{40,256}',v) for v in config.values()) or len(set(config.values()))!=2:
        raise ValueError('Invalid private credential configuration')
    if (ROOT/'.env').stat().st_mode & 0o077:raise ValueError('Credential file permissions must be owner-only')
    return config

def interface_status():
    from experiments.webrtc_continuity.media_path import parse_interfaces
    data=subprocess.run(['/sbin/ifconfig','-a'],capture_output=True,text=True,check=True,timeout=10).stdout
    parsed=parse_interfaces(data)
    return {name:bool(parsed.get(name,{}).get('active')) for name in ['en0','en6']}

def get(path,token=None,timeout=20):
    from experiments.webrtc_continuity.policy_bridge import NoRedirect
    if path not in ['/healthz','/','/app.js','/core.js','/style.css','/jury.js','/recording.js','/signal','/policy/session']:raise ValueError('Unsupported check')
    request=Request(ORIGIN+path,headers={'Authorization':'Bearer '+token} if token else {})
    opener=build_opener(ProxyHandler({}),NoRedirect())
    try:response=opener.open(request,timeout=timeout)
    except HTTPError as error:response=error
    with response:
        raw=response.read(1048577)
        if len(raw)>1048576:raise ValueError('Oversized staging response')
        return response.code,raw

def check(staging=False):
    from mac_hub.competition.run import Session
    config=credentials()
    states=interface_status()
    result={'checked_at':utc(),'interfaces_active':states,'engine_imports':Session('video_call').controller is not None,'private_credentials_valid':True,'http_only_check':staging,'venue_media_qualified':False,'media_or_icmp_started':False}
    result['launcher_files_present']=(all((ROOT/name).is_file() for name in ['SmartConnect-Mac-A.html','SmartConnect-Windows-B.html'])
        or all((ROOT/name).is_file() for name in ['PRIVATE-Mac-Launch.html','3 - Windows Laptop/PRIVATE-Windows-Launch.html']))
    if staging:
        healthy=False
        for attempt in range(3):
            try:
                code,raw=get('/healthz');healthy=code==200 and json.loads(raw)=={'status':'ok'}
            except Exception:healthy=False
            if healthy:break
            if attempt<2:print('Staging is waking or unavailable; bounded HTTPS retry.',flush=True);time.sleep(3)
        result['staging_healthy']=healthy
        if healthy:
            assets=True
            for path,name in [('/','index.html'),('/app.js','app.js'),('/core.js','core.js'),('/style.css','style.css'),('/jury.js','jury.js'),('/recording.js','recording.js')]:
                code,raw=get(path)
                assets=assets and code==200 and hashlib.sha256(raw).digest()==hashlib.sha256((RUNTIME/'experiments/webrtc_continuity'/name).read_bytes()).digest()
            result['application_assets_unchanged']=assets
            code,raw=get('/signal',config['SMARTCONNECT_SIGNAL_TOKEN'])
            result['reader_authenticated_without_join']=code==400 and json.loads(raw).get('error')=='invalid_peer'
            code,raw=get('/policy/session',config['SMARTCONNECT_POLICY_TOKEN'])
            result['writer_valid_and_room_idle']=code==409 and json.loads(raw).get('error')=='no_active_session'
    required=['engine_imports','private_credentials_valid','launcher_files_present']
    if staging:required+=['staging_healthy','application_assets_unchanged','reader_authenticated_without_join','writer_valid_and_room_idle']
    result['ready_for_operator_setup']=all(result.get(k) is True for k in required) and all(states.values())
    save(ROOT/'checks'/('check-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json'),result)
    print(json.dumps(result,indent=2),flush=True)
    print('HTTPS checks do not qualify the venue media path. No call or measurements started.',flush=True)
    return 0 if result['ready_for_operator_setup'] else 1

def remaining_budget(expires,elapsed=0):
    if isinstance(expires,bool) or not isinstance(expires,(int,float)) or not 0<expires<=360:raise ValueError('Invalid session lease')
    # Broker room lives at most 360 s; demo budget is 300 s from the first join.
    return max(0,min(270,float(expires)-60-3-elapsed))

def existing_exports():
    paths=list((Path.home()/'Downloads').glob('controlled-call-[AB]-*.json'))
    usb=Path('/Volumes/NO NAME/SmartConnect-Baseline/RETURN-EVIDENCE')
    if usb.is_dir():paths+=list(usb.glob('controlled-call-[AB]-*.json'))
    return paths

def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def import_evidence():
    pointer=ROOT/'last-run.json'
    if not pointer.exists():print('No new competition run is recorded. Existing evidence was not changed.');return 1
    run_dir=ROOT/'runs'/json.loads(pointer.read_text())['name']
    before=json.loads((run_dir/'approval-scope.json').read_text())['existing_export_hashes']
    imported=0
    for source in existing_exports():
        if source.stat().st_size>5000000:continue
        sha=fingerprint(source)
        if sha in before:continue
        try:data=json.loads(source.read_text())
        except (ValueError,OSError):continue
        if not isinstance(data,dict):continue
        # Imports are private and uncorrelated until both peer reports are analyzed.
        destination=run_dir/'peer-exports'/source.name
        destination.parent.mkdir(mode=0o700,exist_ok=True)
        if destination.exists():continue
        fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(source.read_bytes())
        imported+=1
    print(f'Imported {imported} new peer export(s) privately; cross-peer analysis is still required.')
    print('Windows observations remain in its Downloads folder. Transfer later only if cross-peer analysis is needed; recording and inventory remain optional.')
    return 0

def collect(approved=False,wait_for_export=True):
    # MUST precede credential access, session HTTP, journal creation and probes.
    if not approved:raise ValueError('Fresh separate approval is required')
    from experiments.webrtc_continuity.policy_bridge import Writer, active_session, run, BridgeError
    from mac_hub.monitor import measure
    config=credentials()
    if not all(interface_status().values()):raise ValueError('Both en0 and en6 must be active')
    writer=Writer(ORIGIN,config['SMARTCONNECT_POLICY_TOKEN'])
    requested=time.monotonic();scope=active_session(writer,initial=True)
    # Idle-heartbeat expiry is shorter than the absolute room lifetime. The call
    # budget is anchored to the first join, not to the rolling idle deadline.
    absolute=scope.get('absolute_expires_in_seconds',scope['expires_in_seconds'])
    duration=remaining_budget(absolute,time.monotonic()-requested)
    if duration<=16:raise ValueError('Too little approved call time remains')
    name='competition-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run_dir=ROOT/'runs'/name;run_dir.mkdir(mode=0o700,parents=True)
    save(run_dir/'approval-scope.json',{'operator_acknowledged_at':utc(),'max_call_seconds':300,'max_probe_seconds':270,'maximum_echoes':360,'target':'1.1.1.1','interfaces':['en0','en6'],'packet_capture':False,'network_interruption':False,'existing_export_hashes':[fingerprint(p) for p in existing_exports()]})
    pointer=ROOT/'last-run.json';temp=ROOT/'last-run.new.json';temp.write_text(json.dumps({'name':name}));temp.chmod(0o600);os.replace(temp,pointer)
    deadline=time.monotonic()+duration
    end_shared=requested+absolute-60
    lock=threading.Lock();reserved=0
    fd=os.open(run_dir/'probe-observations.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    journal=os.fdopen(fd,'w')
    def probe(interface,target,count):
        nonlocal reserved
        with lock:
            if interface not in ['en0','en6'] or target!='1.1.1.1' or count!=10 or reserved+count>360 or deadline-time.monotonic()<=count+6:raise BridgeError('Probe budget exhausted')
            reserved+=count
        stamp=utc();measurement=measure(interface,target,count)
        row={'started_at':stamp,'interface':interface,'sent':measurement.sent,'received':measurement.received,'latency_ms':measurement.latency,'loss_percent':measurement.loss,'status':measurement.status}
        with lock:journal.write(json.dumps(row,allow_nan=False)+'\n');journal.flush()
        return measurement
    result={'status':'bounded_stop'}
    try:
        print('Approved collector running; real unchanged engine, maximum 360 echoes. Ctrl+C stops it.',flush=True)
        result=run(execute=True,send=writer,cycles=18,count=10,pause=5,duration=max(1,deadline-time.monotonic()),output=str(run_dir/'policy-journal.jsonl'),cellular='en6',probe=probe)
        result['status']='completed'
    except KeyboardInterrupt:result={'status':'operator_stopped'}
    except BridgeError:result={'status':'bounded_stop','reason':'session_transport_freshness_or_time_limit'}
    except Exception:result={'status':'stopped','reason':'private_error_details_suppressed'}
    finally:
        journal.close();result.update({'maximum_echoes_reserved':reserved,'finished_at':utc(),'physical_handover_verified':False});save(run_dir/'collector-result.json',result)
    print(json.dumps(result),flush=True)
    print('End BOTH browser peers by the 300-second budget. Waiting briefly for the automatic Mac export.',flush=True)
    wait_until=min(time.monotonic()+40,end_shared+8) if wait_for_export else time.monotonic()
    try:
        while time.monotonic()<wait_until:time.sleep(min(1,wait_until-time.monotonic()))
    except KeyboardInterrupt:pass
    import_evidence()
    return 0

def main(argv=None):
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['check','collect','import-evidence']);p.add_argument('--staging',action='store_true');p.add_argument('--approved-300s-360echoes',action='store_true');a=p.parse_args(argv)
    try:
        if a.action=='check':return check(a.staging)
        if a.action=='collect':return collect(a.approved_300s_360echoes)
        return import_evidence()
    except Exception:
        print('Stopped safely: prerequisite, approval, credential, room or transport check failed. No private error details are printed.')
        return 1
if __name__=='__main__':raise SystemExit(main())
