"""Stage A descriptive HTTP outcomes; no causal QoE or policy comparison."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics


def summarize(records):
    result=[]
    for interface in sorted({r['requested_interface'] for r in records}):
        group=[r for r in records if r['requested_interface']==interface]
        actual=[r for r in group if r['source']=='actual_https']
        success=[r for r in actual if r['status']=='success']
        durations=[float(r['request_duration_ms']) for r in success]
        result.append(dict(interface=interface,planned=len(group),actual_attempts=len(actual),successes=len(success),
                           failures=sum(r['status'] not in ('success','cancelled') for r in actual),
                           timeouts=sum(r['status']=='timeout' for r in actual),
                           cancellations=sum(r['status']=='cancelled' for r in actual),
                           confirmed_successes=sum(r.get('capture_egress_status')=='pcap_confirmed' for r in success),
                           mean_success_duration_ms=statistics.mean(durations) if durations else None,
                           sample_sd_ms=statistics.stdev(durations) if len(durations)>1 else None,
                           evidence_type='actual_http_outcomes' if actual else 'dry_run',
                           scope='manual request sequence; not a SmartConnect versus baseline comparison'))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requests-csv',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    a=parser.parse_args()
    with a.requests_csv.open(newline='') as stream:
        data=list(csv.DictReader(stream))
    rows=summarize(data)
    if not rows:
        raise ValueError('No request records')
    a.output_dir.mkdir(parents=True,exist_ok=False)
    with (a.output_dir/'summary.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (a.output_dir/'manifest.json').write_text(json.dumps(dict(input=str(a.requests_csv),sha256=hashlib.sha256(a.requests_csv.read_bytes()).hexdigest()),indent=2)+'\n')
    lines=['# Phase 3 Stage A request outcomes','',
           'Fresh IPv4 HTTPS requests only. Confirmed egress requires independent dual-interface packet evidence. A requested interface, bound-index readback or successful HTTP response alone is not proof of egress.','',
           '| Interface | Actual attempts | Success | Failed | Timeout (subset of failed) | Cancelled | Capture-confirmed success | Mean successful request duration (ms) |',
           '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        mean='unknown' if r['mean_success_duration_ms'] is None else f"{r['mean_success_duration_ms']:.3f}"
        lines.append(f"| {r['interface']} | {r['actual_attempts']} | {r['successes']} | {r['failures']} | {r['timeouts']} | {r['cancellations']} | {r['confirmed_successes']} | {mean} |")
    lines+=['','Request duration includes client setup, TCP, TLS, HTTP headers and bounded response body receipt; it is not ICMP RTT or throughput. Failed attempts are reported separately, not replaced with zero latency. No application was migrated, no policy comparison was performed, and no existing TCP/video session continuity was tested.','']
    (a.output_dir/'REPORT.md').write_text('\n'.join(lines))


if __name__=='__main__':
    main()
