#!/usr/bin/env python3
"""DATA-ONLY reconciliation of a Python behavioral export with frozen local inputs.

No captured upstream module, receipt command, build hook or native binary executes.
Archive/API authentication is the caller's responsibility; bootstrap native bytes
are reported in manifests, not retained in this export and not independently read.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
CASE = ROOT / 'eval/qualification/l5-real/python'
EXPECTED_PREPARER = '4b6277c7d974e192ca123410accd27bedb9ed870ab09b102acb1c7074193da45'
EXPECTED_EXECUTOR = 'dcae5c976c6281fc6174376db4abe765634110628c9b06ec4546d5e78a16076f'
EXPECTED_ORACLE = 'edbbdb303732bb799395caed5e094750fd0daffff00e39a9effbec5ef1544837'
SIDES = ('base', 'reference')
PHASES = ('requirement', 'regression')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pairs(rows):
    result = {}
    for key, value in rows:
        need(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def load(path):
    need(path.is_file() and not path.is_symlink(), 'missing/nonregular export: ' + str(path))
    return json.loads(path.read_text(), object_pairs_hook=pairs)


def digest_map(rows, message):
    need(isinstance(rows, dict) and bool(rows), message)
    for name, digest in rows.items():
        p = PurePosixPath(name)
        need(not p.is_absolute() and '..' not in p.parts and str(p) == name, message + ': unsafe path')
        need(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), message + ': invalid digest')


def verify(directory: Path) -> dict:
    directory = Path(directory)
    expected_files = {'pair.json'} | {f'{side}/{name}' for side in SIDES for name in
        ['receipt.json', 'bootstrap.json', 'requirement-harness.json', 'requirement-tests.json',
         'regression-harness.json', 'regression-tests.json']}
    actual = set()
    for path in directory.rglob('*'):
        need(not path.is_symlink(), 'export symlink prohibited')
        if path.is_dir():
            continue
        need(path.is_file(), 'export nonregular member')
        actual.add(path.relative_to(directory).as_posix())
    need(actual == expected_files, 'export exact 13-file closure mismatch')
    # Only owned, reviewed verifier functions are imported; no upstream imports.
    sys.path.insert(0, str(ROOT / 'eval/scripts'))
    sys.path.insert(0, str(ROOT / 'crates/xrai-eval/harness'))
    import prepare_l5_python as preparation
    import run_l5_python as producer
    from supervisor import verify_receipt, confirmed_receipt
    need(sha((ROOT/'eval/scripts/run_l5_python.py').read_bytes()) == EXPECTED_EXECUTOR,
         'frozen executor changed; explicit verifier review required')
    need(sha((CASE/'oracles/probe.py').read_bytes()) == EXPECTED_ORACLE,
         'frozen oracle changed; explicit verifier review required')
    need(sha((ROOT/'eval/scripts/prepare_l5_python.py').read_bytes()) == EXPECTED_PREPARER,
         'frozen preparer changed; explicit verifier review required')
    capture = preparation.prepare(False)
    need(capture['commit'] == '156ef141f3b270edb06c8ae9af37c55253c0aabe' and
         capture['archive_sha256'] == '70f9d47a3aba04faf22b150075283b0a4311f8b665bf2ab3e447cd5c3685b70b',
         'frozen complete source pin differs')
    source_files = preparation.read_archive(CASE/'sources/base.tar.gz')
    lock = load(CASE/'setup.lock.json')
    pair = load(directory/'pair.json')
    need(pair.get('schema_version') == 'xrai.eval.l5.python.pair.v1', 'wrong pair schema')
    need(pair.get('admitted') is False and pair.get('qualified') is False and pair.get('comparative_runs_allowed') is False,
         'behavioral export cannot assert global qualification')
    need(pair.get('sides') == [{'side':s,'verified':True} for s in SIDES] and pair.get('verified_behavioral_pair') is True,
         'pair producer summary disagrees')
    domains, namespaces, summaries, bootstrap_records = [], [], [], []
    for side in SIDES:
        report = load(directory/side/'receipt.json')
        need(report.get('schema_version') == 'xrai.eval.l5.python.probe.v1' and report.get('side') == side,
             'wrong side schema/identity')
        need(report.get('executor_source_sha256') == EXPECTED_EXECUTOR and report.get('bootstrap_source_sha256') == EXPECTED_EXECUTOR,
             'executor/bootstrap source pin differs')
        expected_sources = dict(source_files)
        if side == 'reference':
            expected_sources.update({p:(CASE/'oracles/reference-sources'/p).read_bytes() for p in preparation.MODULES})
        materialization = {'side':side, 'commit':preparation.COMMIT,
                          'full_source_archive_sha256':capture['archive_sha256'],
                          'source_modules_sha256':{p:sha(expected_sources[p]) for p in preparation.MODULES},
                          'oracle_sha256':EXPECTED_ORACLE,
                          'dependency_lock_sha256':capture['dependency_lock_sha256']}
        need(report.get('materialization') == materialization, 'materialization source/oracle/setup pin differs')
        expected_inventory = {p:sha(v) for p,v in expected_sources.items()}
        expected_inventory['.xrai-probe.py'] = EXPECTED_ORACLE
        expected_inventory['.xrai-materialization.json'] = sha((json.dumps(materialization,indent=2)+'\n').encode())
        need(report.get('source_and_setup_before_sha256') == expected_inventory,
             'full baseline/reference source inventory before differs')
        need(report.get('source_and_setup_after_sha256') == expected_inventory and report.get('source_and_setup_unchanged') is True,
             'full source/setup/oracle changed during probes')
        need(report.get('admitted') is False and report.get('qualified') is False and report.get('verified_behavioral_pair_side') is True,
             'side summary/qualification inconsistent')
        boot = load(directory/side/'bootstrap.json')
        need(boot.get('python_version') == lock['python'] == '3.11.13', 'Python runtime version differs')
        need(boot.get('dependency_wheels') == [{**row,'source_python_extracted':row['package'] != 'scikit-learn'} for row in lock['packages']],
             'wheel pins/data extraction policy differs')
        need(boot.get('bootstrap_method') == 'source checkout plus exact-version wheel compiled extensions; wheel Python excluded'
             and boot.get('source_python_overwritten') is False and boot.get('network_during_probe') is False,
             'bootstrap/source policy differs')
        runtime = boot.get('runtime_files_sha256')
        extensions = boot.get('compiled_extensions_sha256')
        digest_map(runtime,'runtime reported manifest invalid')
        digest_map(extensions,'extension reported manifest invalid')
        need(runtime.get('bin/python3') == boot.get('python_executable_sha256'), 'runtime executable digest inconsistent')
        need(runtime.get('lib/libpython3.11.so') == runtime.get('lib/libpython3.11.so.1.0') and
             'lib/python3.11/os.py' in runtime and 'lib/python3.11/json/__init__.py' in runtime and
             any(p.startswith('lib/python3.11/lib-dynload/_ssl.') for p in runtime), 'runtime closure minimum absent')
        need(all((p.startswith('sklearn/') and p.endswith('.cpython-311-x86_64-linux-gnu.so')) or
                 (p.startswith('scikit_learn.libs/') and '.so' in PurePosixPath(p).name) for p in extensions),
             'extension bootstrap injected Python/non-extension source')
        need(any(p.startswith('sklearn/__check_build/') for p in extensions) and any(p.startswith('scikit_learn.libs/') for p in extensions),
             'compiled extension/bootstrap shared library missing')
        bootstrap_records.append(boot)
        expected_origins = {name:{'path':'/workspace/'+p,'sha256':sha(expected_sources[p])}
                            for name,p in zip(['sklearn.utils._set_output','sklearn.pipeline','sklearn.compose._column_transformer'], preparation.MODULES)}
        need(isinstance(report.get('phases'),list) and [p.get('name') for p in report['phases']] == list(PHASES), 'phase sequence differs')
        for phase, summary in zip(PHASES, report['phases']):
            harness_path = directory/side/(phase+'-harness.json')
            tests_path = directory/side/(phase+'-tests.json')
            harness, tests = load(harness_path), load(tests_path)
            verify_receipt(harness)
            need(confirmed_receipt(harness) and harness.get('eligible_for_agent_run') is True and
                 harness.get('cleanup_status') == 'confirmed' and harness.get('containment') == 'linux_pid_namespace' and
                 harness.get('sandbox') == 'Linux bubblewrap', 'namespace teardown not confirmed/eligible')
            command = ['/usr/bin/env','HOME=/workspace','TMPDIR=/tmp','PYTHONHOME=/workspace/.xrai-python',
                       'PYTHONPATH=/workspace:/workspace/.xrai-deps','LD_LIBRARY_PATH=/workspace/.xrai-python/lib',
                       'OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','PYTHONDONTWRITEBYTECODE=1',
                       '/workspace/.xrai-python/bin/python3','/workspace/.xrai-probe.py',phase,'--report','.xrai-'+phase+'.json']
            need(harness.get('command') == command and harness.get('phase') == 'qualification-'+phase,
                 'namespace command/environment/phase differs')
            expected_exit = 1 if side == 'base' and phase == 'requirement' else 0
            need(harness.get('execution_status') == ('error' if expected_exit else 'ok') and
                 harness.get('status') == harness.get('execution_status') and harness.get('diagnostic') is None,
                 'execution/infrastructure status differs')
            need(isinstance(harness.get('elapsed_seconds'),(int,float)) and 0 <= harness['elapsed_seconds'] <= 310,
                 'bounded probe elapsed time exceeded')
            need(producer.verify_behavior(tests,harness,side,phase,expected_origins), 'exact individual behavior/stream/origin reconciliation failed')
            stderr = base64.b64decode(harness['stderr']['base64'],validate=True).decode('utf-8')
            need(base64.b64decode(harness['stdout']['base64'],validate=True) == b'', 'unexpected oracle stdout')
            for test in tests['tests']:
                need(test['id'].split('.')[-1] in stderr, 'individual test absent from raw unittest stream')
                if expected_exit:
                    error = test['error']
                    final_line = error.rstrip().splitlines()[-1]
                    need(final_line.startswith('ValueError: output config must be') and final_line.endswith('got masked') and
                         error in stderr, 'baseline failure is not exact ValueError in preserved stderr')
            count = len(producer.TEST_IDS[phase])
            need('Ran '+str(count)+' tests' in stderr and ('FAILED (errors=3)' if expected_exit else '\nOK\n') in stderr,
                 'raw unittest summary differs')
            expected_summary = {'name':phase,'expected_exit':expected_exit,'actual_exit':expected_exit,'tests_expected':count,
                                'teardown_verified':True,'behavioral_result_verified':True,'verified':True,
                                'report_sha256':sha(tests_path.read_bytes()), 'harness_receipt':phase+'-harness.json',
                                'test_report':phase+'-tests.json','execution_status':harness['execution_status']}
            need(summary == expected_summary, 'phase summary differs from independently recomputed bytes')
            domains.append(harness['domain_id'])
            namespaces.append(harness['termination_evidence']['pid_namespace'])
            summaries.append({'side':side,'phase':phase,'tests':count,'passed':0 if expected_exit else count,
                              'expected_contract_errors':count if expected_exit else 0,'domain_id':harness['domain_id'],
                              'namespace':harness['termination_evidence']['pid_namespace'],
                              'report_sha256':sha(tests_path.read_bytes()),'harness_sha256':sha(harness_path.read_bytes())})
    need(len(set(domains)) == 4 and len(set(namespaces)) == 4, 'four fresh namespace/domain identities required')
    need(bootstrap_records[0] == bootstrap_records[1], 'baseline/reference runtime/compiled/dependency bootstrap differs')
    return {'schema_version':'xrai.eval.l5.python.export_verified.v1','verified_behavioral_pair':True,
            'verified':True,'input_sha256':capture['input_sha256'],
            'commit':preparation.COMMIT,'source_archive_sha256':capture['archive_sha256'],'executor_source_sha256':EXPECTED_EXECUTOR,
            'oracle_sha256':EXPECTED_ORACLE,'full_source_files_per_side':len(source_files),
            'production_files':capture['production_files'],'nonempty_production_lines':capture['production_nonempty_lines'],
            'dependency_lock_sha256':capture['dependency_lock_sha256'],'reported_python_executable_sha256':bootstrap_records[0]['python_executable_sha256'],
            'reported_runtime_files':len(bootstrap_records[0]['runtime_files_sha256']),
            'reported_compiled_extensions':len(bootstrap_records[0]['compiled_extensions_sha256']),
            'fresh_confirmed_domains':4,'phases':summaries,
            'file_sha256':{p:sha((directory/p).read_bytes()) for p in sorted(expected_files)},
            'limits':['API/run/commit/job/ZIP authentication delegated to caller',
                      'bootstrap runtime and native extension binary bytes not retained in this export: only consistent reported hashes, shape, pins and cross-side identity verified',
                      'receipt evidence reverified, not independent historical process/workspace observation',
                      'three controlled requirements and two regressions; no full upstream suite or comparative agent run claim',
                      'individual contract case behavioral evidence does not close global corpus quotas or external incremental quota'],
            'qualified':False,'admitted':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    print(json.dumps(verify(parser.parse_args().directory),indent=2))
