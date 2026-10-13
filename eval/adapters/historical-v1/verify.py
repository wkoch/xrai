"""Revalidate unchanged owned adapter code against an explicit historical plan capture."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
sys.dont_write_bytecode=True

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
PROVENANCE='eval/adapters/historical-v1/provenance.json'
PROVENANCE_SHA='30001ef3fe6674d7746677d70e00e49087cdeeac15709b93f9b25417b1a25757'
PLAN='docs/PLANO-DE-IMPLEMENTACAO.md'
SNAPSHOT='eval/adapters/historical-v1/original-PLANO-DE-IMPLEMENTACAO.md'
PLAN_SHA='5bffa29b5223ac305663a6e4cbf28a0325a277d96c44e863ebb50ac639d74bbc'
MAX_MEMBER=16*1024*1024
MAX_TOTAL=32*1024*1024
MAX_MEMBERS=128
VERIFIER='eval/adapters/experimental-v1/verify.py'
RESULT='docs/relatorios/logs/L5-C04/adapter/root-recheck.json'


def require(value,message):
    if not value:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def decode(raw):
    require(type(raw) is bytes and 0<len(raw)<=MAX_MEMBER,'bounded historical JSON bytes')
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'duplicate historical JSON key');result[key]=value
        return result
    def bad(_):raise ValueError('nonfinite historical JSON')
    try:return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    except (RecursionError,UnicodeError) as error:raise ValueError('invalid historical JSON') from error


def owned(root,path):
    root=Path(root)
    require(type(path) is str and len(path.encode())<=4096 and '\\' not in path and not any(ord(c)<32 for c in path),'bounded historical relative path')
    p=PurePosixPath(path)
    require(not p.is_absolute() and str(p)==path and all(part not in ('','..','.') for part in path.split('/')),'normalized historical path')
    target=root/path
    require(target.resolve().is_relative_to(root.resolve()) and all(not root.joinpath(*p.parts[:n]).is_symlink() for n in range(1,len(p.parts)+1)),'owned file path/symlink boundary')
    require(target.is_file() and 0<target.stat().st_size<=MAX_MEMBER,'ordinary bounded historical file')
    with target.open('rb') as stream:raw=stream.read(MAX_MEMBER+1)
    require(0<len(raw)<=MAX_MEMBER,'actual historical member byte bound')
    return raw


def provenance(root=ROOT):
    raw=owned(root,PROVENANCE)
    require(sha(raw)==PROVENANCE_SHA,'exact prospectively pinned provenance')
    value=decode(raw)
    require(type(value) is dict and set(value)=={'schema_version','historical_commit','historical_plan_path','historical_plan_sha256','original_receipt_sha256','current_method_policy','closure','execution'} and value['schema_version']=='xrai.eval.historical-adapter-provenance.v1' and value['historical_plan_path']==PLAN and value['historical_plan_sha256']==PLAN_SHA,'typed immutable historical provenance')
    closure=value['closure']
    require(type(closure) is dict and len(closure)==30<=MAX_MEMBERS and sum(row['bytes'] for row in closure.values())<=MAX_TOTAL,'fixed bounded historical closure before reads')
    require(all(type(row) is dict and set(row)=={'input_path','sha256','bytes'} and type(row['bytes']) is int and 0<row['bytes']<=MAX_MEMBER and row['input_path']==(SNAPSHOT if path==PLAN else path) for path,row in closure.items()),'only historical plan substitution permitted')
    return value


def capture(root=ROOT):
    manifest=provenance(root)
    members={};total=0
    for target,entry in manifest['closure'].items():
        raw=owned(root,entry['input_path']);total+=len(raw)
        require(total<=MAX_TOTAL and len(raw)==entry['bytes'] and sha(raw)==entry['sha256'],'exact current owned method/data or historical snapshot bytes: '+target)
        members[target]=raw
    receipt=decode(members['docs/relatorios/logs/L5-C04/adapter/receipt.json'])
    require(sha(members['docs/relatorios/logs/L5-C04/adapter/receipt.json'])==manifest['original_receipt_sha256'] and receipt['source_hashes'][PLAN]==PLAN_SHA,'original receipt historical content binding')
    require(all(path in members and sha(members[path])==digest for path,digest in receipt['source_hashes'].items()),'all nine original method/document hashes preserved')
    return members


def run_capsule(members):
    """Trusted fixed owned source only; no producer/receipt command or artifact code is run."""
    manifest=provenance()
    require(type(members) is dict and set(members)==set(manifest['closure']),'exact capsule source/data closure')
    require(all(type(raw) is bytes and 0<len(raw)<=MAX_MEMBER and len(raw)==manifest['closure'][path]['bytes'] and sha(raw)==manifest['closure'][path]['sha256'] for path,raw in members.items()) and sum(map(len,members.values()))<=MAX_TOTAL,'capsule bytes must equal pinned owned method')
    with tempfile.TemporaryDirectory(prefix='xrai-historical-adapter-') as temporary:
        private=Path(temporary)
        for path,raw in members.items():
            target=private/path;target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:stream.write(raw)
        launch='import runpy,sys; runpy.run_path(sys.argv[1],run_name="__main__")'
        process=subprocess.run([sys.executable,'-I','-B','-X','utf8','-c',launch,str(private/VERIFIER)],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False,
            cwd=private,env={})
        require(len(process.stdout)<=1024*1024 and len(process.stderr)<=1024*1024,'owned verifier output bound')
        require(process.returncode==0 and process.stderr==b'','original isolated own verifier must succeed: '+process.stderr.decode('utf-8',errors='replace')[:512])
        result=decode(process.stdout)
        expected=decode(members[RESULT])
        require(canonical(result)==canonical(expected),'complete isolated original result equals retained historical root recheck')
        require(process.stdout==canonical(result)+b'\n','canonical isolated original verifier output')
        require(all(owned(private,path)==raw for path,raw in members.items()),'private capsule modified during readonly verification')
    return result


def verify(root=ROOT):
    members=capture(root)
    result=run_capsule(members)
    require(capture(root)==members,'current own source/data closure changed during historical verification')
    current_plan=owned(root,PLAN)
    manifest=provenance(root)
    return {'schema_version':'xrai.eval.historical-adapter-verification.v1','verified':True,
        'scope':'historical original adapter replay; current own code exact; original plan snapshot only',
        'historical_commit':manifest['historical_commit'],'historical_plan_sha256':PLAN_SHA,
        'current_plan_sha256':sha(current_plan),'current_plan_binding_claimed':False,
        'original_receipt_sha256':manifest['original_receipt_sha256'],
        'capsule_members':len(members),'capsule_bytes':sum(map(len,members.values())),
        'historical_result':result,'provider_calls':0,'agent_runs':0,'native_execution':False,
        'upstream_execution':False,'campaign_scoring_enabled':False,'new_qualification':False}


if __name__=='__main__':
    try:print(canonical(verify()).decode())
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr);raise SystemExit(1)
