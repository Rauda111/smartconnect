"""Build a short readable findings report from final CSV summary and raw events."""
import argparse
import csv
from html import escape
from pathlib import Path
import statistics

SCENARIOS = ('leaving_wifi', 'congested_wifi', 'large_download', 'recovery')
APPS = ('video_call', 'file_download')
NAMES = {'leaving_wifi': 'Leaving Wi-Fi', 'congested_wifi': 'Congested Wi-Fi',
         'large_download': 'Large Download', 'recovery': 'Recovery',
         'video_call': 'Video Call', 'file_download': 'File Download'}
LABEL = 'Controlled simulation results using realistic assumed Wi-Fi and 5G-like network conditions.'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-dir', type=Path, required=True)
    args = parser.parse_args()
    out = args.results_dir
    with (out / 'tables/mean_sd.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    values = {(r['scenario'], r['application'], r['method'], r['metric']):
              (float(r['mean']), float(r['std'])) for r in rows}
    def pair(scenario, app, metric, digits=2):
        b, bs = values[scenario, app, 'baseline', metric]
        s, ss = values[scenario, app, 'smartconnect', metric]
        return f'{b:.{digits}f} ± {bs:.{digits}f} → {s:.{digits}f} ± {ss:.{digits}f}'
    def behavior(scenario, suffix):
        first, returns, gaps, finals = [], [], [], []
        for seed in range(10):
            path = out / 'raw_csv' / f'{scenario}_seed{seed}_{suffix}.csv'
            with path.open(newline='') as stream:
                samples = list(csv.DictReader(stream))
            switches = [(int(r['time']), r['selected_network']) for r in samples
                        if r['handover'] == 'True']
            first.extend([t for t, net in switches if net == '5G'][:1])
            returns.extend([t for t, net in switches if net == 'WiFi'][-1:])
            gaps.extend(b[0]-a[0] for a,b in zip(switches, switches[1:]))
            finals.append(samples[-1]['selected_network'])
        def describe(v):
            return f'{statistics.mean(v):.2f} ± {statistics.stdev(v):.2f}' if len(v) > 1 else 'not observed'
        return {'first': describe(first), 'return': describe(returns),
                'first_n': len(first), 'return_n': len(returns),
                'min_gap': min(gaps) if gaps else None,
                'fast': sum(g < 8 for g in gaps), 'end_wifi': finals.count('WiFi')}
    congestion = (
        'Congested Wi-Fi + Video Call: selected latency (ms), '
        + pair('congested_wifi','video_call','latency_ms')
        + '; packet loss (%), ' + pair('congested_wifi','video_call','loss_pct',3)
        + '; jitter (ms), ' + pair('congested_wifi','video_call','jitter_ms')
        + '; any prototype guardrail violation (% steps), '
        + pair('congested_wifi','video_call','qoe_any_pct') + '.'
    )
    large = (
        'Large Download + File Download: available path capacity (Mbps), '
        + pair('large_download','file_download','throughput_mbps')
        + '; latency (ms), ' + pair('large_download','file_download','latency_ms')
        + '; handovers per run, ' + pair('large_download','file_download','handovers')
        + '. The higher-capacity path carries a latency tradeoff in this scenario.'
    )
    leaving_bits=[]
    recovery_bits=[]
    for app in APPS:
        base = behavior('leaving_wifi','baseline')
        smart = behavior('leaving_wifi',f'smartconnect_{app}')
        leaving_bits.append(f'{NAMES[app]}: handovers per run {pair("leaving_wifi",app,"handovers")}; '
            f'first switch to 5G-like at step {base["first"]} for baseline and {smart["first"]} for SmartConnect '
            f'(observed in {base["first_n"]}/10 and {smart["first_n"]}/10 runs).')
        base = behavior('recovery','baseline')
        smart = behavior('recovery',f'smartconnect_{app}')
        recovery_bits.append(f'{NAMES[app]}: handovers per run {pair("recovery",app,"handovers")}; '
            f'final return to Wi-Fi at step {base["return"]} for baseline and {smart["return"]} for SmartConnect '
            f'(observed in {base["return_n"]}/10 and {smart["return_n"]}/10 runs). '
            f'SmartConnect ends on Wi-Fi in {smart["end_wifi"]}/10 runs. '
            f'Consecutive switch intervals below 8 steps: baseline {base["fast"]}, SmartConnect {smart["fast"]} '
            f'over all ten runs. This operational measure does not classify every baseline switch as unnecessary.')
    headings = [('Congested Wi-Fi + Video Call',congestion),
                ('Large Download + File Download',large),
                ('Leaving Wi-Fi',' '.join(leaving_bits)),
                ('Recovery',' '.join(recovery_bits))]
    short = '\n\n'.join(title+'\n'+paragraph for title,paragraph in headings)
    text = ('Final Testing & Data Analysis\n'+LABEL+'\n\n'
            'Finalized main: ac860776ba1d168cfa2e1dea8a496c9fa086d7d9. Nine original tests passed.\n'
            '120 fresh executions, 4 scenarios, seeds 0–9, 100 steps per run.\n'
            'All values below are mean ± sample SD across 10 seeds. Arrows show baseline to SmartConnect.\n\n'
            + short + '\n\n'
            'QoE evaluation uses each application’s prototype guardrails equally for both methods.\n'
            'Time is abstract simulation steps; throughput is assumed available capacity, not achieved goodput.\n'
            'These results do not include handover outage/cost and do not establish physical 5G performance.\n')
    (out/'findings.txt').write_text(text)
    handover_rows=''
    for scenario in SCENARIOS:
        for app in APPS:
            b,bs=values[scenario,app,'baseline','handovers']
            s,ss=values[scenario,app,'smartconnect','handovers']
            handover_rows += f'<tr><td>{NAMES[scenario]}</td><td>{NAMES[app]}</td><td>{b:.2f} ± {bs:.2f}</td><td>{s:.2f} ± {ss:.2f}</td></tr>'
    sections=''.join(f'<section><h2>{escape(title)}</h2><p>{escape(paragraph)}</p></section>' for title,paragraph in headings)
    doc='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SmartConnect final findings</title><style>
