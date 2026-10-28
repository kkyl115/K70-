#!/usr/bin/env python3
"""Summarize real paired A/B runs; no embedded or invented benchmark data.
CSV columns: pair,variant,workload,latency_p95_ms,latency_p99_ms,jank_percent,
energy_j,thermal_max_c,battery_start_percent,duration_s. variant: baseline/candidate.
"""
import argparse,csv,json,math,statistics
from pathlib import Path

def analyze(path):
    groups={}
    metrics=['latency_p95_ms','latency_p99_ms','jank_percent','energy_j','thermal_max_c','battery_start_percent','duration_s']
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            key=(row['workload'],row['pair']); variant=row['variant']
            if variant not in ('baseline','candidate'): raise ValueError('unknown variant')
            if variant in groups.setdefault(key,{}): raise ValueError('duplicate paired run')
            values={k:float(row[k]) for k in metrics}
            if any(not math.isfinite(v) or v<0 for v in values.values()): raise ValueError('invalid numeric metric')
            if values['latency_p99_ms']<values['latency_p95_ms']: raise ValueError('p99 < p95')
            if values['duration_s']<=0 or values['jank_percent']>100 or values['battery_start_percent']>100:
                raise ValueError('metric outside valid range')
            groups[key][variant]=values
    if not groups: raise ValueError('no paired measurements')
    deltas={}
    for (workload,pair),runs in groups.items():
        if set(runs)!= {'baseline','candidate'}: raise ValueError('incomplete pair: '+pair)
        a,b=runs['baseline'],runs['candidate']
        if abs(a['duration_s']-b['duration_s'])>1 or abs(a['battery_start_percent']-b['battery_start_percent'])>5:
            raise ValueError('uncontrolled duration/battery in pair '+pair)
        for k in metrics[:5]: deltas.setdefault(workload,{}).setdefault(k,[]).append(b[k]-a[k])
    return {'scope':'descriptive paired differences; does not establish causation or stability',
            'workloads':{w:{k:{'pairs':len(v),'median_candidate_minus_baseline':statistics.median(v),
              'min_delta':min(v),'max_delta':max(v),'needs_more_runs':len(v)<5} for k,v in values.items()} for w,values in deltas.items()}}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('csv'); a=p.parse_args()
    try: print(json.dumps(analyze(a.csv),indent=2))
    except (OSError,ValueError,KeyError) as e: p.exit(2,str(e)+'\n')
