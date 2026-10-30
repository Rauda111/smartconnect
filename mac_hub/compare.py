"""Counterfactual selected-probe comparison; not measured application outcomes."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd


def summarize(frame):
    rows = []
    for column in ('baseline','recommended'):
        selected = frame[column].fillna('none')
        result = dict(method=column, cycles=len(frame),
                      recommendation_changes=int((selected.ne(selected.shift()) & selected.shift().notna()).sum()),
                      no_recommendation_cycles=int(selected.eq('none').sum()))
        for metric in ('latency','loss','rtt_variation'):
            values = pd.Series([r.get(f'{r[column]}_{metric}') for _,r in frame.iterrows()], dtype='float64')
            result[f'{metric}_observed_cycles'] = int(values.notna().sum())
            result[f'{metric}_mean'] = values.mean()
        breaches = []
        for _,r in frame.iterrows():
            n = r[column]
            breaches.append(n == 'none' or pd.notna(r.get(f'{n}_breaches')) and bool(r.get(f'{n}_breaches')))
        result['observed_breach_or_no_path_cycles'] = sum(breaches)
        result['scope'] = 'paired probe selection proxy; unknown jitter/throughput guardrails excluded'
        rows.append(result)
    return pd.DataFrame(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    frame = pd.read_csv(args.csv)
    result = summarize(frame)
    with args.output.open('x') as f:
        result.to_csv(f,index=False)
    args.output.with_suffix('.provenance.json').write_text(json.dumps(dict(input=str(args.csv),sha256=hashlib.sha256(args.csv.read_bytes()).hexdigest(),source=frame.source.unique().tolist()),indent=2))
    print(result.to_string(index=False))


if __name__ == '__main__':
    main()
