"""Reconcile original authenticated C05 API/ZIP as data; never execute retained ELF.

Acquisition authenticity is the caller's authenticated GitHub operation. Arbitrary
API JSON is not a signature. Owned Python verifiers run in fresh isolated children;
this module cannot replace the actual pinned tokenizer with an injected counter.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from reconcile_tsjs_ci import safe_export, directory_members

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = 'wkoch/xrai'
MAX_ZIP_BYTES = 128 * 1024 * 1024
PROFILES = {
    'tokens': {
        'workflow':'.github/workflows/l5-lexical-token.yml',
        'job':'C05 lexical whole-wire tokens','artifact':'c05-lexical-whole-wire-tokens',
        'steps':['Run actions/checkout@v6','Run actions/setup-python@v6','Install pinned measurement tooling',
                 'Verify frozen lexical token protocol','Measure frozen lexical whole-wire envelopes',
                 'Recompute exact controlled token receipts','Reject adversarial controlled token receipts',
                 'Preserve exact lexical token evidence'],
        'top':{'design.json','python.txt','packages.txt','collector.json','verification.json','receipt-tests.stdout','receipt-tests.stderr'},
        'verifier':'eval/context/lexical-token-v1/verifier.py','max_members':1024,
        'event_member_bytes':512 * 1024,'top_member_bytes':64 * 1024 * 1024,'total_bytes':96 * 1024 * 1024,'tests':28,
    },
    'tsjs': {
        'workflow':'.github/workflows/l5-tsjs-session.yml',
        'job':'C05 captured TSJS semantic session','artifact':'c05-tsjs-semantic-session',
        'steps':['Run actions/checkout@v6','Run actions/setup-python@v6','Install pinned verification tooling',
                 'Verify frozen TSJS session design','Build owned TSJS semantic session',
                 'Prove frozen live TSJS semantic update','Recompute complete TSJS session evidence',
                 'Reject adversarial TSJS session substitutions','Preserve exact TSJS semantic session evidence'],
        'top':{'design.json','python.txt','rustc.txt','cargo.txt','collector.json','verification.json','receipt-tests.stdout','receipt-tests.stderr'},
        'verifier':'eval/scripts/verify_tsjs_semantic_session.py','max_members':64,
        'event_member_bytes':32 * 1024 * 1024,'top_member_bytes':32 * 1024 * 1024,'total_bytes':128 * 1024 * 1024,'tests':45,
    },
}
LIFECYCLE = {'Set up job','Post Run actions/setup-python@v6','Post Run actions/checkout@v6','Complete job'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def config(profile):
    need(type(profile) is str and profile in PROFILES, 'explicit known C05 profile')
    return PROFILES[profile]


def decode(raw):
    def pairs(items):
        out = {}
        for key,value in items:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def reject(value):
        raise ValueError('nonfinite JSON ' + value)
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=reject)


def same(a,b):
    return json.dumps(a,sort_keys=True,separators=(',',':'),allow_nan=False) == json.dumps(b,sort_keys=True,separators=(',',':'),allow_nan=False)


def metadata(profile,run,jobs,artifacts,run_id,head,artifact_id,attempt=1):
    p = config(profile)
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


def expected_files(profile):
    p = config(profile)
    if profile == 'tokens':
        event = {'preregistered.json','evaluation.json'} | {f'baselines/{i:03}.json' for i in range(32)} | {f'records/{i:03}.json' for i in range(320)}
    else:
        event = {'receipt.json','verification.json','native-bin/tsjs-semantic-session'} | {
            'inputs/' + n for n in ['protocol.json','freeze-before-session.json','input-a.json','input-b.json','input-invalid.json']} | {
            side + '/' + n for side in ['incremental','rebuild'] for n in ['transcript.jsonl','stdout.jsonl','stderr.bin','process.json']}
    return p['top'] | {'event/' + name for name in event}


def zip_members(raw,profile):
    p = config(profile)
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
    need(set(result) == expected_files(profile), 'exact profile top/event original ZIP closure')
    return result


def bounded_file(path,limit):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit, 'bounded ordinary original metadata/ZIP file')
    raw = path.read_bytes(); need(len(raw) <= limit, 'file grew beyond bound')
    return raw


def export_members(directory,profile):
    p = config(profile)
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


def _recompute(profile,directory,design=False):
    """Fresh owned Python process, no cached/injected module or supplied verifier path."""
    p = config(profile)
    if profile == 'tokens':
        need(sys.version_info[:3] == (3,13,13), 'actual fixed Python 3.13.13 required for token recomputation')
    owned = ROOT / p['verifier']
    launcher = ('import runpy,sys; sys.path.insert(0,sys.argv[1]); '
                'sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0],run_name="__main__")')
    arguments = ['--design-only'] if design else ['--output',str(directory)]
    command = [sys.executable,'-I','-c',launcher,str(owned.parent),str(owned),*arguments]
    completed = subprocess.run(command,capture_output=True,timeout=300,check=False)
    need(completed.returncode == 0 and completed.stderr == b'' and 0 < len(completed.stdout) <= 4 * 1024 * 1024,
         'isolated actual owned verifier failed (no fallback, fake counter or cached result)')
    return decode(completed.stdout)


def reconcile(directory,profile,run_id,head,artifact_id,attempt=1):
    p = config(profile); directory = Path(directory)
    names = ['run.json','jobs.json','artifacts.json']
    raw_metadata = {name:bounded_file(directory / name,4 * 1024 * 1024) for name in names}
    run,jobs,artifacts = [decode(raw_metadata[n]) for n in names]
    job,artifact = metadata(profile,run,jobs,artifacts,run_id,head,artifact_id,attempt)
    original = bounded_file(directory / 'original.zip',MAX_ZIP_BYTES)
    need(sha(original) == artifact['digest'][7:] and len(original) == artifact['size_in_bytes'], 'original ZIP exact API digest/size')
    members = zip_members(original,profile)
    need(export_members(directory / 'export',profile) == members, 'supplied export equals original ZIP exactly')
    need(members['python.txt'] == b'Python 3.13.13\n', 'actual pinned Python CI toolchain')
    tests = members['receipt-tests.stderr'].decode('utf-8')
    need(members['receipt-tests.stdout'] == b'' and re.search(rf'Ran {p["tests"]} tests in [0-9.]+s\n\nOK\n',tests) and
         'skipped' not in tests and 'expected failure' not in tests, 'all actual-profile adversarial checks ran with no skips')
    if profile == 'tokens':
        preregistered = decode(members['event/preregistered.json'])
        need(same(preregistered['environment'],{'repository':REPOSITORY,'head_sha':head,'run_id':str(run_id),'run_attempt':str(attempt)}),
             'token measurement raw environment belongs to authenticated head/run/attempt')
        packages = members['packages.txt'].decode('utf-8').splitlines()
        need(len(packages) == len(set(packages)) and 'tiktoken==0.12.0' in packages and 'regex==2026.9.29' in packages,
             'actual pinned tokenizer packages CI receipt')
    else:
        need(members['rustc.txt'].startswith(b'rustc 1.98.1 ') and b'host: x86_64-unknown-linux-gnu\n' in members['rustc.txt'] and
             members['cargo.txt'].startswith(b'cargo 1.98.1 '), 'actual pinned Rust compiler/Cargo and Linux host')
        receipt = decode(members['event/receipt.json'])
        need(receipt['environment']['github_sha'] == head and receipt['environment']['github_run_id'] == str(run_id), 'session native environment belongs to authenticated run/head')
        binary = members['event/native-bin/tsjs-semantic-session']
        need(binary.startswith(b'\x7fELF') and 4096 <= len(binary) <= p['event_member_bytes'], 'retained owned ELF byte identity')
    # Consume freshly extracted bytes from the bounded original ZIP, never mutable cached export.
    with tempfile.TemporaryDirectory(prefix='xrai-c05-ci-reconcile-') as temporary:
        safe = Path(temporary) / 'export'; safe_export(members,safe)
        recomputed = _recompute(profile,safe / 'event')
        design = _recompute(profile,safe / 'event',design=True)
    need(same(recomputed,decode(members['collector.json'])) and same(recomputed,decode(members['verification.json'])),
         'full fresh actual recomputation equals collector and verification')
    need(same(design,decode(members['design.json'])), 'full frozen design receipt recomputed')
    if profile == 'tsjs':
        need(same(recomputed,decode(members['event/verification.json'])), 'session retained native verification complete equality')
    return {'schema':'xrai.eval.c05.authenticated-ci-reconciliation.v1','verified':True,'data_only':True,'profile':profile,
            'repository':REPOSITORY,'workflow':p['workflow'],'run_id':run_id,'run_attempt':attempt,'code_commit':head,
            'job_id':job['id'],'artifact_id':artifact_id,'artifact_name':p['artifact'],'artifact_zip_sha256':sha(original),
            'artifact_zip_bytes':len(original),'exact_zip_export_files':len(members),
            'metadata_sha256':{n:sha(raw_metadata[n]) for n in names},
            'export_file_sha256':{n:sha(raw) for n,raw in sorted(members.items())},'actual_verification':recomputed,
            'design_verification':design,'reconciler_sha256':sha(Path(__file__).read_bytes()),'global_admission':False,
            'limits':['Caller authenticated original API/ZIP acquisition is required; arbitrary JSON is not a cryptographic signature.',
                      'Original retained ELF is hashed as data and never executed by this reconciler.',
                      'Fresh isolated owned Python recomputes actual fixed L4 tokens or complete session snapshots; no fake measurement fallback.',
                      'No natural task/quota credit, paid provider run, campaign or gate closure.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path); parser.add_argument('--profile',choices=PROFILES,required=True)
    parser.add_argument('--run-id',type=int,required=True); parser.add_argument('--head',required=True)
    parser.add_argument('--artifact-id',type=int,required=True); parser.add_argument('--attempt',type=int,default=1)
    args = parser.parse_args()
    print(json.dumps(reconcile(args.directory,args.profile,args.run_id,args.head,args.artifact_id,args.attempt),indent=2,sort_keys=True))
