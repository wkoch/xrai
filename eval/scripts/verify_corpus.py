#!/usr/bin/env python3
"""Verify corpus provenance, strata, source spans, oracle isolation, fixtures and reconstruction."""
from collections import Counter
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile

from generate_fixtures import generate
from materialize_task import ROOT, materialize, safe_path, tasks


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(rows, sources):
    ids = [r['id'] for r in rows]
    require(len(ids) == len(set(ids)), 'duplicate task id')
    lineage = [r['change_lineage'] for r in rows if r['dataset'] == 'D1']
    require(len(lineage) == len(set(lineage)), 'duplicate D1 change lineage')
    require(Counter(r['dataset'] for r in rows) == {'D0': 20, 'D1': 32}, 'dataset counts')
    for family in ['Rust', 'TSJS', 'Python', 'Go']:
        d0 = [r for r in rows if r['dataset'] == 'D0' and r['family'] == family]
        d1 = [r for r in rows if r['dataset'] == 'D1' and r['family'] == family]
        require(Counter(r['kind'] for r in d0) == {'location': 2, 'comprehension': 1, 'after_edit': 1, 'configuration': 1}, family + ' D0 strata')
        require(Counter(r['kind'] for r in d1) == {'correction': 2, 'contract_change': 2, 'state_config': 2, 'review': 1, 'control': 1}, family + ' D1 strata')
        require(len({r['repository'] for r in d1}) >= 2, family + ' needs two repositories')
    require({'TypeScript','JavaScript'} <= {r['language'] for r in rows if r['dataset']=='D1'}, 'real TS and JS')
    cache = {}
    for key, snap in sources['snapshots'].items():
        archive = ROOT / snap['archive']
        require(hashlib.sha256(archive.read_bytes()).hexdigest() == snap['sha256'], 'archive hash '+key)
        require(len(snap['commit']) == 40, 'full immutable commit '+key)
        with tarfile.open(archive, 'r:gz') as tar:
            files = {}
            for member in tar.getmembers():
                safe_path(member.name)
                require(member.isfile(), 'non-regular archive entry')
                files[member.name] = tar.extractfile(member).read()
        require(len(files)==snap['file_count'], 'source file count')
        require(sum(len(v) for v in files.values())==snap['source_bytes'], 'source size')
        for entry in snap['files']:
            data=files[entry['path']]
            require(len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256'], 'source fingerprint')
        require(snap['license_files'] or snap['supplementary_license'], 'missing license notice')
        for path in snap['license_files']:
            require(path in files, 'snapshot license path')
        if snap['supplementary_license']:
            notice=snap['supplementary_license'];require(hashlib.sha256((ROOT/notice['path']).read_bytes()).hexdigest()==notice['sha256'], 'supplementary license')
        cache[key]=files
    patches=[]
    for task in rows:
        require(task['possible_failure_reasons'] and task['required_capabilities'], 'missing capabilities/failure reasons')
        oracle_path=ROOT/task['agent_success_criteria']['oracle'];oracle=json.loads(oracle_path.read_text(encoding="utf-8"))
        require(oracle['task_id']==task['id'] and oracle['assertions'], 'missing independent oracle')
        require('no xrai/graft/parser output' in oracle['label_method'], 'oracle labeling provenance')
        require(task['recovery_criteria'] != task['agent_success_criteria'], 'recovery and agent outcome conflated')
        files=cache[task['input']['snapshot']]
        for source in task['relevant_sources']:
            data=files[source['path']]
            require(hashlib.sha256(data).hexdigest()==source['sha256'], 'cited source hash')
            require(data[source['byte_start']:source['byte_end']].decode()==source['anchor'], 'source byte span')
            require(data[:source['byte_start']].count(b'\n')+1==source['line'], 'source line')
        patch=oracle['reference_patch']
        if patch:
            raw=(ROOT/patch['path']).read_bytes();require(hashlib.sha256(raw).hexdigest()==patch['sha256'], 'reference patch hash')
            patches.append(patch['sha256'])
        with tempfile.TemporaryDirectory(prefix='xrai-input-') as temp:
            destination=Path(temp)
            materialize(task['id'], destination)
            request=json.loads((destination/'request.json').read_text(encoding="utf-8"))
            require(set(request)<= {'id','family','language','prompt','context_policy','proposed_diff'}, 'unexpected input metadata')
            require(not any('oracle' in str(p.relative_to(destination)).lower() or '.git' in p.parts for p in destination.rglob('*')), 'oracle/git leaked to input')
            for path in task['recovery_criteria']['required_sources']:
                require((destination/'workspace'/path).is_file(), 'missing head source '+task['id']+' '+path)
            for path in task['recovery_criteria']['expected_absent']:
                require(not (destination/'workspace'/path).exists(), 'removed source survives')
            for path, expected in task['recovery_criteria']['changed_source_hashes'].items():
                require(hashlib.sha256((destination/'workspace'/path).read_bytes()).hexdigest()==expected, 'head source hash')
    require(len(patches)==len(set(patches)), 'duplicate reference patches counted independently')
    return {'tasks':len(rows),'datasets':dict(Counter(r['dataset'] for r in rows)),'families':dict(Counter(r['family'] for r in rows)),'repositories':len(sources['repositories']),'snapshots':len(cache),'source_bytes':sum(s['source_bytes'] for s in sources['snapshots'].values()),'archive_bytes':sum(s['archive_bytes'] for s in sources['snapshots'].values()),'reference_patches':len(patches),'materialized_inputs_checked':len(rows),'oracle_leaks':0,'origin_classes':dict(Counter(r['origin_class'] for r in rows if r['dataset']=='D1'))}


def verify():
    rows=tasks();sources=json.loads((ROOT/'sources/manifest.json').read_text(encoding="utf-8"))
    summary=validate(rows,sources)
    invalid=copy.deepcopy(rows)
    d1=[r for r in invalid if r['dataset']=='D1'];d1[1]['change_lineage']=d1[0]['change_lineage']
    try:
        validate(invalid,sources)
    except ValueError as error:
        require(str(error)=='duplicate D1 change lineage', 'wrong duplicate failure')
    else:
        raise ValueError('duplicate lineage accepted')
    with tempfile.TemporaryDirectory(prefix='xrai-fixtures-') as temp:
        first=generate(Path(temp)/'a');second=generate(Path(temp)/'b')
        require(first==second, 'fixture generator nondeterministic')
        require(first==json.loads((ROOT/'fixtures/manifest.json').read_text(encoding="utf-8")), 'committed fixtures differ from generator')
        for file in first['files']:
            data=(ROOT/'fixtures'/file['path']).read_bytes()
            require(hashlib.sha256(data).hexdigest()==file['sha256'], 'fixture hash')
        a=Path(temp)/'a/mtime/base.py';b=Path(temp)/'a/mtime/head.py'
        require(a.stat().st_mtime_ns==b.stat().st_mtime_ns and a.stat().st_size==b.stat().st_size and a.read_bytes()!=b.read_bytes(), 'preserved timestamp fixture')
        require(b'\r\n' in (ROOT/'fixtures/crlf.rs').read_bytes(), 'CRLF fixture normalized')
    summary.update({'dataset_classes':{'D0':'development','D1':'seed'},'competitive_admission':False,'fixture_files':len(first['files']),'fixture_generator_deterministic':True,'duplicate_lineage_rejected':True,'agent_success_measured':False,'statistical_superiority_claimed':False})
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--qualified', action='store_true', help='ADR021 gate; never fall back to development seed')
    args=parser.parse_args()
    try:
        if args.qualified:
            from verify_qualified import validate as validate_qualified
            summary = validate_qualified(tasks('qualified'))
        else:
            summary = verify()
        result={'status':'passed','summary':summary}
    except (ValueError,KeyError,OSError) as error:
        result={'status':'failed','error':str(error)}
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text, encoding="utf-8", newline="\n")
    print(text,end='');sys.exit(result['status']!='passed')
