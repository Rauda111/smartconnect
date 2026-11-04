"""Offline presentation adapters. No collector, DNS, or network calls."""
import csv
import hashlib
import json
import math
from pathlib import Path

REPORT = Path(__file__).parent / 'reports/20261104-final'
DOWNLOAD = 'smartconnect-download-20261103T211238Z'
NETWORKS = ('wifi', 'cellular')
STATUSES = {'success', 'timeout', 'request_failed', 'binding_failed', 'invalid_body_length',
            'not_collected', 'no_request', 'cancelled', 'reachable', 'no_reply', 'error', 'unavailable', 'skipped'}


def number(value):
    if value is None or value == '':
        return None
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Invalid measurement')
    return value


def status(value):
    return value if value in STATUSES else 'unavailable'


def recorded(report=REPORT):
    """Verify public package before reading exact stored numeric values."""
    hashes = json.loads((report / 'package_sha256.json').read_text())
    for name in ('windows.csv', 'requests.csv', 'provenance.json'):
        if hashlib.sha256((report / name).read_bytes()).hexdigest() != hashes[name]:
            raise ValueError('Evidence integrity mismatch')
    with (report / 'windows.csv').open(newline='') as f:
        windows = [r for r in csv.DictReader(f) if r['run'] == DOWNLOAD]
    with (report / 'requests.csv').open(newline='') as f:
        requests = [r for r in csv.DictReader(f) if r['run'] == DOWNLOAD]
    if len(windows) != 8 or len(requests) != 24:
        raise ValueError('Incomplete recorded run')
    last_attachment = windows[0]['elapsed_seconds']
    for i, r in enumerate(windows):
        for key in list(r):
            if key.endswith(('_latency', '_loss', '_sent', '_received', '_score', '_adjusted_score', '_goodput_Mbps')) or key in ('window', 'elapsed_seconds', 'candidate_advantage', 'qualifying_count', 'selected_request_ms'):
                r[key] = number(r[key])
        r['window'] = int(r['window'])
        r['margin'], r['hold_required'], r['dwell_seconds'] = .05, 3, 30
        previous = windows[i-1] if i else None
        if previous is None or previous['selected'] != r['selected']:
            last_attachment = r['elapsed_seconds']
        r['elapsed_dwell'] = r['elapsed_seconds'] - float(last_attachment)
        r['reason'] = reason(r, previous)
    return windows, requests


def reason(row, previous=None):
    if row['selected'] not in NETWORKS:
        return 'No eligible path: observations are unavailable or breach guardrails.'
    if previous is None:
        return 'Initial attachment to an eligible observed path.'
    if previous['selected'] != row['selected']:
        if row.get(previous['selected'] + '_status') != 'reachable':
            return 'Availability exception: the previous path is unavailable; recommend the usable path immediately.'
        return 'Recommendation changed after the qualifying hold and dwell requirements.'
    if row.get('qualifying_count', 0):
        return 'Retained while the candidate builds its consecutive qualifying hold; a single advantage is insufficient.'
    return 'Retained: no qualifying sustained advantage on the current scoring basis.'


def project(row):
    """Allowlist numeric and enumerated fields from a private runner event."""
    d = row['decision']; stability = d['stability']
    r = dict(window=int(row['window']), elapsed_seconds=number(row['elapsed_seconds']),
             selected=d['recommended'] if d['recommended'] in NETWORKS else None,
             profile=row['application'] if row['application'] in ('video_call', 'file_download') else 'unknown',
             timestamp_utc=row['timestamp'], candidate_advantage=number(d.get('advantage')),
             qualifying_count=number(stability['hold_count']), margin=number(stability['margin']),
             hold_required=number(stability['hold_required']), dwell_seconds=number(stability['dwell_seconds']),
             scoring_basis='bounded_goodput_utility_and_loss' if d['scoring_basis']=='bounded_goodput_utility_and_loss' else 'icmp_rtt_and_loss')
    if d.get('direct_recommendation_change'):
        r['qualifying_count'] = r['hold_required'] if d['explanation'].startswith('Recommend change:') else 0
    last = number(stability.get('last_selection_elapsed'))
    r['elapsed_dwell'] = None if last is None else r['elapsed_seconds']-last
    for n in NETWORKS:
        m = row['inputs'][n]; detail = d['details'][n]
        for k in ('latency', 'loss', 'sent', 'received'):
            r[n+'_'+k] = number(m.get(k))
        r[n+'_status'] = status(m['status'])
        r[n+'_adjusted_score'] = number(detail.get('adjusted_score'))
        r[n+'_calibration_goodput_Mbps'] = number(row.get('calibration', {}).get(n, {}).get('goodput_mbps'))
    o = row.get('outcome') or {}
    r.update(selected_request_status=status(o.get('status', 'not_collected')),
             selected_request_ms=number(o.get('request_duration_ms')),
             selected_binding_readback=bool(o.get('binding_index')))
    return r


def request_table(requests):
    result = []
    for r in requests:
        result.append(dict(window=int(r['window']), role='calibration' if r.get('role')=='calibration' else 'selected_outcome',
                           interface={'en0':'Wi-Fi', 'en6':'Cellular'}.get(r.get('requested_interface'), 'Unknown'),
                           status=status(r.get('status')), binding_readback=r.get('binding_readback') in (True, 'True') or bool(r.get('binding_index')),
                           completed_body_bytes=number(r.get('completed_body_bytes', r.get('bytes_received'))),
                           request_ms=number(r.get('request_duration_ms')),
                           bounded_goodput_Mbps=number(r.get('bounded_goodput_Mbps', r.get('goodput_mbps')))))
    return result
