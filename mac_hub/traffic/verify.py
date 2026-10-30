"""Offline, dual-interface classic-PCAP correlation for Stage A. No capture APIs."""
import argparse
import csv
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import struct
import time


def packets(path):
    with path.open('rb') as stream:
        header=stream.read(24)
        magic={b'\xd4\xc3\xb2\xa1':('<',1e6),b'\xa1\xb2\xc3\xd4':('>',1e6),
               b'\x4d\x3c\xb2\xa1':('<',1e9),b'\xa1\xb2\x3c\x4d':('>',1e9)}
        if len(header)!=24 or header[:4] not in magic:
            raise ValueError('Requires classic PCAP, not pcapng or truncated header')
        endian,scale=magic[header[:4]]
        major,minor,_,_,snaplen,link=struct.unpack(endian+'HHIIII',header[4:])
        if (major,minor)!=(2,4) or link not in (0,1,12,101,108) or snaplen>1048576:
            raise ValueError('Unsupported PCAP version/link type/snaplen')
        while True:
            rec=stream.read(16)
            if not rec:
                break
            if len(rec)!=16:
                raise ValueError('Truncated record header')
            sec,fraction,size,original=struct.unpack(endian+'IIII',rec)
            if size>snaplen or size>original or fraction>=scale:
                raise ValueError('Invalid PCAP record lengths or timestamp')
            data=stream.read(size)
            if len(data)!=size:
                raise ValueError('Truncated packet')
            offset=0
            if link==1:
                if len(data)<14:
                    raise ValueError('Truncated ethernet header')
                kind=struct.unpack('!H',data[12:14])[0]
                offset=14
                while kind in (0x8100,0x88a8):
                    if len(data)<offset+4:
                        raise ValueError('Truncated VLAN header')
                    kind=struct.unpack('!H',data[offset+2:offset+4])[0]
                    offset+=4
                if kind!=0x800:
                    continue
            elif link in (0,108):
                if data[:4] not in (b'\x02\x00\x00\x00',b'\x00\x00\x00\x02'):
                    continue
                offset=4
            ip=data[offset:]
            if len(ip)<20 or ip[0]>>4!=4:
                continue
            ihl=(ip[0]&15)*4
            if ihl<20 or len(ip)<ihl+20 or ip[9]!=6:
                continue
            if struct.unpack('!H',ip[6:8])[0]&0x1fff:
                continue
            tcp=ip[ihl:]
            total=struct.unpack('!H',ip[2:4])[0]
            tcp_length=(tcp[12]>>4)*4
            if tcp_length<20 or total<ihl+tcp_length:
                raise ValueError('Invalid IP/TCP header lengths')
            tsval=tsecr=None
            options=tcp[20:min(tcp_length,len(tcp))]
            pos=0
            while pos<len(options):
                kind=options[pos]
                if kind==0:
                    break
                if kind==1:
                    pos+=1;continue
                if pos+2>len(options) or options[pos+1]<2 or pos+options[pos+1]>len(options):
                    break
                size=options[pos+1]
                if kind==8 and size==10:
                    tsval,tsecr=struct.unpack('!II',options[pos+2:pos+10])
                pos+=size
            sequence,ack=struct.unpack('!II',tcp[4:12])
            source=str(ipaddress.IPv4Address(ip[12:16]))
            dest=str(ipaddress.IPv4Address(ip[16:20]))
            sport,dport=struct.unpack('!HH',tcp[:4])
            yield dict(time=sec+fraction/scale,src=source,dst=dest,sport=sport,dport=dport,
                       flags=tcp[13],payload_bytes=total-ihl-tcp_length,sequence=sequence,ack=ack,tcp_tsval=tsval,tcp_tsecr=tsecr)


