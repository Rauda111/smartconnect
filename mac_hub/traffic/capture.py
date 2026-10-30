"""Separate bounded packet-capture helper. Dry-run default. Requires approval.

Only tcpdump runs elevated; the Python process and HTTP client remain ordinary
user processes. No password prompt: approve first, then authenticate sudo in
Terminal yourself if needed. Never change /dev/bpf permissions.
"""
import argparse
import hashlib
import ipaddress
import json
import os
import sys
from pathlib import Path
import signal
import subprocess
import threading
import time


def command(interface, address, path):
    if interface not in ('en0','en6'):
        raise ValueError('Stage A capture is restricted to en0/en6')
    ipaddress.IPv4Address(address)
    return ['/usr/bin/sudo','-n','/usr/sbin/tcpdump','-i',interface,'-p','-n',
            '-s','96','-U','-w',str(path),f'tcp and host {address} and port 443']


def capture(folder,duration=60,address='1.1.1.1',execute=False,approved=False,requests_dir=None):
    if not 5<=duration<=120:
        raise ValueError('Capture duration must be 5..120 seconds')
    commands={n:command(n,address,folder/f'{n}.pcap') for n in ('en0','en6')}
    if not execute:
        return dict(mode='dry_run',commands=commands,requires='explicit approval before privileged capture')
    if not approved:
        raise PermissionError('Explicit capture approval is required')
    if os.geteuid()==0:
        raise PermissionError('Run Python as your ordinary user; only tcpdump uses sudo')
    if requests_dir is not None and (duration!=60 or requests_dir.exists()):
        raise ValueError('Paired Stage A requests require 60s and a fresh request directory')
    folder.mkdir(parents=True,exist_ok=False)
    stop=threading.Event()
    processes={}
    client=None
    threads=[]
    ready={n:threading.Event() for n in commands}
    records={}
    manifest=dict(mode='packet_capture',address=address,duration_seconds=duration,started_epoch=time.time(),
                  interfaces=records,status='starting',snaplen=96,promiscuous=False)
    handlers={sig:signal.signal(sig,lambda *_:stop.set()) for sig in (signal.SIGINT,signal.SIGTERM)}
    def save():
        # Atomic readiness publication; verifier requires final completed state.
        temp=folder/'capture.tmp'
        temp.write_text(json.dumps(manifest,indent=2)+'\n')
        temp.replace(folder/'capture.json')
    try:
        for interface,cmd in commands.items():
            process=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
            processes[interface]=process
            records[interface]=dict(command=cmd,ready_epoch=None,returncode=None)
            def read_output(n=interface,p=process):
                with (folder/f'{n}.stderr').open('x') as stream:
                    for line in p.stderr:
                        stream.write(line)
                        stream.flush()
                        if f'listening on {n},' in line:
                            records[n]['ready_epoch']=time.time()
                            ready[n].set()
            thread=threading.Thread(target=read_output,daemon=True)
            thread.start()
            threads.append(thread)
        deadline=time.monotonic()+8
        while not all(e.is_set() for e in ready.values()):
            if any(p.poll() is not None for p in processes.values()) or time.monotonic()>deadline or stop.wait(.05):
                raise RuntimeError('Capture did not become ready; inspect stderr. No HTTP requests should be started.')
        manifest['status']='ready'
        save()
        print('READY: both physical interfaces capturing. Run Stage A requests in another terminal now.',flush=True)
        end=time.monotonic()+duration
        if requests_dir is not None:
            args=[sys.executable,'-m','mac_hub.traffic.run_stage_a','--execute','--address',address,'--output-dir',str(requests_dir)]
            manifest['request_command']=args
            client=subprocess.Popen(args)
            save()
        while time.monotonic()<end and not stop.wait(.1):
            if any(p.poll() is not None for p in processes.values()):
                raise RuntimeError('A capture exited before the observation interval ended')
        manifest['status']='complete' if not stop.is_set() else 'cancelled'
    except BaseException as exc:
        manifest.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        if client is not None:
            if client.poll() is None:
                client.send_signal(signal.SIGINT)
            client.wait(timeout=35)
            manifest['request_returncode']=client.returncode
        # Stop both wrappers concurrently. SIGTERM is forwarded reliably by
        # sudo and tcpdump handles it gracefully, flushing PCAP/drop statistics.
        manifest['stop_requested_epoch']=time.time()
        for process in processes.values():
            if process.poll() is None:
                process.terminate()
        for interface,process in processes.items():
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                manifest.update(status='failed',error='Capture shutdown deadline exceeded; operator inspection required')
                process.kill()
                process.wait(timeout=2)
            records[interface].update(returncode=process.returncode,stopped_epoch=time.time())
        for thread in threads:
            thread.join(timeout=2)
        manifest['ended_epoch']=time.time()
        manifest['sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*') if p.suffix in ('.pcap','.stderr')}
        save()
        for sig,handler in handlers.items():
            signal.signal(sig,handler)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--duration',type=int,default=60)
    parser.add_argument('--address',default='1.1.1.1')
    parser.add_argument('--stage-a-requests-dir',type=Path,help='send exactly four manual HTTPS requests as the ordinary user after capture readiness')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--approved-capture',action='store_true',help='only after explicit approval; never authorizes configuration changes')
    args=parser.parse_args()
    print(json.dumps(capture(args.output_dir,args.duration,args.address,args.execute,args.approved_capture,args.stage_a_requests_dir),indent=2))


if __name__=='__main__':
    main()
