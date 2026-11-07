"""Read-only interface snapshots and offline selected-candidate comparison.

This never probes, captures packets, changes routes, or establishes a call.
Candidate/address equality is evidence of an interface association, not proof
of physical egress, media continuity, or Wi-Fi-to-cellular migration.
"""
import argparse
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess

MAX_FILE = 1024 * 1024


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError('Invalid evidence timestamp')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Evidence timestamps must include a timezone')
    return stamp


def address(value):
    """Return canonical address and optional scope without resolving mDNS."""
    if not isinstance(value, str) or len(value) > 100:
        return None, None
    host, separator, scope = value.partition('%')
    try:
        result = ipaddress.ip_address(host)
    except ValueError:
        return None, None
    if result.is_unspecified or result.is_loopback or result.is_multicast:
        return None, None
    return result, scope if separator else None


def parse_interfaces(raw):
    if not isinstance(raw, str) or len(raw) > MAX_FILE:
        raise ValueError('Invalid private interface snapshot')
    result, current = {}, None
    for line in raw.splitlines():
        heading = re.match(r'^([A-Za-z0-9]+): flags=', line)
        if heading:
            current = heading[1]
            result[current] = {'active': False, 'addresses': []}
        elif current:
            if line.strip() == 'status: active':
                result[current]['active'] = True
            match = re.match(r'\s+inet6?\s+(\S+)', line)
            if match:
                ip, scope = address(match[1])
                if ip is not None and scope in (None, current):
                    result[current]['addresses'].append(ip)
    return result


def compare(path_snapshot, interface_snapshot, cellular='en6'):
    """Offline evidence correlation; never returns physical_egress_verified=True."""
    if not re.fullmatch(r'en[0-9]+', cellular) or cellular == 'en0':
        raise ValueError('Invalid USB interface name')
    if not isinstance(path_snapshot, dict) or not isinstance(interface_snapshot, dict):
        raise ValueError('Invalid evidence document')
    if path_snapshot.get('schema') != 1 or interface_snapshot.get('schema') != 1:
        raise ValueError('Unsupported evidence schema')
    captured = timestamp(path_snapshot.get('captured_at'))
    inspected = timestamp(interface_snapshot.get('captured_at'))
    generation = path_snapshot.get('candidate_pair_generation')
    if generation is not None and (type(generation) is not int or generation < 1):
        raise ValueError('Invalid selected-pair generation')
    # This label describes the submitted historical snapshots, never live state.
    result = dict(schema=1, status='unverified', interface=None, network=None,
                  candidate_pair_generation=generation, captured_at=captured.isoformat(),
                  interface_snapshot_at=inspected.isoformat(),
                  evidence_source='operator_supplied_snapshots',
                  physical_egress_verified=False, same_session_handover_verified=False,
                  reason='selected_pair_unavailable')
    if abs((captured-inspected).total_seconds()) > 30:
        return dict(result, reason='snapshots_not_contemporaneous')
    interfaces = parse_interfaces(interface_snapshot.get('ifconfig'))
    pair, candidate = path_snapshot.get('selected_pair'), path_snapshot.get('local_candidate')
    if not isinstance(pair, dict) or not isinstance(candidate, dict) or generation is None:
        return result
    if (path_snapshot.get('role') != 'A' or
            path_snapshot.get('connection_state') != 'connected' or
            path_snapshot.get('ice_state') not in ('connected', 'completed') or
            pair.get('state') != 'succeeded' or pair.get('nominated') is not True):
        return dict(result, reason='mac_selected_pair_not_connected')
    # A relay's address belongs to TURN, not the Mac. Do not assign a physical
    # interface from relatedAddress, networkType, recommendation, or a subnet.
    if candidate.get('candidate_type') != 'host':
        return dict(result, reason='non_host_candidate_requires_packet_evidence')
    ip, scope = address(candidate.get('address'))
    if ip is None:
        return dict(result, reason='candidate_address_obscured_or_unavailable')
    matches = [name for name, row in interfaces.items()
               if row['active'] and ip in row['addresses'] and scope in (None, name)]
    if len(matches) != 1:
        return dict(result, reason='address_ambiguous' if matches else 'address_not_matched')
    interface = matches[0]
    if interface not in ('en0', cellular):
        return dict(result, reason='candidate_on_other_interface')
    return dict(result, status='candidate_interface_match', interface=interface,
                network='wifi' if interface == 'en0' else 'cellular',
                reason='exact_host_address_match_requires_packet_corroboration')


def read_json(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_FILE+1)
    if len(raw) > MAX_FILE:
        raise ValueError('Evidence file exceeds size limit')
    return json.loads(raw)


def save_private(path, value):
    # Never overwrite earlier evidence or expose private addresses by default.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def capture_interfaces():
    # Explicit CLI action only. Local read-only inventory; no ping/DNS/traffic.
    proc = subprocess.run(['/sbin/ifconfig', '-a'], capture_output=True,
                          text=True, timeout=5, check=True,
                          env={**os.environ, 'LC_ALL': 'C'})
    if len(proc.stdout) > MAX_FILE:
        raise ValueError('Interface snapshot exceeds size limit')
    return dict(schema=1, captured_at=datetime.now(timezone.utc).isoformat(),
                ifconfig=proc.stdout)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    capture = commands.add_parser('capture-interfaces', help='Read local ifconfig only; save PRIVATE addresses')
    capture.add_argument('--output', type=Path, required=True)
    verify = commands.add_parser('compare', help='Offline comparison of contemporaneous private evidence')
    verify.add_argument('--path-snapshot', type=Path, required=True)
    verify.add_argument('--interfaces', type=Path, required=True)
    verify.add_argument('--cellular', default='en6')
    verify.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'capture-interfaces':
            if args.output.exists():
                raise ValueError('Use a new output path')
            save_private(args.output, capture_interfaces())
            print('Private interface snapshot saved. Do not publish or project it.')
        else:
            result = compare(read_json(args.path_snapshot), read_json(args.interfaces), args.cellular)
            save_private(args.output, result)
            print(result['status'] + ': ' + result['reason'])
            print('Physical egress and same-session migration remain unverified.')
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        print('Evidence unavailable or invalid; no interface verification established.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