body{font-family:Arial,sans-serif;color:#193442;background:#f3f6f8;margin:0;line-height:1.65}
main{max-width:1120px;margin:35px auto;background:white;padding:42px;border-radius:12px}
h1{font-size:32px;line-height:1.2}h2{font-size:23px;margin-top:32px}p{font-size:16px}
.caption{color:#536775}table{border-collapse:collapse;width:100%;font-size:15px}
th,td{text-align:left;padding:12px;border-bottom:1px solid #d9e2e8}th{background:#edf3f6}
img{width:100%;height:auto}a{color:#006a80}footer{border-top:1px solid #d9e2e8;padding-top:16px;margin-top:32px}
@media print{body{background:white}main{margin:0;padding:10px}section{break-inside:avoid}}
</style><main><h1>SmartConnect final Testing &amp; Data Analysis</h1>'''
    doc += f'<p class="caption">{LABEL}</p><p>Finalized main <code>ac860776</code>. '
    doc += 'Nine original tests passed. Four scenarios × ten seeds × three configurations = 120 fresh executions. '
    doc += 'Each execution has 100 abstract simulation steps. All reported summaries use mean ± sample SD across ten seeds.</p>'
    doc += '<p><a href="summary_tables.html">All direct comparison tables</a> · <a href="tables/mean_sd.csv">Full-precision mean and SD CSV</a> · <a href="README.txt">Definitions and reproduction instructions</a></p>'
    doc += sections
    doc += '<h2>Handover comparisons</h2><p>Initial attachment is excluded. Baseline executes once per scenario/seed and is reused for the two application comparisons.</p>'
    doc += '<table><thead><tr><th>Scenario</th><th>Application</th><th>RSSI-only Baseline</th><th>SmartConnect</th></tr></thead><tbody>'+handover_rows+'</tbody></table>'
    doc += '<h2>Congested Wi-Fi + Video Call</h2><img src="figures/dashboard_congested_wifi_video_call.png" alt="Repeated-seed comparison of six metrics for congested Wi-Fi and video call">'
    doc += '<h2>Large Download + File Download</h2><img src="figures/dashboard_large_download_file_download.png" alt="Repeated-seed comparison of six metrics for large download and file download">'
    doc += '<footer><p>Guardrails are prototype assumptions: video call latency &gt;60 ms, loss &gt;2%, jitter &gt;20 ms; file download loss &gt;3% or capacity &lt;20 Mbps. A step violating any applicable threshold counts once.</p><p>Simulation time has no seconds conversion. Throughput is assumed available path capacity. Handover delay, outages and costs are not modeled. Independent noise varies fixed scenario curves; these runs do not establish real-world generalization or physical 5G performance.</p></footer></main></html>'
    (out/'findings.html').write_text(doc)
    print(text)

if __name__=='__main__':
    main()
