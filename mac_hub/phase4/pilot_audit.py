"""Independent, offline location-pilot arithmetic/provenance audit; no networking."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[2]
STAGES = ('A_before', 'B', 'A_return')
ORDER = ['en0','en6','en6','en0','en6','en0','en0','en6']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def near(a, b):
    require(math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-9), f'Numerical mismatch: {a} != {b}')


def read(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


@lru_cache(None)
def historical_hash(revision, path):
    require(re.fullmatch('[a-f0-9]{40}',revision) and not Path(path).is_absolute() and '..' not in Path(path).parts, 'Unsafe source reference')
    result = subprocess.run(['git','show',f'{revision}:{path}'],cwd=ROOT,capture_output=True,check=True)
    return hashlib.sha256(result.stdout).hexdigest()


def sources(manifest, key):
    for path, digest in manifest[key].items():
        require(historical_hash(manifest['revision'],path)==digest, f'Historical source hash mismatch: {path}')


def audit(directory):
    directory=Path(directory)
    preserved=json.loads((directory/'preservation.json').read_text())
    raw=directory/'raw'
    actual={str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}
    require(actual==set(preserved['files']), 'Preserved file inventory differs')
    for name,digest in preserved['files'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Unsafe evidence filename')
        require(hashlib.sha256((raw/name).read_bytes()).hexdigest()==digest, f'Preservation checksum mismatch: {name}')
    summary=read(raw/'pilot_summary.csv')
    require(len(summary)==6,'Expected six stage/path summaries')
    summary_map={(r['stage'],r['network']):r for r in summary}
    require(len(summary_map)==6,'Duplicate summary keys')
    address=(raw/'endpoint-ipv4.txt').read_text().strip()
    ids=set()
    values={}
    timeline=[]
    binding={n:set() for n in ('en0','en6')}
    all_sent=all_received=0
    for stage in STAGES:
        monitor=read(raw/f'{stage}-icmp.csv')
        manifest=json.loads((raw/f'{stage}-icmp.manifest.json').read_text())
        sources(manifest,'source_hashes')
        require(manifest['arguments']['target']=='1.1.1.1' and manifest['arguments']['count']=='10' and manifest['arguments']['cycles']=='4','ICMP configuration mismatch')
        require(len(monitor)==4,'Expected four ICMP windows')
        stage_start=datetime.fromisoformat(manifest['created_utc']).timestamp()
        stamps=[datetime.fromisoformat(row['timestamp']).timestamp() for row in monitor]
        elapsed=[float(row['elapsed_seconds']) for row in monitor]
        require(stamps==sorted(set(stamps)) and elapsed==sorted(set(elapsed)) and stage_start<=stamps[0], 'Nonmonotonic ICMP timeline')
        require(all(row['target']=='1.1.1.1' for row in monitor),'Unexpected ICMP endpoint')
        requests=read(raw/f'{stage}-https'/'requests.csv')
        http_manifest=json.loads((raw/f'{stage}-https'/'manifest.json').read_text())
        sources(http_manifest,'source_sha256')
        require(http_manifest['revision']==manifest['revision'],'Stage source revisions differ')
        require(http_manifest['started_epoch']>=stamps[-1],'HTTP precedes completed stationary ICMP stage')
        if timeline:
            require(stage_start>=timeline[-1]['http_ended_epoch'],'Stages overlap or are out of order')
        require(not http_manifest['cancelled'] and http_manifest['mode']=='actual_https' and http_manifest['uid']!=0,'Unexpected request provenance')
        target=http_manifest['target']
        require(target==dict(address=address,server_name='speed.cloudflare.com',path='/__down?bytes=65536',port=443,timeout=5.0,max_bytes=65536),'Target mismatch')
        require([r['requested_interface'] for r in requests]==ORDER and http_manifest['interfaces']==ORDER,'Request order/count mismatch')
        previous_end=0
        for r in requests:
            require(r['request_id'] not in ids,'Duplicate request ID')
            ids.add(r['request_id'])
            require(r['source']=='actual_https' and r['status']=='success' and int(r['http_status'])==200 and int(r['bytes_received'])==65536,'Request not a successful exact-size object')
            require(r['destination_ip']==address and r['destination_port']=='443' and r['server_name']==target['server_name'] and r['path']==target['path'],'Recorded destination mismatch')
            require(r['egress_status']=='unverified' and not r['verified_egress'],'Unsupported physical egress claim')
            start,end=float(r['start_epoch']),float(r['end_epoch'])
            duration=float(r['request_duration_ms'])
            require(start>=previous_end and start<=float(r['tcp_connected_epoch'])<=end and duration>0,'Invalid request timeline')
            require(abs((end-start)*1000-duration)<50,'Wall/monotonic duration discrepancy >50ms')
            offsets=[float(r[k]) for k in ('tcp_connect_ms','tls_ready_ms','ttfb_ms','request_duration_ms')]
            require(offsets==sorted(offsets) and all(math.isfinite(v) and v>=0 for v in offsets),'Invalid milestone order')
            require(re.fullmatch('[a-f0-9]{64}',r['response_sha256']) is not None,'Invalid recorded body digest')
            require(r['local_ip'] and 0<int(r['local_port'])<=65535 and int(r['binding_index'])>0,'Missing socket provenance')
            binding[r['requested_interface']].add(int(r['binding_index']))
            previous_end=end
        require(http_manifest['started_epoch']<=float(requests[0]['start_epoch']) and http_manifest['ended_epoch']>=float(requests[-1]['end_epoch']),'Manifest does not cover requests')
        timeline.append(dict(stage=stage,icmp_created_epoch=stage_start,first_icmp_completed_epoch=datetime.fromisoformat(monitor[0]['timestamp']).timestamp(),last_icmp_completed_epoch=datetime.fromisoformat(monitor[-1]['timestamp']).timestamp(),http_started_epoch=http_manifest['started_epoch'],http_ended_epoch=http_manifest['ended_epoch']))
        for network,interface in [('wifi','en0'),('cellular','en6')]:
            rtts,variations=[],[]
            for row in monitor:
                require(row['source']=='measured_icmp' and row[f'{network}_interface']==interface,'Measurement provenance mismatch')
                text=row[f'{network}_raw_output']
                match=re.search(r'(\d+) packets transmitted,\s*(\d+) packets received',text)
                require(match is not None,'Missing raw ping counts')
                sent,received=map(int,match.groups())
                replies={int(s):float(t) for s,t in re.findall(r'icmp_seq=(\d+).*?time=([\d.]+)\s*ms',text)}
                require(sent==received==len(replies)==10,'Raw ICMP reply count mismatch')
                require(row[f'{network}_status']=='reachable','Unexpected reachability')
                near(row[f'{network}_sent'],sent); near(row[f'{network}_received'],received)
                near(row[f'{network}_loss'],100*(sent-received)/sent)
                rtt=statistics.fmean(replies.values())
                delta=[abs(replies[s]-replies[s-1]) for s in sorted(replies) if s-1 in replies]
                variation=statistics.fmean(delta)
                near(row[f'{network}_latency'],rtt)
                near(row[f'{network}_rtt_variation'],variation)
                near(row[f'{network}_adjacent_pairs'],len(delta))
                require(all(not row[f'{network}_{k}'] for k in ('rssi','jitter','throughput')),'Unavailable metric populated')
                rtts.append(rtt); variations.append(variation)
                all_sent+=sent; all_received+=received
            path_requests=[r for r in requests if r['requested_interface']==interface]
            durations=[float(r['request_duration_ms']) for r in path_requests]
            goodputs=[int(r['bytes_received'])*8/(float(r['request_duration_ms'])/1000)/1e6 for r in path_requests]
            expected=dict(icmp_windows=4,reachable_windows=4,valid_rtt_windows=4,median_window_rtt_ms=statistics.median(rtts),median_window_rtt_variation_ms=statistics.median(variations),sent=40,received=40,pooled_loss_pct=0,http_attempts=4,valid_64k_successes=4,http_failed_or_wrong_length=0,median_success_response_ms=statistics.median(durations),median_bounded_goodput_mbps=statistics.median(goodputs))
            for key,value in expected.items():
                near(summary_map[stage,network][key],value)
            require(summary_map[stage,network]['egress_status']=='unverified','Summary confirmation unsupported')
            values[stage,network]=expected
    require(all(len(v)==1 for v in binding.values()),'Binding indexes changed during pilot')
    a,b,r=(values[s,'wifi'] for s in STAGES)
    ca,cb,cr=(values[s,'cellular'] for s in STAGES)
    rtt=lambda x:x['median_window_rtt_ms']
    g=lambda x:x['median_bounded_goodput_mbps']
    tolerance=max(20,.3*rtt(ca))
    checks=dict(wifi_rtt_deterioration=rtt(b)-rtt(a)>=20 and rtt(b)>=1.5*rtt(a),wifi_goodput_deterioration=g(b)<=.6*g(a),cellular_B_rtt_stable=abs(rtt(cb)-rtt(ca))<=tolerance,cellular_return_rtt_stable=abs(rtt(cr)-rtt(ca))<=tolerance,cellular_B_goodput_stable=.7*g(ca)<=g(cb)<=1.3*g(ca),cellular_return_goodput_stable=.7*g(ca)<=g(cr)<=1.3*g(ca),wifi_return_rtt=abs(rtt(r)-rtt(a))<=max(10,.25*rtt(a)),wifi_return_goodput=g(r)>=.8*g(a))
    suitable=(checks['wifi_rtt_deterioration'] or checks['wifi_goodput_deterioration']) and all(v for k,v in checks.items() if k not in ('wifi_rtt_deterioration','wifi_goodput_deterioration'))
    require(not suitable,'Expected negative manipulation check changed')
    return dict(classification='unsuitable_location',checks=checks,icmp_sent=all_sent,icmp_received=all_received,actual_http_requests=len(ids),completed_body_bytes=len(ids)*65536,physical_egress='unverified',wifi_B_rtt_change_ms=rtt(b)-rtt(a),wifi_B_goodput_change_pct=100*(g(b)/g(a)-1),cellular_B_rtt_change_ms=rtt(cb)-rtt(ca),cellular_rtt_tolerance_ms=tolerance,wifi_return_goodput_ratio=g(r)/g(a),timeline=timeline,limitations=['No packet capture or original response bodies; hashes cannot establish physical egress or independently reproduce body content.','No operator notes found in preserved inventory; exact movement, settling and phone placement are unverified.','Sequential ICMP/HTTP windows and long inter-stage gaps confound attribution; no policy-driven HTTP selection was tested.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    args=p.parse_args()
    result=audit(args.directory)
    stored=args.directory/'audit.json'
    if stored.exists():
        require(json.loads(stored.read_text())==result,'Saved audit findings differ')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
