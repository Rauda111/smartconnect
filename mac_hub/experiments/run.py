"""Offline paired experiments. No probes, network configuration or actuators."""
import argparse
from dataclasses import fields
from mac_hub.monitor import Measurement
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys
import pandas as pd
from mac_hub.experiments.scenarios import NAMES, generate
from mac_hub.experiments.evaluate import replay, metrics, responses

ROOT = Path(__file__).resolve().parents[2]
APPS = ('video_call', 'file_download')
METHODS = ('wifi_first', 'smartconnect')
SUMMARY_METRICS = ('latency_mean', 'loss_mean', 'rtt_variation_mean', 'recommended_handovers',
                   'observed_guardrail_violation_windows', 'no_path_windows',
                   'quiet_region_changes', 'reversals_within_30s')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(summary):
    rows = []
    for keys, group in summary.groupby(['scenario','source','application','method'],sort=True):
        for metric in SUMMARY_METRICS:
            values = group[metric].dropna()
            rows.append(dict(zip(('scenario','source','application','method'),keys),
                             metric=metric, n=len(values), mean=values.mean(),
                             sample_sd=values.std(ddof=1)))
    return pd.DataFrame(rows)


def paired(summary):
    records = []
    for keys, group in summary.groupby(['scenario','source','seed','application'],sort=True):
        by = group.set_index('method')
        for metric in SUMMARY_METRICS:
            records.append(dict(zip(('scenario','source','seed','application'),keys), metric=metric,
                                smartconnect_minus_wifi_first=by.loc['smartconnect',metric]-by.loc['wifi_first',metric]))
    return pd.DataFrame(records)


def build(output, seeds, measured=(), include_smoke=True):
    if not seeds or len(set(seeds)) != len(seeds) or any(s < 0 for s in seeds):
        raise ValueError('Provide distinct nonnegative seeds')
    if output.exists():
        raise FileExistsError('Choose a fresh output directory; evidence is never overwritten')
    traces, manifest_inputs = [], []
    for name in NAMES:
        for seed in seeds:
            rows, events = generate(name,seed)
            traces.append((pd.DataFrame(rows), events))
    real_paths = list(map(Path,measured))
    if include_smoke:
        real_paths.insert(0,ROOT/'mac_hub/verification/live_smoke_20261030.csv')
    for index, path in enumerate(real_paths):
        frame = pd.read_csv(path)
        if set(frame.source) != {'measured_icmp'}:
            raise ValueError('Measured trace must have source=measured_icmp')
        # Ignore stored policy columns: recompute both methods from observations.
        measurement_columns = {f'{n}_{f.name}' for n in ('wifi','cellular') for f in fields(Measurement)}
        keep = ['timestamp','elapsed_seconds','source'] + [c for c in frame if c in measurement_columns]
        frame = frame[keep].copy()
        frame['scenario'] = f'measured_{index}_{path.stem}'
        frame['seed'] = -1  # no seed/no replication for measured captures
        frame['target'] = pd.read_csv(path).get('target', pd.Series(['unknown']*len(frame)))
        traces.append((frame, []))
        manifest_inputs.append(dict(path=str(path), sha256=sha(path), windows=len(frame)))
    observations, decisions, summaries, event_rows = [], [], [], []
    for frame, events in traces:
        observations.append(frame)
        meta = {k:frame.iloc[0][k] for k in ('scenario','source','seed')}
        for app in APPS:
            result = replay(frame, app)
            decisions.append(result)
            for method in METHODS:
                summaries.append(dict(**meta, **metrics(result,method,app)))
                event_rows.extend(dict(**meta, application=app, **r) for r in responses(result,method,events))
    output.mkdir(parents=True)
    tables = dict(observations=pd.concat(observations,ignore_index=True),
                  decisions=pd.concat(decisions,ignore_index=True),
                  per_run=pd.DataFrame(summaries), event_responses=pd.DataFrame(event_rows))
    tables['aggregate'] = aggregate(tables['per_run'])
    tables['paired_differences'] = paired(tables['per_run'])
    tables['paired_summary'] = tables['paired_differences'].groupby(
        ['scenario','source','application','metric'],sort=True).smartconnect_minus_wifi_first.agg(
            n='count',mean='mean',sample_sd='std').reset_index()
    tables['response_summary'] = tables['event_responses'].groupby(
        ['scenario','source','application','method','event'],sort=True).agg(
            events=('observed_response','size'),observed_responses=('observed_response','sum'),
            already_on_target_events=('already_on_target','sum'),
            mean_response_seconds=('response_seconds','mean'),
            sample_sd_seconds=('response_seconds','std')).reset_index()
    tables['response_summary']['unobserved_responses'] = tables['response_summary'].events-tables['response_summary'].observed_responses
    for name, frame in tables.items():
        frame.to_csv(output/f'{name}.csv',index=False,float_format='%.10g')
    from mac_hub.experiments.visuals import plots, report
    plots(tables, output)
    # Render the exact serialized evidence, avoiding rounding discrepancies
    # between full-precision in-memory statistics and published CSV values.
    report({name:pd.read_csv(output/f'{name}.csv') for name in tables}, output)
    files = sorted([*ROOT.glob('mac_hub/**/*.py'),ROOT/'smartconnect.py'])
    revision = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    manifest = dict(schema_version=1, revision=revision, python=sys.version, seeds=seeds,
                    dependencies={name:version(name) for name in ('numpy','pandas','matplotlib','streamlit')},
                    requirements_sha256=sha(ROOT/'requirements.txt'),
                    synthetic_window_seconds=5, synthetic_windows=90,
                    profiles=list(APPS), methods=list(METHODS),
                    policy=dict(margin=.05,hold_windows=3,dwell_seconds=30,trend_window=5,trend_weight=.5),
                    scope='counterfactual selection proxies; no actual switching or application QoE measurement',
                    source_sha256={str(p.relative_to(ROOT)):sha(p) for p in files},
                    measured_inputs=manifest_inputs,
                    output_sha256={str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return tables


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--seeds',type=int,nargs='+',default=list(range(10)))
    parser.add_argument('--measured',type=Path,action='append',default=[])
    parser.add_argument('--no-smoke',action='store_true',help='exclude the one-window Phase 1 smoke capture')
    args=parser.parse_args()
    tables=build(args.output_dir,args.seeds,args.measured,not args.no_smoke)
    print(f"Wrote {len(tables['per_run'])} policy-run summaries to {args.output_dir}; all outcomes are selection proxies.")


if __name__=='__main__':
    main()
