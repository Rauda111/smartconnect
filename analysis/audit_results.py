"""Independent standard-library audit of fresh SmartConnect experiment outputs.

Does not import the production simulator or the analysis script. Recalculates
selected-path means, handovers, dwell shares, and prototype guardrails directly
from the raw CSVs, then compares across-seed mean/sample SD with mean_sd.csv.

Usage: python audit_results.py --results-dir /path/to/final_testing --repo /path/to/smartconnect
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess

SCENARIOS = ('leaving_wifi', 'congested_wifi', 'large_download', 'recovery')
APPLICATIONS = ('video_call', 'file_download')
TRACE_COLUMNS = ['time'] + [f'{prefix}_{metric}' for prefix in ('wifi', 'g5')
                            for metric in ('rssi', 'latency', 'loss', 'jitter', 'throughput')]
HEADLINE_METRICS = ('latency_ms', 'loss_pct', 'jitter_ms', 'throughput_mbps',
                    'handovers', 'wifi_steps', 'g5_steps', 'wifi_pct', 'g5_pct',
                    'qoe_any_steps', 'qoe_any_pct')
LIMITS = {'video_call': {'latency': 60.0, 'loss': 2.0, 'jitter': 20.0},
          'file_download': {'loss': 3.0, 'throughput': 20.0}}
TOLERANCE = 1e-9


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(newline='') as source:
        return list(csv.DictReader(source))


def is_true(value):
    if value not in ('True', 'False'):
        raise ValueError(f'Unexpected boolean CSV value: {value!r}')
    return value == 'True'


def breach(value, metric, limit):
    return value < limit if metric == 'throughput' else value > limit


def calculate(records, application):
    selected = []
    for row in records:
        prefix = {'WiFi': 'wifi', '5G': 'g5'}[row['selected_network']]
        selected.append({metric: float(row[f'{prefix}_{metric}'])
                         for metric in ('latency', 'loss', 'jitter', 'throughput')})
    count = len(records)
    wifi_steps = sum(row['selected_network'] == 'WiFi' for row in records)
    limits = LIMITS[application]
    violations = [any(breach(value[metric], metric, limit)
                      for metric, limit in limits.items()) for value in selected]
    result = {
        'latency_ms': statistics.mean(value['latency'] for value in selected),
        'loss_pct': statistics.mean(value['loss'] for value in selected),
        'jitter_ms': statistics.mean(value['jitter'] for value in selected),
        'throughput_mbps': statistics.mean(value['throughput'] for value in selected),
        'handovers': sum(is_true(row['handover']) for row in records),
        'wifi_steps': wifi_steps,
        'g5_steps': count - wifi_steps,
        'wifi_pct': 100.0 * wifi_steps / count,
        'g5_pct': 100.0 * (count - wifi_steps) / count,
        'qoe_any_steps': sum(violations),
        'qoe_any_pct': 100.0 * sum(violations) / count,
    }
    for metric, limit in limits.items():
        violation_count = sum(breach(value[metric], metric, limit) for value in selected)
        result[f'qoe_{metric}_pct'] = 100.0 * violation_count / count
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-dir', required=True, type=Path)
    parser.add_argument('--repo', required=True, type=Path)
    args = parser.parse_args()
    result_dir, repo = args.results_dir.resolve(), args.repo.resolve()
    failures = []

    def check(condition, description):
        if not condition:
            failures.append(description)

    manifest = json.loads((result_dir / 'verification/experiment_manifest.json').read_text())
    check(manifest.get('complete') is True, 'Experiment manifest is incomplete.')
    check(manifest.get('source_unchanged') is True, 'Manifest does not assert unchanged source.')
    check(manifest['tests']['count'] == 9 and manifest['tests']['passed'] is True,
          'Required nine-test gate is not recorded as passed.')
    test_log = (result_dir / manifest['tests']['log']).read_text()
    check('Ran 9 tests' in test_log and '\nOK\n' in test_log,
          'Saved test log does not contain Ran 9 tests / OK.')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    check(head == manifest['commit'] == manifest['remote_main_commit'],
          'Checked-out HEAD, manifest commit, and pulled origin/main differ.')
    source_checked = []
    for filename, expected in manifest['source_sha256'].items():
        live = repo / filename
        snapshot = result_dir / 'source_snapshot' / filename
        blob = subprocess.check_output(['git', 'show', f'{head}:{filename}'], cwd=repo)
        check(sha256(live) == expected == sha256(snapshot) == hashlib.sha256(blob).hexdigest(),
              f'Source mismatch: {filename}')
        source_checked.append(filename)

    runs = manifest['runs']
    check(len(runs) == 120, f'Manifest has {len(runs)} runs, expected 120.')
    raw_paths = sorted((result_dir / 'raw_csv').glob('*.csv'))
    check(len(raw_paths) == 120, f'Raw directory has {len(raw_paths)} CSVs, expected 120.')
    check({path.name for path in raw_paths} == {Path(run['raw_csv']).name for run in runs},
          'Raw-directory filenames do not equal manifest filenames.')
    expected_keys = {(scenario, seed, method, app)
                     for scenario in SCENARIOS for seed in range(10)
                     for method, app in [('baseline', None), ('smartconnect', 'video_call'),
                                         ('smartconnect', 'file_download')]}
    indexed = {(run['scenario'], run['seed'], run['method'], run['application']): run for run in runs}
    check(set(indexed) == expected_keys, 'Manifest configuration set differs from exact 4 x 10 x 3 design.')
    check(len(indexed) == len(runs), 'Duplicate scenario/seed/configuration entries in manifest.')
    raw_data = {}
    selected_samples = 0
    smartconnect_handover_gaps = []
    observed_endings = {}
    for key, run in indexed.items():
        path = result_dir / run['raw_csv']
        check(sha256(path) == run['sha256'], f'Raw checksum mismatch: {path.name}')
        data = rows(path)
        raw_data[key] = data
        selected_samples += len(data)
        check(len(data) == 100, f'Run does not have 100 samples: {path.name}')
        check([float(row['time']) for row in data] == list(range(100)),
              f'Time column is not 0..99: {path.name}')
        check(all(math.isfinite(float(row[column])) for row in data for column in TRACE_COLUMNS),
              f'Trace contains nonfinite values: {path.name}')
        check(all(row['selected_network'] in ('WiFi', '5G') for row in data),
              f'Invalid selected path: {path.name}')
        flags = [is_true(row['handover']) for row in data]
        changes = [False] + [data[i]['selected_network'] != data[i-1]['selected_network']
                             for i in range(1, len(data))]
        check(flags == changes, f'Handover flags differ from observed selection changes: {path.name}')
        if run['method'] == 'baseline':
            check(all(row['selected_network'] == ('WiFi' if float(row['wifi_rssi']) >= float(row['g5_rssi'])
                                                  else '5G') for row in data),
                  f'Baseline selections disagree with unchanged RSSI rule: {path.name}')
        else:
            app = run['application']
            events = [int(float(row['time'])) for row in data if is_true(row['handover'])]
            gaps = [second - first for first, second in zip(events, events[1:])]
            smartconnect_handover_gaps.extend(gaps)
            check(all(gap >= 8 for gap in gaps), f'SmartConnect violated its eight-step minimum dwell: {path.name}')
            ending_key = f"{run['scenario']}/{app}"
            observed_endings.setdefault(ending_key, {'WiFi': 0, '5G': 0})[data[-1]['selected_network']] += 1
            for prefix, flag in [('wifi', 'wifi_guardrail'), ('g5', 'g5_guardrail')]:
                check(all(is_true(row[flag]) == any(breach(float(row[f'{prefix}_{metric}']), metric, limit)
                                                    for metric, limit in LIMITS[app].items())
                          for row in data),
                      f'SmartConnect recorded guardrail flags disagree with independent rule: {path.name}/{flag}')

    paired_trace_sets = 0
    paired_field_checks = 0
    for scenario in SCENARIOS:
        for seed in range(10):
            baseline = raw_data[(scenario, seed, 'baseline', None)]
            for app in APPLICATIONS:
                other = raw_data[(scenario, seed, 'smartconnect', app)]
                for i, (first, second) in enumerate(zip(baseline, other)):
                    for column in TRACE_COLUMNS:
                        check(first[column] == second[column],
                              f'Trace mismatch at {scenario}/seed{seed}/{app}/row{i}/{column}')
                        paired_field_checks += 1
            paired_trace_sets += 1

    aggregates = {}
    for scenario in SCENARIOS:
        for app in APPLICATIONS:
            for method in ('baseline', 'smartconnect'):
                records = [calculate(raw_data[(scenario, seed, method, None if method == 'baseline' else app)], app)
                           for seed in range(10)]
                for metric in records[0]:
                    values = [record[metric] for record in records]
                    aggregates[(scenario, app, method, metric)] = {
                        'n': len(values), 'mean': statistics.mean(values), 'std': statistics.stdev(values)}

    per_run_comparisons = 0
    per_run_maximum_error = 0.0
    for table, expected_rows in [('per_run_metrics.csv', 120), ('per_application_metrics.csv', 160)]:
        run_table = rows(result_dir / 'tables' / table)
        check(len(run_table) == expected_rows, f'{table} has {len(run_table)} rows, expected {expected_rows}.')
        seen = set()
        for row in run_table:
            scenario, app, method, seed = row['scenario'], row['application'], row['method'], int(row['seed'])
            key = (scenario, seed, method, None if method == 'baseline' else app)
            check((scenario, seed, method, app) not in seen, f'Duplicate per-run key in {table}: {key}/{app}')
            seen.add((scenario, seed, method, app))
            expected = calculate(raw_data[key], app or 'video_call')
            check(int(row['n_steps']) == 100, f'Invalid n_steps in {table}: {key}')
            for metric, number in expected.items():
                if not app and metric.startswith('qoe_'):
                    check(row.get(metric, '') == '', f'Profile-neutral baseline has QoE field in {table}: {metric}')
                    continue
                if metric not in row:
                    check(False, f'Missing metric in {table}: {metric}')
                    continue
                error = abs(float(row[metric]) - number)
                per_run_maximum_error = max(per_run_maximum_error, error)
                check(error <= TOLERANCE, f'Per-run numeric mismatch in {table}: {key}/{app}/{metric}')
                per_run_comparisons += 1

    summaries = rows(result_dir / 'tables/mean_sd.csv')
    comparison_count = 0
    maximum_absolute_error = 0.0
    matched_summary_keys = set()
    unknown_metrics = set()
    for row in summaries:
        key = (row['scenario'], row['application'], row['method'], row['metric'])
        if key not in aggregates:
            unknown_metrics.add(row['metric'])
            continue
        check(key not in matched_summary_keys, f'Duplicate summary key: {key}')
        matched_summary_keys.add(key)
        expected = aggregates[key]
        check(int(row['n']) == expected['n'] == 10, f'Summary n is not 10: {key}')
        for statistic in ('mean', 'std'):
            actual = float(row[statistic])
            error = abs(actual - expected[statistic])
            maximum_absolute_error = max(maximum_absolute_error, error)
            check(math.isfinite(actual) and error <= TOLERANCE,
                  f'Numeric mismatch {key}/{statistic}: table={actual}, independent={expected[statistic]}')
            comparison_count += 1
    expected_summary_keys = {(scenario, app, method, metric)
                             for scenario in SCENARIOS for app in APPLICATIONS
                             for method in ('baseline', 'smartconnect') for metric in HEADLINE_METRICS}
    check(expected_summary_keys <= matched_summary_keys, 'Some required headline summaries were absent.')

    report = {
        'passed': not failures,
        'audited_utc': datetime.now(timezone.utc).isoformat(),
        'implementation': 'Independent Python standard library csv/statistics; no simulator or analysis imports.',
        'commit': head,
        'raw_csv_count': len(raw_paths),
        'manifest_run_count': len(runs),
        'samples_per_run_expected': 100,
        'selected_path_samples': selected_samples,
        'unique_scenario_seed_traces': paired_trace_sets,
        'unique_trace_samples': paired_trace_sets * 100,
        'trace_columns_verified': TRACE_COLUMNS,
        'paired_trace_field_comparisons': paired_field_checks,
        'raw_hashes_verified': len(indexed),
        'smartconnect_minimum_observed_handover_gap_steps': min(smartconnect_handover_gaps) if smartconnect_handover_gaps else None,
        'smartconnect_final_selected_network_counts': observed_endings,
        'source_files_verified_against_manifest_snapshot_and_git': source_checked,
        'summary_rows_compared': len(matched_summary_keys),
        'numeric_mean_and_sd_comparisons': comparison_count,
        'numeric_per_run_metric_comparisons': per_run_comparisons,
        'sample_sd_definition': 'statistics.stdev over 10 per-run metrics; sample denominator n-1.',
        'numeric_absolute_tolerance': TOLERANCE,
        'maximum_absolute_error': maximum_absolute_error,
        'maximum_per_run_absolute_error': per_run_maximum_error,
        'additional_summary_metrics_not_independently_checked': sorted(unknown_metrics),
        'guardrails_independently_applied': LIMITS,
        'guardrail_inequalities': 'latency/loss/jitter > limit; throughput < limit; equality is allowed.',
        'handover_definition': 'Changes between consecutive selected networks; initial attachment excluded.',
        'time_definition': 'Simulation steps; no wall-clock duration assumed.',
        'simulation_label': manifest['simulation_label'],
        'failures': failures,
    }
    path = result_dir / 'verification/independent_audit.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit('Independent audit failed; see verification/independent_audit.json.')


if __name__ == '__main__':
    main()
