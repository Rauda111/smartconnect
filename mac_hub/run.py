"""Run two concurrent interface-bound probes and flush a paired CSV each cycle."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

from mac_hub.engine import Engine, NETWORKS
from mac_hub.monitor import measure


def record(measurements, elapsed, application, engine, source='measured_icmp'):
    decision = engine.step(measurements, elapsed)
    row = dict(timestamp=datetime.now(timezone.utc).isoformat(), elapsed_seconds=elapsed,
               source=source, **{k:v for k,v in decision.items() if k != 'details'})
    for n in NETWORKS:
        row.update({f'{n}_{k}':v for k,v in measurements[n].dict().items()})
        row.update({f'{n}_{k}':v for k,v in decision['details'][n].items()})
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wifi', default='en0')
    p.add_argument('--cellular', default='en6')
    p.add_argument('--target', default='1.1.1.1')
    p.add_argument('--count', type=int, default=10)
    p.add_argument('--pause', type=float, default=2, help='seconds AFTER each probe window')
    p.add_argument('--cycles', type=int, default=0, help='0 runs until Ctrl-C')
    p.add_argument('--application', choices=['video_call','file_download'], default='video_call')
    p.add_argument('--output', type=Path, default=None)
    args = p.parse_args()
    from mac_hub.monitor import ping_command
    for interface in (args.wifi, args.cellular):
        ping_command(interface, args.target, args.count)
    if args.wifi == args.cellular or args.cycles < 0 or not 0 <= args.pause <= 3600:
        p.error('Use distinct interfaces, nonnegative cycles and pause 0..3600')
    out = args.output or Path('mac_hub/logs') / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.csv')
    out.parent.mkdir(parents=True, exist_ok=True)
    engine = Engine(args.application)
    start = time.monotonic()
    print(f'DECISION ONLY; logging to {out}', flush=True)
    # Exclusive create avoids accidental destruction of experimental evidence.
    with out.open('x', newline='') as stream:
        manifest = dict(arguments={k:str(v) for k,v in vars(args).items()},
                        policy=dict(margin=.05, hold=3, dwell_seconds=30, trend_window=5, trend_weight=.5),
                        created_utc=datetime.now(timezone.utc).isoformat(),
                        source_hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest()
                                       for f in [*Path('mac_hub').glob('*.py'), Path('smartconnect.py')]})
        manifest['revision'] = subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
        out.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2))
        writer = None
        cycle = 0
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                while not args.cycles or cycle < args.cycles:
                    futures = {n:pool.submit(measure, interface, args.target, args.count)
                               for n,interface in [('wifi',args.wifi),('cellular',args.cellular)]}
                    measurements = {n:f.result() for n,f in futures.items()}
                    row = record(measurements,time.monotonic()-start,args.application,engine)
                    row['target'] = args.target
                    if writer is None:
                        writer = csv.DictWriter(stream,fieldnames=list(row))
                        writer.writeheader()
                    writer.writerow(row)
                    stream.flush()
                    print(f"{row['timestamp']} SmartConnect={row['recommended']} Wi-Fi-first={row['baseline']} | {row['explanation']}",flush=True)
                    cycle += 1
                    if not args.cycles or cycle < args.cycles:
                        time.sleep(args.pause)
        except KeyboardInterrupt:
            print('Monitor stopped; completed cycles preserved.')


if __name__ == '__main__':
    main()
