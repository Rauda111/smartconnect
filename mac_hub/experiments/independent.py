"""Standard-library numerical audit, independent of engine/metric implementations.

The event specification below is the published experimental design. Recompute
from observed decisions, not from saved summaries or production metric helpers.
"""
from collections import defaultdict
import csv
import math
import statistics

METHODS = ('wifi_first', 'smartconnect')
APPS = ('video_call', 'file_download')
PATHS = ('wifi', 'cellular')
METRICS = ('latency', 'loss', 'rtt_variation')
SUMMARY = ('latency_mean','loss_mean','rtt_variation_mean','recommended_handovers',
           'observed_guardrail_violation_windows','no_path_windows','quiet_region_changes','reversals_within_30s')
EVENTS = {
    'stable': [],
    'deteriorating_wifi': [(100,'cellular','wifi_degradation_onset')],
    'congested_wifi': [(100,'cellular','wifi_degradation_onset')],
    'cellular_degradation': [(100,'wifi','cellular_degradation_onset')],
    'wifi_recovery': [(100,'cellular','wifi_degradation_onset'),(275,'wifi','wifi_recovery_onset')],
    'network_unavailability': [(100,'cellular','wifi_no_reply'),(175,'none','both_unavailable'),(250,'wifi','wifi_returns')],
}


def rows(folder, name):
    with (folder/(name+'.csv')).open(newline='') as stream:
        return list(csv.DictReader(stream))


def number(value):
    if value is None or value == '' or str(value).lower() == 'nan':
        return None
    result=float(value)
    if not math.isfinite(result):
        raise ValueError('Nonfinite numeric evidence')
    return result


def same(actual, expected):
    if expected is None:
        return number(actual) is None
    if isinstance(expected,bool):
        return actual == str(expected)
    if isinstance(expected,(int,float)):
        value=number(actual)
        return value is not None and math.isclose(value,expected,rel_tol=1e-8,abs_tol=1e-7)
    return actual == expected


def compare(actual, expected, keys, label):
    def index(records):
        result={}
        for row in records:
            key=tuple(str(row[k]) for k in keys)
            if key in result:
                raise ValueError(f'{label}: duplicate key {key}')
            result[key]=row
        return result
    a,e=index(actual),index(expected)
    if a.keys() != e.keys():
        raise ValueError(f'{label}: missing or extra records')
    for key,row in e.items():
        for field,value in row.items():
            if field not in a[key] or not same(a[key][field],value):
                raise ValueError(f'{label}: mismatch {key} / {field}: {a[key].get(field)} != {value}')


def moments(values):
    values=[v for v in values if v is not None]
    return dict(n=len(values), mean=statistics.mean(values) if values else None,
                sample_sd=statistics.stdev(values) if len(values)>1 else None)


