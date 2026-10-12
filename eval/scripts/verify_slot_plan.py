#!/usr/bin/env python3
"""Validate conditional ADR021 allocation. Never qualifies or admits a task."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
FAMILIES=('Rust','TSJS','Python','Go')
STRATA={'correction':2,'contract_change':2,'state_config':2,'review':1,'control':1}

def require(condition,message):
    if not condition: raise ValueError(message)

def bind(root,receipt):
    path=root/receipt['path']
    require(path.resolve().is_relative_to(root.resolve()),'artifact escapes repository')
    data=path.read_bytes()
    require(hashlib.sha256(data).hexdigest()==receipt['sha256'],'pilot artifact hash')
    return data

def factual_matrix(plan, root):
    """A bound current matrix may update progress, never targets or admission."""
    spec=importlib.util.spec_from_file_location('slot_c02',Path(__file__).with_name('verify_c02.py'))
    verifier=importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    summarize=verifier.summarize; validate_state=verifier.validate_state
    matrix=json.loads(bind(root,plan['factual_progress']))
    require(matrix['schema']=='xrai.eval.c02.factual-matrix.v1' and matrix['data_only'] is True,'C02 factual matrix schema')
    for source in matrix['sources']: bind(root,source)
    for row in matrix['tasks']:
        eligible=validate_state(row['states'],row['kind'],root=root)
        require(row['individually_eligible'] is eligible,'C02 matrix eligibility mismatch')
    summary=summarize(matrix['tasks'])
    require(summary==matrix['summary'],'C02 factual matrix summary mismatch')
    require(root==ROOT and matrix==verifier.reconcile(),
            'C02 factual matrix differs from recomputed dossier evidence')
    return matrix

def validate(plan,*,root=ROOT):
    require(plan['schema']=='xrai.eval.qualification.slot-plan.v1' and plan['status']=='conditional_planning_only','planning schema/status')
    require(plan['admitted_tasks']==0 and type(plan['admitted_tasks']) is int and plan['competitive_runs_allowed'] is False and plan['gate_status']=='closed','false admission')
    raw=bind(root,plan['pilot_artifact']); pilots=[json.loads(line) for line in raw.decode().splitlines()]
    selection=json.loads(bind(root,plan['selection_artifact']))
    actual={r['id']:r for r in pilots}
    require(len(actual)==4 and {r['id'] for r in selection['cases']}==set(actual),'four pilot identity bindings')
    slots=plan['slots']; require(len(slots)==32,'exactly32 allocation')
    require(len({s['slot_id'] for s in slots})==32,'duplicate slot')
    require(all(s['family'] in FAMILIES and s['kind'] in STRATA for s in slots),'unknown family/type')
    require(max(Counter(s['repository_target'] for s in slots).values())<=4,'max four primary slots per repo')
    repos={r['repository']:r for r in plan['repositories']}
    require(len(repos)==len(plan['repositories']) and set(repos)=={s['repository_target'] for s in slots},'repository registry')
    for repo in repos.values():
        require(repo['family'] in FAMILIES and repo['conditions'] and repo['size_floor_status']=='pending_conservative_production_measurement_for_complex_slots' and repo['setup_status']=='pending_each_new_case','conditional size/setup proof')
        require(repo['triage_commit'] is None or re.fullmatch('[0-9a-f]{40}',repo['triage_commit']),'full triage commit or pending')
        require(repo['triage_commit'] is not None or repo['triage_status']=='pending_not_measured','unknown repo measurement promoted')
    retained=[]
    for s in slots:
        require(s['repository_target'] in repos and repos[s['repository_target']]['family']==s['family'],'repo/family binding')
        require(s['status'] in ('conditional_slot','existing_pilot_candidate') and s['unresolved'],'slot claims completed task')
        expected_language={'Rust':['Rust'],'Python':['Python'],'Go':['Go'],'TSJS':['TypeScript','JavaScript']}[s['family']]
        require(s['language_target'] in expected_language,'family/language')
        require(set(s['target'])=={'complex','public_historical','multi_module','incremental_same_process'} and all(type(v) is bool for v in s['target'].values()),'target types')
        if s['kind']=='control': require(not any(s['target'].values()),'control inflates quota')
        if s['target']['incremental_same_process']: require(s['kind']=='state_config','incremental type')
        if s['target']['complex']: require(s['target']['multi_module'],'complex needs module target')
        if s['status']=='existing_pilot_candidate':
            require(s['existing_candidate_id'] in actual,'unknown pilot')
            a=actual[s['existing_candidate_id']]; retained.append(a['id'])
            require((s['family'],s['kind'],s['language_target'],s['repository_target'])==(a['family'],a['kind'],a['language'],a['repository']),'pilot relabeled')
            expected={'complex':a['complexity']['complex'],'historical':a['origin']['class']=='public_change','multi_module_declared':len(a['production_modules'])>=2,'individually_reviewed':a['review_receipt']['status']=='accepted','globally_admitted':False}
            require(s['existing_evidence']==expected,'pilot evidence promoted')
            require(s['target']['complex']==a['complexity']['complex'] and s['target']['public_historical'] is True and s['target']['multi_module'] is True,'pilot target relabeling')
        else:
            require(s['existing_candidate_id'] is None and s['existing_evidence'] is None,'new slot claims pilot evidence')
    require(len(retained)==4 and set(retained)==set(actual),'existing pilots not preserved exactly once')
    families={}
    for family in FAMILIES:
        rows=[s for s in slots if s['family']==family]
        require(len(rows)==8 and Counter(s['kind'] for s in rows)==STRATA,'family strata')
        require(len({s['repository_target'] for s in rows})>=2,'two projects per family')
        complexes=[s for s in rows if s['target']['complex']]
        distribution=Counter(s['repository_target'] for s in complexes)
        require(len(complexes)>=4 and sum(n>=2 for n in distribution.values())>=2,'four complex targets in two projects')
        historical=sum(s['target']['public_historical'] for s in rows)
        require(historical>=4,'four historical targets per family')
        require(any(s['target']['incremental_same_process'] for s in rows),'incremental event target per family')
        families[family]={'slots':8,'strata':dict(Counter(s['kind'] for s in rows)),'complex_targets':len(complexes),'complex_targets_by_repository':dict(distribution),'historical_targets':historical,'repository_targets':sorted({s['repository_target'] for s in rows})}
    languages=Counter(s['language_target'] for s in slots if s['family']=='TSJS')
    require(languages['JavaScript']>=2 and languages['TypeScript']>=2,'two JS and two TS targets')
    # VS Code is not automatically JavaScript; a JS allocation requires explicit unresolved proof.
    for s in slots:
        if s['language_target']=='JavaScript':
            require(repos[s['repository_target']]['language_evidence_status']=='pending_JS_production_modules_not_TypeScript_or_generated','JS production evidence required')
    multi=sum(s['target']['multi_module'] for s in slots)
    require(multi>=20,'20 noncontrol module targets')
    known_complex=sum(p['complexity']['complex'] for p in pilots)
    known_historical=sum(p['origin']['class']=='public_change' for p in pilots)
    known_multi=sum(len(p['production_modules'])>=2 for p in pilots)
    matrix=factual_matrix(plan,root) if 'factual_progress' in plan else None
    if matrix:
        retained_matrix=[r for r in matrix['tasks'] if r['source']=='preserved_l3_pilot']
        require({r['id'] for r in retained_matrix}==set(actual),'C02 pilot identities not preserved')
        deficits=matrix['summary']['conditional_projection']
        delivered=matrix['summary']['new_dossiers_individually_eligible']
        dossier_status='factual_individual_eligibility_global_gate_closed'
    else:
        deficits={'additional_tasks':28,'additional_complex':max(0,16-known_complex),'additional_historical':max(0,16-known_historical),'additional_multi_module':max(0,20-known_multi),'new_dossiers_remaining':4,'admission_deficit':32}
        delivered=0
        dossier_status='none_delivered_in_this_preparation_increment'
    require(plan['conditional_deficits']==deficits,'conditional deficits mismatch')
    next_work=plan['new_dossiers']; selected=next_work['next_slots']; lookup={s['slot_id']:s for s in slots}
    require(next_work['required']==4 and next_work['completed']==delivered and next_work['status']==dossier_status,'new dossiers falsely delivered')
    require(len(selected)==len(set(selected))==4 and all(i in lookup and lookup[i]['status']=='conditional_slot' for i in selected),'four new dossier targets')
    require({lookup[i]['family'] for i in selected}==set(FAMILIES),'new dossiers family coverage')
    require(any(lookup[i]['language_target']=='JavaScript' for i in selected) and all(lookup[i]['target']['complex'] for i in selected),'new dossiers address JS/complexity gaps')
    return {'schema':'xrai.eval.qualification.slot-plan.verification.v1','allocation_consistent':True,'planning_only':True,'admitted_tasks':0,'competitive_runs_allowed':False,'global_gate':'closed','families':families,'TSJS_language_targets':dict(languages),'multi_module_targets':multi,'conditional_deficits':deficits,'new_dossiers_delivered':delivered,'factual_summary':matrix['summary'] if matrix else None,'limits':['Allocation targets and current factual progress are different units; neither admits the global corpus','C02 factual matrix is hash-bound to current sources; verify_c02 recomputes the underlying evidence','Required real family state cases and complete 32-task quotas remain pending']}

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('plan',type=Path,nargs='?',default=ROOT/'eval/qualification/l5-slot-plan.json')
    args=parser.parse_args(); print(json.dumps(validate(json.loads(args.plan.read_bytes())),indent=2,sort_keys=True))

if __name__=='__main__': main()
