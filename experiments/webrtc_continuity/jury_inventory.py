"""Read-only OS inventory for local browser matching. No probes or route changes."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.webrtc_continuity.media_path import parse_interfaces

def snapshot(raw=None):
    if raw is None:
        if sys.platform!='darwin':raise ValueError('Mac inventory requires macOS')
        raw=subprocess.run(['/sbin/ifconfig','-a'],capture_output=True,text=True,timeout=10,check=True).stdout
    interfaces=parse_interfaces(raw)
    return {'schema':1,'kind':'interface_inventory','platform':'macos','role':'A',
            'captured_at':datetime.now(timezone.utc).isoformat(),
            'interfaces':[{'id':name,'active':bool(interfaces.get(name,{}).get('active')),
                           'addresses':[str(ip) for ip in interfaces.get(name,{}).get('addresses',[])],
                           'network':'wifi' if name=='en0' else 'cellular'} for name in ['en0','en6']]}

def write_current(path,data):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    # Keep the inode/path stable for the browser's read-only file handle. A reader
    # seeing a partial write rejects JSON and shows UNKNOWN until its next read.
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    os.fchmod(fd,0o600)
    with os.fdopen(fd,'w') as f:json.dump(data,f);f.flush()

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path.home()/'SmartConnectPrivate'/'current-interfaces.json')
    p.add_argument('--duration',type=int,default=420)
    p.add_argument('--once',action='store_true')
    a=p.parse_args(argv)
    if not 1<=a.duration<=420:p.error('Duration must be 1..420 seconds')
    os.umask(0o077);a.output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    history=a.output.parent/('PRIVATE-inventory-A-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.jsonl')
    fd=os.open(history,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    end=time.monotonic()+a.duration;count=0
    try:
        with os.fdopen(fd,'w') as f:
            while time.monotonic()<end:
                data=snapshot();write_current(a.output,data);f.write(json.dumps(data)+'\n');f.flush();count+=1
                if a.once:break
                time.sleep(min(5,max(0,end-time.monotonic())))
        print(json.dumps({'inventory_samples':count,'addresses_printed':False,'network_traffic_sent':False,'interfaces_changed':False}))
    except KeyboardInterrupt:print('Local inventory stopped; no network changes made.')
    except Exception:print('Inventory unavailable; private error details suppressed.');return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