def check(folder):
    observations=rows(folder,'observations')
    decisions=rows(folder,'decisions')
    raw={}
    for row in observations:
        key=tuple(row[k] for k in ('scenario','source','seed','elapsed_seconds'))
        if key in raw:
            raise ValueError('Duplicate paired observation')
        raw[key]=row
        for n in PATHS:
            for metric in ('rssi','throughput','jitter'):
                if number(row.get(f'{n}_{metric}')) is not None:
                    raise ValueError('Unexpected unavailable metric populated')
    groups=defaultdict(list)
    for row in decisions:
        key=tuple(row[k] for k in ('scenario','source','seed','elapsed_seconds'))
        if key not in raw:
            raise ValueError('Decision without paired observation')
        for field,value in raw[key].items():
            if row.get(field) != value:
                raise ValueError(f'Policy input changed: {field}')
        if row['application'] not in APPS or row['outcome_type'] != 'counterfactual_selection_proxy':
            raise ValueError('Unknown profile or evidence type')
        baseline=next((n for n in PATHS if row[f'{n}_status']=='reachable'),'none')
        if row['wifi_first'] != baseline:
            raise ValueError('Wi-Fi-first fairness failure')
        groups[tuple(row[k] for k in ('scenario','source','seed','application'))].append(row)
    expected_groups={(*key[:3],app) for key in raw for app in APPS}
    if set(groups) != expected_groups:
        raise ValueError('Missing or extra profile replay')
    runs,events=[],[]
    for keys, trace in groups.items():
        meta=dict(zip(('scenario','source','seed','application'),keys))
        times=[number(row['elapsed_seconds']) for row in trace]
        if any(a>=b for a,b in zip(times,times[1:])):
            raise ValueError('Non-increasing replay time')
        if len(trace) != sum(key[:3] == keys[:3] for key in raw):
            raise ValueError('Replay omitted or duplicated observations')
        for method in METHODS:
            paths=[row[method] for row in trace]
            if any(p not in (*PATHS,'none') for p in paths):
                raise ValueError('Unknown recommendation')
            switches=[i for i in range(1,len(paths)) if paths[i-1] in PATHS and paths[i] in PATHS and paths[i]!=paths[i-1]]
            result=dict(**meta,method=method,windows=len(trace),recommended_handovers=len(switches),
                        no_path_windows=paths.count('none'),
                        outage_entries=sum(paths[i]=='none' and paths[i-1]!='none' for i in range(1,len(paths))),
                        reattachments=sum(paths[i]!='none' and paths[i-1]=='none' for i in range(1,len(paths))))
            for metric in METRICS:
                values=[number(row.get(f'{path}_{metric}')) if path in PATHS else None for row,path in zip(trace,paths)]
                values=[v for v in values if v is not None]
                result[f'{metric}_mean']=statistics.mean(values) if values else None
                result[f'{metric}_observed_windows']=len(values)
            violations,unknown,complete=0,0,0
            limits={'latency':60,'loss':2,'jitter':20} if meta['application']=='video_call' else {'loss':3,'throughput':20}
            for row,path in zip(trace,paths):
                values={k:number(row.get(f'{path}_{k}')) if path in PATHS else None for k in limits}
                violations += any(v is not None and (v < limits[k] if k=='throughput' else v > limits[k]) for k,v in values.items())
                unknown += any(v is None for v in values.values())
                complete += all(v is not None for v in values.values())
            assessed=meta['source']=='synthetic' and all(row.get('stable_region') in ('True','False') for row in trace)
            result.update(observed_guardrail_violation_windows=violations,guardrail_unknown_windows=unknown,
                          fully_assessed_guardrail_windows=complete,quiet_region_assessed=assessed,
                          quiet_region_changes=sum(trace[i]['stable_region']=='True' and trace[i-1]['stable_region']=='True' for i in switches) if assessed else None,
                          reversals_within_30s=sum(paths[a-1]==paths[b] and 'none' not in paths[a:b+1] and times[b]-times[a]<=30 for a,b in zip(switches,switches[1:])))
            runs.append(result)
            specs=EVENTS.get(meta['scenario'],[])
            for j,(onset,target,label) in enumerate(specs):
                end=specs[j+1][0] if j+1<len(specs) else math.inf
                hits=[t for t,p in zip(times,paths) if onset<=t<end and p==target]
                before=[p for t,p in zip(times,paths) if t<onset]
                events.append(dict(**meta,method=method,event=label,onset_seconds=onset,expected_path=target,
                                   already_on_target=bool(before and before[-1]==target),observed_response=bool(hits),
                                   response_seconds=hits[0]-onset if hits else None))
    compare(rows(folder,'per_run'),runs,('scenario','source','seed','application','method'),'per_run')
    compare(rows(folder,'event_responses'),events,('scenario','source','seed','application','method','event'),'event_responses')
    grouped=defaultdict(list)
    by_pair=defaultdict(dict)
    for row in runs:
        grouped[tuple(row[k] for k in ('scenario','source','application','method'))].append(row)
        by_pair[tuple(row[k] for k in ('scenario','source','seed','application'))][row['method']]=row
    aggregates=[]
    for key, group in grouped.items():
        for metric in SUMMARY:
            aggregates.append(dict(zip(('scenario','source','application','method'),key),metric=metric,**moments([row[metric] for row in group])))
    compare(rows(folder,'aggregate'),aggregates,('scenario','source','application','method','metric'),'aggregate')
    differences=[]
    paired_groups=defaultdict(list)
    for key, group in by_pair.items():
        for metric in SUMMARY:
            a,b=group['smartconnect'][metric],group['wifi_first'][metric]
            value=a-b if a is not None and b is not None else None
            differences.append(dict(zip(('scenario','source','seed','application'),key),metric=metric,smartconnect_minus_wifi_first=value))
            paired_groups[(key[0],key[1],key[3],metric)].append(value)
    compare(rows(folder,'paired_differences'),differences,('scenario','source','seed','application','metric'),'paired_differences')
    pairs=[dict(zip(('scenario','source','application','metric'),key),**moments(values)) for key,values in paired_groups.items()]
    compare(rows(folder,'paired_summary'),pairs,('scenario','source','application','metric'),'paired_summary')
    response_groups=defaultdict(list)
    for row in events:
        response_groups[tuple(row[k] for k in ('scenario','source','application','method','event'))].append(row)
    response_summary=[]
    for key, group in response_groups.items():
        stats=moments([r['response_seconds'] for r in group])
        response_summary.append(dict(zip(('scenario','source','application','method','event'),key),
            events=len(group),observed_responses=sum(r['observed_response'] for r in group),
            unobserved_responses=sum(not r['observed_response'] for r in group),
            already_on_target_events=sum(r['already_on_target'] for r in group),
            mean_response_seconds=stats['mean'],sample_sd_seconds=stats['sample_sd']))
    compare(rows(folder,'response_summary'),response_summary,('scenario','source','application','method','event'),'response_summary')
    return len(runs)
