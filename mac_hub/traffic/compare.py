"""Actual Stage B outcomes. No egress or continuity inference from HTTP success."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics


def summarize(rows):
    summaries=[]
    paired_cycles={r['cycle'] for r in rows if 'cycle' in r and {q['policy'] for q in rows if q.get('cycle')==r['cycle']}=={'wifi_first','smartconnect'}}
    for policy in ('wifi_first','smartconnect'):
        group=[r for r in rows if r['policy']==policy]
        actual=[r for r in group if r['source']=='actual_https']
        active=[r for r in group if r['source'] in ('actual_https','no_request')]
        no_path=[r for r in group if r['source']=='no_request']
        success=[r for r in actual if r['status']=='success']
        changes=[r for r in group if str(r['recommended_change'])=='True']
        durations=[float(r['request_duration_ms']) for r in success]
        failed=[r for r in actual if r['status'] not in ('success','cancelled')]
        confirmed=[r for r in actual if r.get('capture_egress_status')=='pcap_confirmed']
        all_verified=bool(actual) and len(confirmed)==len(actual)
        confirmed_changes=None
        if all_verified:
            paths=[r['capture_verified_egress'] for r in actual]
            confirmed_changes=sum(a!=b for a,b in zip(paths,paths[1:]))
        # A sampled workload interruption proxy, not network outage duration.
        # Only report a gap bracketed by success with >=1 intervening failure.
        last_success=None
        failing=False
        gaps=[]
        max_streak=streak=0
        for r in active:
            if r['status']=='success':
                if failing and last_success is not None:
                    gaps.append((float(r['end_epoch'])-last_success)*1000)
                last_success=float(r['end_epoch']);failing=False;streak=0
            elif r['status']!='cancelled':
                failing=True;streak+=1;max_streak=max(max_streak,streak)
        summaries.append(dict(policy=policy,complete_paired_rounds=len(paired_cycles),recorded_attempts=len(group),actual_attempts=len(actual),active_workload_slots=len(active),no_eligible_path_slots=len(no_path),successes=len(success),
                              failed_or_no_path_attempts=len(failed)+len(no_path),timeouts=sum(r['status']=='timeout' for r in actual),
                              cancelled=sum(r['status']=='cancelled' for r in actual),
                              recommended_path_changes=len(changes),independently_confirmed_path_changes=confirmed_changes,
                              mean_success_duration_ms=statistics.mean(durations) if durations else None,
                              sample_sd_ms=statistics.stdev(durations) if len(durations)>1 else None,
                              failed_attempts_on_change_round=sum(r['status'] not in ('success','cancelled') for r in active if str(r['recommended_change'])=='True'),
                              longest_failure_streak=max_streak,trailing_failure_streak=streak if failing else 0,
                              bracketed_failure_gaps=len(gaps),max_bracketed_failure_gap_ms=max(gaps) if gaps else None,
                              confirmed_transition_delay_ms=None,
                              interpretation='actual request outcomes; unverified per-request egress unless packet evidence attached'))
    return summaries


def report(input_dir,output):
    with (input_dir/'requests.csv').open(newline='') as stream:
        rows=list(csv.DictReader(stream))
    manifest=json.loads((input_dir/'manifest.json').read_text())
    summaries=summarize(rows)
    output.mkdir(parents=True,exist_ok=False)
    with (output/'summary.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(summaries[0]));writer.writeheader();writer.writerows(summaries)
    lines=['# Phase 3 Stage B controlled request comparison','',
           f"Input mode: {manifest['mode']}. Scope: {manifest['input_scope']}. Profile: {manifest['application']}.",'',
           'Both policies receive the same per-round observation snapshot. Each makes a separate new GET to the same endpoint, alternating request order across rounds. These are actual outcomes, not identical counterfactual outcomes; sequential timing, TLS/endpoint variability and shared-path contention can differ. This is a functional steering test, not a randomized QoE trial. Summaries retain all attempts, including failures; complete paired-round counts expose any cancellation imbalance.','',
           '| Policy | Actual attempts | Success | Failed/no path | Requested path changes | Independently confirmed path changes | Mean successful request time (ms) |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for r in summaries:
        confirmed='unverified' if r['independently_confirmed_path_changes'] is None else str(r['independently_confirmed_path_changes'])
        mean='unknown' if r['mean_success_duration_ms'] is None else f"{r['mean_success_duration_ms']:.3f}"
        lines.append(f"| {r['policy']} | {r['actual_attempts']} | {r['successes']} | {r['failed_or_no_path_attempts']} | {r['recommended_path_changes']} | {confirmed} | {mean} |")
    lines+=['',
            'Controlled mode uses explicitly synthetic Wi-Fi deterioration at 5 seconds and recovery at 40 seconds to exercise the real request client without changing actual networks. Its assumed QoS values are not measurements. Live mode instead uses concurrent interface-bound ICMP snapshots; those ICMP probes still do not measure application jitter, RSSI or capacity.', '',
            'Stage A independently validated this client on en0/en6, but does not establish the egress of each later request. No new capture was authorized for this comparison. Confirmed traffic transition delay remains unknown; successful responses alone are not egress confirmation.', '',
            'rounds.csv separates monitoring-window duration from decision-computation duration. requests.csv records dispatch delay after the decision and decision-to-success duration. A bracketed failure gap is a sampled application interruption proxy only if failures occur between two successful attempts; it includes intentional cadence and workload time and is not network outage duration. With no failures, there is no measured failure gap, rather than proof of zero interruption. No existing connections, downloads or calls were migrated.','']
    (output/'REPORT.md').write_text('\n'.join(lines))
    (output/'manifest.json').write_text(json.dumps(dict(inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in input_dir.glob('*') if p.is_file()}),indent=2)+'\n')
    return summaries


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(report(a.input_dir,a.output_dir),indent=2))


if __name__=='__main__':
    main()
