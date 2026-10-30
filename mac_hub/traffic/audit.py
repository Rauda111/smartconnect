"""Offline Phase 3 evidence checks; reads existing PCAPs, never captures."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import tempfile
from mac_hub.traffic.verify import verify
from mac_hub.traffic.compare import report
from mac_hub.engine import Engine
from mac_hub.monitor import Measurement


def read(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def audit(evidence,requests,captures):
    stored=json.loads((evidence/'stage_a_verification/stage_a.json').read_text())
    with tempfile.TemporaryDirectory() as directory:
        fresh=verify(requests,captures,Path(directory)/'stage_a')
        for field in ('stage_a_passed','client_sha256','request_csv_sha256','request_manifest_sha256',
                      'capture_manifest_sha256','records','confirmed_successes','interface_indices'):
            if fresh[field]!=stored[field]:
                raise ValueError(f'Stage A evidence mismatch: {field}')
        if fresh['stage_a_passed'] is not True:
            raise ValueError('Stage A failed')
        for name,report_name in [('controlled_final','controlled_report'),('live_workload','live_report')]:
            folder=evidence/name
            rows=read(folder/'requests.csv')
            rounds=read(folder/'rounds.csv')
            manifest=json.loads((folder/'manifest.json').read_text())
            if manifest['uid']==0:
                raise ValueError('Request process was privileged')
            snapshot=(folder/'controller_source.txt').read_bytes()
            if hashlib.sha256(snapshot).hexdigest()!=manifest['source_sha256']['experiment.py']:
                raise ValueError('Executed controller snapshot hash mismatch')
            engine=Engine(manifest['application'])
            for r in rounds:
                metrics={}
                for network,interface in [('wifi','en0'),('cellular','en6')]:
                    metrics[network]=Measurement(interface,status=r[f'{network}_status'],
                        latency=float(r[f'{network}_latency']) if r[f'{network}_latency'] else None,
                        loss=float(r[f'{network}_loss']) if r[f'{network}_loss'] else None)
                    for unavailable in ('rssi','jitter','throughput'):
                        if r[f'{network}_{unavailable}']:
                            raise ValueError('Unavailable metric populated')
                d=engine.step(metrics,float(r['elapsed_seconds']))
                base=next((n for n in ('wifi','cellular') if metrics[n].status=='reachable'),'none')
                if (d['recommended'],base)!=(r['smartconnect'],r['wifi_first']):
                    raise ValueError('Recorded recommendations do not match causal engine replay')
                pair=[q for q in rows if q['cycle']==r['cycle']]
                if {q['policy'] for q in pair}!={'smartconnect','wifi_first'} or len(pair)!=2:
                    raise ValueError('Missing paired workload slot')
                expected=['wifi_first','smartconnect'] if int(r['cycle'])%2==0 else ['smartconnect','wifi_first']
                if [q['policy'] for q in pair]!=expected:
                    raise ValueError('Request-order balancing mismatch')
                for q in pair:
                    if q['selected_path']!=r[q['policy']] or q['monitor_source']!=r['monitor_source']:
                        raise ValueError('Policy did not consume the common observation snapshot')
                    if q['verified_egress'] or q['egress_status']!='unverified' or q['confirmed_transition_ms']:
                        raise ValueError('Later request incorrectly claims independent egress/transition proof')
            generated=Path(directory)/name
            report(folder,generated)
            for filename in ('summary.csv','REPORT.md'):
                if (generated/filename).read_bytes()!=(evidence/report_name/filename).read_bytes():
                    raise ValueError(f'Comparison report mismatch: {name}/{filename}')
            summaries=read(evidence/report_name/'summary.csv')
            for s in summaries:
                group=[r for r in rows if r['policy']==s['policy']]
                successes=[r for r in group if r['source']=='actual_https' and r['status']=='success']
                duration=[float(r['request_duration_ms']) for r in successes]
                if duration and abs(float(s['mean_success_duration_ms'])-statistics.mean(duration))>1e-9:
                    raise ValueError('Successful-request mean mismatch')
                actual=[r for r in group if r['source']=='actual_https']
                if int(s['actual_attempts'])!=len(actual) or int(s['successes'])!=len(successes):
                    raise ValueError('Actual request count mismatch')
                if int(s['timeouts'])!=sum(r['status']=='timeout' for r in actual):
                    raise ValueError('Timeout count mismatch')
                if s['independently_confirmed_path_changes'] or s['confirmed_transition_delay_ms']:
                    raise ValueError('Unverified traffic transition reported as measured')
    return 'PASS: 4 Stage A flows independently verified; both later workload reports and causal decisions checked; later egress remains unverified'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-dir',type=Path,default=Path('mac_hub/traffic/evidence'))
    p.add_argument('--stage-a-request-dir',type=Path,default=Path('mac_hub/logs/phase3-stage-a-clean-requests'))
    p.add_argument('--stage-a-capture-dir',type=Path,default=Path('mac_hub/logs/phase3-stage-a-clean-capture'))
    a=p.parse_args()
    print(audit(a.evidence_dir,a.stage_a_request_dir,a.stage_a_capture_dir))


if __name__=='__main__':
    main()
