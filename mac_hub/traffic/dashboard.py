"""Read-only live Stage A outcome viewer. Never starts traffic or capture."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import pandas as pd
import streamlit as st
from mac_hub.traffic.dashboard_evidence import PRESETS, resolve, load

st.set_page_config(page_title='SmartConnect Phase 3',layout='wide')
st.title('SmartConnect Phase 3 · controlled new-request traffic')
st.warning('Stage A independently verifies the backend. Later requests need their own evidence to confirm egress. This read-only viewer starts no traffic or capture; existing sessions are not migrated.')
def choose_evidence():
    values=PRESETS[st.session_state['traffic_evidence_preset']]
    for key,value in zip(('traffic_request_path','traffic_verified_path','traffic_proof_path'),values):
        st.session_state[key]=value


if 'traffic_request_path' not in st.session_state:
    for key,value in zip(('traffic_request_path','traffic_verified_path','traffic_proof_path'),next(iter(PRESETS.values()))):
        st.session_state[key]=value
st.selectbox('Evidence experiment',list(PRESETS),key='traffic_evidence_preset',on_change=choose_evidence)
path=resolve(st.text_input('Request CSV',key='traffic_request_path'))
verified_value=st.text_input('Verified request CSV (optional)',key='traffic_verified_path')
proof_value=st.text_input('Verification report JSON (optional)',key='traffic_proof_path')
verification=resolve(verified_value) if verified_value else None
proof_path=resolve(proof_value) if proof_value else None
st.caption('Presets select separate experiments. Editing a path does not transfer confirmation between datasets.')



@st.fragment(run_every=3)
def view():
    if not path.is_file():
        st.info('Run the Stage A CLI first. Dry-run is the default; request execution is opt-in.')
        return
    try:
        frame,provenance=load(path,verification,proof_path)
        if frame.empty:
            st.info('Waiting for a complete request record.')
            return
        st.caption(f'Request evidence: {path}')
        st.write('Recorded traffic source:', ', '.join(sorted(frame.source.unique())))
        if provenance['status']=='saved_packet_evidence_confirmed':
            st.success(provenance['message'])
            if provenance.get('capture_ended_epoch'):
                stamp=pd.to_datetime(provenance['capture_ended_epoch'],unit='s',utc=True)
                st.caption(f'Historical packet capture ended: {stamp.isoformat()} (UTC). This is saved evidence, not current live path validation.')
        else:
            st.warning(provenance['message'])
        with st.expander('Evidence paths and provenance'):
            st.json(provenance)
        choices=st.multiselect('Show requested interfaces',sorted(frame.requested_interface.unique()),default=sorted(frame.requested_interface.unique()))
        shown=frame[frame.requested_interface.isin(choices)]
        columns=st.columns(4)
        columns[0].metric('Actual request attempts',int(shown.source.eq('actual_https').sum()))
        columns[1].metric('Successful requests',int(shown.status.eq('success').sum()))
        columns[2].metric('Failed or timed-out requests',int(shown.status.isin(['binding_failed','request_failed','http_error','timeout']).sum()))
        columns[3].metric('Packet-confirmed requests',int(shown.capture_egress_status.eq('pcap_confirmed').sum()))
        if 'policy' in shown:
            st.write('Decision input source:', ', '.join(sorted(shown.monitor_source.unique())))
            policy=st.selectbox('Policy detail',['smartconnect','wifi_first'])
            detail=shown[shown.policy==policy]
            changes=int(detail.recommended_change.eq(True).sum())
            confirmed=detail.capture_egress_status.eq('pcap_confirmed').all() and not detail.empty
            switch_count=int(detail.capture_verified_egress.ne(detail.capture_verified_egress.shift()).iloc[1:].sum()) if confirmed else None
            timing=st.columns(3)
            timing[0].metric('Recommended new-request path changes',changes)
            timing[1].metric('Independently confirmed path changes','Unverified' if switch_count is None else switch_count)
            timing[2].metric('Confirmed transition delay','Unverified')
            st.dataframe(detail[['cycle','monitor_window_ms','decision_compute_ms','decision_to_request_start_ms','decision_to_response_ms']],hide_index=True)
            from mac_hub.traffic.compare import summarize
            st.dataframe(summarize(shown.fillna('').to_dict('records')),hide_index=True)
            st.caption('No bracketed failures means no measured failure gap, not proof of zero interruption. A failure gap includes planned request cadence. Controlled input values are synthetic; HTTP outcomes are actual when execute mode was used.')
        else:
            st.caption('Stage A is a manual binding test. Confirmed path changes between its new flows do not demonstrate an engine-driven transition or uninterrupted sessions.')
        st.dataframe(shown[['timestamp','source','requested_interface','capture_verified_egress','capture_egress_status','status','http_status','request_duration_ms','error']],hide_index=True)
        st.line_chart(shown[['timestamp','request_duration_ms']].set_index('timestamp'))
        st.caption('All attempted-request durations include client overhead/TCP/TLS/HTTP. Success/failure are separate; dry-run timings remain unknown. Request path provenance is updated only from independent capture verification.')
    except (OSError,ValueError,KeyError) as exc:
        st.error(f'Cannot read request evidence: {exc}')

view()
