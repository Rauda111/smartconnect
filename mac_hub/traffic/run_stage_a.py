"""Manual interface selection for Stage A only. No engine integration."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import threading
import time
from mac_hub.traffic.client import Target, request, target_dict

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true',help='opt in to real HTTPS requests (no admin needed)')
    parser.add_argument('--interfaces',nargs='+',default=['en0','en6','en0','en6'])
    parser.add_argument('--address',default='1.1.1.1')
    parser.add_argument('--server-name',default='one.one.one.one')
    parser.add_argument('--path',default='/cdn-cgi/trace')
    parser.add_argument('--timeout',type=float,default=10)
    parser.add_argument('--pause',type=float,default=1)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    target=Target(args.address,args.server_name,args.path,timeout=args.timeout)
    target.validate()
    if len(args.interfaces)>20 or not 0<=args.pause<=10:
        parser.error('At most 20 requests and pause 0..10s')
    import re
    if not all(re.fullmatch(r'en\d+',i) for i in args.interfaces):
        parser.error('Use enN interface names')
    args.output_dir.mkdir(parents=True,exist_ok=False)
    cancel=threading.Event()
    previous={sig:signal.signal(sig,lambda *_:cancel.set()) for sig in (signal.SIGINT,signal.SIGTERM)}
    manifest=dict(uid=os.getuid(),stage='A',mode='actual_https' if args.execute else 'dry_run',target=target_dict(target),
                  interfaces=args.interfaces,platform=platform.platform(),python=platform.python_version(),
                  started_epoch=time.time(),policy='manual sequence only; no SmartConnect integration',
                  source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
                  revision=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip())
    writer=None
    try:
        with (args.output_dir/'requests.csv').open('x',newline='') as stream:
            for interface in args.interfaces:
                if cancel.is_set():
                    break
                row=request(interface,target,args.execute,cancel)
                if writer is None:
                    writer=csv.DictWriter(stream,fieldnames=list(row))
                    writer.writeheader()
                writer.writerow(row)
                stream.flush()
                print(json.dumps(row),flush=True)
                if cancel.wait(args.pause):
                    break
    finally:
        manifest.update(ended_epoch=time.time(),cancelled=cancel.is_set())
        (args.output_dir/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        for sig,handler in previous.items():
            signal.signal(sig,handler)


if __name__=='__main__':
    main()
