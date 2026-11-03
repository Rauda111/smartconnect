"""Bounded own-new-flow demo; no routes, session migration or automatic retries."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import signal
import threading
import time
from mac_hub.monitor import measure, parse_ping
from mac_hub.phase4.policy import Controller, goodput
from mac_hub.phase4.run import resolve
from mac_hub.traffic.client import Target, request

INTERFACES = {'wifi': 'en0', 'cellular': 'en6'}
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).parent/'evidence/dorm-continuous-20261103.csv'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def diagnostic(m):
    replies = re.findall(r'icmp_seq=(\d+).*?time=([\d.]+)\s*ms', m.raw_output)
    summary = re.search(r'round-trip min/avg/max/stddev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', m.raw_output)
    return dict(parsed_reply_count=len({s for s, _ in replies}),
                rtt_reply_count_mismatch=m.received != len({s for s, _ in replies}),
                ping_summary_mean_ms=float(summary[2]) if summary else None)


class Session:
    def __init__(self, application):
        self.controller = Controller(application)
        self.previous_recommendation = None
        self.previous_success_interface = None

    def decide(self, measurements, probes, elapsed):
        d = self.controller.step(measurements, probes, elapsed)
        current = d['recommended']
        d['direct_recommendation_change'] = (self.previous_recommendation in INTERFACES and current in INTERFACES
                                            and current != self.previous_recommendation)
        self.previous_recommendation = current
        engine = self.controller.engine
        d['stability'] = dict(pending=engine.pending, hold_count=engine.streak,
                             last_selection_elapsed=engine.last_switch if math.isfinite(engine.last_switch) else None,
                             dwell_seconds=engine.dwell, hold_required=engine.hold, margin=engine.margin)
        return d

    def outcome(self, result):
        interface = result.get('requested_interface')
        success = result.get('status') == 'success' and bool(result.get('binding_index'))
        changed = success and self.previous_success_interface is not None and interface != self.previous_success_interface
        if success:
            self.previous_success_interface = interface
        return dict(successful_bound_request=success, successful_bound_request_interface_change=bool(changed),
                    physical_new_flow_change=None, existing_session_handover=None)


def replay_rows(path=EVIDENCE, application='video_call'):
    """Historical measured inputs only; no requests or synthetic HTTP outcomes."""
    path = Path(path)
    expected = json.loads((EVIDENCE.parent/'provenance.json').read_text())
    if digest(path) != expected['csv_sha256'] or digest(path.with_suffix('.manifest.json')) != expected['manifest_sha256']:
        raise ValueError('Historical evidence hash mismatch')
    manifest = json.loads(path.with_suffix('.manifest.json').read_text())
    session = Session(application)
    previous_stamp = None
    with path.open(newline='') as stream:
        for index, row in enumerate(csv.DictReader(stream), 1):
            if row['source'] != 'measured_icmp':
                raise ValueError('Expected historical measured ICMP')
            stamp = datetime.fromisoformat(row['timestamp'])
            if stamp.tzinfo is None or (previous_stamp is not None and stamp <= previous_stamp):
                raise ValueError('Historical timestamps must increase with timezone')
            previous_stamp = stamp
            measurements = {}
            for n, interface in INTERFACES.items():
                if row[n+'_interface'] != interface:
                    raise ValueError('Historical interface mismatch')
                m = parse_ping(row[n+'_raw_output'], interface)
                if m.sent != int(manifest['arguments']['count']):
                    raise ValueError('Historical probe count mismatch')
                for metric in ('latency', 'loss'):
                    if not math.isclose(getattr(m, metric), float(row[n+'_'+metric]), abs_tol=1e-10):
                        raise ValueError('Historical metric mismatch')
                measurements[n] = m
            probes = {n: {'status': 'not_measured'} for n in INTERFACES}
            d = session.decide(measurements, probes, float(row['elapsed_seconds']))
            if application == manifest['arguments']['application'] and d['recommended'] != row['recommended']:
                raise ValueError('Historical recommendation mismatch')
            yield dict(mode='historical_real_input_replay', window=index, timestamp=row['timestamp'],
                       elapsed_seconds=float(row['elapsed_seconds']), application=application,
                       inputs={n: asdict(m) for n, m in measurements.items()},
                       diagnostics={n: diagnostic(m) for n, m in measurements.items()},
                       decision=d, baseline=row['baseline'], outcome=None,
                       evidence_sha256=expected['csv_sha256'], location_stage=None)


def live(output, application='video_call', cycles=6, count=10, pause=5., size=65536):
    if not 1 <= cycles <= 30 or not 2 <= count <= 30 or not math.isfinite(pause) or not 1 <= pause <= 30:
        raise ValueError('Use 1..30 cycles, 2..30 echoes, pause 1..30 seconds')
    if not 16384 <= size <= 262144 or cycles*3*size > 24*1024*1024:
        raise ValueError('Body 16..256 KiB; requested payload <=24 MiB')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    cancel = threading.Event()
    old = {s: signal.signal(s, lambda *_: cancel.set()) for s in (signal.SIGINT, signal.SIGTERM)}
    session = Session(application)
    paths = ['mac_hub/competition/run.py', 'mac_hub/phase4/policy.py', 'mac_hub/traffic/client.py',
             'mac_hub/monitor.py', 'mac_hub/engine.py', 'smartconnect.py']
    manifest = dict(mode='live', application=application, cycles=cycles, count=count, pause=pause,
                    body_bytes=size, maximum_requests=cycles*(3 if application == 'file_download' else 1),
                    requested_payload_ceiling_bytes=cycles*size*(3 if application == 'file_download' else 1),
                    interfaces=INTERFACES, start_utc=datetime.now(timezone.utc).isoformat(),
                    source_hashes={p: digest(ROOT/p) for p in paths},
                    physical_egress='unverified', location_stages='unassigned', completed_windows=0)
    origin = time.monotonic()
    def write(stream, item):
        stream.write(json.dumps(item, allow_nan=False)+'\n')
        stream.flush()
    try:
        with (output/'events.jsonl').open('x') as events, (output/'requests.jsonl').open('x') as requests:
            addresses = resolve(cancel)
            if not addresses or cancel.is_set():
                raise ValueError('Endpoint preparation cancelled or unavailable')
            target = Target(address=addresses[0], server_name='speed.cloudflare.com',
                            path=f'/__down?bytes={size}', max_bytes=size, timeout=5.)
            target.validate()
            manifest['target'] = asdict(target)
            def send(interface, role, window):
                result = request(interface, target, execute=True, cancel=cancel)
                if result['status'] == 'success' and result['bytes_received'] != size:
                    result.update(status='invalid_body_length', error='Unexpected response length')
                result.update(role=role, window=window, goodput_mbps=goodput(result))
                write(requests, result)
                return result
            for index in range(1, cycles+1):
                if cancel.is_set():
                    break
                with ThreadPoolExecutor(2) as pool:
                    futures = {n: pool.submit(measure, interface, '1.1.1.1', count) for n, interface in INTERFACES.items()}
                    measurements = {n: f.result() for n, f in futures.items()}
                if cancel.is_set():
                    break
                probes = {n: {'status': 'not_measured'} for n in INTERFACES}
                if application == 'file_download':
                    order = list(INTERFACES) if index % 2 else list(reversed(INTERFACES))
                    for n in order:
                        if cancel.is_set():
                            break
                        probes[n] = send(INTERFACES[n], 'calibration', index)
                if cancel.is_set():
                    break
                elapsed = time.monotonic()-origin
                decision = session.decide(measurements, probes, elapsed)
                record = dict(mode='live', window=index, timestamp=datetime.now(timezone.utc).isoformat(),
                              elapsed_seconds=elapsed, application=application,
                              freshness_limit_seconds=count+6+15+pause+5,
                              inputs={n: asdict(m) for n, m in measurements.items()},
                              diagnostics={n: diagnostic(m) for n, m in measurements.items()}, calibration=probes,
                              decision=decision,
                              baseline=next((n for n in INTERFACES if measurements[n].status == 'reachable'), 'none'))
                write(events, dict(record, event='decision', outcome=None))
                n = decision['recommended']
                result = send(INTERFACES[n], 'selected_outcome', index) if n in INTERFACES and not cancel.is_set() else dict(status='no_request', source='no_request')
                record.update(event='completed_window', outcome=result, flow_evidence=session.outcome(result))
                write(events, record)
                manifest['completed_windows'] += 1
                print(f"Window {index}: {n}; HTTPS {result['status']}; physical egress unverified", flush=True)
                if index < cycles and cancel.wait(pause):
                    break
    except BaseException as exc:
        manifest['run_error_type'] = type(exc).__name__
        raise
    finally:
        manifest.update(cancelled=cancel.is_set(), end_utc=datetime.now(timezone.utc).isoformat(),
                        output_hashes={p.name: digest(p) for p in output.glob('*.jsonl')})
        (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        for sig, handler in old.items():
            signal.signal(sig, handler)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true', help='Real ICMP/DNS/HTTPS; explicit approval required')
    p.add_argument('--output', type=Path)
    p.add_argument('--replay', type=Path, default=EVIDENCE)
    p.add_argument('--application', choices=['video_call', 'file_download'], default='video_call')
    p.add_argument('--cycles', type=int, default=6)
    p.add_argument('--count', type=int, default=10)
    p.add_argument('--pause', type=float, default=5.)
    a = p.parse_args()
    if a.execute:
        if a.output is None:
            p.error('--execute requires fresh --output directory')
        live(a.output, a.application, a.cycles, a.count, a.pause)
    else:
        for row in replay_rows(a.replay, a.application):
            print(json.dumps(row, allow_nan=False))

if __name__ == '__main__':
    main()
