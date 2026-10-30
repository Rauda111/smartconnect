"""Read-only local dashboard. Start the monitor separately."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import streamlit as st
from mac_hub.compare import summarize

st.set_page_config(page_title='SmartConnect Mac Hub',layout='wide')
st.title('SmartConnect · Mac Hub · Decision-only evaluation')
st.warning('Decision recommendations only. Actual application traffic follows macOS routing. No session continuity or 5G radio claim.')
path=Path(st.sidebar.text_input('Monitor CSV path','mac_hub/logs/live.csv'))
st.caption('RSSI, application jitter and throughput: unavailable. RTT variation is an ICMP-derived diagnostic, not application jitter. File Download capacity is unknown.')


@st.fragment(run_every=3)
def live():
    if not path.is_file():
        st.info('Start the monitor with --output mac_hub/logs/live.csv, or enter an existing CSV path.')
        return
    try:
        frame=pd.read_csv(path,on_bad_lines='skip')
        # A flushed CSV row is complete; ignore an in-progress final write.
        frame=frame.dropna(subset=['timestamp','recommended','cellular_interface'])
        if frame.empty:
            st.info('Waiting for first complete measurement window.')
            return
        row=frame.iloc[-1]
        st.caption(f"Source: {row.source} | Profile: {row.application} | Last completed window: {row.timestamp}")
        age=(pd.Timestamp.now(tz='UTC')-pd.to_datetime(row.timestamp,utc=True)).total_seconds()
        if age > 45:
            st.warning(f'Log is stale ({age:.0f}s since last window); recommendations are historical.')
        st.metric('Recommended path',row.recommended)
        st.info(row.explanation)
        st.write(f"Wi-Fi-first baseline: {row.baseline} · Original profile weight covered: {row.coverage:.0%}")
        cols=st.columns(2)
        for col,n in zip(cols,('wifi','cellular')):
            with col:
                st.subheader(f'{n} · {row[f"{n}_interface"]}')
                st.write(f"Status: {row[f'{n}_status']} · Trend: {row[f'{n}_trend']}")
                for key,label in [('latency','Mean RTT (ms)'),('loss','ICMP loss (%)'),('rtt_variation','Adjacent RTT variation (ms)'),('adjusted_score','Partial adjusted score')]:
                    v=row[f'{n}_{key}']
                    st.metric(label,'Unavailable' if pd.isna(v) else f'{v:.3f}')
                st.write('Observed breaches:', 'None observed' if pd.isna(row[f'{n}_breaches']) else str(row[f'{n}_breaches']))
                st.write('Unknown guardrails:',str(row[f'{n}_unknown_guardrails']))
                if pd.notna(row[f'{n}_error']):
                    st.error(row[f'{n}_error'])
        for metric in ('latency','loss','rtt_variation','adjusted_score'):
            st.write(metric)
            st.line_chart(frame.set_index('elapsed_seconds')[[f'wifi_{metric}',f'cellular_{metric}']])
        st.subheader('Paired counterfactual probe comparison')
        st.dataframe(summarize(frame))
        st.caption('Sample means; missing values excluded with counts reported. These are selection proxies, not achieved QoE or handovers.')
        st.dataframe(frame[['timestamp','recommended','baseline','explanation','wifi_trend','cellular_trend']].tail(100))
    except (ValueError,KeyError,OSError,pd.errors.EmptyDataError) as exc:
        st.error(f'Cannot read monitor log: {exc}')

live_tab, experiment_tab = st.tabs(['Live monitoring', 'Phase 2 experiments'])
with live_tab:
    live()
with experiment_tab:
    from mac_hub.experiments.dashboard import experiments
    experiments()
