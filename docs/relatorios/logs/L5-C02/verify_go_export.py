#!/usr/bin/env python3
"""Data-only reconciliation of Go export. Never execute/import captured source.
Imports only own supervisor receipt validation; never launches its executor.

The caller separately authenticates run/commit/jobs and the exact ZIP membership
against GitHub. This checks consistency of receipts against frozen local source,
not independent observation of a past workspace or retained toolchain binaries.
"""
import argparse
import base64
import gzip
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import uuid
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
from supervisor import verify_receipt, confirmed_receipt
CASE=ROOT/'eval/qualification/l5-real/go'
COMMIT='8eefa1f6dedf2488db2c9e12c916e8e51f673160'
ARCHIVE_SHA='3cd918c96a563db6a64e8c9717d556097240de799f9f0948ba50060e6143c190'
HIDDEN='services/convert/xrai_url_contract_test.go'
PACKAGE='code.gitea.io/gitea/services/convert'
TESTS={'requirement':['TestXraiContractHelper','TestXraiContractModel','TestXraiContractAPI'],'regression':['TestXraiRegressionOrdinaryURL','TestXraiRegressionUserinfoAndInvalidURL']}

def require(value,message):
    if not value:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def digest(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None

def pairs(rows):
    result={}
    for key,value in rows:
        require(key not in result,'duplicate JSON key '+key);result[key]=value
    return result

def decode(raw):return json.loads(raw,object_pairs_hook=pairs)

class Reader:
    def __init__(self,directory,overrides=None):
        self.directory=Path(directory).resolve();self.overrides=overrides or {};self.hashes={}
    def raw(self,name):
        rel=PurePosixPath(name);require(not rel.is_absolute() and '..' not in rel.parts,'unsafe export path')
        path=self.directory/str(rel)
        require(path.resolve().is_relative_to(self.directory) and not any(p.is_symlink() for p in [path,*path.parents] if p.is_relative_to(self.directory)),'export link or escaping path')
        require(path.is_file() and path.stat().st_size<=128*1024*1024,'missing or oversized export '+name)
        raw=self.overrides.get(name,path.read_bytes());self.hashes[name]=sha(raw);return raw
    def json(self,name):return decode(self.raw(name))

def frozen_source():
    archive=CASE/'sources/base.tar.gz';require(sha(archive.read_bytes())==ARCHIVE_SHA,'frozen archive pin mismatch')
    cap=decode((CASE/'capture.json').read_bytes());require(cap['commit']==COMMIT and cap['archive_sha256']==ARCHIVE_SHA,'capture source pin mismatch')
    invraw=(CASE/'sources/base-inventory.json.gz').read_bytes();require(sha(invraw)==cap['inventory_sha256'],'inventory export hash mismatch')
    inv=decode(gzip.decompress(invraw));rows=inv['files'];actual={};base_url=None
    with tarfile.open(archive) as tree:
        for m in tree:
            p=PurePosixPath(m.name)
            require(not p.is_absolute() and '..' not in p.parts and p.parts[0]=='gitea-'+COMMIT,'unsafe/unpinned frozen source path')
            if m.isdir():continue
            name=str(PurePosixPath(*p.parts[1:]));require(m.isfile() and len(p.parts)>1 and name not in actual,'nonregular/duplicate frozen source')
            data=tree.extractfile(m).read()
            if name=='modules/util/url.go':base_url=data
            actual[name]={'path':name,'bytes':len(data),'sha256':sha(data),'mode':m.mode&0o777}
    require(len(rows)==inv['file_count']==len(actual),'inventory source file count mismatch')
    require(len({r['path'] for r in rows})==len(rows),'duplicate inventory source row')
    for row in rows:
        require(row['path'] in actual and all(actual[row['path']][k]==row[k] for k in ['path','bytes','sha256','mode']),'full inventory source row mismatch')
    require(sum(r['bytes'] for r in rows)==inv['source_bytes'],'inventory source bytes mismatch')
    require(sum(r['production_nonempty_lines']>0 for r in rows)==inv['production_files'] and sum(r['production_nonempty_lines'] for r in rows)==inv['production_nonempty_lines'],'inventory production total mismatch')
    require(inv['production_files']>=500 or inv['production_nonempty_lines']>=50000,'production floor not met')
    locks={p:sha((CASE/'setup'/p).read_bytes()) for p in ['go.mod','go.sum']}
    require(locks==cap['setup'] and all(actual[p]['sha256']==locks[p] for p in locks),'frozen source locks mismatch')
    case=decode((CASE/'case.json').read_bytes())
    require(case['base']==COMMIT and case['origin']=='controlled_contract_change' and case['historical_change_claimed'] is False,'case origin/source mismatch')
    reference=(CASE/'oracles/reference-url.go').read_bytes()
    expected_patch=''.join(difflib.unified_diff(base_url.decode().splitlines(keepends=True),reference.decode().splitlines(keepends=True),fromfile='a/modules/util/url.go',tofile='b/modules/util/url.go')).encode()
    require((CASE/'oracles/reference.patch').read_bytes()==expected_patch,'reference patch differs from exact source delta')
    for p in ['agent/input.md','oracles/reference.patch','oracles/reference-url.go','oracles/xrai_url_contract_test.go','oracles/source-relations.json']:
        raw=(CASE/p).read_bytes();require(case['artifacts'][p]=={'sha256':sha(raw),'bytes':len(raw)},'frozen oracle/input/reference hash mismatch '+p)
    return {'file_count':len(actual),'production_files':inv['production_files'],'production_nonempty_lines':inv['production_nonempty_lines'],'archive_sha256':ARCHIVE_SHA,'locks':locks,'oracle_sha256':sha((CASE/'oracles/xrai_url_contract_test.go').read_bytes())}

def manifest(reader,side,name):
    filename=side+'/'+name+'-manifest.json';raw=reader.raw(filename);row=decode(raw);files=row['files']
    require(type(row['file_count']) is int and 0<row['file_count']==len(files)<=500000,'tool/cache file count mismatch')
    seen=set()
    for f in files:
        rel=PurePosixPath(f['path']);require(not rel.is_absolute() and '..' not in rel.parts and str(rel)==f['path'] and len(rel.parts)>0,'unsafe tool/cache manifest path')
        require(f['path'] not in seen and type(f['bytes']) is int and 0<=f['bytes']<=1024*1024*1024 and digest(f['sha256']),'duplicate/invalid tool/cache row');seen.add(f['path'])
    require(files==sorted(files,key=lambda x:PurePosixPath(x['path'])),'unordered tool/cache manifest')
    require(row['bytes']==sum(x['bytes'] for x in files) and row['manifest_sha256']==sha(json.dumps(files,sort_keys=True).encode()),'tool/cache manifest aggregate mismatch')
    require(row['method']=='regular byte copies, no symlinks or host hardlinks','tool/cache copy method mismatch')
    return raw,row

def contained(row,expected_exit,phase,command):
    verify_receipt(row)
    require(confirmed_receipt(row),'supervisor teardown contract not confirmed')
    expected='error' if expected_exit else 'ok'
    require(type(row['exit_code']) is int and row['exit_code']==expected_exit,'unexpected behavioral exit')
    require(row['status']==row['execution_status']==expected and row['diagnostic'] is None,'timeout/setup/teardown infrastructure failure')
    require(row['phase']=='qualification-'+phase and row['command']==command,'probe command/filter mismatch')
    require(type(row['elapsed_seconds']) in [int,float] and 0<=row['elapsed_seconds']<=900,'operation wall limit exceeded')
    require(row['sandbox']=='Linux bubblewrap' and row['containment']=='linux_pid_namespace' and row['cleanup_status']=='confirmed' and row['eligible_for_agent_run'] is True,'namespace/teardown not confirmed')
    domain=uuid.UUID(row['domain_id']);require(domain.version==4 and str(domain)==row['domain_id'],'invalid domain ID')
    ev=row['termination_evidence'];require(type(ev['init_pid']) is int and 1<ev['init_pid']<2**31,'invalid namespace init PID')
    require(isinstance(ev['pid_namespace'],str) and re.fullmatch(r'pid:\[[1-9][0-9]*\]',ev['pid_namespace']) is not None,'invalid PID namespace identity')
    require(all(ev.get(k) is True for k in ['init_held_before_pin','pidfd_exit_observed','wrapper_reaped']),'incomplete pidfd teardown evidence')
    m=ev['user_namespace_mapping'];require(set(m)=={'uid','gid','count','setgroups'} and all(type(m[k]) is int and 0<=m[k]<2**32-1 for k in ['uid','gid']) and type(m['count']) is int and m['count']==1 and m['setgroups']=='deny','unsafe user namespace mapping')
    streams={}
    for channel in ['stdout','stderr']:
        s=row[channel];raw=base64.b64decode(s['base64'],validate=True)
        require(s['truncated'] is False and type(s['captured_bytes']) is int and s['captured_bytes']==s['observed_bytes']==len(raw)<=1024*1024,'incomplete/bounded stream mismatch')
        require(s['sha256']==sha(raw),'stream digest mismatch');streams[channel]=raw
    return streams

def test_outcomes(raw,side,name):
    events=[decode(line) for line in raw.splitlines() if line.strip()]
    require(events and all(isinstance(e,dict) and e.get('Package')==PACKAGE for e in events),'invalid Go JSON package events')
    terminal=[e for e in events if e.get('Test') and e.get('Action') in ['pass','fail','skip']]
    expected=TESTS[name];failed=side=='base' and name=='requirement'
    require(sorted(e['Test'] for e in terminal)==sorted(expected),'missing/extra/duplicate named Go results')
    require(all(e['Action']==('fail' if failed else 'pass') for e in terminal),'unexpected named test pass/fail/skip')
    package=[e for e in events if not e.get('Test') and e.get('Action') in ['pass','fail','skip']]
    require(len(package)==1 and package[0]['Action']==('fail' if failed else 'pass'),'missing or mismatched Go package exit')
    require(set(e['Test'] for e in events if e.get('Test'))==set(expected),'extra Go test event')
    for test in expected:
        output=''.join(e.get('Output','') for e in events if e.get('Test')==test)
        require('XRAI_CONTRACT_INFRASTRUCTURE' not in output and 'panic:' not in output,'named infrastructure/panic failure')
        if failed:require('XRAI_CONTRACT_SECRET_QUERY' in output,'baseline failed without exact behavioral assertion')
        require(sum(e.get('Test')==test and e.get('Action')=='run' for e in events)==1,'missing/duplicate test start')
    return {'test_names':expected,'passed':0 if failed else len(expected),'failed':len(expected) if failed else 0,'skipped':0}

def _verify(directory,overrides=None):
    reader=Reader(directory,overrides);source=frozen_source();domains=[];namespaces=[];sides={};tools=[];caches=[]
    for side in ['base','reference']:
        probe=reader.json(side+'/probe.json');require(probe['schema_version']=='xrai.eval.l5.go.probe.v1' and probe['side']==side and probe['platform'].startswith('Linux-'),'probe identity/platform mismatch')
        require(probe['executor_source_sha256']==sha((ROOT/'eval/scripts/run_l5_go.py').read_bytes()) and probe['oracle_sha256']==source['oracle_sha256'],'producer/oracle pin mismatch')
        require(probe['admitted'] is False and probe['competitive_runs_allowed'] is False,'export cannot claim admission')
        require(probe['go_version']=='go1.22.12','unpinned Go version')
        material=probe['materialization'];changed=['modules/util/url.go'] if side=='reference' else []
        require(material=={'side':side,'commit':COMMIT,'archive_sha256':ARCHIVE_SHA,'reference_changed_paths':changed,'oracle_sha256':source['oracle_sha256'],'lock_sha256':source['locks'],'agent_workspace':False,'hidden_evaluator_only':True},'source/oracle materialization mismatch')
        require(probe['source_validation']=={'full_pinned_source_files_verified':source['file_count'],'additional_go_sources':[HIDDEN],'reference_changed_paths':changed},'full pinned source validation mismatch')
        require(probe['lock_before']==probe['lock_after']==source['locks'],'source dependency lock changed')
        toolraw,tool=manifest(reader,side,'toolchain');cacheraw,cache=manifest(reader,side,'module-cache')
        require(sha(toolraw)==probe['toolchain_manifest_sha256'] and sha(cacheraw)==probe['module_cache_manifest_sha256'],'tool/cache export digest mismatch')
        bins={r['path']:r for r in tool['files']};require('bin/go' in bins and 'VERSION' in bins and bins['bin/go']['sha256']==probe['go_executable_sha256'],'reported Go binary hash inconsistent with copied inventory')
        require(digest(probe['go_executable_sha256']),'invalid reported Go binary hash')
        native=probe['native_compilers'];require(len(native)==2 and all(re.fullmatch(r'/usr/bin/[A-Za-z0-9_.+-]+',p) and digest(h) for p,h in native.items()),'native compiler pin invalid')
        cc=[p for p in native if 'gcc' in p];cxx=[p for p in native if 'g++' in p];require(len(cc)==len(cxx)==1,'compiler roles ambiguous')
        phases=probe['phases'];require([r['name'] for r in phases]==['requirement','regression'],'phase set mismatch')
        results={}
        for phase in phases:
            name=phase['name'];prefix='^TestXraiContract' if name=='requirement' else '^TestXraiRegression';exit_code=1 if side=='base' and name=='requirement' else 0
            require(phase['expected_tests']==TESTS[name] and phase['expected_exit']==phase['actual_exit']==exit_code,'phase expected labels/exit mismatch')
            require(phase['harness']==name+'-harness.json' and phase['jsonl']==name+'-go-test.jsonl','phase evidence paths mismatch')
            command=['/usr/bin/env','HOME=/workspace','TMPDIR=/tmp','PATH=/workspace/.xrai-go/bin:/usr/bin:/bin','CC='+cc[0],'CXX='+cxx[0],'GOROOT=/workspace/.xrai-go','GOMODCACHE=/workspace/.xrai-mod','GOCACHE=/workspace/.xrai-build','GOPROXY=off','GOSUMDB=off','GOTOOLCHAIN=local','GOFLAGS=-mod=readonly','CGO_ENABLED=1','/workspace/.xrai-go/bin/go','test','-json','-count=1','-timeout=600s','-tags=sqlite,sqlite_unlock_notify','-run='+prefix,'./services/convert']
            row=reader.json(side+'/'+phase['harness']);streams=contained(row,exit_code,name,command)
            require(phase['execution_status']==row['execution_status'],'phase execution status differs')
            raw=reader.raw(side+'/'+phase['jsonl']);require(raw==streams['stdout'] and sha(raw)==phase['jsonl_sha256'],'Go JSONL not exact harness stdout')
            results[name]=test_outcomes(raw,side,name);domains.append(row['domain_id']);namespaces.append(row['termination_evidence']['pid_namespace'])
        sides[side]={'requirement':results['requirement'],'regression':results['regression'],'go_executable_sha256':probe['go_executable_sha256'],'toolchain_files':tool['file_count'],'module_cache_files':cache['file_count'],'locks_unchanged':True};tools.append(toolraw);caches.append(cacheraw)
    require(len(set(domains))==4 and len(set(namespaces))==4,'namespace/domain reused across operations')
    require(tools[0]==tools[1] and caches[0]==caches[1],'baseline/reference toolchain or module-cache inventories differ')
    require(sides['base']['go_executable_sha256']==sides['reference']['go_executable_sha256'],'baseline/reference Go executable differs')
    return {'schema_version':'xrai.eval.l5.go.export-verified.v1','verified':True,'verified_behavioral_pair':True,'source_commit':COMMIT,'source':source,'sides':sides,'fresh_namespace_domains':domains,'fresh_pid_namespaces':namespaces,'file_sha256':dict(sorted(reader.hashes.items())),'admitted':False,'competitive_runs_allowed':False,'limits':['Caller must authenticate CI commit/jobs and original ZIP plus exact membership independently.','Toolchain/cache/compiler bytes are reported hashes and copied-file inventories; binaries are not retained in this export.','Source validation and teardown are receipt consistency, not independent observation of past workspace or processes.','No full post-probe source/toolchain/cache inventory was produced; locks before/after are checked, materialization and copied inventories describe pre-probe state.','No same-process/index Go state A-to-B, agent success or global admission inferred.']}

def verify(directory:Path)->dict:return _verify(directory)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);args=p.parse_args();print(json.dumps(verify(args.directory),indent=2,sort_keys=True))
if __name__=='__main__':main()
