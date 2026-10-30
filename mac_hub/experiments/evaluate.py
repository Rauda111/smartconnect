"""Independent metric calculations on paired replay inputs and recommendations."""
from dataclasses import fields
import math
import pandas as pd
from mac_hub.engine import Engine, NETWORKS
from mac_hub.monitor import Measurement
from smartconnect import LIMITS

METRICS = ('latency', 'loss', 'rtt_variation')


def validate(frame):
    required = ['timestamp', 'elapsed_seconds', 'source'] + [
        f'{n}_{k}' for n in NETWORKS for k in ('status', *METRICS)]
    missing = set(required)-set(frame.columns)
    if missing or frame.empty:
        raise ValueError(f'Empty trace or missing columns: {sorted(missing)}')
    frame = frame.copy(deep=True)
    times = pd.to_numeric(frame.elapsed_seconds, errors='raise')
    frame['elapsed_seconds'] = times
    if not times.map(math.isfinite).all() or (times < 0).any() or not times.is_monotonic_increasing or times.duplicated().any():
        raise ValueError('Elapsed seconds must be finite, nonnegative and strictly increasing')
    if any(pd.Timestamp(s).tzinfo is None for s in frame.timestamp):
        raise ValueError('Timestamps must include a timezone')
    stamps = pd.to_datetime(frame.timestamp, utc=True, errors='raise')
    if stamps.isna().any() or not stamps.is_monotonic_increasing or stamps.duplicated().any():
        raise ValueError('Timestamps must be valid and strictly increasing')
    # Wall clocks may slew on real collectors: monotonic elapsed time governs policy.
    if frame.source.nunique(dropna=False) != 1 or frame.source.iloc[0] not in ('synthetic', 'measured_icmp'):
        raise ValueError('One known evidence source per trace required')
    for n in NETWORKS:
        if not frame[f'{n}_status'].isin(['reachable', 'no_reply', 'error']).all():
            raise ValueError('Unknown path status')
        for k in METRICS:
            v = pd.to_numeric(frame[f'{n}_{k}'], errors='raise')
            frame[f'{n}_{k}'] = v
            if not v.dropna().map(math.isfinite).all() or (v.dropna() < 0).any() or (k == 'loss' and (v.dropna() > 100).any()):
                raise ValueError(f'Invalid {n}_{k}')
    return frame


def baseline(measurements):
    """Wi-Fi-first uses probe reachability only; no guardrails or future data."""
    return next((n for n in NETWORKS if measurements[n].status == 'reachable'), 'none')


def replay(frame, application):
    frame = validate(frame)
    engine = Engine(application)
    records = []
    for _, row in frame.iterrows():
        measurements = {}
        for n in NETWORKS:
            values = {}
            for field in fields(Measurement):
                v = row.get(f'{n}_{field.name}')
                if v is not None and pd.notna(v):
                    values[field.name] = v
            values['interface'] = str(row.get(f'{n}_interface', n))
            measurements[n] = Measurement(**values)
        # Do not let incomplete reachable inputs shrink the score to loss-only.
        # Retain original probe status for the baseline, but mark SmartConnect
        # observations unusable if either required scoring dimension is unknown.
        policy_inputs = {}
        for n, m in measurements.items():
            policy_inputs[n] = m
            if m.status == 'reachable' and (m.latency is None or m.loss is None):
                policy_inputs[n] = Measurement(m.interface, error='Incomplete RTT/loss observation')
        decision = engine.step(policy_inputs, float(row.elapsed_seconds))
        result = row.to_dict()
        result.update(application=application, smartconnect=decision['recommended'],
                      wifi_first=baseline(measurements), explanation=decision['explanation'],
                      coverage=decision['coverage'], outcome_type='counterfactual_selection_proxy')
        records.append(result)
    return pd.DataFrame(records)


def changes(paths):
    """Initial attachment excluded. Only direct path-to-path changes are handover recommendations."""
    paths = list(paths)
    return [i for i in range(1, len(paths)) if paths[i] in NETWORKS and paths[i-1] in NETWORKS and paths[i] != paths[i-1]]


def selected(frame, method, metric):
    return pd.Series([row.get(f'{row[method]}_{metric}', float('nan')) if row[method] in NETWORKS else float('nan')
                      for _, row in frame.iterrows()], index=frame.index, dtype=float)


def metrics(frame, method, application):
    paths = list(frame[method])
    switches = changes(paths)
    result = dict(method=method, application=application, windows=len(frame),
                  recommended_handovers=len(switches),
                  no_path_windows=paths.count('none'),
                  outage_entries=sum(paths[i] == 'none' and paths[i-1] != 'none' for i in range(1,len(paths))),
                  reattachments=sum(paths[i] != 'none' and paths[i-1] == 'none' for i in range(1,len(paths))))
    for metric in METRICS:
        v = selected(frame, method, metric)
        result[f'{metric}_mean'] = v.mean()
        result[f'{metric}_observed_windows'] = int(v.notna().sum())
    # Assess guardrails independently of production-engine detail fields.
    breach, complete, unknown = [], [], []
    for _, row in frame.iterrows():
        n = row[method]
        checks = []
        if n in NETWORKS:
            for key, limit in LIMITS[application].items():
                value = row.get(f'{n}_{key}')
                checks.append(None if value is None or pd.isna(value) else
                              bool(value < limit if key == 'throughput' else value > limit))
        else:
            checks = [None] * len(LIMITS[application])
        breach.append(any(v is True for v in checks))
        complete.append(all(v is not None for v in checks))
        unknown.append(any(v is None for v in checks))
    result.update(observed_guardrail_violation_windows=sum(breach),
                  guardrail_unknown_windows=sum(unknown), fully_assessed_guardrail_windows=sum(complete))
    stable = frame.get('stable_region', pd.Series([False]*len(frame),index=frame.index))
    # Conservative operational proxy: both adjacent observations must be in a
    # predeclared quiet region. Does not classify real switches as unnecessary.
    assessed = 'stable_region' in frame and frame.source.iloc[0] == 'synthetic'
    result['quiet_region_changes'] = sum(bool(stable.iloc[i]) and bool(stable.iloc[i-1]) for i in switches) if assessed else None
    # A -> B -> A within 30 s, without intervening no-path observations.
    result['reversals_within_30s'] = sum(
        paths[a-1] == paths[b] and all(p in NETWORKS for p in paths[a:b+1]) and
        float(frame.iloc[b].elapsed_seconds)-float(frame.iloc[a].elapsed_seconds) <= 30
        for a,b in zip(switches,switches[1:]))
    result['quiet_region_assessed'] = 'stable_region' in frame and frame.source.iloc[0] == 'synthetic'
    return result


def responses(frame, method, events):
    records = []
    for index, event in enumerate(events):
        onset = event['onset_seconds']
        end = events[index+1]['onset_seconds'] if index+1 < len(events) else math.inf
        segment = frame[(frame.elapsed_seconds >= onset) & (frame.elapsed_seconds < end)]
        target = event['expected_path']
        hits = segment[segment[method] == target]
        before = frame[frame.elapsed_seconds < onset]
        already = not before.empty and before.iloc[-1][method] == target
        delay = float(hits.iloc[0].elapsed_seconds)-onset if not hits.empty else None
        records.append(dict(**event, method=method, already_on_target=already,
                            observed_response=not hits.empty, response_seconds=delay,
                            interpretation='first observed target recommendation; not switching completion'))
    return records
