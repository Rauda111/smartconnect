"""Static artifacts derived only from experiment CSV-equivalent tables."""
import os
from pathlib import Path
import tempfile
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'smartconnect-phase2-mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mac_hub.experiments.evaluate import selected

LABELS={'wifi_first':'Wi-Fi-first','smartconnect':'SmartConnect'}
COLORS={'wifi_first':'#b76529','smartconnect':'#157f88'}


def plots(tables, output):
    folder=output/'plots'
    folder.mkdir()
    decisions=tables['decisions']
    for scenario in sorted(decisions.scenario.unique()):
        for app in ('video_call','file_download'):
            data=decisions[(decisions.scenario==scenario)&(decisions.application==app)]
            seed=data.seed.min()
            data=data[data.seed==seed]
            fig,axes=plt.subplots(5,1,figsize=(10,11),sharex=True)
            for ax,metric,label in zip(axes,('latency','loss','rtt_variation'),('Probe RTT (ms)','Probe loss (%)','RTT variation (ms)')):
                for n,color in [('wifi','#5555aa'),('cellular','#33995c')]:
                    ax.plot(data.elapsed_seconds,data[f'{n}_{metric}'],label=n,alpha=.6,color=color)
                for method in LABELS:
                    ax.plot(data.elapsed_seconds,selected(data,method,metric),label=LABELS[method]+' selected proxy',linestyle='--',color=COLORS[method])
                ax.set_ylabel(label)
                ax.grid(alpha=.15)
            for method in LABELS:
                y=data[method].map({'none':-1,'wifi':0,'cellular':1})
                axes[3].step(data.elapsed_seconds,y,where='post',label=LABELS[method],color=COLORS[method])
            axes[3].set_yticks([-1,0,1],['none','Wi-Fi','cellular'])
            axes[3].set_ylabel('Recommendation')
            for n in ('wifi','cellular'):
                axes[4].step(data.elapsed_seconds,data[f'{n}_status'].map({'error':-1,'no_reply':0,'reachable':1}),where='post',label=n)
            axes[4].set_yticks([-1,0,1],['error','no reply','reachable'])
            axes[4].set_ylabel('Probe status')
            axes[4].set_xlabel('Elapsed seconds (observation completion)')
            for ax in axes:
                ax.legend(fontsize=7,loc='upper left',ncol=2)
            source=data.source.iloc[0]
            run_label=f'seed {seed}' if source=='synthetic' else 'observational capture (no noise seed)'
            fig.suptitle(f'{scenario} / {app} / {run_label}\nInput: {source}; selected values are counterfactual proxies')
            fig.tight_layout(rect=(0,0,1,.95))
            fig.savefig(folder/f'{scenario}_{app}.png',dpi=120)
            plt.close(fig)
    aggregate=tables['aggregate']
    synth=aggregate[aggregate.source=='synthetic']
    metrics=('latency_mean','loss_mean','rtt_variation_mean','recommended_handovers','observed_guardrail_violation_windows','quiet_region_changes')
    for app in ('video_call','file_download'):
        fig,axes=plt.subplots(3,2,figsize=(13,12))
        for ax,metric in zip(axes.flat,metrics):
            subset=synth[(synth.application==app)&(synth.metric==metric)]
            names=sorted(subset.scenario.unique())
            for j,method in enumerate(LABELS):
                group=subset[subset.method==method].set_index('scenario').loc[names]
                ax.bar([i+(j-.5)*.36 for i in range(len(names))],group['mean'],width=.36,
                       yerr=group.sample_sd.to_numpy() if group.sample_sd.notna().any() else None,label=LABELS[method],color=COLORS[method],capsize=2)
            ax.set_xticks(range(len(names)),[n.replace('_','\n') for n in names],fontsize=7)
            ax.set_title({'latency_mean':'Selected-probe RTT (ms)', 'loss_mean':'Selected-probe loss (%)', 'rtt_variation_mean':'Selected RTT variation (ms)', 'recommended_handovers':'Recommended path-to-path changes', 'observed_guardrail_violation_windows':'Observed guardrail violations (windows)', 'quiet_region_changes':'Quiet-region recommendation changes'}[metric])
            ax.legend(fontsize=8)
        fig.suptitle(f'{app}: synthetic input, counterfactual selection proxies\nMean ± sample SD where n > 1; unknown guardrails excluded')
        fig.tight_layout(rect=(0,0,1,.94))
        fig.savefig(folder/f'comparison_{app}.png',dpi=130)
        plt.close(fig)


