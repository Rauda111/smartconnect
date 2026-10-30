"""Check artifact hashes, replay fairness and summaries; no network access."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from mac_hub.experiments.evaluate import replay, metrics


def audit(folder):
    manifest=json.loads((folder/'manifest.json').read_text())
    for name,digest in manifest['output_sha256'].items():
        actual=hashlib.sha256((folder/name).read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f'Artifact checksum mismatch: {name}')
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
                    if isinstance(value,(int,float)) and not isinstance(value,bool):
                        if abs(value-stored)>1e-6:
                            raise ValueError(f'Summary mismatch: {metric}')
                    elif value != stored:
                        raise ValueError(f'Summary mismatch: {metric}')
                runs+=1
    return runs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results',type=Path)
    args=parser.parse_args()
    print(f'PASS: checksums, paired replay and {audit(args.results)} policy-run summaries verified')


if __name__=='__main__':
    main()
