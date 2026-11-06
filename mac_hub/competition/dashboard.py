"""Local-only public-safe viewer; never starts a collector or sends traffic."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json
from datetime import datetime, timezone, timedelta
import pandas as pd
import streamlit as st
from mac_hub.competition.run import replay_rows, INTERFACES, digest


from mac_hub.competition.dashboard_ui import read_events


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


from html import escape
from mac_hub.competition import dashboard_ui as ui


def explanation(row, mode):
    selected = LABELS[row['selected']]
    if mode == MODES[0] and row['window'] == 7:
        return 'Wi-Fi returned 0/10 ICMP replies. An availability exception selected cellular immediately. A new HTTPS request completed in 224.695 ms. This was not a proactive goodput-driven switch.'
    if row['selected'] is None:
        return 'Neither connection has enough usable observations to recommend a new request.'
    other = 'cellular' if row['selected']=='wifi' else 'wifi'
    if row[other+'_status'] != 'reachable':
        return selected+' was retained because the other connection was unavailable in this observation.'
    if mode == MODES[0] and row['window'] == 6:
        return 'Wi-Fi was retained while cellular had only one qualifying observation out of three. The selected Wi-Fi HTTPS request then timed out.'
    if row['qualifying_count']:
        return selected+' was retained while the alternative builds its normal three-observation hold. One better-looking sample is not enough.'
    if row['window'] == 1:
        return selected+' was usable and became the initial selection for a new request.'
    if row['reason'].startswith('Recommendation changed'):
        return selected+' was selected after the alternative stayed better through the normal hold and dwell checks.'
    return selected+' was retained: the other connection did not show a sustained qualifying advantage.'


def overview(rows, requests, mode, index):
    r = rows[index]
    left, right = st.columns([1, 2])
    with left:
        st.markdown(f'<div class="selection"><small>SELECTED FOR A NEW REQUEST</small><h2>{LABELS[r["selected"]]}</h2><span>Window {r["window"]} of {len(rows)}</span></div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="why"><b>Why this decision?</b><p>'+escape(explanation(r, mode))+'</p></div>', unsafe_allow_html=True)
    for col, n in zip(st.columns(2), NETWORKS):
        with col:
            health, style = ui.path_health(r, n)
            replies = f"{r[n+'_received']:g}/{r[n+'_sent']:g}" if r[n+'_received'] is not None and r[n+'_sent'] is not None else 'Unavailable'
            selected = ' · SELECTED' if r['selected']==n else ''
            st.markdown(f'''<section class="network-card {style}" aria-label="{LABELS[n]} measurements">
            <div class="network-heading"><b>{LABELS[n]}{selected}</b><span>{health}</span></div>
            <div class="network-metrics"><div title="{escape(ui.TERMS['RTT'][0])}"><small>Response time · RTT</small><strong>{fmt(r[n+'_latency'], ' ms')}</strong></div><div title="{escape(ui.TERMS['Packet loss'][0])}"><small>Missed replies · ICMP loss</small><strong>{fmt(r[n+'_loss'], ' %')}</strong></div></div>
            <div class="network-foot">Echo replies: {replies} · Small-download calibration: {fmt(r.get(n+'_calibration_goodput_Mbps'), ' Mbps')}</div></section>''', unsafe_allow_html=True)
    outcome = r['selected_request_status']
    if outcome == 'not_collected':
        st.info('No HTTPS outcomes were collected in this historical replay. Only policy decisions are replayed.')
    else:
        a, b, c = st.columns(3)
        a.metric('Latest inspected HTTPS result', 'Completed' if outcome=='success' else 'Failed · '+outcome, help='The actual selected-outcome request at the inspected window; separate from calibration.')
        b.metric('Completion time' if outcome=='success' else 'Time until failure', fmt(r.get('selected_request_ms'), ' ms'), help='Whole new HTTPS request time, including connection and TLS setup.')
        c.metric('Socket setting readback', 'Confirmed' if r.get('selected_binding_readback') in (True,'True') else 'Unconfirmed', help=' '.join(ui.TERMS['Socket binding']))
        if outcome != 'success':
            st.error('Selected request failed: '+outcome+'. No alternate-interface retry was made.')
    if mode==MODES[0]:
        st.caption('FULL RUN · 20/24 HTTPS requests completed (includes calibration) · Selected outcomes: 7/8 · Cellular: 2 × 64 KiB · Wi-Fi-first made identical selections here.')
    elif requests:
        public = requests if 'interface' in requests[0] else request_table(requests)
        st.caption(f"LOGGED REQUESTS · {sum(x['status']=='success' for x in public)}/{len(public)} completed, including calibration when present.")
    st.caption('Recorded samples are not live collection. Selection applies to a new request; socket readback is not packet-confirmed physical egress.' if mode!=MODES[2] else 'Read-only log viewer. Socket readback is not packet-confirmed physical egress; this page never starts collection.')


def technical(rows, requests, index):
    r = rows[index]; history = rows[:index+1]
    st.subheader('Technical Details')
    st.caption('Replay is paused while this area is open. Inspect a different window with the navigation controls; nothing advances automatically.')
    st.button('Back to Overview', on_click=ui.back, args=(st.session_state,), key='back_overview')
    with st.expander('Plain-English terms', expanded=st.session_state.get('show_terms', False)):
        term = st.selectbox('Explain a term', list(ui.TERMS), key='term')
        short, detail = ui.TERMS[term]
        st.write(short)
        st.caption(detail)
    with st.expander('Measurement charts', expanded=False):
        a,b = st.columns(2)
        with a:
            chart(history, 'latency', 'Response time · ICMP RTT', 'ICMP RTT (ms)')
        with b:
            chart(history, 'loss', 'Missed replies · ICMP loss', 'ICMP loss (%)')
        chart(history, 'calibration_goodput_Mbps', 'Pre-decision small-download calibration', 'Bounded-object goodput (Mbps)')
        st.caption('Measured samples only. Missing values remain unavailable; lines do not describe observations between windows.')
    with st.expander('Decision timeline and scoring', expanded=False):
        st.metric('Recommendation changes', sum(a['selected']!=b['selected'] and a['selected'] in NETWORKS and b['selected'] in NETWORKS for a,b in zip(rows,rows[1:])))
        st.write('Profile: '+('File Download' if r['profile']=='file_download' else 'Video'))
        st.write('Scoring basis: '+('bounded HTTPS goodput utility + loss' if r['scoring_basis']=='bounded_goodput_utility_and_loss' else 'ICMP RTT + loss'))
        a,b,c,d = st.columns(4)
        a.metric('Switching margin', fmt(r.get('margin')), help='Required score advantage in the normal switching rule; not a speed difference in Mbps.')
        b.metric('Qualifying hold', f"{r['qualifying_count']:g} / {r['hold_required']:g}", help=' '.join(ui.TERMS['Hysteresis']))
        c.metric('Required dwell', f"{r['dwell_seconds']:g} s", help=' '.join(ui.TERMS['Dwell']))
        d.metric('Candidate advantage', fmt(r.get('candidate_advantage')))
        st.caption('Normal hold: three consecutive qualifying observations; dwell: 30 seconds. An unavailable selected path triggers an immediate availability exception. Observed-guardrail rescue may qualify below the margin but still requires hold/dwell. A scoring-basis change resets trend and hold.')
        st.write('Elapsed dwell at this observation: '+fmt(r.get('elapsed_dwell'), ' s'))
        st.dataframe(pd.DataFrame([dict(window=x['window'], selected=LABELS[x['selected']], reason=x['reason'], HTTPS=x['selected_request_status'], request_ms=x.get('selected_request_ms')) for x in rows]), hide_index=True, use_container_width=True)
        st.dataframe(pd.DataFrame([dict(window=x['window'], **{LABELS[n]+' adjusted score':x.get(n+'_adjusted_score') for n in NETWORKS}) for x in history]), hide_index=True, use_container_width=True)
        st.write('Video scores observed ICMP RTT/loss, not video-call QoE. File Download uses calibration only when both paths have valid bounded transfers; otherwise it uses RTT/loss. Download utility combines 80% capped goodput against a fixed 10 Mbps reference and 20% RTT quality before the existing loss/trend policy.')
    with st.expander('HTTPS request ledger · calibration versus selected outcome', expanded=False):
        if requests:
            public = requests if 'interface' in requests[0] else request_table(requests)
            st.dataframe(pd.DataFrame(public), hide_index=True, use_container_width=True)
            successes = sum(x['status']=='success' for x in public)
            st.write(f'{successes} successful / {len(public)} attempts; {len(public)-successes} failed or incomplete.')
        else:
            st.info('No request ledger available. No outcomes are invented.')
        st.write('Calibration samples both paths before selection; its alternating interfaces are not policy switches. Selected-outcome requests follow the recommendation. Bounded goodput includes all fresh HTTPS overhead and is not link capacity.')
    with st.expander('Evidence provenance and limits', expanded=False):
        st.write('Public package: mac_hub/competition/reports/20261104-final/. Recorded CSV and provenance hashes are checked. UTC timestamps and exact stored values are preserved; display metrics round to three decimals.')
        st.write('This fallback run gives the same selections as Wi-Fi-first; it demonstrates integrated fallback, not comparative superiority. No separate baseline HTTPS outcomes were executed.')
        st.write('No seamless session migration, verified 5G radio, actual video QoE, measured handover time or packet-confirmed physical egress is claimed. Historical movement boundaries were not recorded. Historical W15 parsed RTT excludes a late reply present in the ping summary.')


def tour(row):
    stages = ['Monitor', 'Decide', 'Act', 'Verify']
    stage = st.radio('Guided tour · Monitor → Decide → Act → Verify', stages, horizontal=True, on_change=ui.pause, args=(st.session_state,), key='tour_stage')
    messages = {
        'Monitor': 'Read both connection cards. RTT is response time; packet loss is missed ICMP replies. Unavailable means no usable value was recorded.',
        'Decide': 'Read “Why this decision?”. Normal hold avoids flip-flopping. At W7, 0/10 Wi-Fi replies trigger the immediate availability exception.',
        'Act': 'Inspect the new HTTPS request. At recorded W7, the cellular-selected request completed 64 KiB in 224.695 ms. Existing sessions were not migrated.',
        'Verify': 'Check the result and socket-setting readback. Readback confirms the setting, not physical egress. The full run completed 20/24 requests, including calibration.',
    }
    st.info(messages[stage])


def navigation(count, mode):
    state = st.session_state
    state['window'] = max(1, min(count, state.get('window', 1)))
    cols = st.columns([1,1,1.1,1,1.8])
    cols[0].button('Previous', disabled=state['window']==1, on_click=ui.choose, args=(state,state['window']-1), key='previous', use_container_width=True)
    cols[1].button('Next', disabled=state['window']==count, on_click=ui.choose, args=(state,state['window']+1), key='next', use_container_width=True)
    cols[2].button('Pause' if state.get('playing') else 'Play', disabled=mode==MODES[2] or state.get('technical',False) or state['window']==count, on_click=ui.play_pause, args=(state,count), key='play_pause', help='Replay saved windows only. Disabled in Live monitoring and while Technical Details is open. Restart after the last window.', use_container_width=True)
    cols[3].button('Restart', disabled=state['window']==1 and not state.get('playing'), on_click=ui.choose, args=(state,1), key='restart', use_container_width=True)
    cols[4].selectbox('Replay speed', list(ui.SPEEDS), key='speed', on_change=ui.pause, args=(state,), disabled=mode==MODES[2], label_visibility='collapsed', help='Changing speed pauses replay. Press Play to continue at the new speed.')
    status = 'Playing' if state.get('playing') else 'Finished · last window' if state['window']==count else 'Paused'
    if mode==MODES[2]:
        status = 'Inspecting saved log window'
    st.caption(f"{status} · Window {state['window']} of {count}"+(' · Technical inspection locks replay' if state.get('technical') else ''))


def timeline(rows):
    cols = st.columns(len(rows))
    for i,(col,row) in enumerate(zip(cols,rows)):
        changed = i>0 and row['selected']!=rows[i-1]['selected']
        label = f"W{row['window']}{' ↳' if changed else ''} · {LABELS[row['selected']]}"
        col.button(label, key='timeline_'+str(row['window']), type='primary' if st.session_state['window']==i+1 else 'secondary', help=('Transition: Wi-Fi had 0/10 ICMP replies; availability exception. ' if changed else '')+'Inspect this recorded window. Mouse or keyboard activation pauses replay.', on_click=ui.choose, args=(st.session_state,i+1), use_container_width=True)


def live_controls():
    known = ui.known_logs()
    options = ['Choose a log'] + [f'Approved local log {i+1}' for i in range(len(known))] + ['Enter an existing log path privately']
    selected = st.sidebar.selectbox('Read-only collector log', options, key='log_choice', on_change=ui.reset, args=(st.session_state,))
    path = None
    if selected == options[-1]:
        path = st.sidebar.text_input('Existing log path (hidden)', type='password', help='Read-only local path. Never projected in the public view; raw errors and identifiers are hidden.', key='private_log', on_change=ui.reset, args=(st.session_state,)) or None
    elif selected!='Choose a log':
        path = known[options.index(selected)-1]
    with st.sidebar.expander('Expected log location', expanded=False):
        st.code('/tmp/smartconnect-approved-demo/events.jsonl')
        st.caption('Only this conventional approved location is checked automatically. A run may also contain requests.jsonl and manifest.json. Collection is separate and requires approval.')
    st.sidebar.button('Refresh log', key='refresh_log', help='Re-read the existing file. Does not start a collector.')
    return path


def main():
    st.set_page_config(page_title='SmartConnect · EDGE 2026', page_icon='↔', layout='wide', initial_sidebar_state='expanded')
    st.markdown('<style>'+Path(__file__).with_suffix('.css').read_text()+'</style>', unsafe_allow_html=True)
    state = st.session_state
    for key,value in dict(window=1, playing=False, technical=False, show_terms=False, speed='Normal · 2 seconds', source_id=None).items():
        if key not in state:
            state[key] = value
    st.markdown('<div class="eyebrow">ADVANCED TECHNOLOGY PIONEERS 2026 · EDGE</div><h1>SmartConnect</h1><p class="subtitle">See both connections. Understand the choice. Verify the next request.</p>', unsafe_allow_html=True)
    if state.pop('switch_to_recorded', False):
        state['mode'] = MODES[0]
        ui.reset(state)
    mode = st.sidebar.radio('Demonstration mode', MODES, key='mode', on_change=ui.reset, args=(state,))
    st.sidebar.caption('Recorded: real saved results. Historical: real ICMP inputs, replayed policy. Live: read-only files from a separately approved collector.')
    profile = st.sidebar.selectbox('Application profile', ['video_call','file_download'], key='profile', on_change=ui.reset, args=(state,)) if mode==MODES[1] else None
    path = live_controls() if mode==MODES[2] else None
    st.sidebar.toggle('Guided demo tour', key='guided', on_change=ui.pause, args=(state,), help='A short Monitor → Decide → Act → Verify explanation. Opening or changing the tour pauses playback.')
    st.sidebar.caption('No probes, HTTPS requests, captures or network changes are started by this viewer.')
    # A fixed local UI clock avoids rebuilding fragment ownership on Play/Pause.
    # tick() changes windows only while playing; technical inspection stays locked.
    @st.fragment(run_every=.5)
    def render():
        try:
            if mode==MODES[0]:
                rows, requests = recorded()
                st.caption('RECORDED REAL EXPERIMENT · NOT LIVE · '+recorded_date(rows[0]['timestamp_utc'])+' · File Download')
            elif mode==MODES[1]:
                st.caption('HISTORICAL REAL OBSERVATIONS · REPLAYED POLICY DECISIONS · NOT LIVE')
                st.caption('18 real-ICMP windows. No historical HTTPS outcomes or movement-stage boundaries. Video replay changes at W4 and W18.')
                rows = [project(r) for r in replay_rows(application=profile)]
                for i,r in enumerate(rows):
                    r['reason'] = reason(r, rows[i-1] if i else None)
                requests = []
            else:
                st.caption('LIVE LOG VIEWER · READ ONLY · collection remains separate')
                data = ui.load_live(path)
                for kind, message in data['notices']:
                    getattr(st,kind)(message)
                rows, requests = data['rows'], data['requests']
            if not rows:
                if mode!=MODES[2]:
                    st.warning('No completed windows are available. Choose another evidence mode.')
                if st.button('Open recorded demo', key='open_recorded'):
                    state['switch_to_recorded'] = True
                    st.rerun()
                return
            source = (mode, profile, str(path) if path else None)
            if state.get('source_id') != source:
                state['source_id'] = source
                state['window'] = len(rows) if mode==MODES[2] else 1
            ui.tick(state, len(rows))
            navigation(len(rows), mode)
            if mode==MODES[0]:
                timeline(rows)
            else:
                st.slider('Inspect measurement window', 1, len(rows), key='window', on_change=ui.pause, args=(state,), disabled=len(rows)==1) if len(rows)>1 else st.caption('One completed window available')
            a,b = st.columns([1,1])
            a.toggle('Technical Details', key='technical', on_change=ui.pause, args=(state,), help='Opening details pauses replay. Playback stays locked until you return to Overview.')
            b.button('Explain terms', key='explain_terms', on_click=ui.inspect_details, args=(state,True), help='Open a plain-English glossary and pause replay.')
            index = state['window']-1
            if state.get('technical'):
                technical(rows, requests, index)
            else:
                if state.get('guided'):
                    tour(rows[index])
                overview(rows, requests, mode, index)
        except Exception:
            ui.pause(state)
            st.error('Evidence unavailable or corrupt — recorded files may be missing or invalid. Check them privately; no raw details are displayed.')
    render()


if __name__ == '__main__':
    main()
