#!/usr/bin/env python3
"""Evaluator-only Gitea materialization and contained Linux behavioral probes."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys

from prepare_l5_go import CASE, ROOT, COMMIT, sha, source_tree, verify

HIDDEN='services/convert/xrai_url_contract_test.go'
EXPECTED={'requirement':['TestXraiContractHelper','TestXraiContractModel','TestXraiContractAPI'], 'regression':['TestXraiRegressionOrdinaryURL','TestXraiRegressionUserinfoAndInvalidURL']}

def materialize(workspace,side):
    if side not in ['base','reference']:raise ValueError('unknown evaluator side')
    verify()
    if workspace.exists():raise ValueError('fresh workspace required')
    tree=source_tree(CASE/'sources/base.tar.gz');workspace.mkdir(parents=True)
    for path,(data,mode) in tree.items():
        p=workspace/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);p.chmod(mode)
    if side=='reference':(workspace/'modules/util/url.go').write_bytes((CASE/'oracles/reference-url.go').read_bytes())
    (workspace/HIDDEN).write_bytes((CASE/'oracles/xrai_url_contract_test.go').read_bytes())
    receipt={'side':side,'commit':COMMIT,'archive_sha256':sha((CASE/'sources/base.tar.gz').read_bytes()),'reference_changed_paths':['modules/util/url.go'] if side=='reference' else [],'oracle_sha256':sha((workspace/HIDDEN).read_bytes()),'lock_sha256':{p:sha((workspace/p).read_bytes()) for p in ['go.mod','go.sum']},'agent_workspace':False,'hidden_evaluator_only':True}
    (workspace/'.xrai-materialization.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt

def copy_tree(source,target):
    source=source.resolve()
    if not source.is_dir() or target.exists():raise ValueError('fresh tool/cache copy required')
    rows=[]
    for p in sorted(source.rglob('*')):
        if p.is_symlink() or (not p.is_dir() and not p.is_file()):raise ValueError('tool/cache link or nonregular entry denied')
        if p.is_file():rows.append({'path':str(p.relative_to(source)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
    shutil.copytree(source,target,symlinks=False,copy_function=shutil.copy2)
    if any((target/r['path']).stat().st_ino == (source/r['path']).stat().st_ino and (target/r['path']).stat().st_dev == (source/r['path']).stat().st_dev for r in rows):raise ValueError('host hardlink denied')
    for row in rows:
        if sha((target/row['path']).read_bytes())!=row['sha256']:raise ValueError('tool/cache copy changed')
    return {'file_count':len(rows),'bytes':sum(r['bytes'] for r in rows),'manifest_sha256':sha(json.dumps(rows,sort_keys=True).encode()),'files':rows,'method':'regular byte copies, no symlinks or host hardlinks'}

def classify(events,side,name):
    expected=EXPECTED[name]
    terminal=[e for e in events if e.get('Test') and e.get('Action') in ['pass','fail','skip']]
    if sorted(e['Test'] for e in terminal)!=sorted(expected):return False
    failed=side=='base' and name=='requirement'
    if any(e['Action']!=('fail' if failed else 'pass') for e in terminal):return False
    for test in expected:
        out=''.join(e.get('Output','') for e in events if e.get('Test')==test)
        if failed and 'XRAI_CONTRACT_SECRET_QUERY' not in out:return False
        if 'XRAI_CONTRACT_INFRASTRUCTURE' in out:return False
    return True

def validate_workspace(workspace,side):
    if side not in ['base','reference']:raise ValueError('unknown evaluator side')
    tree=source_tree(CASE/'sources/base.tar.gz')
    for name,(data,mode) in tree.items():
        expected=(CASE/'oracles/reference-url.go').read_bytes() if side=='reference' and name=='modules/util/url.go' else data
        path=workspace/name
        if path.is_symlink() or not path.is_file() or path.read_bytes()!=expected:raise ValueError('workspace source mismatch '+name)
    expected_sources={name for name in tree if name.endswith('.go')}|{HIDDEN}
    actual_sources={str(p.relative_to(workspace)) for p in workspace.rglob('*.go') if p.is_file()}
    if actual_sources!=expected_sources:raise ValueError('workspace extra or missing Go source')
    if any(p.is_symlink() for p in workspace.rglob('*')):raise ValueError('workspace symlink denied')
    return {'full_pinned_source_files_verified':len(tree),'additional_go_sources':[HIDDEN],'reference_changed_paths':['modules/util/url.go'] if side=='reference' else []}

def probe(workspace,side,goroot,module_cache,output,timeout):
    if not 0 < timeout <= 900:raise ValueError('timeout must be positive and at most 900 seconds')
    if platform.system()!='Linux':raise ValueError('upstream probes require disposable Linux namespace; local macOS denied')
    import os
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('disposable CI required')
    verify();workspace=workspace.resolve();output.mkdir(parents=True,exist_ok=False)
    source_validation=validate_workspace(workspace,side)
    materialization=json.loads((workspace/'.xrai-materialization.json').read_text())
    if materialization['side']!=side or materialization['commit']!=COMMIT:raise ValueError('workspace side mismatch')
    for p in ['go.mod','go.sum']:
        if (workspace/p).read_bytes()!=(CASE/'setup'/p).read_bytes():raise ValueError('prepared lock changed '+p)
    if (workspace/HIDDEN).read_bytes()!=(CASE/'oracles/xrai_url_contract_test.go').read_bytes():raise ValueError('hidden oracle changed')
    tool=copy_tree(goroot,workspace/'.xrai-go');cache=copy_tree(module_cache,workspace/'.xrai-mod')
    if (workspace/'.xrai-go/VERSION').read_text().splitlines()[0]!='go1.22.12':raise ValueError('toolchain version not pinned go1.22.12')
    for name,value in [('toolchain',tool),('module-cache',cache)]:
        (output/(name+'-manifest.json')).write_text(json.dumps(value,indent=2)+'\n')
    sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
    from runner import execute
    from supervisor import verify_receipt, confirmed_receipt
    cc=Path(shutil.which('gcc') or '/nonexistent').resolve()
    cxx=Path(shutil.which('g++') or '/nonexistent').resolve()
    if not all(p.is_file() and p.is_relative_to('/usr') for p in [cc,cxx]):raise ValueError('native compilers must resolve to visible /usr regular files')
    phases=[];domains=set();lock_before={p:sha((workspace/p).read_bytes()) for p in ['go.mod','go.sum']}
    for name,prefix in [('requirement','^TestXraiContract'),('regression','^TestXraiRegression')]:
        command=['/usr/bin/env','HOME=/workspace','TMPDIR=/tmp','PATH=/workspace/.xrai-go/bin:/usr/bin:/bin','CC='+str(cc),'CXX='+str(cxx),'GOROOT=/workspace/.xrai-go','GOMODCACHE=/workspace/.xrai-mod','GOCACHE=/workspace/.xrai-build','GOPROXY=off','GOSUMDB=off','GOTOOLCHAIN=local','GOFLAGS=-mod=readonly','CGO_ENABLED=1','/workspace/.xrai-go/bin/go','test','-json','-count=1','-timeout=600s','-tags=sqlite,sqlite_unlock_notify','-run='+prefix,'./services/convert']
        run=execute(command,workspace,timeout=timeout,output_limit=1024*1024,phase='qualification-'+name,arbitrary_agent=True)
        (output/(name+'-harness.json')).write_text(json.dumps(run,indent=2)+'\n');verify_receipt(run)
        raw=base64.b64decode(run['stdout']['base64'])
        (output/(name+'-go-test.jsonl')).write_bytes(raw)
        events=[]
        try:events=[json.loads(line) for line in raw.splitlines() if line.strip()]
        except (ValueError,UnicodeError):pass
        behavior=classify(events,side,name)
        expected_exit=1 if side=='base' and name=='requirement' else 0
        behavior = behavior and not any(run[c]['truncated'] for c in ['stdout','stderr']) and run['execution_status'] in ['ok','error']
        teardown=confirmed_receipt(run) and run['eligible_for_agent_run'] and run['domain_id'] not in domains
        domains.add(run['domain_id'])
        phases.append({'name':name,'expected_tests':EXPECTED[name],'expected_exit':expected_exit,'actual_exit':run['exit_code'],'behavioral_result_verified':behavior,'teardown_verified':teardown,'execution_status':run['execution_status'],'harness':name+'-harness.json','jsonl':name+'-go-test.jsonl','jsonl_sha256':sha(raw),'verified':bool(teardown and behavior and run['exit_code']==expected_exit)})
    locks={p:sha((workspace/p).read_bytes()) for p in ['go.mod','go.sum']}
    receipt={'schema_version':'xrai.eval.l5.go.probe.v1','side':side,'materialization':materialization,'source_validation':source_validation,'platform':platform.platform(),'go_version':'go1.22.12','native_compilers':{str(p):sha(p.read_bytes()) for p in [cc,cxx]},'go_executable_sha256':sha((workspace/'.xrai-go/bin/go').read_bytes()),'toolchain_manifest_sha256':sha((output/'toolchain-manifest.json').read_bytes()),'module_cache_manifest_sha256':sha((output/'module-cache-manifest.json').read_bytes()),'executor_source_sha256':sha(Path(__file__).read_bytes()),'oracle_sha256':sha((CASE/'oracles/xrai_url_contract_test.go').read_bytes()),'lock_before':lock_before,'lock_after':locks,'phases':phases,'verified':all(p['verified'] for p in phases) and locks==lock_before,'admitted':False,'competitive_runs_allowed':False}
    (output/'probe.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    m=s.add_parser('materialize');m.add_argument('--workspace',type=Path,required=True);m.add_argument('--side',choices=['base','reference'],required=True)
    r=s.add_parser('probe');r.add_argument('--workspace',type=Path,required=True);r.add_argument('--side',choices=['base','reference'],required=True);r.add_argument('--goroot',type=Path,required=True);r.add_argument('--module-cache',type=Path,required=True);r.add_argument('--output',type=Path,required=True);r.add_argument('--timeout',type=float,default=900)
    a=p.parse_args();result=materialize(a.workspace,a.side) if a.action=='materialize' else probe(a.workspace,a.side,a.goroot,a.module_cache,a.output,a.timeout);print(json.dumps(result,indent=2));return 0 if a.action=='materialize' or result['verified'] else 1
if __name__=='__main__':raise SystemExit(main())
