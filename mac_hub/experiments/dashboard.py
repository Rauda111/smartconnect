"""Read-only presentation of completed offline experimental artifacts."""
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st
from mac_hub.experiments.evaluate import selected


def experiments():
    st.subheader('Experimental results · paired offline replay')
    st.info('Inputs are labeled synthetic or measured ICMP. All selected-path comparisons are counterfactual proxies. Recommendations are not actual handovers or achieved application QoE.')
    folder=Path(st.text_input('Experiment results directory','mac_hub/experiments/results'))
    if not (folder/'manifest.json').is_file():
        st.code('python -m mac_hub.experiments.run --output-dir mac_hub/experiments/results')
        st.caption('Generate the offline experiment artifacts first; this dashboard does not run probes.')
        return
    try:
        data=pd.read_csv(folder/'decisions.csv')
        aggregate=pd.read_csv(folder/'aggregate.csv')
        per_run=pd.read_csv(folder/'per_run.csv')
        events=pd.read_csv(folder/'event_responses.csv')
        scenario=st.selectbox('Experiment scenario',sorted(data.scenario.unique()))
        app=st.selectbox('Experiment application',['video_call','file_download'])
        subset=data[(data.scenario==scenario)&(data.application==app)]
        seed=st.selectbox('Noise seed (−1 = measured capture)',sorted(subset.seed.unique()))
        trace=subset[subset.seed==seed].copy()
        st.caption(f'Input source: {trace.source.iloc[0]} · {len(trace)} windows · RTT/loss scoring only; RSSI, throughput and application jitter unavailable.')
        if trace.source.iloc[0]=='measured_icmp':
            st.warning('Measured-input replay; no controlled event or quiet-region labels. The bundled one-window smoke trace cannot evaluate switching or field improvements.')
        for metric in ('latency','loss','rtt_variation'):
            chart=trace[['elapsed_seconds',f'wifi_{metric}',f'cellular_{metric}']].copy()
            for method in ('wifi_first','smartconnect'):
                chart[method+'_selected_proxy']=selected(trace,method,metric)
            st.write({'latency':'Mean RTT (ms)','loss':'Probe packet loss (%)','rtt_variation':'Adjacent RTT variation (ms)'}[metric])
            st.line_chart(chart.set_index('elapsed_seconds'))
        long=trace.melt(id_vars=['elapsed_seconds'],value_vars=['wifi_first','smartconnect'],var_name='Policy',value_name='Recommended path')
        st.altair_chart(alt.Chart(long).mark_line(interpolate='step-after').encode(
            x=alt.X('elapsed_seconds:Q',title='Elapsed seconds'),y='Recommended path:N',color='Policy:N'),width='stretch')
        st.subheader('Run metrics and missing-data counts')
        st.dataframe(per_run[(per_run.scenario==scenario)&(per_run.application==app)&(per_run.seed==seed)],hide_index=True)
        st.caption('Recommended handovers count direct Wi-Fi↔cellular recommendation changes. Outages and reattachments are separate. Quiet-region changes and reversals are stability proxies, not proven unnecessary switches.')
        response=events[(events.scenario==scenario)&(events.application==app)&(events.seed==seed)]
        st.subheader('Response to annotated events')
        if response.empty:
            st.caption('No controlled event annotations available for this trace.')
        else:
            st.dataframe(response,hide_index=True)
            st.caption('First target recommendation after event onset; already-on-target cases flagged. Blank response means unobserved before the next event. Delay is not actual handover completion time.')
        st.subheader('Comparative summary across runs')
        summary=aggregate[(aggregate.scenario==scenario)&(aggregate.application==app)].copy()
        metric=st.selectbox('Summary metric',list(summary.metric.unique()))
        bars=summary[summary.metric==metric].copy()
        bars['lower']=bars['mean']-bars.sample_sd
        bars['upper']=bars['mean']+bars.sample_sd
        base=alt.Chart(bars).encode(x='method:N')
        st.altair_chart(base.mark_bar().encode(y=alt.Y('mean:Q',title=metric),color='method:N')+
                       base.transform_filter('isValid(datum.sample_sd)').mark_rule().encode(y='lower:Q',y2='upper:Q'),width='stretch')
        st.caption('Mean ± sample SD across synthetic seed-level runs. Measured captures are separate; n=1 has no SD. No pooling of synthetic and measured evidence.')
        st.dataframe(summary,hide_index=True)
        with st.expander('Experimental report / poster wording'):
            st.markdown((folder/'REPORT.md').read_text())
        st.download_button('Download per-run CSV',(folder/'per_run.csv').read_bytes(),'per_run.csv','text/csv')
    except (OSError,ValueError,KeyError) as exc:
        st.error(f'Cannot load experimental artifacts: {exc}')
