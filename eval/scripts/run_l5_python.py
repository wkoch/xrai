#!/usr/bin/env python3
"""Frozen Python contract probes, only disposable Linux CI execution domains."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import sys
import tempfile
import urllib.request
import zipfile

from prepare_l5_python import CASE, ROOT, MODULES, COMMIT, prepare, read_archive, sha


def wheel_files(path):
    result={}
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) > 20000:
            raise ValueError('wheel member count exceeds bound')
        for entry in archive.infolist():
            p=PurePosixPath(entry.filename)
            if p.is_absolute() or '..' in p.parts or not p.parts:
                raise ValueError('unsafe wheel path')
            if entry.is_dir():
                continue
            mode=(entry.external_attr >> 16) & 0o170000
            if mode not in {0,0o100000} or entry.filename in result or entry.file_size > 100*1024*1024:
                raise ValueError('wheel nonregular/duplicate/oversized member')
            result[entry.filename]=archive.read(entry)
    return result


def fetch(cache):
    cache.mkdir(parents=True,exist_ok=True)
    rows=json.loads((CASE/'setup.lock.json').read_text())['packages']
    for row in rows:
        path=cache/row['filename']
        if not path.exists():
            with urllib.request.urlopen(row['url'],timeout=120) as response:
                data=response.read(row['bytes']+1)
            if len(data)!=row['bytes'] or sha(data)!=row['sha256']:
                raise ValueError('download wheel fingerprint differs')
            path.write_bytes(data)
        if path.stat().st_size != row['bytes'] or sha(path.read_bytes())!=row['sha256']:
            raise ValueError('cached wheel differs')
    return rows


def materialize(destination,side):
    capture=prepare(False)
    files=read_archive(CASE/'sources/base.tar.gz')
    destination.mkdir(parents=True,exist_ok=False)
    for name,data in files.items():
        path=destination/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
    if side=='reference':
        for name in MODULES:
            data=(CASE/'oracles/reference-sources'/name).read_bytes()
            if sha(data)!=capture['reference_sources_sha256'][name]:
                raise ValueError('reference frozen source differs')
            (destination/name).write_bytes(data)
    oracle=(CASE/'oracles/probe.py').read_bytes()
    (destination/'.xrai-probe.py').write_bytes(oracle)
    return {'side':side,'commit':COMMIT,'full_source_archive_sha256':capture['archive_sha256'],
            'source_modules_sha256':{p:sha((destination/p).read_bytes()) for p in MODULES},
            'oracle_sha256':sha(oracle),'dependency_lock_sha256':capture['dependency_lock_sha256']}


def bootstrap(destination,cache):
    """Read-only wheel data extraction; no pip, build hooks or imported upstream."""
    lock=json.loads((CASE/'setup.lock.json').read_text())
    if platform.system()!='Linux' or platform.machine()!='x86_64' or platform.python_version()!=lock['python']:
        raise ValueError('bootstrap requires pinned Linux x86_64 Python '+lock['python'])
    dependencies=destination/'.xrai-deps'
    dependencies.mkdir()
    rows=[]
    extensions={}
    for row in lock['packages']:
        path=cache/row['filename']
        if sha(path.read_bytes())!=row['sha256'] or path.stat().st_size!=row['bytes']:
            raise ValueError('wheel changed after fetch')
        files=wheel_files(path)
        for name,data in files.items():
            parts=PurePosixPath(name).parts
            if row['package']=='scikit-learn':
                # Source Python is canonical. Only version-matched compiled
                # extension modules and their bundled shared libraries are seeded.
                if parts[0]=='sklearn' and name.endswith('.so'):
                    target=destination/name
                    if target.exists():
                        raise ValueError('extension would overwrite captured source')
                    extensions[name]=sha(data)
                elif parts[0]=='scikit_learn.libs' and '.so' in parts[-1]:
                    target=destination/name
                    extensions[name]=sha(data)
                else:
                    continue
            else:
                target=dependencies/name
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                raise ValueError('dependency files collide')
            target.write_bytes(data)
        rows.append({**row,'source_python_extracted':row['package']!='scikit-learn'})
    runtime=destination/'.xrai-python'
    (runtime/'bin').mkdir(parents=True)
    (runtime/'lib').mkdir()
    executable=Path(sys.executable).resolve()
    shutil.copy2(executable,runtime/'bin/python3')
    stdlib=Path(sys.base_prefix)/'lib/python3.11'
    shutil.copytree(stdlib,runtime/'lib/python3.11',ignore=shutil.ignore_patterns('site-packages','__pycache__'),symlinks=False)
    for library in (Path(sys.base_prefix)/'lib').glob('libpython3.11.so*'):
        if library.is_file():
            shutil.copy2(library,runtime/'lib'/library.name)
    runtime_files={str(p.relative_to(runtime)):sha(p.read_bytes()) for p in sorted(runtime.rglob('*')) if p.is_file()}
    if any(p.is_symlink() for p in runtime.rglob('*')):
        raise ValueError('Python runtime symlink escaped closure')
    return {'python_version':platform.python_version(),'python_executable_sha256':sha(executable.read_bytes()),
            'runtime_files_sha256':runtime_files,'dependency_wheels':rows,'compiled_extensions_sha256':extensions,
            'bootstrap_method':'source checkout plus exact-version wheel compiled extensions; wheel Python excluded',
            'source_python_overwritten':False,'network_during_probe':False}


TEST_IDS = {
    'requirement': {
        '__main__.Contract.test_transformer_dense_and_masked',
        '__main__.Contract.test_feature_union_pipeline_and_context',
        '__main__.Contract.test_column_transformer_pipeline_and_context',
    },
    'regression': {
        '__main__.Regression.test_default_dense_and_context_restored',
        '__main__.Regression.test_sparse_rejection_and_invalid_mode',
    },
}


def verify_behavior(report, run, side, name, expected_origins):
    expected_exit = 1 if side == 'base' and name == 'requirement' else 0
    if not report or run.get('execution_status') not in {'ok', 'error'} or run.get('exit_code') != expected_exit:
        return False
    for stream in ('stdout', 'stderr'):
        record=run.get(stream,{})
        if record.get('truncated') is not False or record.get('captured_bytes') != record.get('observed_bytes'):
            return False
        try:
            raw=base64.b64decode(record['base64'],validate=True)
        except (KeyError,ValueError):
            return False
        if len(raw)!=record['captured_bytes'] or sha(raw)!=record.get('sha256'):
            return False
    rows=report.get('tests',[])
    ids=[r.get('id') for r in rows]
    expected_status='error' if expected_exit else 'passed'
    if report.get('phase')!=name or report.get('tests_run')!=len(TEST_IDS[name]) or len(ids)!=len(set(ids)) or set(ids)!=TEST_IDS[name]:
        return False
    if report.get('success') != (expected_exit==0) or any(r.get('status')!=expected_status for r in rows):
        return False
    if expected_exit and not all('output config must be' in r.get('error','') and 'got masked' in r['error'] for r in rows):
        return False
    return report.get('module_origins')==expected_origins


def probe(workspace,side,output,timeout,bootstrap_receipt):
    sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
    from runner import execute
    from supervisor import verify_receipt, confirmed_receipt
    output.mkdir(parents=True,exist_ok=False)
    (output/'bootstrap.json').write_text(json.dumps(bootstrap_receipt,indent=2)+'\n')
    materialized=json.loads((workspace/'.xrai-materialization.json').read_text())
    pinned_paths=list(read_archive(CASE/'sources/base.tar.gz'))+['.xrai-probe.py','.xrai-materialization.json']
    before={p:sha((workspace/p).read_bytes()) for p in sorted(pinned_paths)}
    phases=[]
    for name,count in [('requirement',3),('regression',2)]:
        report_name='.xrai-'+name+'.json'
        command=['/usr/bin/env','HOME=/workspace','TMPDIR=/tmp','PYTHONHOME=/workspace/.xrai-python',
                 'PYTHONPATH=/workspace:/workspace/.xrai-deps','LD_LIBRARY_PATH=/workspace/.xrai-python/lib',
                 'OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','PYTHONDONTWRITEBYTECODE=1',
                 '/workspace/.xrai-python/bin/python3','/workspace/.xrai-probe.py',name,'--report',report_name]
        run=execute(command,workspace,timeout=timeout,output_limit=1024*1024,phase='qualification-'+name,arbitrary_agent=True)
        (output/(name+'-harness.json')).write_text(json.dumps(run,indent=2)+'\n')
        verify_receipt(run)
        teardown=confirmed_receipt(run) and run['eligible_for_agent_run']
        if not teardown:
            # Never remove or reuse an execution domain whose shutdown is not
            # confirmed. Preserve its workspace for containment investigation.
            (output/'unconfirmed-domain.json').write_text(json.dumps({'workspace':str(workspace),'phase':name,'preserved':True},indent=2)+'\n')
            raise RuntimeError('execution-domain teardown unconfirmed; workspace preserved')
        path=workspace/report_name
        report=json.loads(path.read_text()) if path.is_file() else None
        if report:
            shutil.copyfile(path,output/(name+'-tests.json'))
        expected_exit=1 if side=='base' and name=='requirement' else 0
        expected_origins={name:{'path':'/workspace/'+path,'sha256':materialized['source_modules_sha256'][path]}
                          for name,path in zip(['sklearn.utils._set_output','sklearn.pipeline','sklearn.compose._column_transformer'],MODULES)}
        behavior=verify_behavior(report,run,side,name,expected_origins)
        phases.append({'name':name,'expected_exit':expected_exit,'actual_exit':run['exit_code'],'tests_expected':count,
                       'teardown_verified':teardown,'behavioral_result_verified':behavior,
                       'verified':bool(teardown and behavior and run['exit_code']==expected_exit),
                       'report_sha256':sha(path.read_bytes()) if path.is_file() else None,
                       'harness_receipt':name+'-harness.json','test_report':name+'-tests.json' if path.is_file() else None,
                       'execution_status':run['execution_status']})
    after={p:sha((workspace/p).read_bytes()) for p in before}
    receipt={'schema_version':'xrai.eval.l5.python.probe.v1','side':side,'materialization':materialized,
             'executor_source_sha256':sha(Path(__file__).read_bytes()),'bootstrap_source_sha256':sha(Path(__file__).read_bytes()),
             'phases':phases,'source_and_setup_before_sha256':before,'source_and_setup_after_sha256':after,
             'source_and_setup_unchanged':before==after,'qualified':False,'admitted':False,
             'verified_behavioral_pair_side':before==after and all(p['verified'] for p in phases)}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['fetch','run'])
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--timeout',type=float,default=300)
    args=parser.parse_args()
    if args.mode=='fetch':
        print(json.dumps(fetch(args.cache),indent=2));return
    if platform.system()!='Linux' or os.environ.get('GITHUB_ACTIONS')!='true':
        raise ValueError('upstream probes restricted to disposable Linux GitHub CI')
    if not args.output or args.timeout<=0 or args.timeout>600:
        raise ValueError('fresh output and bounded timeout required')
    args.output.mkdir(parents=True,exist_ok=False)
    prepare(False)
    fetch(args.cache)
    sides=[]
    for side in ['base','reference']:
        temp=Path(tempfile.mkdtemp(prefix='xrai-l5-python-'))
        workspace=temp/'checkout'
        materialized=materialize(workspace,side)
        (workspace/'.xrai-materialization.json').write_text(json.dumps(materialized,indent=2)+'\n')
        boot=bootstrap(workspace,args.cache)
        result=probe(workspace,side,args.output/side,args.timeout,boot)
        sides.append(result)
        # probe returns only after both fresh domains have confirmed teardown.
        shutil.rmtree(temp)
    receipt={'schema_version':'xrai.eval.l5.python.pair.v1','sides':[{'side':s['side'],'verified':s['verified_behavioral_pair_side']} for s in sides],
             'verified_behavioral_pair':all(s['verified_behavioral_pair_side'] for s in sides),
             'real_A_to_B_pending':True,'admitted':False,'qualified':False,'comparative_runs_allowed':False}
    (args.output/'pair.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
    if not receipt['verified_behavioral_pair']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
