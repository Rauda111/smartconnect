"""Check artifact hashes, replay fairness and summaries; no network access."""
import argparse
import hashlib
import json
import math
from numbers import Real
import tempfile
from pathlib import Path
import pandas as pd
from mac_hub.experiments.evaluate import replay, metrics


def audit(folder):
    manifest=json.loads((folder/'manifest.json').read_text())
    for name,digest in manifest['output_sha256'].items():
        actual=hashlib.sha256((folder/name).read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f'Artifact checksum mismatch: {name}')
    required={'observations.csv','decisions.csv','per_run.csv','aggregate.csv','paired_differences.csv','paired_summary.csv','event_responses.csv','response_summary.csv','REPORT.md'}
    if not required.issubset(manifest['output_sha256']):
        raise ValueError('Required evidence omitted from checksum manifest')
    observations=pd.read_csv(folder/'observations.csv')
    decisions=pd.read_csv(folder/'decisions.csv')
    summary=pd.read_csv(folder/'per_run.csv')
    runs=0
    for keys, trace in observations.groupby(['scenario','source','seed'],sort=True):
        for app in ('video_call','file_download'):
            expected=replay(trace.reset_index(drop=True),app)
            actual=decisions[(decisions.scenario==keys[0])&(decisions.source==keys[1])&
                             (decisions.seed==keys[2])&(decisions.application==app)].reset_index(drop=True)
            pd.testing.assert_frame_equal(expected,actual,check_dtype=False,check_like=True,atol=1e-7,rtol=1e-8)
            for method in ('wifi_first','smartconnect'):
                row=summary[(summary.scenario==keys[0])&(summary.source==keys[1])&
                            (summary.seed==keys[2])&(summary.application==app)&(summary.method==method)]
                if len(row)!=1:
                    raise ValueError('Missing or duplicate policy summary')
                for metric,value in metrics(actual,method,app).items():
                    stored=row.iloc[0][metric]
                    if pd.isna(value) and pd.isna(stored):
                        continue
                    if pd.isna(value) != pd.isna(stored):
                        raise ValueError(f'Summary missingness mismatch: {metric}')
                    if isinstance(value,Real) and not isinstance(value,bool):
                        if not math.isfinite(float(stored)) or not math.isclose(value,stored,rel_tol=1e-8,abs_tol=1e-7):
                            raise ValueError(f'Summary mismatch: {metric}')
                    elif value != stored:
                        raise ValueError(f'Summary mismatch: {metric}')
                runs+=1
    from mac_hub.experiments.independent import check
    if check(folder) != runs:
        raise ValueError('Independent run count mismatch')
    from mac_hub.experiments.scenarios import generate
    from mac_hub.experiments.run import ROOT
    synthetic=observations[observations.source=='synthetic']
    expected_groups={(name,seed) for name in ('stable','deteriorating_wifi','congested_wifi','cellular_degradation','wifi_recovery','network_unavailability') for seed in manifest['seeds']}
    if set(zip(synthetic.scenario,synthetic.seed)) != expected_groups:
        raise ValueError('Synthetic scenario/seed coverage mismatch')
    for (scenario,seed), trace in synthetic.groupby(['scenario','seed'],sort=True):
        generated=pd.DataFrame(generate(scenario,int(seed))[0])
        pd.testing.assert_frame_equal(generated,trace[generated.columns].reset_index(drop=True),
                                      check_dtype=False,atol=1e-7,rtol=1e-8)
    for index, item in enumerate(manifest['measured_inputs']):
        path=Path(item['path'])
        if not path.is_absolute():
            path=ROOT/path
        if not path.is_file():
            candidates=[ROOT/'mac_hub/verification'/path.name,ROOT/'mac_hub/experiments/measurements'/path.name]
            path=next((p for p in candidates if p.is_file()),path)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f'Measured input unavailable or checksum mismatch: {path}')
        raw=pd.read_csv(path)
        trace=observations[observations.scenario==f'measured_{index}_{path.stem}'].reset_index(drop=True)
        if len(trace) != item['windows'] or set(raw.source) != {'measured_icmp'}:
            raise ValueError('Measured input coverage mismatch')
        columns=[c for c in trace if c in raw and c not in ('application','stable_region')]
        pd.testing.assert_frame_equal(raw[columns],trace[columns],check_dtype=False,atol=1e-7,rtol=1e-8)
    from mac_hub.experiments.visuals import report
    tables={name:pd.read_csv(folder/(name+'.csv')) for name in ('aggregate','per_run','response_summary')}
    with tempfile.TemporaryDirectory() as directory:
        report(tables,Path(directory))
        if (Path(directory)/'REPORT.md').read_bytes() != (folder/'REPORT.md').read_bytes():
            raise ValueError('Report does not match verified CSV tables')
    return runs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results',type=Path)
    args=parser.parse_args()
    print(f'PASS: checksums, original inputs, paired replay, {audit(args.results)} policy-run summaries, independent statistics, event timings and CSV-rendered report verified')


if __name__=='__main__':
    main()