def report(tables, output):
    aggregate=tables['aggregate']
    lines=['# SmartConnect Phase 2 experimental results', '',
           'Decision-only evaluation against Wi-Fi-first. No routes or network settings changed. All selected-path results are counterfactual selection proxies, not actual handovers or achieved application QoE.', '',
           '## Design', '',
           'Six synthetic scenarios × '+str(tables['per_run'].query("source == 'synthetic'").seed.nunique())+' seeds × two profiles × two policies. Each synthetic trace has 90 timestamped windows at five-second spacing. Both policies receive identical observations; each profile is replayed with a fresh causal engine. Synthetic noise seeds measure sensitivity to assumed conditions, not real-world generalization.', '',
           'RTT/loss weights renormalize to 50%/50% in both profiles (60% original weight coverage for Video Call, 30% for File Download). Different observed guardrails may produce different choices. Throughput, RSSI and application jitter are absent. RTT variation is evaluated diagnostically and never substituted for application jitter.', '',
           '## Synthetic outcomes', '',
           '| Scenario / profile | RTT: Wi-Fi-first → SmartConnect (ms) | Loss: baseline → SmartConnect (%) | Recommended path changes: baseline → SmartConnect |',
           '|---|---:|---:|---:|']
    for scenario in sorted(aggregate.query("source == 'synthetic'").scenario.unique()):
        for app in ('video_call','file_download'):
            group=aggregate[(aggregate.scenario==scenario)&(aggregate.application==app)]
            cells=[]
            for metric in ('latency_mean','loss_mean','recommended_handovers'):
                parts=[]
                for method in ('wifi_first','smartconnect'):
                    r=group[(group.method==method)&(group.metric==metric)].iloc[0]
                    precision=3 if metric == 'loss_mean' else 2
                    uncertainty=f'{r.sample_sd:.{precision}f}' if r.n > 1 else 'SD unavailable (n=1)'
                    parts.append(f'{r["mean"]:.{precision}f} ± {uncertainty}')
                cells.append(' → '.join(parts))
            lines.append(f'| {scenario} / {app} | '+ ' | '.join(cells)+' |')
    lines += ['', '## Synthetic event response', '',
              '| Scenario / profile / event | Wi-Fi-first: observed/n, mean delay (s) | SmartConnect: observed/n, mean delay (s) |',
              '|---|---:|---:|']
    for keys, group in tables['response_summary'].groupby(['scenario','application','event'],sort=True):
        cells=[]
        for method in ('wifi_first','smartconnect'):
            r=group[group.method==method].iloc[0]
            delay='unobserved' if r.observed_responses == 0 else f'{r.mean_response_seconds:.2f}'
            cells.append(f'{int(r.observed_responses)}/{int(r.events)}, {delay} (already on target: {int(r.already_on_target_events)})')
        lines.append('| '+' / '.join(keys)+' | '+' | '.join(cells)+' |')
    lines += ['', 'Response delays are conditional on an observed response. Failed responses remain explicitly counted; already-on-target cases are not switching-speed evidence.', '']
    real=tables['per_run'].query("source == 'measured_icmp'")
    lines += ['', 'Synthetic QoS table values are mean ± sample SD across seed-level summaries; SD is not a confidence interval. See aggregate.csv for variation, guardrail, stability and missing-data results, paired_differences.csv for within-trace differences, and event_responses.csv for response times (including failures to respond).', '',
              'The cellular-degradation fixture illustrates a trade-off: SmartConnect selects cellular at 100 and 105 seconds after degradation begins and recommends Wi-Fi at 110 seconds. The three-window hold therefore retains a known guardrail-breaching path for two observations despite a usable alternative. Lower whole-run RTT and higher whole-run loss are a genuine policy trade-off, not an across-the-board improvement. Stable and unavailable-path conditions may show no advantage over the baseline. Quiet-region changes can include legitimate initial policy adaptation or recovery; they are not automatically unnecessary switches.', '', '## Measured-input replay', '']
    if real.empty:
        lines.append('No measured input included.')
    else:
        for scenario, group in real.groupby('scenario'):
            lines.append(f'- {scenario}: {int(group.iloc[0].windows)} observed window(s), replayed for both profiles. No synthetic replication or SD is assigned to this capture. Measured inputs are real; selected-path outcomes and policy recommendations remain counterfactual. A one-window smoke capture cannot establish switching delay, stability or performance improvement.')
    if not real.empty:
        lines += ['', '| Measured capture / profile / policy | RTT mean (ms) | Loss mean (%) | RTT variation mean (ms) | Observed RTT windows |',
                  '|---|---:|---:|---:|---:|']
        for _,r in real.iterrows():
            lines.append(f'| {r.scenario} / {r.application} / {r.method} | {r.latency_mean:.3f} | {r.loss_mean:.3f} | {r.rtt_variation_mean:.3f} | {int(r.latency_observed_windows)} |')
    lines += ['', '## Definitions and poster-safe interpretation', '',
              '- Selected-path RTT, loss and variation are arithmetic means over observed windows; each metric has its own denominator. No-path windows and unknown values are counted separately, never replaced with zero. All-loss measurements remain present in observations even if neither policy recommends that path.',
              '- Recommended handovers count direct Wi-Fi↔cellular transitions only; initial attachment, transitions to none and reattachments are separate. None represents no eligible recommendation, not demonstrated internet failure.',
              '- Response time is from a predefined synthetic event onset to the first observation recommending its expected path, before the next event. Already-on-target cases are flagged; blank delay means no observed response, not zero. These are sampled decision delays, not switching or session-restoration times. Real traces have no event labels and no reported response-time estimate.',
              '- Observed guardrail violations, unknown-guardrail windows and no-path windows are separate. Video Call RTT >60 ms or loss >2%; File Download loss >3%. Application jitter and capacity guardrails are unknown, so no full QoE pass rate is reported.',
              '- Quiet-region path changes (both adjacent observations in a predefined stable region) and A→B→A reversals within 30 seconds are stability proxies. They do not prove a switch was unnecessary. Real traces lack stable-region truth, so that assessment is unavailable.',
              '- Window means and counts are not time-weighted. Correlated windows are not independent experimental replicates. Synthetic five-second cadence and assumed probe counts differ from real monitor windows.', '',
              '## Conclusion and limits', '',
              'The framework demonstrates reproducible application-profile-aware recommendations and paired evaluation. Examine all scenarios and both profiles, including recovery delays, unavailable periods and unfavorable trade-offs; there is no universal improvement claim. Phase 1 policy is retained for complete inputs; incomplete RTT/loss replay observations are explicitly ineligible for SmartConnect rather than scored on an accidental subset.', '',
              'For a poster: “SmartConnect was compared with Wi-Fi-first on identical timestamped traces using partial RTT/loss scoring, trends, guardrails, hold and dwell. Results quantify counterfactual selected-probe quality and recommendation stability under controlled synthetic conditions; real application QoE and switching continuity remain unverified.”', '',
              'Next: repeated naturally varying real captures, independently verified interface binding, held-out threshold calibration and authorized application goodput/call-quality experiments. No automatic switching, seamless connectivity or verified 5G radio access is claimed.', '']
    (output/'REPORT.md').write_text('\n'.join(lines))
