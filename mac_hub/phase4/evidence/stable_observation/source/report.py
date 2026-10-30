"""Offline paired summaries, cluster uncertainty and evidence audit."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from mac_hub.phase4.policy import goodput, Controller
from mac_hub.monitor import Measurement
from dataclasses import fields

KEY = ['trial', 'application', 'cycle']


def audit(path):
    path = Path(path)
    m = json.loads((path/'manifest.json').read_text())
    for name, digest in m['files'].items():
        if hashlib.sha256((path/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'CSV hash mismatch: {name}')
    r = pd.read_csv(path/'requests.csv', keep_default_na=True)
    d = pd.read_csv(path/'rounds.csv') if (path/'rounds.csv').exists() else pd.DataFrame()
    if not r.egress_status.eq('unverified').all():
        raise ValueError('This framework has no packet-confirmation importer; unsupported egress claim')
    for row in r.to_dict('records'):
        expected = goodput(row)
        actual = row['goodput_mbps']
        if expected is None:
            if not pd.isna(actual):
                raise ValueError('Missing/failed observation has invented goodput')
        elif not np.isclose(expected, actual):
            raise ValueError('Goodput calculation mismatch')
        if row.get('source') == 'actual_https':
            if row['end_epoch'] < row['start_epoch'] or row['request_duration_ms'] < 0:
                raise ValueError('Invalid request timing')
            if row['status'] == 'success' and row['bytes_received'] != row['expected_bytes']:
                raise ValueError('Wrong body length')
    measurements = pd.read_csv(path/'measurements.csv') if (path/'measurements.csv').exists() else pd.DataFrame()
    controllers = {}
    for _, dec in d.iterrows():
        subset = r
        for k in KEY:
            subset = subset[subset[k] == dec[k]]
        outcomes = subset[subset.role.eq('outcome')]
        # Cancellation may leave a final incomplete pair; never pretend it is complete.
        if not m['cancelled'] and set(outcomes.policy) != {'smartconnect', 'wifi_first'}:
            raise ValueError('Missing paired policy slot')
        for _, row in outcomes.iterrows():
            if row.network != dec[row.policy]:
                raise ValueError('Policy requested different path than recorded decision')
            if row.start_epoch < dec.decision_epoch:
                raise ValueError('Outcome precedes decision')
        probes = subset[subset.role.eq('probe')]
        if len(probes) != 2 or set(probes.network) != {'wifi','cellular'} or (probes.end_epoch > dec.decision_epoch).any():
            raise ValueError('Decision used future or missing probes')
        measured = measurements
        for k in KEY:
            measured = measured[measured[k] == dec[k]]
        if len(measured) != 2 or set(measured.network) != {'wifi','cellular'}:
            raise ValueError('Missing common network input')
        inputs = {}
        for _, row in measured.iterrows():
            kwargs = {f.name: (None if pd.isna(row[f.name]) else row[f.name]) for f in fields(Measurement)}
            inputs[row.network] = Measurement(**kwargs)
            if row.monitor_end_epoch > dec.decision_epoch:
                raise ValueError('Future monitor input')
        baseline = next((n for n in ('wifi','cellular') if inputs[n].status == 'reachable'), 'none')
        if baseline != dec.wifi_first:
            raise ValueError('Wi-Fi-first did not use shared reachability')
        controller = controllers.setdefault((dec.trial, dec.application), Controller(dec.application))
        replay = controller.step(inputs, {row.network: row.to_dict() for _, row in probes.iterrows()}, dec.elapsed_seconds)
        recorded = json.loads(dec.policy_details)
        def equal(a, b):
            if isinstance(a, dict) and isinstance(b, dict):
                return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
            if isinstance(a, (int,float)) and isinstance(b, (int,float)):
                return bool(np.isclose(a, b, rtol=1e-10, atol=1e-10))
            return a == b
        if not equal(replay, recorded) or dec.smartconnect != replay['recommended']:
            raise ValueError('Causal policy replay mismatch')
        expected_order = ['smartconnect', 'wifi_first'] if (int(dec.trial)+int(dec.cycle)) % 2 == 0 else ['wifi_first', 'smartconnect']
        if outcomes.sort_values('order_index').policy.tolist() != expected_order[:len(outcomes)]:
            raise ValueError('Unbalanced policy order')
    return m, r, d


def summarize(path):
    path = Path(path)
    m, r, d = audit(path)
    rows, contrasts = [], []
    outcomes = r[r.role.eq('outcome')]
    for (app, policy), group in outcomes.groupby(['application', 'policy']):
        success = group[group.status.eq('success')]
        # Count direct path changes per independent trial, excluding initial attachment
        # and none transitions. Availability transitions are separately counted.
        changes = availability = 0
        max_fail = 0
        gaps = []
        for _, trial in group.groupby('trial'):
            last = None
            streak = 0
            last_success_end = None
            failed = False
            for _, row in trial.sort_values('cycle').iterrows():
                if last is not None:
                    changes += int(last in ('wifi','cellular') and row.network in ('wifi','cellular') and last != row.network)
                    availability += int((last == 'none') != (row.network == 'none'))
                last = row.network
                if row.status == 'success':
                    if failed and last_success_end is not None:
                        gaps.append((row.end_epoch-last_success_end)*1000)
                    last_success_end = row.end_epoch
                    streak = 0
                    failed = False
                elif row.source != 'dry_run':
                    streak += 1
                    failed = True
                    max_fail = max(max_fail, streak)
        rows.append(dict(application=app, policy=policy, slots=len(group), actual_attempts=int(group.source.eq('actual_https').sum()),
                         successes=len(success), failures=int((group.source.eq('actual_https') & ~group.status.eq('success')).sum()),
                         no_eligible_slots=int(group.status.eq('no_eligible_path').sum()),
                         mean_success_response_ms=success.request_duration_ms.mean(),
                         mean_success_goodput_mbps=success.goodput_mbps.mean(),
                         recommended_path_changes=changes, availability_transitions=availability,
                         max_failed_slot_streak=max_fail, max_bracketed_failure_gap_ms=max(gaps, default=None),
                         packet_confirmed_requests=0))
    # Paired complete-success contrasts. Failures retained above, never imputed zero.
    for app, group in outcomes.groupby('application'):
        for metric in ('request_duration_ms', 'goodput_mbps'):
            successes = group[group.status.eq('success')]
            pairs = successes.pivot(index=['trial','cycle'], columns='policy', values=metric)
            if not {'smartconnect','wifi_first'} <= set(pairs.columns):
                deltas = pd.Series(dtype=float)
            else:
                deltas = (pairs.smartconnect-pairs.wifi_first).dropna()
            clusters = deltas.groupby(level='trial').mean() if len(deltas) else deltas
            lo = hi = None
            if len(clusters) >= 4:
                rng = np.random.default_rng(2026)
                estimates = rng.choice(clusters.to_numpy(), (10000,len(clusters)), replace=True).mean(axis=1)
                lo, hi = np.quantile(estimates, [.025,.975])
            contrasts.append(dict(application=app, metric=metric, paired_successes=len(deltas), trials=len(clusters),
                                  smart_minus_wifi_mean=clusters.mean(), cluster_bootstrap_low=lo, cluster_bootstrap_high=hi))
    summary, contrast = pd.DataFrame(rows), pd.DataFrame(contrasts)
    summary.to_csv(path/'summary.csv', index=False, lineterminator='\n')
    contrast.to_csv(path/'contrasts.csv', index=False, lineterminator='\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10,4))
    for ax, metric in zip(axes, ['request_duration_ms','goodput_mbps']):
        for (app, policy), group in outcomes[outcomes.status.eq('success')].groupby(['application','policy']):
            ax.plot(range(len(group)), group[metric], marker='.', label=f'{app}/{policy}')
        ax.set(xlabel='Successful outcome index (failed slots excluded)', ylabel=metric)
        if ax.lines:
            ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(path/'outcomes.png', dpi=150)
    plt.close(fig)
    lines = ['# Phase 4 paired application evidence', '', f"Mode: {m['mode']}; operator condition label: {m['condition']}.",
             'No contemporaneous capture: all requested interfaces remain physically unverified.',
             'Body goodput = delivered body bits / full fresh HTTPS duration, including TCP/TLS/server time. Not capacity.',
             'Response metric is successful full-request duration, not video latency or QoE.',
             'Paired difference = SmartConnect minus Wi-Fi-first; lower response time / higher goodput is favorable.',
             'Contrasts require both successes; inspect failure and no-eligible counts for survivor bias.',
             '95% percentile bootstrap resamples trial means (seed 2026); suppressed below four trials. Trials on one host are not independent populations.',
             'Failure gap spans successful completions bracketing failed slots, includes cadence/other traffic; absent gap means unknown disruption, not zero interruption.',
             'Direct recommended path changes exclude initial attachment and unavailable transitions; no confirmed handover or existing-session metric.', '',
             '```', summary.to_string(index=False), '```', '', '```', contrast.to_string(index=False), '```', '',
             'No missing values are replaced with zero. No achieved QoE improvement is asserted. Favorable and unfavorable signed contrasts are retained.']
    (path/'REPORT.md').write_text('\n'.join(lines)+'\n')
    return summary, contrast


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory')
    p.add_argument('--audit-only', action='store_true')
    a = p.parse_args()
    if a.audit_only:
        audit(a.directory)
        print('Phase 4 evidence audit passed')
    else:
        summarize(a.directory)

if __name__ == '__main__':
    main()
