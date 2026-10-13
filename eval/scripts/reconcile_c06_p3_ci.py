"""Authenticated original CI proof for prospective native diff byte-context.

Only owned Python verifiers are executed. Retained ELF and captured sources are
bytes. Acquisition through authenticated GitHub is contextual evidence, not a
signature on arbitrary JSON. Historical producers and checkers remain unchanged.
"""
import argparse
import datetime
import io
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
import json
from reconcile_c05_ci import need,sha,decode,same,bounded_file,successful_tests
from reconcile_tsjs_ci import safe_export,directory_members

ROOT=Path(__file__).resolve().parents[2]
REPOSITORY='wkoch/xrai'
MAX_ZIP_BYTES=128*1024*1024
EVENT={'inputs/protocol.json','inputs/cases.json','inputs/freeze-before-native.json','native-bin/context-diff-spike','session/transcript.jsonl','session/stdout.jsonl','session/stderr.bin','session/process.json','rebuild/transcript.jsonl','rebuild/stdout.jsonl','rebuild/stderr.bin','rebuild/process.json','receipt.json','verification.json'}
TOP={'python.txt','design.json','rustc.txt','cargo.txt','collector.json','verification.json','receipt-tests.stdout','receipt-tests.stderr'}
CONFIG={
 'workflow':'.github/workflows/l5-p3-diff-native.yml',
 'job':'C06 validated diff native context','artifact':'c06-validated-diff-native-context',
 'steps':['Run actions/checkout@v6','Run actions/setup-python@v6','Install pinned verification tooling',
          'Verify frozen native diff context design','Build owned native diff context',
          'Prove frozen native diff context and expansion','Recompute complete native diff context evidence',
          'Reject adversarial native diff context substitutions','Preserve exact native diff context evidence'],
 'max_members':1024,'event_member_bytes':32*1024*1024,'top_member_bytes':32*1024*1024,'total_bytes':128*1024*1024,
}
LIFECYCLE={'Set up job','Post Run actions/setup-python@v6','Post Run actions/checkout@v6','Complete job'}
# Root fixes verifier/test count to the producer's stable final interface before CI.
VERIFIER='eval/scripts/p3_diff_native_verify.py'
TESTS=47

def metadata(run,jobs,artifacts,run_id,head,artifact_id,attempt=1):
    p = CONFIG
    need(all(type(n) is int and n > 0 for n in [run_id,artifact_id,attempt]) and type(head) is str and
         re.fullmatch('[0-9a-f]{40}',head), 'explicit typed run/head/artifact/attempt')
    need(type(run['id']) is int and run['id'] == run_id and run['head_sha'] == head and run['head_branch'] == 'main' and
         type(run['run_attempt']) is int and run['run_attempt'] == attempt and run['path'] == p['workflow'] and
         run['event'] == 'workflow_dispatch' and run['status'] == 'completed' and run['conclusion'] == 'success' and
         run['repository']['full_name'] == REPOSITORY and run['html_url'] == f'https://github.com/{REPOSITORY}/actions/runs/{run_id}',
         'successful exact profile/workflow/run/head/attempt/repository')
    need(type(jobs['total_count']) is int and jobs['total_count'] == len(jobs['jobs']) == 1, 'complete single-job API')
    job = jobs['jobs'][0]
    need(job['name'] == p['job'] and type(job['run_id']) is int and job['run_id'] == run_id and job['head_sha'] == head and
         type(job['run_attempt']) is int and job['run_attempt'] == attempt and job['status'] == 'completed' and
         job['conclusion'] == 'success' and 'ubuntu-24.04' in job['labels'] and type(job['id']) is int and job['id'] > 0 and
         job['html_url'] == f'https://github.com/{REPOSITORY}/actions/runs/{run_id}/job/{job["id"]}', 'exact successful Linux job')
    steps = job['steps']; names = [s['name'] for s in steps]
    need(len(names) == len(set(names)) and set(p['steps']) <= set(names) <= set(p['steps']) | LIFECYCLE and
         [n for n in names if n in p['steps']] == p['steps'], 'complete exact required step names/order')
    numbers = [s['number'] for s in steps]
    need(all(type(n) is int and n > 0 for n in numbers) and numbers == sorted(set(numbers)) and
         all(s['status'] == 'completed' and s['conclusion'] == 'success' for s in steps), 'all steps successful without skip')
    need(type(artifacts['total_count']) is int and artifacts['total_count'] == len(artifacts['artifacts']), 'complete artifact API')
    selected = [a for a in artifacts['artifacts'] if type(a['id']) is int and a['id'] == artifact_id]
    need(len(selected) == 1, 'unique exact artifact ID')
    artifact = selected[0]
    need(artifact['name'] == p['artifact'] and artifact['expired'] is False and type(artifact['size_in_bytes']) is int and
         0 < artifact['size_in_bytes'] <= MAX_ZIP_BYTES and re.fullmatch('sha256:[0-9a-f]{64}',artifact['digest']) and
         artifact['archive_download_url'] == f'https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip',
         'live original profile ZIP digest/size/download URL')
    wr = artifact['workflow_run']
    need(type(wr['id']) is int and wr['id'] == run_id and wr['head_sha'] == head and wr['head_branch'] == 'main', 'artifact exact run/head')
    def instant(value):
        t = datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
        need(t.tzinfo is not None and t.utcoffset() == datetime.timedelta(0), 'UTC API timestamps')
        return t
    upload = next(s for s in steps if s['name'] == p['steps'][-1])
    need(instant(job['started_at']) <= instant(upload['started_at']) <= instant(artifact['created_at']) <=
         instant(upload['completed_at']) <= instant(job['completed_at']), 'artifact belongs to attempt upload window')
    return job,artifact

