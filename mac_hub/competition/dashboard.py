"""Local-only public-safe viewer; never starts a collector or sends traffic."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json
from datetime import datetime, timezone, timedelta
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


from mac_hub.competition.dashboard_data import recorded, project, reason, request_table, NETWORKS
import altair as alt

MODES = ['Recorded real experiment', 'Historical policy replay', 'Live monitoring']
LABELS = {'wifi': 'Wi-Fi', 'cellular': 'Cellular', None: 'No eligible path'}


def fmt(value, suffix=''):
    return 'Unavailable' if value is None else f'{value:.3f}{suffix}'


def recorded_date(timestamp):
    local = datetime.fromisoformat(timestamp).astimezone(timezone(timedelta(hours=4)))
    return f'{local:%B} {local.day}, {local.year} · UAE (UTC+4)'


def selection_timeline(rows, current):
    cells = []
    for i, row in enumerate(rows):
        transition = i > 0 and row['selected'] != rows[i-1]['selected']
        classes = ('cellular' if row['selected']=='cellular' else 'wifi')
        classes += ' current' if row['window']==current else ''
        marker = '<span class="transition">↳</span>' if transition else ''
        cells.append(f'<div class="window {classes}">{marker}<b>W{row["window"]}</b><span>{LABELS[row["selected"]]}</span></div>')
    return '<div class="window-timeline" aria-label="Recorded eight-window network selection">'+''.join(cells)+'</div>'


def chart_spec(rows, metric, unit):
    points = [dict(window=r['window'], network=LABELS[n], value=r.get(n+'_'+metric)) for r in rows for n in NETWORKS]
    return alt.Chart(pd.DataFrame(points)).mark_line(point=True).encode(
        x=alt.X('window:Q', title='Measurement window', axis=alt.Axis(values=[r['window'] for r in rows], format='d', labelAngle=0)),
        y=alt.Y('value:Q', title=unit),
        color=alt.Color('network:N', scale=alt.Scale(domain=['Wi-Fi', 'Cellular'], range=['#41d9ed', '#a99bff']), title=None),
        tooltip=['window:Q', 'network:N', alt.Tooltip('value:Q', format='.6f')]).properties(height=185)


def chart(rows, metric, title, unit):
    st.caption(title)
    st.altair_chart(chart_spec(rows, metric, unit), use_container_width=True)
    missing = [f'{LABELS[n]} W{r["window"]}' for r in rows for n in NETWORKS if r.get(n+'_'+metric) is None]
    if missing:
        st.caption(('RTT unavailable: ' if metric=='latency' else 'Measurement unavailable: ')+', '.join(missing)+'. Missing values are not zero.')


def present(rows, requests, mode, index):
    r = rows[index]; history = rows[:index+1]
    selected = LABELS[r['selected']]
    if mode == MODES[0]:
        st.markdown(selection_timeline(rows, r['window']), unsafe_allow_html=True)
        st.caption('W6 → W7: availability exception · Wi-Fi returned 0/10 ICMP replies')
    st.markdown(f'<div class="selection"><span>SELECTED INTERFACE · WINDOW {r["window"]} / {len(rows)}</span><h2>{selected}</h2></div>', unsafe_allow_html=True)
    if mode==MODES[0] and r['window']==7:
        st.info('Wi-Fi returned 0/10 ICMP replies. The controller used the availability exception to recommend cellular immediately. This was not a proactive goodput-driven switch.')
    else:
        st.info(r['reason'])
    outcome = r['selected_request_status']
    if outcome == 'not_collected':
        st.info('No historical HTTPS outcomes were collected in this replay.')
    else:
        if outcome != 'success':
            st.error('Selected request failed: ' + outcome + '. No alternate-interface retry was made.')
        a, b, c = st.columns(3)
        a.metric('Outcome', outcome)
        b.metric('Request completion / elapsed time', fmt(r.get('selected_request_ms'), ' ms'))
        binding = r.get('selected_binding_readback') in (True, 'True')
        c.metric('Socket option readback', 'Confirmed' if binding else 'Unconfirmed')
    for col, n in zip(st.columns(2), NETWORKS):
        with col:
            available = r[n+'_status']=='reachable'
            network_status = 'Reachable' if available else 'Unavailable'
            if not available:
                st.error(LABELS[n]+': Network unavailable in this observation')
            if available and (r[n+'_latency'] is None or r[n+'_loss'] is None):
                st.warning('Incomplete observation: unknown metrics cannot certify this path.')
            replies = f"{r[n+'_received']:g}/{r[n+'_sent']:g}" if r[n+'_received'] is not None and r[n+'_sent'] is not None else 'Unavailable'
            st.markdown(f'''<div class="network-card"><div class="network-heading"><b>{LABELS[n]}{' · SELECTED' if r['selected']==n else ''}</b><span>{network_status}</span></div>
            <div class="network-metrics"><div><small>ICMP mean RTT</small><strong>{fmt(r[n+'_latency'], ' ms')}</strong></div><div><small>ICMP loss</small><strong>{fmt(r[n+'_loss'], ' %')}</strong></div></div>
            <div class="network-foot">Echo replies: {replies} · Calibration: {fmt(r.get(n+'_calibration_goodput_Mbps'), ' Mbps')}</div></div>''', unsafe_allow_html=True)
    if mode == MODES[0]:
        st.caption('FULL RUN · HTTPS completed 20/24 · Failed 4/24 · Selected outcomes 7/8 successful · Cellular completions 2 × 64 KiB · Includes 16 calibration requests and 8 selected outcomes.')
    elif requests:
        public = request_table(requests)
        st.caption(f"LOGGED HTTPS · {sum(x['status']=='success' for x in public)} completed / {len(public)} attempts")
    st.caption('Cellular-backed iPhone USB; radio generation unverified. Socket readback confirms the option, not packet-confirmed egress. Unknown goodput remains unavailable.')
    a, b = st.columns(2)
    with a:
        chart(history, 'latency', 'Responsiveness', 'ICMP RTT (ms)')
    with b:
        chart(history, 'loss', 'Reachability', 'ICMP loss (%)')
    st.caption('Measured window samples only; lines do not describe observations between windows. Failed request time is elapsed time to failure.')
    with st.expander('Bounded HTTPS goodput chart', expanded=False):
        chart(history, 'calibration_goodput_Mbps', 'Pre-decision calibration', 'Bounded-object goodput (Mbps)')
    with st.expander('Decision timeline and scoring', expanded=False):
        st.metric('Recommendation changes', sum(a['selected']!=b['selected'] and a['selected'] in NETWORKS and b['selected'] in NETWORKS for a,b in zip(rows,rows[1:])))
        st.write('Profile: ' + ('File Download' if r['profile']=='file_download' else 'Video'))
        st.write('Scoring basis: ' + ('bounded HTTPS goodput utility + loss' if r['scoring_basis']=='bounded_goodput_utility_and_loss' else 'ICMP RTT + loss'))
        a,b,c,d = st.columns(4)
        a.metric('Switching margin', fmt(r.get('margin')))
        b.metric('Qualifying hold', f"{r['qualifying_count']:g} / {r['hold_required']:g}")
        c.metric('Required dwell', f"{r['dwell_seconds']:g} s")
        d.metric('Candidate advantage', fmt(r.get('candidate_advantage')))
        st.caption('Normal hysteresis requires three consecutive qualifying windows and 30 seconds dwell. An unavailable selected path triggers an immediate availability exception. Observed-guardrail rescue may qualify below the margin but still requires hold/dwell. A scoring-basis change resets trend and hold.')
        if 'elapsed_dwell' in r:
            st.write('Elapsed dwell at this observation: '+fmt(r['elapsed_dwell'], ' s'))
        st.dataframe(pd.DataFrame([dict(window=x['window'], selected=LABELS[x['selected']], reason=x['reason'], HTTPS=x['selected_request_status'], request_ms=x.get('selected_request_ms')) for x in rows]), hide_index=True, use_container_width=True)
        st.dataframe(pd.DataFrame([dict(window=x['window'], **{LABELS[n]+' adjusted score':x.get(n+'_adjusted_score') for n in NETWORKS}) for x in history]), hide_index=True, use_container_width=True)
        st.write('Video scores observed ICMP RTT/loss; it does not measure video-call QoE. File Download uses pre-decision calibration only when both paths have valid bounded transfers; otherwise it falls back to RTT/loss. The download utility combines 80% capped goodput against a fixed 10 Mbps reference and 20% RTT quality before the existing loss/trend policy.')
    with st.expander('HTTPS request ledger · calibration versus selected outcome', expanded=False):
        if requests:
            public = request_table(requests)
            st.dataframe(pd.DataFrame(public), hide_index=True, use_container_width=True)
            successes = sum(x['status']=='success' for x in public)
            st.write(f'{successes} successful / {len(public)} attempts; {len(public)-successes} failed or incomplete.')
        else:
            st.info('Request ledger unavailable. No outcomes are invented.')
        st.write('Calibration deliberately samples both paths before a download decision. Its alternating interfaces are not policy switches. Selected-outcome requests follow the recommendation. Goodput is delivered body bits divided by full fresh HTTPS time, including TCP/TLS/server/request overhead; it is not link capacity.')
    with st.expander('Evidence provenance and limits', expanded=False):
        st.write('Sanitized evidence: mac_hub/competition/reports/20261104-final/. Public CSV and provenance hashes are checked before recorded playback. Exact stored values are retained; display metrics round to three decimals. Hover charts or inspect the ledger for greater precision.')
        st.write('The eight-window run makes the same decisions as Wi-Fi-first. It demonstrates integrated fallback capability, not comparative superiority; no separate baseline HTTPS outcomes were executed.')
        st.write('No seamless handover, packet-confirmed physical switching, verified 5G access, actual video QoE, measured handover time, or universal improvement is claimed. Historical movement-stage boundaries were not recorded. The historical W15 parsed RTT excludes a late reply present in the ping summary.')


def main():
    st.set_page_config(page_title='SmartConnect · EDGE 2026', page_icon='↔', layout='wide', initial_sidebar_state='expanded')
    st.markdown('''<style>
    .stApp {background:#071322;color:#e6f1fa}
    [data-testid="stSidebar"] {background:#0c1d30}
    .block-container {max-width:1280px;padding-top:3rem;padding-bottom:1rem}
    h1 {font-size:2rem;padding:0;margin:0}
    h1,h2,h3 {letter-spacing:-.025em;color:#eefaff}
    [data-testid="stMetricValue"] {color:#63e6ef;font-variant-numeric:tabular-nums;font-size:1.45rem}
    [data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px}
    .eyebrow {color:#63e6ef;letter-spacing:.2em;font-size:.75rem;font-weight:700}
    .selection {background:linear-gradient(110deg,#103447,#10223b);border:1px solid #26788b;border-radius:16px;padding:8px 16px;margin:4px 0}
    .selection span {color:#80e7ed;font-size:.75rem;letter-spacing:.12em}
    .selection h2 {margin:0;padding:0;font-size:1.7rem}
    .selection p {margin:0;color:#b4cbd9}
    [data-testid="stVerticalBlock"] {gap:.65rem}
    .window-timeline {display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:5px}
    .window {position:relative;display:flex;justify-content:center;gap:6px;flex-wrap:wrap;padding:7px 3px;border-radius:6px;background:#103447;color:#80e7ed;font-size:.75rem}
    .window.cellular {background:#292648;color:#c5baff}
    .window.current {outline:2px solid #e6f1fa;outline-offset:-2px}
    .transition {position:absolute;left:-7px;top:-10px;color:#fff;font-size:1.3rem;font-weight:bold}
    .network-card {background:#0c1d30;border:1px solid #244458;border-radius:12px;padding:12px 15px}
    .network-heading {display:flex;justify-content:space-between;gap:8px;font-size:1rem}
    .network-heading span {font-size:.8rem;color:#b8cddc}
    .network-metrics {display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:7px 0}
    .network-metrics small {display:block;color:#b8cddc;font-size:.75rem}
    .network-metrics strong {display:block;color:#63e6ef;font-size:1.35rem}
    .network-foot {color:#b8cddc;font-size:.75rem}
    @media(max-width:700px) {.window-timeline {gap:3px}.window span {font-size:.6rem}.network-metrics strong {font-size:1.1rem}}
    </style>''', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">ADVANCED TECHNOLOGY PIONEERS 2026 · EDGE</div>', unsafe_allow_html=True)
    st.title('SmartConnect')
    st.write('Application-aware selection for new HTTPS connections · Real measurements, explainable fallback.')
    mode = st.sidebar.radio('Demonstration mode', MODES)
    st.sidebar.caption('Offline viewer · no probes, HTTPS requests, captures, or network-setting changes are started here.')
    profile = st.sidebar.selectbox('Application profile', ['video_call','file_download']) if mode == MODES[1] else None
    path = st.sidebar.text_input('Existing runner events.jsonl', '/tmp/smartconnect-approved-demo/events.jsonl') if mode==MODES[2] else None
    play = st.sidebar.toggle('Replay animation', value=False) if mode!=MODES[2] else False
    if st.sidebar.button('Restart replay'):
        st.session_state['frame'] = 0

    @st.fragment(run_every=2 if play or path else None)
    def render():
        try:
            requests = []
            if mode==MODES[0]:
                rows, requests = recorded()
                st.caption('RECORDED REAL EXPERIMENT, NOT LIVE · '+recorded_date(rows[0]['timestamp_utc'])+' · File Download')
            elif mode==MODES[1]:
                st.caption('HISTORICAL REAL OBSERVATIONS · REPLAYED POLICY DECISIONS · NOT LIVE')
                st.caption('18 real-ICMP windows. No historical HTTPS outcomes. No recorded movement-stage boundaries. Default Video replay changes recommendations at W4 and W18.')
                raw = list(replay_rows(application=profile))
                rows = [project(x) for x in raw]
                for i,r in enumerate(rows):
                    r['reason'] = reason(r, rows[i-1] if i else None)
            else:
                st.caption('LIVE LOG VIEWER · existing collector files only')
                events = read_events(path)
                if not events:
                    st.info('Waiting for completed measurements. Opening this viewer starts no collection.')
                    return
                if any(e.get('mode')!='live' for e in events):
                    raise ValueError('Wrong mode')
                completed_events = [e for e in events if e.get('event')=='completed_window']
                latest = completed_events[-1] if completed_events else events[-1]
                age = (datetime.now(timezone.utc)-datetime.fromisoformat(latest['timestamp'])).total_seconds()
                if age > latest.get('freshness_limit_seconds',45) or age < -5:
                    st.error('Stale observations or clock change. Selection must not be treated as current.')
                completed = Path(path).with_name('manifest.json')
                if completed.exists():
                    manifest = json.loads(completed.read_text())
                    for name, expected in manifest['output_hashes'].items():
                        if Path(name).name!=name or digest(completed.parent/name)!=expected:
                            raise ValueError('Integrity mismatch')
                    st.warning('Collector finished or cancelled. This is a saved log, not active collection.')
                    if manifest.get('run_error_type'):
                        st.error('Collector stopped with an error; partial evidence retained.')
                rows = [project(e) for e in events if e.get('event')=='completed_window']
                for i,r in enumerate(rows):
                    r['reason'] = reason(r, rows[i-1] if i else None)
                request_path = Path(path).with_name('requests.jsonl')
                if request_path.is_file():
                    requests = read_events(request_path)
            if not rows:
                st.info('No completed measurement windows available yet.')
                return
            if play:
                index = st.session_state.get('frame',0) % len(rows)
                st.session_state['frame'] = index+1
                st.caption(f'Replaying window {index+1} of {len(rows)} · animation loops')
            elif len(rows)==1:
                index = 0
            else:
                index = st.slider('Inspect measurement window', 1, len(rows), len(rows) if path else 1, key='window_'+str(MODES.index(mode)))-1
            present(rows, requests, mode, index)
        except Exception:
            st.error('Evidence unavailable, incomplete, or invalid. Check the local evidence privately; no raw network details are displayed.')
    render()


if __name__ == '__main__':
    main()
