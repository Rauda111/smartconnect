"""One local watcher for explicitly approved call budgets. Import is inert."""
import argparse,fcntl,hashlib,importlib.util,json,os,subprocess,sys,time,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def load_operator():
    # Use the already installed private bridge and unchanged Prototype 1 runtime.
    spec=importlib.util.spec_from_file_location('smartconnect_private_operator',ROOT/'jury_operator.py')
    operator=importlib.util.module_from_spec(spec);spec.loader.exec_module(operator)
    return operator
def readiness():
    operator=load_operator();operator.credentials()
    from mac_hub.competition.run import Session
    states=operator.interface_status()
    return {'credentials_valid':True,'engine_ready':Session('video_call').controller is not None,
            'wifi_available':states.get('en0') is True,'cellular_available':states.get('en6') is True,
            'media_or_probes_started':False,'http_sent':False}
def arm_one_call(approved=False):
    # This explicit gate precedes credential access, HTTP, files and processes.
    # The assistant invokes it only AFTER fresh call/probe approval. Existing
    # browser tabs remain open; no launcher or browser configuration is repeated.
    if not approved:raise ValueError('Fresh separate approval is required')
    checks=readiness()
    if not all(checks[k] for k in ['credentials_valid','engine_ready','wifi_available','cellular_available']):raise ValueError('Interface prerequisites unavailable')
    os.umask(0o077);state=ROOT/'.state';state.mkdir(exist_ok=True,mode=0o700)
    with (state/'watch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        operator=load_operator();credentials=operator.credentials()
        code,raw=operator.get('/policy/session',credentials['SMARTCONNECT_POLICY_TOKEN'],timeout=8)
        if code!=409 or json.loads(raw).get('error')!='no_active_session':raise ValueError('End the previous call before arming')
        grant={'approved':True,'grant_id':str(uuid.uuid4()),'max_sessions':1,
            'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=20)).isoformat(),
            'max_echoes_per_session':360,'max_probe_seconds':270,'max_call_seconds':300,
            'target':'1.1.1.1','interfaces':['en0','en6']}
        path=ROOT/'approved-demo.json';temporary=path.with_suffix('.new')
        temporary.write_text(json.dumps(grant));temporary.chmod(0o600);os.replace(temporary,path)
    try:
        subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--kit-dir',str(ROOT)],cwd=ROOT,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    except Exception:
        # Failed startup must not leave a grant that a later launcher can consume.
        if json.loads(path.read_text()).get('grant_id')==grant['grant_id']:path.unlink()
        raise
    return {'waiting_for_one_call':True,'browser_tabs_reopened':False,'max_echoes':360,'max_probe_seconds':270,'max_call_seconds':300}
def approved_grant(path,now=None):
    try:
        if path.stat().st_mode & 0o077:return None
        grant=json.loads(path.read_text());now=now or datetime.now(timezone.utc)
        expiry=datetime.fromisoformat(grant['expires_at'])
        if (grant.get('approved') is not True or not isinstance(grant.get('grant_id'),str)
                or len(grant['grant_id'])>80 or not grant['grant_id']
                or type(grant.get('max_sessions')) is not int or not 1<=grant['max_sessions']<=2
                or not 300<=(expiry-now).total_seconds()<=3600
                or grant.get('max_echoes_per_session')!=360 or grant.get('max_probe_seconds')!=270
                or grant.get('max_call_seconds')!=300 or grant.get('target')!='1.1.1.1'
                or grant.get('interfaces')!=['en0','en6']):return None
        return grant
    except Exception:return None
def main():
    # No credentials, polling or probes without a fresh separately approved grant.
    grant=approved_grant(ROOT/'approved-demo.json')
    if not grant:return 0
    os.umask(0o077);state=ROOT/'.state';state.mkdir(exist_ok=True,mode=0o700)
    with (state/'watch.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return 0
        operator=load_operator()
        credentials=operator.credentials();receipt=state/'approved-calls.json'
        try:used=json.loads(receipt.read_text()) if receipt.exists() else {}
        except Exception:return 1
        if used and (not isinstance(used,dict) or not isinstance(used.get('session_fingerprints'),list)
                     or any(not isinstance(x,str) or len(x)!=64 for x in used['session_fingerprints'])):return 1
        if used.get('grant_id')!=grant['grant_id']:used={'grant_id':grant['grant_id'],'session_fingerprints':[]}
        while len(used['session_fingerprints'])<grant['max_sessions']:
            current=approved_grant(ROOT/'approved-demo.json')
            if not current or current['grant_id']!=grant['grant_id']:break
            try:
                code,raw=operator.get('/policy/session',credentials['SMARTCONNECT_POLICY_TOKEN'],timeout=8);reply=json.loads(raw)
                identity=reply.get('session_id');fingerprint=hashlib.sha256(identity.encode()).hexdigest() if isinstance(identity,str) else None
                if code==200 and reply.get('policy_window')==0 and fingerprint and fingerprint not in used['session_fingerprints']:
                    used['session_fingerprints'].append(fingerprint)
                    temporary=receipt.with_suffix('.new');temporary.write_text(json.dumps(used));temporary.chmod(0o600);os.replace(temporary,receipt)
                    operator.collect(approved=True,wait_for_export=False)
            except Exception:
                # No raw credential, URL, session identifier or probe errors.
                pass
            time.sleep(2)
    return 0
def cli(argv=None):
    global ROOT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit-dir',type=Path)
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--check-only',action='store_true');mode.add_argument('--arm-one-call',action='store_true')
    parser.add_argument('--approved-300s-360echoes',action='store_true')
    args=parser.parse_args(argv)
    if args.kit_dir:ROOT=args.kit_dir.resolve()
    if args.check_only:
        checks=readiness();print(json.dumps(checks));return 0 if all(checks[k] for k in ['credentials_valid','engine_ready','wifi_available','cellular_available']) else 1
    if args.arm_one_call:print(json.dumps(arm_one_call(args.approved_300s_360echoes)));return 0
    return main()
if __name__=='__main__':
    try:raise SystemExit(cli())
    except Exception:
        print('Bridge preparation stopped: approval, idle room, interface, credential or watcher check failed. Private details suppressed.')
        raise SystemExit(1)