def zip_members(raw):
    p = CONFIG
    need(type(raw) is bytes and 0 < len(raw) <= MAX_ZIP_BYTES, 'bounded original ZIP bytes')
    result,seen,directories,total = {},set(),set(),0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        need(0 < len(infos) <= p['max_members'], 'profile ZIP member count')
        for info in infos:
            name = info.filename
            need(name == info.orig_filename, 'ZIP truncated native member name')
            need(name not in seen, 'duplicate ZIP member')
            seen.add(name)
            need(name and not name.startswith('/') and '\\' not in name and ':' not in name and not any(ord(c) < 32 for c in name),
                 'ZIP absolute/drive/control path')
            parts = name[:-1].split('/') if name.endswith('/') else name.split('/')
            need(all(x not in ('','.','..') for x in parts), 'ZIP path alias/traversal')
            kind = stat.S_IFMT(info.external_attr >> 16)
            if info.is_dir():
                need(kind in [0,stat.S_IFDIR] and info.file_size == 0 and not info.flag_bits & 1, 'regular unencrypted ZIP directory')
                directories.add(name); continue
            need(kind in [0,stat.S_IFREG] and not info.flag_bits & 1, 'regular unencrypted ZIP file')
            limit = p['event_member_bytes'] if name.startswith('event/') else p['top_member_bytes']
            need(0 <= info.file_size <= limit, 'profile member byte cap')
            total += info.file_size; need(total <= p['total_bytes'], 'profile ZIP expansion cap')
            raw_member = archive.read(info)
            need(len(raw_member) == info.file_size, 'complete member bytes')
            result[name] = raw_member
    for name in result:
        need(all('/'.join(name.split('/')[:i]) not in result for i in range(1,len(name.split('/')))), 'ZIP file/directory collision')
    need(all(any(name.startswith(d) for name in result) for d in directories), 'no extra empty ZIP directories')
    need(set(result)==TOP|{'event/'+name for name in EVENT}, 'exact workflow top/event original closure')
    return result

def export_members(directory):
    p = CONFIG
    need(directory.is_dir() and not directory.is_symlink(), 'ordinary exported directory')
    total,count = 0,0
    for path in directory.rglob('*'):
        need(not path.is_symlink(), 'export symlink')
        if path.is_dir():continue
        name = path.relative_to(directory).as_posix()
        limit = p['event_member_bytes'] if name.startswith('event/') else p['top_member_bytes']
        need(path.is_file() and path.stat().st_size <= limit, 'profile export ordinary member cap')
        total += path.stat().st_size; count += 1
        need(total <= p['total_bytes'] and count <= p['max_members'], 'profile export total/file cap')
    return directory_members(directory)


