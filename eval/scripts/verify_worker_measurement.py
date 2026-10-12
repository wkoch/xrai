#!/usr/bin/env python3
"""Offline receipt verifier; never promotes the synthetic slice to the M0-06 gate."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import tarfile
import blake3

def load(path):
    return json.loads(path.read_bytes())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def require(condition, reason):
    if not condition: raise ValueError(reason)

def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0

def resources(directory):
    r = load(directory/'resources.json')
    require(r['exit']==0 and not r['timed_out'], 'failed session')
    require(r['output_sha256']==sha(directory/'stdout') and r['stderr_sha256']==sha(directory/'stderr'), 'output hash')
    for key in ('cpu_user_seconds','cpu_system_seconds','observer_self_user_seconds','observer_self_system_seconds','observer_ps_user_seconds','observer_ps_system_seconds'):
        require(number(r[key]), 'CPU value')
    peaks=[]
    previous=0
    for sample in r['samples']:
        require(number(sample['begin_ns']) and number(sample['end_ns']) and previous<=sample['begin_ns']<=sample['end_ns'], 'sample ordering')
        previous=sample['end_ns']
        rows=sample['processes']
        require(len({p['pid'] for p in rows})==len(rows), 'duplicate PID')
        for p in rows:
            require(number(p['rss_bytes']) and p['start_observed'], 'RSS identity')
            by_pid={p['pid']:p for p in rows}
            ancestor=p['pid']; visited=set()
            while ancestor!=r['pid']:
                require(ancestor in by_pid and ancestor not in visited, 'process tree outside experiment')
                visited.add(ancestor); ancestor=by_pid[ancestor]['ppid']
        if sample['error'] is None:
            require(sample['sum_rss_bytes']==sum(p['rss_bytes'] for p in rows), 'simultaneous RSS sum')
            if rows: peaks.append(sample['sum_rss_bytes'])
        else:
            require(sample['sum_rss_bytes'] is None, 'failed sampler became zero')
    require(r['sampled_peak_sum_rss']==(max(peaks) if peaks else None), 'RSS peak')
    return r

def verify(directory):
    p=load(directory/'preregistered.json'); summary=load(directory/'summary.json')
    require(summary['schema']=='xrai.eval.worker.comparison.v1','schema')
    require(summary['preregistration_sha256']==sha(directory/'preregistered.json'),'preregistration hash')
    require(summary['m0_06_complete'] is False and summary['production_mode_recommendation'] is None,'unproved gate')
    require(p['sources_archive_sha256']==sha(directory/'sources.tar.gz'),'source archive hash')
    require(p['modes']==['direct','xrw1','xrw2'] and p['concurrency']==1,'modes/concurrency')
    require(p['dialects']==['rust','javascript','jsx','typescript','tsx','python','go'],'dialects')
    require(p['sessions']>=1 and p['requests_per_class_pattern']>=1,'matrix bounds')
    require(p['classes'] and len(set(p['classes']))==len(p['classes']) and set(p['classes'])<={'small','medium','dense','large-comments','error'},'class identities')
    require(p['patterns']==['repeated','distinct'],'patterns')
    complete=set(p['classes'])=={'small','medium','dense','large-comments','error'} and p['sessions']>=3 and p['requests_per_class_pattern']>=30
    require(summary['complete_synthetic_matrix']==complete,'synthetic completeness')
    require(p['mode_order']==[p['modes'][s%3:]+p['modes'][:s%3] for s in range(p['sessions'])],'mode order')
    descriptors={d['key']:d for d in p['descriptors']}
    expected_keys={f'{dialect}/{kind}/{pattern}/{n}' for dialect in p['dialects'] for kind in p['classes'] for pattern in p['patterns'] for n in range(p['requests_per_class_pattern'])}
    require(set(descriptors)==expected_keys and len(descriptors)==len(p['descriptors']),'matrix coverage')
    with tarfile.open(directory/'sources.tar.gz','r:gz') as archive:
        for key,d in descriptors.items():
            dialect,kind,pattern,n=key.split('/')
            variant='0' if pattern=='repeated' else n
            data=archive.extractfile(f'{dialect}-{kind}-{variant}.txt').read()
            require(len(data)==d['source_bytes'] and hashlib.sha256(data).hexdigest()==d['source_sha256'],'source bytes/hash')
            d['source_blake3']=blake3.blake3(data).hexdigest()
    calibration=load(directory/'calibration/calibration.json'); raw=resources(directory/'calibration')
    payload=load(directory/'calibration/stdout')
    expected_user=payload['self_user']+sum(c['user'] for c in payload['child_usage'])
    expected_system=payload['self_system']+sum(c['system'] for c in payload['child_usage'])
    require(abs(raw['cpu_user_seconds']-expected_user)<=.03 and abs(raw['cpu_system_seconds']-expected_system)<=.03,'CPU inclusivity')
    maximum=max((len(s['processes']) for s in raw['samples']),default=0)
    require(calibration['cpu_inclusive_validated'] and calibration['maximum_simultaneous_processes']==maximum and maximum>=3,'CPU/RSS calibration')
    reference=load(directory/'reference.json')
    expected={s['key']:s for s in reference['samples']}
    require(set(expected)==expected_keys and len(reference['samples'])==len(expected_keys),'reference coverage')
    for key, row in expected.items():
        require(row['source_blake3']==descriptors[key]['source_blake3'] and row['source_bytes']==descriptors[key]['source_bytes'],'reference source provenance')
    require(len(summary['sessions'])==p['sessions']*3,'session coverage')
    groups=[]; classes=[]; combined={}
    for s in summary['sessions']:
        target=directory/f"session-{s['session']}-{s['mode']}"
        r=resources(target); data=load(target/'stdout'); plan=load(target/'input.json')
        require(s['session'] in range(p['sessions']) and s['mode'] in p['modes'],'session identity')
        require(data['mode']==plan['mode']==s['mode'] and data['parent_pid']==r['pid'],'mode/parent identity')
        require(len(data['samples'])==len(plan['requests']),'output/plan count')
        require([row['request'] for row in data['samples']]==list(range(len(data['samples']))),'request identities')
        require([row['key'] for row in data['samples']]==[row['key'] for row in plan['requests']],'plan order')
        rows=[row for row in data['samples'] if not row['warmup']]
        require(len(rows)==len(expected_keys)==s['requests'],'request coverage')
        require({row['key'] for row in rows}==expected_keys and len({row['key'] for row in rows})==len(rows),'request keys')
        require([row['key'] for row in rows]==[d['key'] for d in p['descriptors']],'request order')
        for row in rows:
            ref=expected[row['key']]
            for key in ('response_blake3','source_blake3','source_bytes','producer','configuration','dialect'):
                require(row[key]==ref[key],f'reference mismatch {key}')
            require(row['attempts']==1 and number(row['end_to_end_ns']),'unexpected retry/latency')
            dialect,kind,_,_=row['key'].split('/')
            combined.setdefault((s['mode'],dialect,kind),[]).append(row['end_to_end_ns']/1e6)
        observed={process['pid'] for sample in r['samples'] for process in sample['processes']}
        missed=sorted({row['pid'] for row in data['samples']}-observed)
        require(missed==s['worker_pids_missed_by_sampler'],'sampling gap')
        for key in ('cpu_user_seconds','cpu_system_seconds','sampled_peak_sum_rss'):
            require(s[key]==r[key],'resource summary')
        if s['mode']=='xrw2':
            require(data['retention']['held_ticket_reserved_bytes']>0 and data['retention']['after_transfer_reserved_bytes']==0 and data['retention']['full_direct_equal'],'retention accounting')
            require(all(row['incarnation'] for row in rows),'incarnation')
        times=sorted(row['end_to_end_ns']/1e6 for row in rows)
        groups.append({'mode':s['mode'],'session':s['session'],'requests':len(rows),'p50_ms':statistics.median(times),'p95_ms':times[max(0,(95*len(times)+99)//100-1)],'measured_requests_per_second':len(times)/(sum(times)/1000),'cpu_user_seconds':r['cpu_user_seconds'],'cpu_system_seconds':r['cpu_system_seconds'],'sampled_peak_sum_rss':r['sampled_peak_sum_rss'],'missed_worker_pids':len(missed)})
        for dialect in p['dialects']:
            for kind in p['classes']:
                for pattern in p['patterns']:
                    selected=[row for row in rows if row['key'].startswith(f'{dialect}/{kind}/{pattern}/')]
                    values=sorted(row['end_to_end_ns']/1e6 for row in selected)
                    classes.append({'mode':s['mode'],'session':s['session'],'dialect':dialect,'class':kind,'pattern':pattern,'requests':len(values),'p50_ms':statistics.median(values),'p95_ms':values[max(0,(95*len(values)+99)//100-1)]})
    require({(s['session'],s['mode']) for s in summary['sessions']}=={(n,m) for n in range(p['sessions']) for m in p['modes']},'duplicate session')
    comparisons=[]
    for dialect in p['dialects']:
        for kind in p['classes']:
            medians={mode:statistics.median(combined[mode,dialect,kind]) for mode in p['modes']}
            comparisons.append({'dialect':dialect,'class':kind,'requests_per_mode':len(combined['direct',dialect,kind]),'p50_ms':medians,'xrw2_over_direct_p50':medians['xrw2']/medians['direct'] if medians['direct'] else None,'direct_faster_than_xrw2':medians['direct']<medians['xrw2']})
    return {'schema':'xrai.eval.worker.verification.v1','sessions':groups,'class_statistics':classes,'cross_session_class_comparison':comparisons,'full_response_equivalent':True,'m0_06_complete':False,'limitations':p['limitations']}

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('directory',type=Path)
    args=parser.parse_args(); print(json.dumps(verify(args.directory),sort_keys=True,indent=2))

if __name__=='__main__': main()