def correlate(row, captures):
    result=dict(request_id=row['request_id'],requested_interface=row['requested_interface'],
                verified_egress='',egress_status='unverified',outbound_syn=0,inbound_synack=0,outbound_payload_packets=0)
    if row['source']!='actual_https' or not row.get('local_port') or not row.get('local_ip'):
        return result
    start,end=float(row['start_epoch']),float(row['end_epoch'])
    if end<start:
        raise ValueError('Request wall clock moved backwards')
    observed={}
    for interface, frames in captures.items():
        outgoing=[]
        incoming=[]
        for frame in frames:
            if not start-.1<=frame['time']<=end+.1:
                continue
            if (frame['src'],frame['sport'],frame['dst'],frame['dport'])==(row['local_ip'],int(row['local_port']),row['destination_ip'],int(row['destination_port'])):
                outgoing.append(frame)
            if (frame['dst'],frame['dport'],frame['src'],frame['sport'])==(row['local_ip'],int(row['local_port']),row['destination_ip'],int(row['destination_port'])):
                incoming.append(frame)
        observed[interface]=dict(syn=sum(f['flags']&0x12==2 for f in outgoing),
                                 synack=sum(f['flags']&0x12==0x12 for f in incoming),
                                 payload=sum(f['payload_bytes']>0 for f in outgoing),outbound=len(outgoing),
                                 outbound_syn_times=[f['time'] for f in outgoing if f['flags']&0x12==2],
                                 inbound_synack_times=[f['time'] for f in incoming if f['flags']&0x12==0x12],
                                 outbound_payload_times=[f['time'] for f in outgoing if f['payload_bytes']>0],
                                 syn_details=[{k:f[k] for k in ('time','sequence','ack','tcp_tsval','tcp_tsecr')} for f in outgoing if f['flags']&0x12==2],
                                 synack_details=[{k:f[k] for k in ('time','sequence','ack','tcp_tsval','tcp_tsecr')} for f in incoming if f['flags']&0x12==0x12],
                                 matching_handshake=any(i['ack']==(o['sequence']+1)&0xffffffff and i['time']>=o['time'] for o in outgoing if o['flags']&0x12==2 for i in incoming if i['flags']&0x12==0x12))
    requested=row['requested_interface']
    if requested not in observed:
        raise ValueError('Requested path not captured')
    result['supporting_evidence']=observed
    result['flow_tuple']=dict(source_ip=row['local_ip'],source_port=int(row['local_port']),destination_ip=row['destination_ip'],destination_port=int(row['destination_port']))
    result['request_time_bounds']=[start,end]
    own=observed[requested]
    result.update(outbound_syn=own['syn'],inbound_synack=own['synack'],outbound_payload_packets=own['payload'])
    if any(v['outbound'] for n,v in observed.items() if n!=requested):
        result['egress_status']='mismatch_or_multiple_paths'
    elif own['syn'] and own['synack'] and own['payload'] and own['matching_handshake']:
        result.update(verified_egress=requested,egress_status='pcap_confirmed',explanation='Exact connection tuple and packet timestamps match SYN, SYN-ACK and outbound payload on the requested physical interface; no matching outbound packets on the other interface')
    return result