def _recompute(directory,design=False):
    owned=ROOT/VERIFIER
    launcher=('import runpy,sys; sys.path.insert(0,sys.argv[1]); '
              'sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0],run_name="__main__")')
    arguments=['--design-only'] if design else ['--output',str(directory)]
    result=subprocess.run([sys.executable,'-I','-c',launcher,str(owned.parent),str(owned),*arguments],capture_output=True,timeout=300,check=False)
    need(result.returncode==0 and result.stderr==b'' and 0<len(result.stdout)<=4*1024*1024,
         'fresh isolated owned verifier failed; no fallback/cache/ELF execution')
    return decode(result.stdout)


def reconcile(directory,run_id,head,artifact_id,attempt=1):
    directory=Path(directory)
    metadata_raw={n:bounded_file(directory/n,4*1024*1024) for n in ['run.json','jobs.json','artifacts.json']}
    run,jobs,artifacts=[decode(metadata_raw[n]) for n in ['run.json','jobs.json','artifacts.json']]
    job,artifact=metadata(run,jobs,artifacts,run_id,head,artifact_id,attempt)
    original=bounded_file(directory/'original.zip',MAX_ZIP_BYTES)
    need(sha(original)==artifact['digest'][7:] and len(original)==artifact['size_in_bytes'],'original ZIP exact API digest/size')
    members=zip_members(original)
    need(export_members(directory/'export')==members,'supplied export equals original ZIP exactly')
    need(members['python.txt']==b'Python 3.13.13\n','pinned Python CI')
    need(members['rustc.txt'].startswith(b'rustc 1.98.1 ') and b'host: x86_64-unknown-linux-gnu\n' in members['rustc.txt'] and members['cargo.txt'].startswith(b'cargo 1.98.1 '),'pinned compiler/Cargo Linux host')
    need(type(TESTS) is int and TESTS>0,'stable root test count required')
    need(members['receipt-tests.stdout']==b'' and successful_tests(members['receipt-tests.stderr'],TESTS),'all actual producer checks passed without skip')
    binary=members['event/native-bin/context-diff-spike']
    need(binary.startswith(b'\x7fELF') and 4096<=len(binary)<=CONFIG['event_member_bytes'],'retained own ELF identity')
    receipt=decode(members['event/receipt.json'])
    need(receipt['environment']['github_sha']==head and receipt['environment']['github_run_id']==str(run_id),'raw native environment belongs to authenticated head/run')
    with tempfile.TemporaryDirectory(prefix='xrai-c06-original-replay-') as tmp:
        safe=Path(tmp)/'export';safe_export(members,safe)
        result=_recompute(safe/'event');design=_recompute(safe/'event',True)
    need(same(result,decode(members['collector.json'])) and same(result,decode(members['verification.json'])) and same(result,decode(members['event/verification.json'])),'complete fresh native proof recomputed, no field removal')
    need(same(design,decode(members['design.json'])),'complete frozen design recomputed')
    return {'schema':'xrai.eval.c06.native-diff.authenticated-ci-reconciliation.v1','verified':True,'data_only':True,'repository':REPOSITORY,'workflow':CONFIG['workflow'],'run_id':run_id,'run_attempt':attempt,'code_commit':head,'job_id':job['id'],'artifact_id':artifact_id,'artifact_name':CONFIG['artifact'],'artifact_zip_sha256':sha(original),'artifact_zip_bytes':len(original),'exact_zip_export_files':len(members),'metadata_sha256':{n:sha(raw) for n,raw in metadata_raw.items()},'export_file_sha256':{n:sha(raw) for n,raw in sorted(members.items())},'actual_verification':result,'design_verification':design,'reconciler_sha256':sha(Path(__file__).read_bytes()),'provider_calls':0,'admitted':False,'limits':['Authenticated original acquisition required; arbitrary JSON is not a signature.','Retained ELF never executed locally; only owned Python verifier in a fresh isolated process.','Typed diff intake and byte context only; no model token measurement or semantic planner equivalence.','No natural dossier/quota/campaign/gate is admitted by this proof.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--run-id',required=True,type=int);p.add_argument('--head',required=True);p.add_argument('--artifact-id',required=True,type=int);p.add_argument('--attempt',default=1,type=int)
    a=p.parse_args();print(json.dumps(reconcile(a.directory,a.run_id,a.head,a.artifact_id,a.attempt),indent=2,sort_keys=True))
