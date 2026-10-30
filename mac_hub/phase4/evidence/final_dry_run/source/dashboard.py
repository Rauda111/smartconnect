"""Read-only Phase 4 experiment viewer. Starts no requests or capture."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd
import json
import streamlit as st
from mac_hub.phase4.report import audit_products
st.set_page_config(page_title='SmartConnect Phase 4', layout='wide')
st.title('Phase 4 · paired application requests')
st.warning('Requested interface is not packet-confirmed egress. No existing sessions are migrated; this viewer starts no network workloads.')
root = Path(__file__).resolve().parents[2]
presets = {'Actual stable observation — egress unverified':'mac_hub/phase4/evidence/stable_observation',
           'Dry run — no network measurements':'mac_hub/phase4/evidence/dry_run',
           'Custom completed experiment':'mac_hub/logs/phase4-custom'}
def choose():
    st.session_state['phase4_path'] = presets[st.session_state['phase4_preset']]
if 'phase4_path' not in st.session_state:
    st.session_state['phase4_path'] = next(iter(presets.values()))
st.selectbox('Evidence source', list(presets), key='phase4_preset', on_change=choose)
value = st.text_input('Experiment directory', key='phase4_path')
path = Path(value).expanduser()
if not path.is_absolute():
    path = root/path

@st.fragment(run_every=5)
def view():
    if not (path/'manifest.json').exists():
        st.info('Choose a completed experiment directory. CLI writes results on completion or cancellation.')
        return
    try:
        manifest, requests, rounds = audit_products(path)
    except Exception as exc:
        st.error(f'Evidence audit failed: {exc}')
        return
    st.caption(str(path.resolve()))
    st.json(manifest, expanded=False)
    st.write('Source:', manifest['mode'], 'Condition label:', manifest['condition'])
    profile = st.selectbox('Application', ['video_call','file_download'])
    subset = requests[requests.application.eq(profile)]
    st.subheader('Actual workload records and provenance')
    st.dataframe(subset, hide_index=True)
    if (path/'measurements.csv').exists():
        measured = pd.read_csv(path/'measurements.csv')
        st.subheader('Shared pre-decision ICMP inputs')
        st.caption('RTT variation is adjacent-packet RTT difference, not application jitter. Three-packet loss estimates have coarse resolution.')
        st.dataframe(measured[measured.application.eq(profile)], hide_index=True)
    calibration = subset[subset.role.eq('probe') & subset.status.eq('success')]
    if not calibration.empty:
        st.subheader('Pre-decision bounded download goodput by requested path')
        st.line_chart(calibration.reset_index().pivot(index='index', columns='network', values='goodput_mbps'))
    actual = subset[subset.source.eq('actual_https')]
    a,b,c = st.columns(3)
    a.metric('Actual attempts', len(actual))
    b.metric('Successful requests', int(actual.status.eq('success').sum()))
    c.metric('Packet-confirmed', 0)
    if not rounds.empty:
        st.subheader('Recommendations and explanations')
        selected_rounds = rounds[rounds.application.eq(profile)]
        st.dataframe(selected_rounds, hide_index=True)
        details = []
        for _, row in selected_rounds.iterrows():
            for network, detail in json.loads(row.policy_details)['details'].items():
                details.append(dict(trial=row.trial, cycle=row.cycle, network=network, **detail))
        st.write('Score trends and observed/unknown guardrails')
        st.dataframe(pd.DataFrame(details), hide_index=True)
    successes = subset[subset.role.eq('outcome') & subset.status.eq('success')]
    for metric in ['request_duration_ms','goodput_mbps']:
        if not successes.empty:
            chart = successes.reset_index().pivot(index='index', columns='policy', values=metric)
            st.write(metric)
            st.line_chart(chart)
    st.caption('Goodput includes connection setup and server response. ICMP variation is not application jitter. Empty metrics mean unavailable.')
    for name in ['summary.csv','contrasts.csv']:
        if (path/name).exists():
            st.write(name)
            st.dataframe(pd.read_csv(path/name), hide_index=True)
    if (path/'REPORT.md').exists():
        st.markdown((path/'REPORT.md').read_text())
view()
