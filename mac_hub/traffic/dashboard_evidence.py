"""Read-only dataset selection and provenance checks for dashboard evidence."""
import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
BASE='mac_hub/traffic/evidence'
PRESETS={
    'Stage A — packet-confirmed clean capture': (
        f'{BASE}/stage_a_verification/source_requests.csv',
        f'{BASE}/stage_a_verification/verified_requests.csv',
        f'{BASE}/stage_a_verification/stage_a.json'),
    'Controlled workload — 32 requests, egress unverified': (
        f'{BASE}/controlled_final/requests.csv','',''),
    'Live workload — 8 requests, egress unverified': (
        f'{BASE}/live_workload/requests.csv','',''),
    'Earlier Stage A — unverified capture workflow': (
        'mac_hub/logs/phase3-approved-requests/requests.csv','',''),
    'Custom / live log': ('mac_hub/logs/phase3-approved-requests/requests.csv','',''),
}


def resolve(value):
    path=Path(value)
    return path if path.is_absolute() else ROOT/path


def load(request_path,verified_path=None,manifest_path=None):
    """Never inherit confirmation from an arbitrary CSV or an ID-only join.

    This checks the saved evidence association; the separate offline audit
    re-reads raw PCAPs. It does not perform capture or fresh network verification.
    """
    frame=pd.read_csv(request_path).dropna(subset=['request_id','status','end_epoch'])
    frame=frame.drop(columns=['capture_verified_egress','capture_egress_status'],errors='ignore')
    frame['capture_verified_egress']=None
    frame['capture_egress_status']='unverified'
    provenance=dict(status='unverified',message='No packet-verification evidence attached to this dataset.',
                    request_path=str(request_path),verified_path=str(verified_path) if verified_path else None,
                    manifest_path=str(manifest_path) if manifest_path else None)
    if not verified_path or not manifest_path:
        return frame,provenance
    try:
        proof=json.loads(manifest_path.read_text())
        if proof.get('stage_a_passed') is not True:
            raise ValueError('Stage A verification did not pass')
        if hashlib.sha256(request_path.read_bytes()).hexdigest()!=proof['request_csv_sha256']:
            raise ValueError('Request file hash differs from the independently verified source')
        verified=pd.read_csv(verified_path)
        if frame.request_id.duplicated().any() or verified.request_id.duplicated().any():
            raise ValueError('Duplicate request identifiers')
        records=proof['records']
        by_id={r['request_id']:r for r in records}
        if len(by_id)!=len(records) or set(frame.request_id)!=set(by_id) or set(verified.request_id)!=set(by_id):
            raise ValueError('Request IDs do not match the verification report')
        original_columns=[c for c in frame if not c.startswith('capture_')]
        left=frame[original_columns].sort_values('request_id').reset_index(drop=True)
        right=verified[original_columns].sort_values('request_id').reset_index(drop=True)
        pd.testing.assert_frame_equal(left,right,check_dtype=False)
        for _,row in verified.iterrows():
            record=by_id[row.request_id]
            if (record['egress_status']!='pcap_confirmed' or record['requested_interface']!=row.requested_interface
                    or record['verified_egress']!=row.requested_interface
                    or row.capture_egress_status!=record['egress_status']
                    or row.capture_verified_egress!=record['verified_egress']):
                raise ValueError('Per-request path evidence does not match')
        frame=frame.drop(columns=['capture_verified_egress','capture_egress_status']).merge(
            verified[['request_id','capture_verified_egress','capture_egress_status']],
            on='request_id',how='left',validate='one_to_one')
        provenance.update(status='saved_packet_evidence_confirmed',
                          message='Saved clean Stage A packet evidence matches this exact request file and every request row. No fresh capture was performed.',
                          capture_ended_epoch=proof.get('capture_ended_epoch'),
                          capture_manifest_sha256=proof['capture_manifest_sha256'],
                          request_csv_sha256=proof['request_csv_sha256'])
    except (OSError,ValueError,KeyError,AssertionError) as exc:
        frame['capture_verified_egress']=None
        frame['capture_egress_status']='unverified'
        provenance['message']=f'Packet evidence not attached: {exc}'
    return frame,provenance
