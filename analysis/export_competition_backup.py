"""Offline allowlist exporter. Private originals stay local; output must be new."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

RUNS = ['smartconnect-smoke-20261103T202919Z','smartconnect-natural-20261103T203950Z',
        'smartconnect-movement-20261103T205000Z','smartconnect-download-20261103T211238Z']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_csv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, keys, lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def export(archive, output):
    archive, output = Path(archive), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    windows, requests, provenance = [], [], {}
    continuous = archive/'raw/original_mac_hub_logs/dorm-continuous-20261103.csv'
    name = continuous.stem
    provenance[name] = {continuous.name:digest(continuous),continuous.with_suffix('.manifest.json').name:digest(continuous.with_suffix('.manifest.json'))}
    with continuous.open(newline='') as stream:
        for i, row in enumerate(csv.DictReader(stream),1):
            out = dict(run=name, window=i, source='historical_measured_icmp', profile=row['application'],
                       timestamp_utc=row['timestamp'], elapsed_seconds=float(row['elapsed_seconds']),
                       selected=row['recommended'], baseline=row['baseline'],
                       candidate_advantage=row['advantage'], qualifying_count=int(row['hold_count']),
                       scoring_basis='icmp_rtt_and_loss', selected_request_status='not_collected',
                       selected_requested_interface='', selected_binding_readback='',
                       selected_request_ms='', selected_goodput_Mbps='', physical_egress='unverified')
            for n in ('wifi','cellular'):
                for field in ('latency','loss','sent','received','status','score','adjusted_score','breaches','unknown_guardrails'):
                    out[n+'_'+field] = row[n+'_'+field]
            windows.append(out)
    for name in RUNS:
        folder=archive/'raw'/name
        manifest=json.loads((folder/'manifest.json').read_text())
        for f,h in manifest['output_hashes'].items():
            if Path(f).name!=f or digest(folder/f)!=h:raise ValueError('Original evidence hash mismatch')
        provenance[name]={p.name:digest(p) for p in sorted(folder.iterdir()) if p.is_file()}
        events=[json.loads(line) for line in (folder/'events.jsonl').read_text().splitlines()]
        completed=[r for r in events if r.get('event')=='completed_window']
        if len(completed)!=manifest['completed_windows'] or manifest.get('cancelled'):
            raise ValueError('Expected completed uncancelled run')
        for row in completed:
            d=row['decision']; outcome=row.get('outcome') or {}
            out=dict(run=name,window=row['window'],source='actual_network_observations',profile=row['application'],
                     timestamp_utc=row['timestamp'],elapsed_seconds=row['elapsed_seconds'],selected=d['recommended'],
                     baseline=row['baseline'],candidate_advantage=d['advantage'],qualifying_count=d['hold_count'],
                     scoring_basis=d['scoring_basis'],selected_request_status=outcome.get('status'),
                     selected_requested_interface=outcome.get('requested_interface') if outcome.get('requested_interface') in ('en0','en6') else '',
                     selected_binding_readback=bool(outcome.get('binding_index')),selected_request_ms=outcome.get('request_duration_ms'),
                     selected_goodput_Mbps=outcome.get('goodput_mbps'),physical_egress='unverified')
            for n in ('wifi','cellular'):
                for field in ('latency','loss','sent','received','status'):out[n+'_'+field]=row['inputs'][n][field]
                for field in ('score','adjusted_score','breaches','unknown_guardrails'):out[n+'_'+field]=d['details'][n][field]
                cal=row.get('calibration',{}).get(n,{})
                out[n+'_calibration_status']=cal.get('status')
                out[n+'_calibration_goodput_Mbps']=cal.get('goodput_mbps')
            windows.append(out)
        raw_requests=[json.loads(line) for line in (folder/'requests.jsonl').read_text().splitlines()]
        for line,r in enumerate(raw_requests,1):
            requests.append(dict(run=name,source_request_line=line,window=r['window'],role=r['role'],
                                 requested_interface=r['requested_interface'] if r['requested_interface'] in ('en0','en6') else 'unknown',
                                 binding_readback=bool(r.get('binding_index')),status=r['status'],http_status=r.get('http_status'),
                                 completed_body_bytes=r.get('bytes_received'),request_duration_ms=r.get('request_duration_ms'),
                                 bounded_goodput_Mbps=r.get('goodput_mbps'),physical_egress='unverified'))
    save_csv(output/'windows.csv',windows);save_csv(output/'requests.csv',requests)
    summaries=[]
    for name in dict.fromkeys(r['run'] for r in windows):
        subset=[r for r in windows if r['run']==name]
        selected=[r for r in requests if r['run']==name and r['role']=='selected_outcome']
        summaries.append(dict(run=name,windows=len(subset),recommendation_changes=sum(a['selected']!=b['selected'] and a['selected'] in ('wifi','cellular') and b['selected'] in ('wifi','cellular') for a,b in zip(subset,subset[1:])),
                              selected_attempts=len(selected),selected_successes=sum(r['status']=='success' for r in selected),
                              selected_failures=sum(r['status']!='success' for r in selected),
                              selected_interfaces=[r['requested_interface'] for r in selected],physical_egress='unverified'))
    (output/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    def number(v):return float(v) if v not in (None,'') else float('nan')
    for name in dict.fromkeys(r['run'] for r in windows):
        subset=[r for r in windows if r['run']==name];x=[r['elapsed_seconds'] for r in subset]
        fig,axes=plt.subplots(3,1,figsize=(9,7),sharex=True)
        for n,label in [('wifi','Wi-Fi'),('cellular','Cellular-backed USB')]:
            axes[0].plot(x,[number(r[n+'_latency']) for r in subset],marker='o',label=label)
            axes[1].plot(x,[number(r[n+'_loss']) for r in subset],marker='o',label=label)
        axes[0].set_ylabel('Parsed mean RTT (ms)');axes[0].legend()
        axes[1].set_ylabel('ICMP loss (%)')
        axes[2].step(x,[{'wifi':1,'cellular':2}.get(r['selected'],0) for r in subset],where='post',label='SmartConnect')
        axes[2].step(x,[{'wifi':1,'cellular':2}.get(r['baseline'],0) for r in subset],where='post',linestyle='--',label='Wi-Fi-first')
        axes[2].set_yticks([0,1,2],['None','Wi-Fi','Cellular']);axes[2].set_ylim(-.2,2.2);axes[2].legend();axes[2].set_xlabel('Actual elapsed seconds (window completion)')
        fig.suptitle(name+'\nMeasured inputs; recommendations are not physical handovers',fontsize=10)
        fig.text(.02,.01,'Missing RTT stays missing. Location stages unassigned. Dorm continuous W15 parsed RTT omits a late reply.',fontsize=8)
        fig.tight_layout(rect=[0,.035,1,.93]);fig.savefig(output/(name+'.png'),dpi=150);plt.close(fig)
    name = RUNS[-1]
    subset=[r for r in windows if r['run']==name]
    x=[r['elapsed_seconds'] for r in subset]
    fig,axes=plt.subplots(2,1,figsize=(9,6),sharex=True)
    for n,label in [('wifi','Wi-Fi calibration'),('cellular','Cellular calibration')]:
        axes[0].plot(x,[number(r[n+'_calibration_goodput_Mbps']) for r in subset],marker='o',label=label)
    axes[0].set_ylabel('Bounded-object goodput (Mbps)');axes[0].legend()
    for status,marker,label in [('success','o','Successful selected request'),('timeout','x','Timed-out selected request')]:
        selected=[r for r in subset if r['selected_request_status']==status]
        axes[1].scatter([r['elapsed_seconds'] for r in selected],[number(r['selected_request_ms']) for r in selected],marker=marker,label=label)
    axes[1].set_ylabel('Whole selected-request duration (ms)');axes[1].set_xlabel('Actual elapsed seconds');axes[1].legend()
    fig.suptitle('Real File Download demonstration: calibration and selected outcomes',fontsize=11)
    fig.text(.02,.01,'64 KiB objects; setup included. Failed calibration goodput is missing, not zero. No matched Wi-Fi-first HTTP outcomes.',fontsize=8)
    fig.tight_layout(rect=[0,.04,1,.93]);fig.savefig(output/'download_goodput_and_outcomes.png',dpi=150);plt.close(fig)
    (output/'provenance.json').write_text(json.dumps(dict(original_sha256=provenance,
        privacy='Allowlisted fields only; no local IPs, MACs, ports, request identifiers, raw errors or ping text.',
        integrity='Original hashes recorded at export; not authenticated collection signatures.',
        numeric_units=dict(latency='ms, parsed successful-reply mean per window',loss='percent',goodput='Mbps, completed body bits/full fresh request duration'),
        output_sha256={p.name:digest(p) for p in sorted(output.iterdir()) if p.is_file()}),indent=2)+'\n')
    return summaries

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(export(a.archive,a.output),indent=2))
