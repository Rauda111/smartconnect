"""One local watcher for explicitly approved call budgets. Import is inert."""
import fcntl,hashlib,json,os,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
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
        import jury_operator as operator
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
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:raise SystemExit(1)
