"""Strict public policy envelope. No measurements, sockets or secrets on import."""
from datetime import datetime, timezone
import math
import re

MAX_AGE = 45
REASONS = ('availability', 'hold', 'qualified_change', 'no_eligible_path')
EXPLANATIONS = {
    'availability': 'Availability reset: recommend usable path immediately',
    'hold': 'Hold: insufficient advantage or candidate breaches observed guardrails',
    'qualified_change': 'Recommend change: sustained advantage; observed guardrails and dwell satisfied',
    'no_eligible_path': 'No eligible path: unavailable or observed guardrail breach',
}


def validate_explanation(value, reason):
    """Only the frozen engine's own fixed/numeric explanations may be relayed."""
    if not isinstance(value, str) or len(value) > 160:
        raise ValueError('invalid_policy')
    if value == EXPLANATIONS.get(reason):
        return value
    if reason == 'hold' and re.fullmatch(r'Hold: superiority [1-9][0-9]{0,4}/3; elapsed dwell [0-9]{1,5}\.[0-9]/30s', value):
        return value
    raise ValueError('invalid_policy')


def number(value, low, high, nullable=False):
    if value is None and nullable:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('invalid_policy')
    return value


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid_policy')
    return value


def validate_policy(data, session_id, previous_window, now=None):
    """Rebuild an allowlisted envelope; reject extra fields rather than publishing them."""
    expected = {'session_id', 'window', 'timestamp', 'application', 'source', 'recommended',
                'reason_code', 'measurements', 'stability', 'coverage'}
    if not isinstance(data, dict) or set(data) not in (expected, expected | {'explanation'}):
        raise ValueError('invalid_policy')
    if data['session_id'] != session_id or data['application'] != 'video_call' or data['source'] != 'measured_icmp':
        raise ValueError('invalid_scope')
    window = integer(data['window'], 1, 10000)
    if window <= previous_window:
        raise ValueError('replayed_policy')
    if data['recommended'] not in ('wifi', 'cellular', 'none') or data['reason_code'] not in REASONS:
        raise ValueError('invalid_policy')
    if (data['recommended'] == 'none') != (data['reason_code'] == 'no_eligible_path'):
        raise ValueError('invalid_policy')
    if not isinstance(data['timestamp'], str) or len(data['timestamp']) > 40:
        raise ValueError('invalid_policy')
    stamp = datetime.fromisoformat(data['timestamp'])
    if stamp.tzinfo is None:
        raise ValueError('invalid_policy')
    age = ((now or datetime.now(timezone.utc)) - stamp).total_seconds()
    if not 0 <= age <= MAX_AGE:
        raise ValueError('stale_policy')
    if not isinstance(data['measurements'], dict) or set(data['measurements']) != {'wifi', 'cellular'}:
        raise ValueError('invalid_policy')
    measurements = {}
    for name, row in data['measurements'].items():
        if not isinstance(row, dict) or set(row) != {'status', 'latency_ms', 'loss_percent', 'sent', 'received', 'score', 'adjusted_score', 'trend'}:
            raise ValueError('invalid_policy')
        if row['status'] not in ('reachable', 'no_reply', 'error') or row['trend'] not in ('Improving', 'Stable', 'Degrading', 'Unavailable'):
            raise ValueError('invalid_policy')
        sent = integer(row['sent'], 0, 30)
        received = integer(row['received'], 0, sent)
        latency = number(row['latency_ms'], 0, 3600000, nullable=True)
        loss = number(row['loss_percent'], 0, 100, nullable=True)
        score = number(row['score'], 0, 1, nullable=True)
        adjusted = number(row['adjusted_score'], 0, 1, nullable=True)
        if row['status'] == 'reachable':
            if received < 1 or None in (latency, loss, score, adjusted) or row['trend'] == 'Unavailable':
                raise ValueError('invalid_policy')
        elif score is not None or adjusted is not None or row['trend'] != 'Unavailable':
            raise ValueError('invalid_policy')
        if row['status'] == 'no_reply' and (sent < 1 or received != 0 or latency is not None or loss != 100):
            raise ValueError('invalid_policy')
        if sent and loss is not None and not math.isclose(loss, 100*(sent-received)/sent, abs_tol=1e-6):
            raise ValueError('invalid_policy')
        measurements[name] = dict(row)
    if data['recommended'] != 'none' and measurements[data['recommended']]['status'] != 'reachable':
        raise ValueError('invalid_policy')
    stability = data['stability']
    if not isinstance(stability, dict) or set(stability) != {'hold_count', 'hold_required', 'dwell_seconds', 'margin'}:
        raise ValueError('invalid_policy')
    integer(stability['hold_count'], 0, 10000)
    if type(stability['hold_required']) is not int or stability['hold_required'] != 3:
        raise ValueError('invalid_policy')
    if number(stability['dwell_seconds'], 0, 60) != 30 or number(stability['margin'], 0, 1) != .05:
        raise ValueError('invalid_policy')
    # The frozen Video Call adapter measures only latency and loss, carrying
    # 0.30+0.30 of the original profile. Do not accept an inflated coverage claim.
    coverage = number(data['coverage'], 0, 1)
    if not math.isclose(coverage, .6, abs_tol=1e-12):
        raise ValueError('invalid_policy')
    result = {key: data[key] for key in expected if key not in ('measurements', 'stability')}
    result.update(measurements=measurements, stability=dict(stability), coverage=coverage,
                  status='fresh', age_seconds=age, physical_interface='unverified')
    if 'explanation' in data:
        result['explanation'] = validate_explanation(data['explanation'], data['reason_code'])
    return result