def verify(request_dir,capture_dir,output):
    manifest=json.loads((capture_dir/'capture.json').read_text())
    if manifest.get('status')!='complete' or set(manifest['interfaces'])!={'en0','en6'}:
        raise ValueError('Both captures must complete successfully')
    captures={}
    for interface,info in manifest['interfaces'].items():
        path=capture_dir/f'{interface}.pcap'
        stderr=capture_dir/f'{interface}.stderr'
        for p in (path,stderr):
            if hashlib.sha256(p.read_bytes()).hexdigest()!=manifest['sha256'][p.name]:
                raise ValueError('Capture checksum mismatch')
        text=stderr.read_text()
        if info['returncode']!=0 or not re.search(r'\b0 packets dropped by kernel',text):
            raise ValueError('Capture exited unsuccessfully or has drops/unknown drop count')
        if f'listening on {interface},' not in text or info['ready_epoch'] is None:
            raise ValueError('Physical-interface capture readiness missing')
        cmd=info['command']
        if cmd[cmd.index('-i')+1]!=interface or '-p' not in cmd:
            raise ValueError('Capture command does not identify the physical interface')
        captures[interface]=list(packets(path))
    with (request_dir/'requests.csv').open(newline='') as stream:
        requests=list(csv.DictReader(stream))
    if not requests:
        raise ValueError('No request observations')
    if len({r['request_id'] for r in requests})!=len(requests):
        raise ValueError('Duplicate request identity')
    if any(float(a['end_epoch'])>float(b['start_epoch']) for a,b in zip(requests,requests[1:])):
        raise ValueError('Stage A requires sequential non-overlapping requests')
    if manifest.get('request_returncode',0)!=0:
        raise ValueError('Manual request runner did not complete successfully')
    request_manifest=json.loads((request_dir/'manifest.json').read_text())
    client=Path(__file__).with_name('client.py')
    digest=hashlib.sha256(client.read_bytes()).hexdigest()
    if request_manifest.get('uid',0)==0 or request_manifest.get('source_sha256',{}).get('mac_hub/traffic/client.py')!=digest:
        raise ValueError('Requires unprivileged request provenance for the current client implementation')
    records=[]
    for row in requests:
        if row['destination_ip']!=manifest['address']:
            raise ValueError('Capture destination mismatch')
        for info in manifest['interfaces'].values():
            if not info['ready_epoch']<=float(row['start_epoch'])<=float(row['end_epoch'])<=info['stopped_epoch']:
                raise ValueError('Request outside capture readiness interval')
        records.append(correlate(row,captures))
    counts={n:sum(r['egress_status']=='pcap_confirmed' and r['verified_egress']==n and q['status']=='success'
                  for r,q in zip(records,requests)) for n in ('en0','en6')}
    passed=all(v>=2 for v in counts.values()) and all(r['egress_status']=='pcap_confirmed' and q['status']=='success' for r,q in zip(records,requests))
    output.mkdir(parents=True,exist_ok=False)
    with (output/'verified_requests.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(requests[0])+['capture_verified_egress','capture_egress_status'])
        writer.writeheader()
        for q,r in zip(requests,records):
            writer.writerow(dict(q,capture_verified_egress=r['verified_egress'],capture_egress_status=r['egress_status']))
    report=dict(stage_a_passed=passed,verified_epoch=time.time(),capture_ended_epoch=manifest.get('ended_epoch'),client_sha256=digest,criterion='all requests successful and independently captured on requested path only; >=2 per interface',
                confirmed_successes=counts,records=records,
                request_manifest_sha256=hashlib.sha256((request_dir/'manifest.json').read_bytes()).hexdigest(),
                request_csv_sha256=hashlib.sha256((request_dir/'requests.csv').read_bytes()).hexdigest(),
                capture_manifest_sha256=hashlib.sha256((capture_dir/'capture.json').read_bytes()).hexdigest(),
                scope='new HTTPS connections only; no existing-session continuity claim')
    report['interface_indices']={n:sorted({int(r['binding_index']) for r in requests if r['requested_interface']==n and r.get('binding_index')}) for n in ('en0','en6')}
    report['target']=request_manifest.get('target')
    lines=['# Stage A independent physical-egress verification', '', f'Gate passed: {passed}. Captures completed with clean exits and zero reported kernel drops.', '', '| Request ID | Requested | Confirmed egress | SYN / SYN-ACK / payload packets | Evidence |', '|---|---|---|---|---|']
    for r in records:
        lines.append(f"| {r['request_id']} | {r['requested_interface']} | {r['verified_egress'] or 'unverified'} | {r['outbound_syn']} / {r['inbound_synack']} / {r['outbound_payload_packets']} | {r.get('explanation','Insufficient independent evidence')} |")
    lines+=['','stage_a.json contains exact per-interface flow tuples and UTC epoch packet timestamps for each SYN, SYN-ACK and payload observation. Request/capture manifests and SHA-256 hashes bind the evidence. Packet capture times, handshake sequence/ACK numbers and TCP timestamp-option TSval/TSecr values (when present) are recorded separately; missing options remain unknown. No inference is based solely on source IP, requested binding or successful connection.','']
    (output/'VERIFICATION.md').write_text('\n'.join(lines))
    (output/'stage_a.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request-dir',type=Path,required=True)
    p.add_argument('--capture-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(verify(a.request_dir,a.capture_dir,a.output_dir),indent=2))


if __name__=='__main__':
    main()
