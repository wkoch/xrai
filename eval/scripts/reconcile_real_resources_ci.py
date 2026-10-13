#!/usr/bin/env python3
"""Reconcile caller-authenticated GitHub API and both original real-resource ZIPs.

No network, retained executable launch, native execution or upstream import.
Local API JSON is not a signature: authentic acquisition remains the caller's duty.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import io
import json
import re
import stat
import tempfile
import unicodedata
import zipfile
from pathlib import Path

import verify_real_resources as event

REPOSITORY = 'wkoch/xrai'
WORKFLOW = '.github/workflows/l5-real-resources.yml'
WORKFLOW_NAME = 'L5 captured real worker resources'
HOSTS = {'x86_64-unknown-linux-gnu':('ubuntu-24.04','Linux'),
         'aarch64-apple-darwin':('macos-15','Darwin')}
REQUIRED_STEP_ORDER = [
    'Run actions/checkout@v6','Run actions/setup-python@v6',
    'Install pinned resource verification tooling','Verify frozen real source design',
    'Build owned experimental resource driver','Measure owned workers on frozen captured sources',
    'Recompute complete real resource evidence','Reject adversarial resource substitutions',
    'Preserve exact real resource proof and native bytes']
LIFECYCLE_STEPS = {'Set up job','Post Run actions/setup-python@v6',
    'Post Run actions/checkout@v6','Complete job'}
UPLOAD_STEP = REQUIRED_STEP_ORDER[-1]
BUNDLE_FILES = {'design.json','rustc.txt','cargo.txt','python.txt','collector.json',
    'verification.json','receipt-tests.stdout','receipt-tests.stderr'}
BINARIES = {'native-bin/worker-benchmark-real','native-bin/worker-spike','native-bin/worker-persistent'}
MODES = ('direct','direct_cached','xrw1','xrw2')
MAX_ZIP_BYTES = 256*1024*1024
MAX_MEMBER_BYTES = 32*1024*1024
MAX_TOTAL_BYTES = 512*1024*1024
MAX_MEMBERS = 4096
MAX_METADATA_BYTES = 8*1024*1024


def need(value, message):
    if not value: raise ValueError(message)


def sha(raw): return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def pairs(values):
        result={}
        for k,v in values:
            need(k not in result,'duplicate JSON key');result[k]=v
        return result
    def reject(value): raise ValueError('nonfinite JSON number: '+value)
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=reject)


def same(a,b):
    return json.dumps(a,sort_keys=True,separators=(',',':'),allow_nan=False)==json.dumps(b,sort_keys=True,separators=(',',':'),allow_nan=False)


def positive(value): return type(value) is int and value>0


def instant(value):
    need(isinstance(value,str),'API timestamp string')
    parsed=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    need(parsed.tzinfo is not None and parsed.utcoffset()==datetime.timedelta(0),'API timestamp UTC')
    return parsed


def metadata(run,jobs,artifacts,run_id,head,artifact_ids,attempt=1):
    """Exact two-host API identity, complete jobs/steps and upload-attempt linkage."""
    need(positive(run_id) and positive(attempt) and isinstance(head,str) and re.fullmatch('[0-9a-f]{40}',head),'explicit head/run/attempt')
    need(isinstance(artifact_ids,dict) and set(artifact_ids)==set(HOSTS) and all(positive(v) for v in artifact_ids.values()) and len(set(artifact_ids.values()))==2,'two distinct explicit artifact identities')
    need(positive(run['id']) and run['id']==run_id and run['head_sha']==head and run['head_branch']=='main' and
         positive(run['run_attempt']) and run['run_attempt']==attempt and run['path']==WORKFLOW and run['name']==WORKFLOW_NAME and
         run['event']=='workflow_dispatch' and run['status']=='completed' and run['conclusion']=='success' and
         run['repository']['full_name']==REPOSITORY,'successful exact repository/workflow/head/run/attempt')
    need(run['html_url']==f'https://github.com/{REPOSITORY}/actions/runs/{run_id}','exact run URL')
    need(type(jobs['total_count']) is int and jobs['total_count']==2 and isinstance(jobs['jobs'],list) and len(jobs['jobs'])==2,'complete two-job envelope')
    names={f'C04 real resources {host}':host for host in HOSTS}
    need({job['name'] for job in jobs['jobs']}==set(names) and len({job['id'] for job in jobs['jobs']})==2,'two distinct named host jobs')
    checked={}
    for job in jobs['jobs']:
        host=names[job['name']];runner,_=HOSTS[host]
        need(positive(job['id']) and positive(job['run_id']) and job['run_id']==run_id and job['head_sha']==head and
             positive(job['run_attempt']) and job['run_attempt']==attempt and job['status']=='completed' and job['conclusion']=='success','successful exact job/run/attempt')
        need(isinstance(job['labels'],list) and runner in job['labels'],'declared runner host')
        need(job['html_url']==f'https://github.com/{REPOSITORY}/actions/runs/{run_id}/job/{job["id"]}','exact job URL')
        steps=job['steps'];need(isinstance(steps,list),'steps array')
        stepnames=[s['name'] for s in steps]
        need(len(stepnames)==len(set(stepnames)) and set(REQUIRED_STEP_ORDER)<=set(stepnames)<=set(REQUIRED_STEP_ORDER)|LIFECYCLE_STEPS,'exact step and lifecycle closure')
        need([n for n in stepnames if n in REQUIRED_STEP_ORDER]==REQUIRED_STEP_ORDER,'required step order')
        need(all(s['status']=='completed' and s['conclusion']=='success' and positive(s['number']) for s in steps),'every job step successful and typed')
        numbers=[s['number'] for s in steps];need(numbers==sorted(set(numbers)),'unique increasing step numbers')
        started,finished=instant(job['started_at']),instant(job['completed_at'])
        need(started<=finished,'ordered job timestamps')
        previous=started
        for step in steps:
            begin,end=instant(step['started_at']),instant(step['completed_at'])
            need(previous<=begin<=end<=finished,'ordered step intervals inside job');previous=end
        checked[host]={'job':job}
    need(type(artifacts['total_count']) is int and artifacts['total_count']==2 and isinstance(artifacts['artifacts'],list) and len(artifacts['artifacts'])==2,'complete exact two-artifact envelope')
    need(len({a['id'] for a in artifacts['artifacts']})==2 and {a['id'] for a in artifacts['artifacts']}==set(artifact_ids.values()),'exact original artifact ID closure')
    for host,value in checked.items():
        artifact=next(a for a in artifacts['artifacts'] if a['id']==artifact_ids[host]);job=value['job']
        need(positive(artifact['id']) and artifact['name']==f'c04-real-resources-{host}' and artifact['expired'] is False and
             isinstance(artifact['digest'],str) and re.fullmatch('sha256:[0-9a-f]{64}',artifact['digest']) and
             type(artifact['size_in_bytes']) is int and 0<artifact['size_in_bytes']<=MAX_ZIP_BYTES,'live exact host artifact bounds/digest')
        wr=artifact['workflow_run'];need(positive(wr['id']) and wr['id']==run_id and wr['head_sha']==head and wr['head_branch']=='main','artifact original run/head/branch')
        need(artifact['archive_download_url']==f'https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact["id"]}/zip','original artifact API URL')
        upload=next(s for s in job['steps'] if s['name']==UPLOAD_STEP)
        need(instant(upload['started_at'])<=instant(artifact['created_at'])<=instant(upload['completed_at']),'artifact created within this attempt upload')
        value['artifact']=artifact
    return checked


def checked_path(name):
    need(isinstance(name,str) and 0<len(name.encode('utf-8'))<=4096 and not name.startswith('/') and '\\' not in name and ':' not in name and not any(ord(c)<32 for c in name),'bounded normalized relative ZIP path')
    pieces=name.rstrip('/').split('/')
    need(not name.endswith('//') and all(p not in ('','.','..') for p in pieces),'no ZIP alias/traversal')
    return '/'.join(pieces)


def zip_members(raw):
    """Bound before decompression; reject aliases, specials, links and collisions."""
    need(isinstance(raw,bytes) and 0<len(raw)<=MAX_ZIP_BYTES,'original ZIP byte bound')
    result={};directories=set();seen=set();aliases=set();total=0
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos=archive.infolist();need(0<len(infos)<=MAX_MEMBERS,'ZIP member count bound')
            for member in infos:
                name=member.filename;plain=checked_path(name)
                need(name not in seen,'duplicate ZIP name');seen.add(name)
                alias=unicodedata.normalize('NFC',plain).casefold()
                need(alias not in aliases,'case/Unicode/file-directory alias');aliases.add(alias)
                kind=stat.S_IFMT(member.external_attr>>16)
                need(not member.flag_bits&1,'encrypted ZIP member')
                if member.is_dir():
                    need(kind in (0,stat.S_IFDIR) and member.file_size==0,'ordinary empty directory marker')
                    directories.add(name);continue
                need(kind in (0,stat.S_IFREG),'ordinary regular member, no links/specials')
                need(0<=member.file_size<=MAX_MEMBER_BYTES,'ZIP member expansion bound')
                total+=member.file_size;need(total<=MAX_TOTAL_BYTES,'ZIP total expansion bound')
                content=archive.read(member);need(len(content)==member.file_size,'ZIP declared member length')
                result[name]=content
    except (zipfile.BadZipFile,NotImplementedError,RuntimeError) as error:
        raise ValueError('invalid or unsupported ZIP container') from error
    for name in result:
        parts=name.split('/')
        need(not any('/'.join(parts[:n]) in result for n in range(1,len(parts))),'file ancestor collision')
    need(all(any(n.startswith(d) for n in result) for d in directories),'no extraneous empty ZIP directory')
    need({name for name in result if '/' not in name}==BUNDLE_FILES and all(n in BUNDLE_FILES or n.startswith('event/') for n in result),'workflow top/prefix closure')
    return result


def directory_members(directory):
    need(directory.is_dir() and not directory.is_symlink(),'ordinary captured export directory')
    result={};dirs=set();total=0;seen=0
    for path in directory.rglob('*'):
        seen+=1;need(seen<=MAX_MEMBERS,'captured export path bound')
        need(not path.is_symlink(),'no captured export symlink')
        rel=path.relative_to(directory).as_posix();checked_path(rel)
        if path.is_dir(): dirs.add(rel+'/');continue
        need(path.is_file() and stat.S_ISREG(path.stat().st_mode),'ordinary captured export file')
        size=path.stat().st_size;need(size<=MAX_MEMBER_BYTES,'captured export member bound')
        total+=size;need(total<=MAX_TOTAL_BYTES,'captured export total bound')
        result[rel]=path.read_bytes();need(len(result[rel])==size,'captured export read size')
    need(all(any(n.startswith(d) for n in result) for d in dirs),'no extra empty export directory')
    return result


def safe_export(members,destination):
    need(not destination.exists(),'fresh private export')
    destination.mkdir()
    for name,raw in members.items():
        checked_path(name)
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)


def event_closure(members):
    """Predict exact owned filenames from frozen source/configuration/matrix IDs."""
    _,manifest=event.frozen();source_ids={s['id'] for s in manifest['sources']}
    expected={'event/preregistered.json','event/reference.json','event/producers.json'}
    expected|={'event/'+name for name in BINARIES}
    expected|={'event/sources/'+sid for sid in source_ids}
    expected|={'event/calibration/'+name for name in ('input.json','stdout','stderr','resources.json','calibration.json')}
    expected|={f'event/reference-responses/{sid}--{config}.response.gz' for sid in source_ids for config in range(2)}
    common={'input.json','stdout','stderr','resources.json','control/idle.ready','control/idle.start','control/warm_idle.ready','control/warm_idle.start'}
    for mode in MODES:
        prefix=f'event/equivalence-{mode}/'
        expected|={prefix+name for name in common}
        # Driver request order is verified by the verifier; equivalence reference
        # filenames are operational request indices, never caller-given paths.
        expected|={prefix+f'control/references/{i}.response.gz' for i in range(len(source_ids)*2)}
        for session in range(3):
            for concurrency in (1,2):
                prefix=f'event/session-{session}-c{concurrency}-{mode}/'
                expected|={prefix+name for name in common}
    need(set(members)==BUNDLE_FILES|expected,'exact source/response/session/native bundle file closure')
    return manifest


def environment(metadata_value,host,run_id,head,attempt):
    expected={'repository':REPOSITORY,'head_sha':head,'run_id':run_id,'run_attempt':attempt,
              'platform':HOSTS[host][1],'host':host}
    need(same(metadata_value['environment'],expected),'native actual host/repository/head/run/attempt')
    need(metadata_value['schema_version']=='xrai.eval.resources.real-preregistration.v1','typed real preregistration schema')


def bind_native(members,host,run_id,head,attempt):
    value=decode(members['event/preregistered.json']);environment(value,host,run_id,head,attempt)
    need(set(value['binary_sha256'])==BINARIES,'exact three retained executable identities')
    for path in BINARIES:
        raw=members['event/'+path]
        need(4096<=len(raw)<=MAX_MEMBER_BYTES and sha(raw)==value['binary_sha256'][path],'actual retained native bytes SHA/bound')
        if host=='x86_64-unknown-linux-gnu':
            need(raw[:6]==b'\x7fELF\x02\x01' and len(raw)>=20 and int.from_bytes(raw[18:20],'little')==62,'native ELF64 little-endian x86_64')
        else:
            need(raw[:4]==b'\xcf\xfa\xed\xfe' and int.from_bytes(raw[4:8],'little')==0x0100000c,'native Mach-O64 arm64')
    need(set(value['source_bindings_sha256'])==set(event.SOURCE_PATHS),'native source/grammar/query/lock/protocol binding closure')
    for path,digest in value['source_bindings_sha256'].items():
        need(isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest) and sha((event.ROOT/path).read_bytes())==digest,'native own source/protocol binding unchanged: '+path)
    rust=members['rustc.txt'].decode();cargo=members['cargo.txt'].decode();python=members['python.txt'].decode()
    need(re.search(r'^rustc 1\.98\.1\b',rust,re.M) and re.search(r'^host: '+re.escape(host)+r'$',rust,re.M),'actual compiler version/host')
    need(re.search(r'^cargo 1\.98\.1\b',cargo) and python.strip()=='Python 3.13.13','pinned Cargo/Python versions')
    return value


def native_time_window(members,job,native):
    """Bind own observed epochs and actual command to the successful native step.

    GitHub API step timestamps have seconds resolution; only that quantization
    is allowed at the outer boundary. Calibration uses its separately validated
    historical receipt; new sessions carry explicit epoch/observer-tail fields.
    """
    step=next(s for s in job['steps'] if s['name']=='Measure owned workers on frozen captured sources')
    begin=int(instant(step['started_at']).timestamp()*1_000_000_000)
    end=int(instant(step['completed_at']).timestamp()*1_000_000_000)+999_999_999
    frozen=native['frozen_epoch_ns']
    need(type(frozen) is int and begin<=frozen<=end,'preregistration belongs to this native step')
    reference=decode(members['event/reference.json'])['equivalence_completed_epoch_ns']
    need(type(reference) is int and frozen<=reference<=end,'equivalence decision belongs to this native step')
    directories=[f'equivalence-{m}' for m in MODES]+[f'session-{s}-c{cc}-{m}' for s in range(3) for cc in (1,2) for m in MODES]
    for directory in directories:
        receipt=decode(members[f'event/{directory}/resources.json'])
        payload=decode(members[f'event/{directory}/stdout'])
        epochs=[receipt[k] for k in ('epoch_started_ns','epoch_finished_ns','observer_epoch_finished_ns')]
        need(all(type(v) is int for v in epochs) and frozen<=epochs[0]<=epochs[1]<=epochs[2]<=end,'observed native session belongs to successful API execution step')
        need(positive(receipt['pid']) and positive(payload['parent_pid']) and receipt['pid']==payload['parent_pid'],'observer actual target PID equals native parent')
        expected=str(Path(native['output_root'])/'native-bin/worker-benchmark-real')
        need(receipt['command']==[expected],'observed target command binds actual retained measured executable')


def reconcile(directory,run_id,head,artifact_ids,attempt=1):
    directory=Path(directory);names=('run.json','jobs.json','artifacts.json');raw_metadata={}
    for name in names:
        path=directory/name;need(path.is_file() and not path.is_symlink() and path.stat().st_size<=MAX_METADATA_BYTES,'ordinary bounded raw API metadata')
        raw_metadata[name]=path.read_bytes()
    run,jobs,artifacts=(decode(raw_metadata[n]) for n in names)
    authenticated=metadata(run,jobs,artifacts,run_id,head,artifact_ids,attempt);results={}
    for host,bindings in authenticated.items():
        original_path=directory/host/'original.zip'
        need(original_path.is_file() and not original_path.is_symlink() and original_path.stat().st_size<=MAX_ZIP_BYTES,'ordinary bounded original ZIP')
        raw=original_path.read_bytes();artifact=bindings['artifact']
        need(sha(raw)==artifact['digest'][7:] and len(raw)==artifact['size_in_bytes'],'original ZIP digest/size equals API')
        members=zip_members(raw);need(directory_members(directory/host/'export')==members,'captured export exact original ZIP bytes/closure')
        event_closure(members);native=bind_native(members,host,run_id,head,attempt)
        native_time_window(members,bindings["job"],native)
        with tempfile.TemporaryDirectory(prefix='xrai-real-resource-ci-') as temporary:
            private=Path(temporary)/'export';safe_export(members,private)
            recomputed=event.verify(private/'event')
            need(same(recomputed,decode(members['collector.json'])) and same(recomputed,decode(members['verification.json'])),'retained collector/verification match complete private recomputation')
        need(recomputed['verified'] is True and recomputed['data_only'] is True and recomputed['m0_06_complete'] is False and recomputed['production_recommendation'] is None,'experimental verification boundary')
        tests=members['receipt-tests.stderr'].decode()
        need(members['receipt-tests.stdout']==b'' and re.search(r'Ran ([1-9][0-9]*) tests in [0-9.]+s\n\nOK\n',tests) and 'skipped' not in tests,'actual all adversarial native-receipt tests successful')
        design=decode(members['design.json'])
        need(design['verified'] is True and design['data_only'] is True and design['measured'] is False and design['sources']==80 and design['protocol_sha256']==sha((event.DESIGN/'protocol.json').read_bytes()),'consumed premeasurement frozen source design')
        results[host]={'job_id':bindings['job']['id'],'artifact_id':artifact['id'],'artifact_name':artifact['name'],
            'artifact_zip_sha256':sha(raw),'artifact_zip_bytes':len(raw),'exact_zip_export_files':len(members),
            'export_file_sha256':{p:sha(b) for p,b in sorted(members.items())},'environment':native['environment'],
            'native_verification':recomputed,'actual_native_binary_sha256':native['binary_sha256']}
    return {'schema_version':'xrai.eval.c04.real-resources-ci-reconciliation.v1','verified':True,'data_only':True,
        'run_id':run_id,'run_attempt':attempt,'code_commit':head,'repository':REPOSITORY,'workflow':WORKFLOW,
        'hosts':results,'metadata_sha256':{p:sha(raw) for p,raw in raw_metadata.items()},
        'reconciler_source_sha256':sha(Path(__file__).read_bytes()),'m0_06_complete':False,'production_recommendation':None,
        'limits':['Caller authenticates original GitHub API/ZIP acquisition; arbitrary local JSON is not a signature.',
                  'Retained own native binaries are hashed and never executed by this reconciler.',
                  'Experimental captured-source resources only; no competitive admission or production choice.']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--run-id',type=int,required=True);parser.add_argument('--head',required=True)
    parser.add_argument('--attempt',type=int,default=1);parser.add_argument('--linux-artifact-id',type=int,required=True)
    parser.add_argument('--macos-artifact-id',type=int,required=True);args=parser.parse_args()
    ids={'x86_64-unknown-linux-gnu':args.linux_artifact_id,'aarch64-apple-darwin':args.macos_artifact_id}
    print(json.dumps(reconcile(args.directory,args.run_id,args.head,ids,args.attempt),indent=2,sort_keys=True))


if __name__=='__main__':main()
