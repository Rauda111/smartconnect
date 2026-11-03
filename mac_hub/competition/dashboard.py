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


def decision_view(row):
    """Read recorded state only; never recompute or change the collector policy."""
    d = row['decision']; state = d['stability']
    before = d.get('previous')
    candidate = next((n for n in INTERFACES if n != before), None) if before in INTERFACES else None
    held = state['hold_required'] if d['explanation'].startswith('Recommend change:') else state['hold_count']
    return dict(candidate=candidate or 'initial attachment', advantage=d.get('advantage'),
                margin=state['margin'], qualifying=f"{held}/{state['hold_required']}",
                elapsed_dwell=(row['elapsed_seconds']-state['last_selection_elapsed']) if state['last_selection_elapsed'] is not None else None,
                eligibility={n: 'Passes observed guardrails only' if v['score'] is not None and not v['breaches']
                             else 'Observed breach' if v['score'] is not None else 'Unavailable / incomplete'
                             for n,v in d['details'].items()})


def public_requests(requests):
    """All calibration/outcome bindings, without private tuples or error strings."""
    return [dict(window=r['window'], role=r.get('role', 'selected_outcome'),
                 requested_interface=r.get('requested_interface') if r.get('requested_interface') in INTERFACES.values() else 'none/unknown',
                 binding_readback=bool(r.get('binding_index')), status=r['status'],
                 request_ms=r.get('request_duration_ms'), completed_body_bytes=r.get('bytes_received'),
                 bounded_goodput_Mbps=r.get('goodput_mbps'), physical_egress='unverified') for r in requests]


def safe_view(rows):
    """Explicit field allowlist: never return raw output, tuples, paths or errors."""
    result = []; previous_interface = None
    for r in rows:
        outcome = r.get('outcome') or {}; interface = outcome.get('requested_interface')
        changed = interface in INTERFACES.values() and previous_interface is not None and interface != previous_interface
        if interface in INTERFACES.values():
            previous_interface = interface
        v = decision_view(r)
        result.append(dict(window=r['window'], timestamp=r['timestamp'], selected=r['decision']['recommended'],
                           baseline=r['baseline'], candidate=v['candidate'], advantage=v['advantage'],
                           required_margin=v['margin'], qualifying=v['qualifying'],
                           recommendation_change=r['decision']['direct_recommendation_change'],
                           requested_interface=interface if interface in INTERFACES.values() else 'none',
                           requested_interface_change=changed,
                           HTTPS=outcome.get('status', 'not sent: historical replay'),
                           binding_readback=bool(outcome.get('binding_index')),
                           request_ms=outcome.get('request_duration_ms'), physical_egress='unverified',
                           bound_request_interface_change=r.get('flow_evidence', {}).get('successful_bound_request_interface_change', False)))
    return result


def main():
    st.set_page_config(page_title='SmartConnect · EDGE', layout='wide')
    st.title('SmartConnect')
    st.caption('Application-aware selection for our own NEW HTTPS connections')
    st.warning('No existing-session migration. New flows are physically unverified unless separately packet-confirmed. 5G radio access is unverified.')
    mode = st.sidebar.radio('Evidence source', ['Historical real-input replay', 'Live collector log'])
    profile = st.sidebar.selectbox('Application profile', ['video_call', 'file_download']) if mode == 'Historical real-input replay' else None
    if mode == 'Live collector log':
        st.sidebar.caption('Live profile comes from the collector log; this viewer cannot change its policy.')
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
            if path:
                st.metric('Latest recorded selected interface', INTERFACES.get(row['decision']['recommended'], 'none eligible'))
            if path and rows:
                inspected = st.selectbox('Inspect completed decision window', [r['window'] for r in rows], index=len(rows)-1)
                row = next(r for r in rows if r['window'] == inspected)
            d = row['decision']
            view = decision_view(row)
            st.subheader('Selected interface: '+INTERFACES.get(d['recommended'], 'none eligible'))
            st.caption(f"Inspecting window {row['window']} · recorded UTC {row['timestamp']}")
            st.write(d['explanation'])
            st.caption(f"Recorded profile: {row['application']} · scoring basis: {d['scoring_basis']} · legacy RTT/loss weight coverage: {d['coverage']:.0%}")
            st.write('Candidate:', view['candidate'])
            cols = st.columns(3)
            cols[0].metric('Candidate adjusted-score advantage', 'N/A' if view['advantage'] is None else f"{view['advantage']:.6f}")
            cols[1].metric('Required switching margin', f"{view['margin']:.2f}")
            cols[2].metric('Consecutive qualifying observations', view['qualifying'])
            dwell = view['elapsed_dwell']
            st.caption(f"Dwell since latest attachment/change: {'unknown' if dwell is None else f'{dwell:.1f}'} / {d['stability']['dwell_seconds']} seconds. Switch rows show the completed hold; stored streak resets after switching. Availability resets bypass normal hold/dwell.")
            st.caption('Observed-guardrail rescue can qualify a positive advantage below the normal margin; it still requires hold/dwell. Calibration goodput is used only when both paths have valid transfers.')
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
                    st.metric('Adjacent RTT variation (ms; not RTP jitter)', 'Unknown' if m['rtt_variation'] is None else f"{m['rtt_variation']:.3f}")
                    st.caption(f"Echo replies / attempts: {m['received']} / {m['sent']}")
                    st.metric('Raw partial score', 'Unknown' if details['score'] is None else f"{details['score']:.6f}")
                    st.metric('Trend-adjusted partial score', 'Unknown' if details['adjusted_score'] is None else f"{details['adjusted_score']:.6f}")
                    st.write('Eligibility:', view['eligibility'][n])
                    st.caption('Eligibility checks observed dimensions only; unknown guardrails are not certified.')
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
                st.metric('Inspected HTTPS outcome', outcome['status'])
                st.write('Requested outcome interface:', outcome.get('requested_interface') if outcome.get('requested_interface') in INTERFACES.values() else 'none')
                st.write('Binding readback:', 'confirmed socket option' if outcome.get('binding_index') else 'not confirmed')
                if outcome['status'] != 'success':
                    st.error('Selected request did not succeed. No alternate-interface retry was made.')
            else:
                st.caption('HTTPS outcome: none. Historical ICMP replay never fabricates a request.')
            st.subheader('Run history — completed windows')
            table = safe_view(rows)
            st.metric('Recommendation changes', sum(x['recommendation_change'] for x in table))
            st.metric('Requested outcome-interface changes', sum(x['requested_interface_change'] for x in table))
            st.metric('Successful bound-request interface changes', sum(x['bound_request_interface_change'] for x in table))
            st.metric('Successful logged HTTPS requests', sum(x['HTTPS'] == 'success' for x in table))
            st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)
            if path:
                request_path = Path(path).with_name('requests.jsonl')
                if request_path.is_file():
                    st.subheader('New HTTPS request bindings — calibration and selected outcomes')
                    st.dataframe(pd.DataFrame(public_requests(read_events(request_path))), hide_index=True, use_container_width=True)
                    st.caption('Calibration deliberately samples both paths; its interface alternation is not a policy switch. Readback confirms the socket option, not packet-confirmed egress. Only selected-outcome attempts count toward requested-interface changes.')
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
