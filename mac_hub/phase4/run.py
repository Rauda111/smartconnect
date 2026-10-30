"""Sequential, bounded paired trials. Dry-run performs no DNS or traffic."""
import argparse
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import signal
import shutil
import os
import platform
import queue
import socket
import threading
import time
from mac_hub.monitor import Measurement, measure
from mac_hub.traffic.client import Target, request
from mac_hub.phase4.policy import Controller, goodput

NETWORKS = {'wifi': 'en0', 'cellular': 'en6'}
HOST = 'speed.cloudflare.com'


def write_csv(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, keys, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def resolve(cancel, timeout=5.):
    """Bound preparation wait; libc resolver may finish later, with no requests."""
    results = queue.Queue()
    def lookup():
        try:
            results.put(sorted({item[4][0] for item in socket.getaddrinfo(HOST, 443, socket.AF_INET, socket.SOCK_STREAM)}))
        except Exception as exc:
            results.put(exc)
    threading.Thread(target=lookup, daemon=True).start()
    deadline = time.monotonic()+timeout
    while not cancel.is_set() and time.monotonic() < deadline:
        try:
            value = results.get(timeout=.05)
        except queue.Empty:
            continue
        if isinstance(value, Exception):
            raise value
        return value
    raise TimeoutError('DNS preparation cancelled or exceeded five seconds; no application requests started')


def run(output, execute=False, trials=4, cycles=4, size=262144, interval=5., condition='stable_observation', address=None):
    if not 2 <= trials <= 8 or trials % 2 or not 1 <= cycles <= 12:
        raise ValueError('Use an even 2..8 trials, 1..12 cycles')
    if not 16384 <= size <= 1048576 or not 1 <= interval <= 60:
        raise ValueError('Body 16 KiB..1 MiB; interval 1..60 seconds')
    # Both profiles, two probes and two outcome requests per cycle.
    budget = trials * cycles * 2 * 4 * size
    if budget > 32 * 1024 * 1024:
        raise ValueError('Payload budget exceeds 32 MiB; reduce size/cycles/trials')
    if not condition or len(condition) > 120:
        raise ValueError('Supply a short observational condition label')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    cancel = threading.Event()
    previous = {s: signal.signal(s, lambda *_: cancel.set()) for s in (signal.SIGINT, signal.SIGTERM)}
    rows, rounds, observations = [], [], []
    manifest = dict(schema=1, mode='actual_requests' if execute else 'dry_run', condition=condition,
                    trials=trials, cycles=cycles, bytes_per_download=size, payload_budget_bytes=budget,
                    interval_seconds=interval, start_epoch=time.time(), endpoint_host=HOST,
                    uid=os.getuid(), platform=platform.platform(), python=platform.python_version(),
                    address=address, dns_scope='ordinary resolver, not interface-bound',
                    egress='unverified: no contemporaneous packet capture',
                    policy='phase4-goodput-adapter-v1', profiles=['video_call', 'file_download'],
                    baseline='Wi-Fi-first on shared ICMP reachability; cellular fallback',
                    resets='fresh controller per profile/trial; no warmup exclusion',
                    hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')})
    source_dir = output/'source'
    source_dir.mkdir()
    for source in Path(__file__).parent.glob('*.py'):
        shutil.copyfile(source, source_dir/source.name)
    manifest['dependencies'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve().parents[1]/'traffic/client.py', Path(__file__).resolve().parents[1]/'engine.py', Path(__file__).resolve().parents[1]/'monitor.py']}
    try:
        if execute and address is None:
            # One common public IPv4 endpoint pinned for all paired requests.
            addresses = resolve(cancel)
            if not addresses:
                raise ValueError('No IPv4 endpoint')
            address = addresses[0]
            manifest['resolved_addresses'] = addresses
        address = address or '1.1.1.1'  # placeholder only, no DNS in dry-run
        manifest['address'] = address
        target = Target(address=address, server_name=HOST, path=f'/__down?bytes={size}', max_bytes=size, timeout=10)
        target.validate()
        for trial in range(trials):
            profiles = ['video_call', 'file_download'] if trial % 2 == 0 else ['file_download', 'video_call']
            for profile in profiles:
                controller = Controller(profile)
                origin = time.monotonic()
                for cycle in range(cycles):
                    if cancel.wait(interval if execute and cycle else 0):
                        break
                    key = dict(trial=trial, application=profile, cycle=cycle, condition=condition)
                    monitor_start = time.time()
                    monitor_mono = time.monotonic()
                    if execute:
                        with ThreadPoolExecutor(2) as pool:
                            futures = {n: pool.submit(measure, interface, '1.1.1.1', 3) for n, interface in NETWORKS.items()}
                            measurements = {n: f.result() for n, f in futures.items()}
                    else:
                        measurements = {n: Measurement(interface=i, status='error', error='dry_run: no measurement') for n, i in NETWORKS.items()}
                    monitor_end = time.time()
                    monitor_end_mono = time.monotonic()
                    for n, m in measurements.items():
                        observations.append(dict(**key, network=n, monitor_start_epoch=monitor_start,
                                                 monitor_end_epoch=monitor_end, **asdict(m)))
                    order = list(NETWORKS) if (trial+cycle) % 2 == 0 else list(reversed(NETWORKS))
                    probes = {}
                    for index, n in enumerate(order):
                        if cancel.is_set():
                            break
                        r = request(NETWORKS[n], target, execute, cancel)
                        if r['status'] == 'success' and r['bytes_received'] != size:
                            r.update(status='invalid_body_length', error='Expected exact requested body size')
                        r.update(tls_ready_epoch_estimate=(r['start_epoch']+r['tls_ready_ms']/1000) if r.get('tls_ready_ms') is not None else None,
                                 headers_ready_epoch_estimate=(r['start_epoch']+r['ttfb_ms']/1000) if r.get('ttfb_ms') is not None else None)
                        r.update(**key, role='probe', policy='', network=n, order_index=index,
                                 goodput_mbps=goodput(r), decision_epoch=None)
                        r['expected_bytes'] = size
                        probes[n] = r
                        rows.append(r)
                        write_csv(output/'requests.csv', rows)
                    if cancel.is_set():
                        break
                    now = time.monotonic()
                    decision = controller.step(measurements, probes, now-origin)
                    decision_epoch = time.time()
                    decision_mono = time.monotonic()
                    baseline = next((n for n in NETWORKS if measurements[n].status == 'reachable'), 'none')
                    rounds.append(dict(**key, monitor_start_epoch=monitor_start, monitor_end_epoch=monitor_end,
                                       decision_epoch=decision_epoch, decision_compute_ms=(decision_mono-now)*1000,
                                       elapsed_seconds=now-origin,
                                       monitor_window_ms=(monitor_end_mono-monitor_mono)*1000,
                                       monitoring_to_decision_ms=(decision_mono-monitor_end_mono)*1000,
                                       smartconnect=decision['recommended'], wifi_first=baseline,
                                       scoring_basis=decision['scoring_basis'], explanation=decision['explanation'],
                                       policy_details=json.dumps(decision, sort_keys=True)))
                    policies = ['smartconnect', 'wifi_first'] if (trial+cycle) % 2 == 0 else ['wifi_first', 'smartconnect']
                    for index, policy in enumerate(policies):
                        if cancel.is_set():
                            break
                        n = decision['recommended'] if policy == 'smartconnect' else baseline
                        dispatch_mono = time.monotonic()
                        if n == 'none':
                            r = dict(source='no_request', status='no_eligible_path', requested_interface='',
                                     start_epoch=time.time(), end_epoch=time.time(), request_duration_ms=None,
                                     bytes_received=None, egress_status='unverified')
                        else:
                            outcome_size = 16384 if profile == 'video_call' else size
                            outcome_target = replace(target, path=f'/__down?bytes={outcome_size}', max_bytes=outcome_size)
                            r = request(NETWORKS[n], outcome_target, execute, cancel)
                            r['expected_bytes'] = outcome_size
                            if r['status'] == 'success' and r['bytes_received'] != outcome_size:
                                r.update(status='invalid_body_length', error='Expected exact requested body size')
                        r.update(tls_ready_epoch_estimate=(r['start_epoch']+r['tls_ready_ms']/1000) if r.get('tls_ready_ms') is not None else None,
                                 headers_ready_epoch_estimate=(r['start_epoch']+r['ttfb_ms']/1000) if r.get('ttfb_ms') is not None else None)
                        r.update(**key, role='outcome', policy=policy, network=n, order_index=index,
                                 goodput_mbps=goodput(r), decision_epoch=decision_epoch,
                                 decision_to_start_ms=(dispatch_mono-decision_mono)*1000,
                                 decision_to_completion_ms=(time.monotonic()-decision_mono)*1000)
                        rows.append(r)
                        write_csv(output/'requests.csv', rows)
                    write_csv(output/'rounds.csv', rounds)
                    write_csv(output/'measurements.csv', observations)
                if cancel.is_set():
                    break
            if cancel.is_set():
                break
    except BaseException as exc:
        manifest['run_error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        manifest.update(end_epoch=time.time(), cancelled=cancel.is_set(), request_rows=len(rows))
        write_csv(output/'requests.csv', rows)
        write_csv(output/'rounds.csv', rounds)
        write_csv(output/'measurements.csv', observations)
        manifest['files'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.csv')}
        (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        for s, handler in previous.items():
            signal.signal(s, handler)
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--trials', type=int, default=4)
    p.add_argument('--cycles', type=int, default=4)
    p.add_argument('--bytes', type=int, default=262144)
    p.add_argument('--interval', type=float, default=5)
    p.add_argument('--condition', default='stable_observation')
    p.add_argument('--address', help='Optional public IPv4 pin; TLS host remains speed.cloudflare.com')
    a = p.parse_args()
    output = run(a.output, a.execute, a.trials, a.cycles, a.bytes, a.interval, a.condition, a.address)
    print(f'Experiment saved: {output.resolve()}')

if __name__ == '__main__':
    main()
