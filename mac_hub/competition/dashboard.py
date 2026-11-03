"""Local-only public-safe viewer; never starts a collector or sends traffic."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from mac_hub.competition.run import replay_rows, INTERFACES, digest


def read_events(path):
    """Tolerate only an incomplete last append; do not hide internal corruption."""
    text = Path(path).read_text()
    lines = text.splitlines()
    rows = []
    for index, line in enumerate(lines):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if index != len(lines)-1 or text.endswith('\n'):
                raise ValueError('Event log is corrupt')
    return rows


def safe_view(rows):
    """Explicit field allowlist: never return raw output, tuples, paths or errors."""
    return [dict(window=r['window'], timestamp=r['timestamp'],
                 selected=r['decision']['recommended'], baseline=r['baseline'],
                 recommendation_change=r['decision']['direct_recommendation_change'],
                 HTTPS=(r.get('outcome') or {}).get('status', 'not sent: historical replay'),
                 binding_readback=bool((r.get('outcome') or {}).get('binding_index')),
                 request_ms=(r.get('outcome') or {}).get('request_duration_ms'),
                 bound_request_interface_change=r.get('flow_evidence', {}).get('successful_bound_request_interface_change', False))
            for r in rows]


def main():
    st.set_page_config(page_title='SmartConnect · EDGE', layout='wide')
    st.title('SmartConnect')
    st.caption('Application-aware selection for our own NEW HTTPS connections')
    st.warning('No existing-session migration. New flows are physically unverified unless separately packet-confirmed. 5G radio access is unverified.')
    mode = st.sidebar.radio('Evidence source', ['Historical real-input replay', 'Live collector log'])
    profile = st.sidebar.selectbox('Application profile', ['video_call', 'file_download'])
    st.sidebar.caption('Video profile uses ICMP RTT/loss. Download adds pre-decision bounded-goodput calibration when available. Neither is achieved application QoE.')
    path = st.sidebar.text_input('Live event log', '/tmp/smartconnect-approved-demo/events.jsonl') if mode == 'Live collector log' else None
    autoplay = st.sidebar.toggle('Play historical timeline', value=False) if path is None else False

    @st.fragment(run_every=2)
    def render():
        try:
            rows = read_events(path) if path else list(replay_rows(application=profile))
            if not rows:
                st.info('Waiting for the first completed measurement. Start the approved collector separately.')
                return
            if path:
                if any(r.get('mode') != 'live' for r in rows):
                    raise ValueError('Expected live-mode collector records')
                row = rows[-1]
                rows = [r for r in rows if r.get('event') == 'completed_window']
                age = (datetime.now(timezone.utc)-datetime.fromisoformat(row['timestamp'])).total_seconds()
                if age > row.get('freshness_limit_seconds', 45) or age < -5:
                    st.error('Measurements are stale or the clock changed. Do not treat the displayed selection as current.')
                st.info(f"LIVE LOG · {row['application']} · collected observations, not independent egress verification")
                done = Path(path).with_name('manifest.json')
                if done.exists():
                    manifest = json.loads(done.read_text())
                    for name, expected in manifest['output_hashes'].items():
                        if Path(name).name != name or digest(done.parent/name) != expected:
                            raise ValueError('Completed log integrity mismatch')
                    st.warning('Collector finished/cancelled. This is a saved run, not active collection.')
                    if manifest.get('run_error_type'):
                        st.error('Collector stopped with an error. Partial evidence retained.')
            else:
                st.info('HISTORICAL REAL-INPUT REPLAY · November 3–4, 2026 · no requests are sent')
                if autoplay:
                    st.session_state['frame'] = (st.session_state.get('frame', 0)+1) % len(rows)
                    index = st.session_state['frame']
                    st.write(f'Historical window {index+1} / {len(rows)}')
                else:
                    index = st.slider('Historical window', 1, len(rows), 1)-1
                row = rows[index]
                rows = rows[:index+1]
                st.caption('Location stages unassigned: movement timestamps were not recorded. Download replay lacks goodput and uses the documented fallback.')
            d = row['decision']
            st.subheader('Selected interface: '+INTERFACES.get(d['recommended'], 'none eligible'))
            st.write(d['explanation'])
            st.caption(f"Scoring basis: {d['scoring_basis']} · hold {d['stability']['hold_count']}/3 · dwell 30 seconds · margin 0.05")
            for col, n in zip(st.columns(2), INTERFACES):
                with col:
                    m = row['inputs'][n]
                    details = d['details'][n]
                    st.subheader(('Wi-Fi' if n == 'wifi' else 'Cellular-backed iPhone USB')+' · '+INTERFACES[n])
                    st.write('Probe status: '+m['status'])
                    if m['status'] != 'reachable':
                        st.error('Interface probe unavailable/error. Inspect the local private log; no automatic unbound fallback.')
                    st.metric('Parsed mean RTT (ms)', 'Unknown' if m['latency'] is None else f"{m['latency']:.3f}")
                    st.metric('Observed ICMP loss (%)', 'Unknown' if m['loss'] is None else f"{m['loss']:.3f}")
                    st.write('Adjusted partial score:', details['adjusted_score'])
                    st.write('Trend:', details['trend'])
                    calibration = row.get('calibration', {}).get(n, {})
                    if calibration.get('goodput_mbps') is not None:
                        st.metric('Calibration bounded-object goodput (Mbps)', f"{calibration['goodput_mbps']:.3f}")
                    elif row['application'] == 'file_download':
                        st.caption('Goodput unavailable: RTT/loss fallback; capacity remains unknown.')
                    st.write('Observed breaches:', details['breaches'] or 'None observed')
                    st.caption('Application jitter, RSSI and link capacity unknown. No full QoE pass.')
                    if row['diagnostics'][n]['rtt_reply_count_mismatch']:
                        st.warning('Late/omitted reply: parsed RTT excludes some received replies; ping-summary average differs.')
            outcome = row.get('outcome')
            if outcome:
                st.metric('Latest HTTPS outcome', outcome['status'])
                st.write('Binding readback:', 'confirmed socket option' if outcome.get('binding_index') else 'not confirmed')
                if outcome['status'] != 'success':
                    st.error('Selected request did not succeed. No alternate-interface retry was made.')
            else:
                st.caption('HTTPS outcome: none. Historical ICMP replay never fabricates a request.')
            table = safe_view(rows)
            st.metric('Recommendation changes', sum(x['recommendation_change'] for x in table))
            st.metric('Successful logged HTTPS requests', sum(x['HTTPS'] == 'success' for x in table))
            st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)
            chart = [dict(elapsed_seconds=r['elapsed_seconds'], wifi_RTT_ms=r['inputs']['wifi']['latency'],
                          cellular_RTT_ms=r['inputs']['cellular']['latency']) for r in rows]
            if chart:
                st.line_chart(pd.DataFrame(chart).set_index('elapsed_seconds'))
            st.caption('Successful bound-request interface changes describe new sockets. Physical egress changes and existing-session continuity remain unmeasured. This viewer never starts probes, requests or capture.')
        except Exception:
            # Do not expose raw exception strings containing local paths/network identifiers.
            st.error('Evidence unavailable or invalid. Check the collector and local log privately.')
    render()

if __name__ == '__main__':
    main()
