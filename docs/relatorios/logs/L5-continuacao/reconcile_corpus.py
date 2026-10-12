#!/usr/bin/env python3
"""Data-only reconciliation of exported Rust/JS behavioral evidence.

Reads JSON, logs and frozen local pins. Never imports a producer, invokes a
command, extracts an archive to disk, or executes receipt/namespace code.
This verifies bounded evidence consistency, not competitive admission.
"""
import argparse
import base64
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[4]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Reader:
    def __init__(self, root, overrides=None):
        self.root = Path(root).resolve()
        self.overrides = overrides or {}
        self.hashes = {}

    def raw(self, name):
        rel = PurePosixPath(name)
        require(not rel.is_absolute() and '..' not in rel.parts, 'unsafe relative evidence path')
        path = self.root / str(rel)
        require(path.resolve().is_relative_to(self.root), 'evidence path escapes export')
        require(not any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(self.root)), 'symlink evidence path')
        require(path.is_file() and path.stat().st_size <= 64*1024*1024, 'missing or oversized evidence: '+name)
        data = self.overrides.get(name, path.read_bytes())
        self.hashes[name] = digest(data)
        return data

    def json(self, name):
        raw = self.raw(name)
        require(len(raw) <= 16*1024*1024, 'oversized JSON evidence')
        return json.loads(raw)


def source(name):
    path = ROOT / name
    require(path.is_file(), 'missing frozen source '+name)
    return path.read_bytes()


def source_json(name):
    return json.loads(source(name))


def hex_digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def streams(row, reader, prefix=None):
    result = []
    for name in ['stdout', 'stderr']:
        stream = row[name]
        raw = base64.b64decode(stream['base64'], validate=True)
        require(stream['truncated'] is False and stream['captured_bytes'] == stream['observed_bytes'] == len(raw), 'truncated or mismatched harness stream')
        require(stream['sha256'] == digest(raw), 'harness stream digest mismatch')
        if prefix is not None:
            require(reader.raw(prefix+'.'+name+'.log') == raw, 'exported harness log differs from captured bytes')
        result.append(raw.decode('utf-8', 'replace'))
    return '\n'.join(result)


def contained(row, exit_code, reader, prefix=None, timeout=600):
    require(row['exit_code'] == exit_code and type(row['exit_code']) is int, 'unexpected behavioral exit')
    expected = 'ok' if exit_code == 0 else 'error'
    require(row['status'] == row['execution_status'] == expected and row['diagnostic'] is None, 'timeout, teardown or infrastructure error')
    require(0 <= row['elapsed_seconds'] <= timeout, 'command deadline exceeded')
    require(row['sandbox'] == 'Linux bubblewrap' and row['containment'] == 'linux_pid_namespace' and row['cleanup_status'] == 'confirmed', 'containment/cleanup not confirmed')
    identity = uuid.UUID(row['domain_id'])
    require(str(identity) == row['domain_id'] and identity.version == 4, 'invalid namespace domain')
    ev = row['termination_evidence']
    require(type(ev['init_pid']) is int and 1 < ev['init_pid'] < 2**31 and re.fullmatch(r'pid:\[[1-9][0-9]*\]', ev['pid_namespace']) is not None, 'invalid namespace/init evidence')
    require(all(ev.get(k) is True for k in ['init_held_before_pin','pidfd_exit_observed','wrapper_reaped']), 'teardown observation absent')
    mapping = ev['user_namespace_mapping']
    require(set(mapping) == {'uid','gid','count','setgroups'} and all(type(mapping[k]) is int and 0 <= mapping[k] < 2**32-1 for k in ['uid','gid']) and type(mapping['count']) is int and mapping['count'] == 1 and mapping['setgroups'] == 'deny', 'invalid user namespace mapping')
    require(row['eligible_for_agent_run'] is True, 'namespace command ineligible')
    return streams(row, reader, prefix)


def preparation(reader, path):
    row = reader.json(path+'.json')
    require(row['exit_code'] == 0 and row['error'] is None and row['cleanup_status'] == 'child_reaped_pipes_closed', 'preparation failed or incomplete')
    require(row['elapsed_seconds'] <= row['timeout_seconds'] == 600, 'preparation timeout')
    for name in ['stdout','stderr']:
        record = row['streams'][name]
        # Export logs are relocated. Never follow the producer's host path.
        raw = reader.raw(path+'.'+name+'.log')
        require(record['truncated'] is False and record['captured_bytes'] == record['observed_bytes'] == len(raw), 'preparation stream incomplete')
        require(record['captured_sha256'] == record['observed_sha256'] == digest(raw), 'preparation stream digest mismatch')
    return row


def rust(reader):
    root = 'eval/qualification/l5-real/rust/'
    summary = reader.json('rust/summary.json')
    require(summary['runner_sha256'] == digest(source('eval/scripts/run_real_rust_probes.py')) and summary['bounded_process_runner_sha256'] == digest(source('eval/scripts/run_vertical_probes.py')), 'Rust producer source differs from frozen files')
    require(summary['vertical_pair_verified'] is True and summary['admitted'] is False and summary['competitive_runs_allowed'] is False, 'Rust summary result/admission invalid')
    require(summary['platform'].startswith('Linux-') and summary['machine'] == 'x86_64' and summary['guard_is_containment'] is False, 'Rust platform/domain invalid')
    native = summary['native_compilers']; tools = summary['toolchain_copy']
    require(tools['copies_no_hardlinks'] is True and type(tools['file_count']) is int and tools['file_count'] > 0 and all(hex_digest(tools[k]) for k in ['cargo_sha256','rustc_sha256']), 'Rust toolchain copy provenance invalid')
    require(all(re.fullmatch(r'/usr/bin/[A-Za-z0-9_.+-]+', native[k]) and hex_digest(native[k+'_sha256']) for k in ['cc','cxx']), 'Rust native compiler provenance invalid')
    plan = source_json(root+'oracles/probe-plan.json')
    hidden_bytes = source(root+'oracles/non_exhaustive_let.rs')
    hidden = digest(hidden_bytes)
    require(hidden == plan['hidden_test']['sha256'], 'Rust hidden test pin mismatch')
    oracle = source_json(root+'oracles/oracle.json')
    patch = source(root+'oracles/reference.patch')
    require(digest(patch) == oracle['patch']['sha256'], 'Rust reference patch pin mismatch')
    changed_paths = re.findall(r'^--- a/(.+)$', patch.decode(), flags=re.M)
    require(changed_paths and len(changed_paths) == len(set(changed_paths)), 'Rust patch paths invalid')
    captured = {}
    domains, rows = [], {}
    for side in ['baseline','reference']:
        pin = source_json(root+side+'-inventory.json')
        require(pin['archive_sha256'] == digest(source(root+side+'.tar.gz')), 'Rust source archive digest mismatch')
        lock = digest(source(root+'captures/'+side+'/Cargo.lock'))
        require(lock == plan['cargo_lock_sha256'], 'Rust local lock pin mismatch')
        wanted = set(changed_paths+[plan['hidden_test']['copied_to'],'Cargo.lock'])
        archived = {}
        with tarfile.open(ROOT/root/(side+'.tar.gz')) as tree:
            for member in tree:
                path = PurePosixPath(member.name)
                if not member.isfile() or len(path.parts) < 2: continue
                name = str(PurePosixPath(*path.parts[1:]))
                if name in wanted:
                    require(name not in archived and member.size <= 16*1024*1024, 'duplicate/oversized Rust pinned source')
                    archived[name] = tree.extractfile(member).read()
        require(set(archived) == wanted and digest(archived['Cargo.lock']) == lock, 'Rust archive pinned source/lock absent or mismatched')
        require(archived[plan['hidden_test']['copied_to']].split(b'#[cfg(test)]')[0] == hidden_bytes.split(b'#[cfg(test)]')[0], 'Rust hidden handler changes production prefix')
        captured[side] = archived
        row = summary['results'][side]
        require(row['source_archive_sha256'] == pin['archive_sha256'] and row['hidden_test_sha256'] == hidden, 'Rust materialization/oracle mismatch')
        require(row['lock_sha256_before'] == row['lock_sha256_after'] == lock and row['probe_verified'] is True, 'Rust lock or claimed behavioral result invalid')
        env = row['preparation_environment']
        require(env['RUSTUP_TOOLCHAIN'] == '1.98.1' and env['CARGO_BUILD_JOBS'] == '2' and env['CARGO_PROFILE_DEV_DEBUG'] == env['CARGO_PROFILE_TEST_DEBUG'] == '0' and env['CARGO_TARGET_DIR'].endswith('/'+side+'-target') and env['CARGO_HOME'].endswith('/_cargo'), 'Rust toolchain/jobs/targets mismatch')
        for name in ['tooling','prepare']:
            prep = preparation(reader, 'rust/'+side+'/'+name)
            require(prep['command'] == (['cargo','--version'] if name == 'tooling' else ['cargo','fetch','--locked']), 'Rust preparation command drift')
            if name == 'tooling':
                require(reader.raw('rust/'+side+'/tooling.stdout.log').startswith(b'cargo 1.98.1 ('), 'Rust tooling version mismatch')
        probe = reader.json('rust/'+side+'/probe.json')
        command = probe['command']
        suffix = ['test','--manifest-path','/workspace/'+side+'/Cargo.toml','--locked','--offline','-p','ide-diagnostics','regression_23336','--','--nocapture']
        prefix = ['/usr/bin/env','PATH=/workspace/_toolchain/bin:/usr/bin:/bin','CARGO_WORKSPACE_DIR=/workspace/'+side,'CARGO_HOME=/workspace/_cargo','CARGO_TARGET_DIR=/workspace/'+side+'-target','RUSTC=/workspace/_toolchain/bin/rustc','CARGO_BUILD_JOBS=2','CARGO_PROFILE_DEV_DEBUG=0','CARGO_PROFILE_TEST_DEBUG=0','CC='+native['cc'],'CXX='+native['cxx'],'CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER='+native['cc'],'/workspace/_toolchain/bin/cargo']
        require(command == prefix+suffix, 'Rust probe filter/command drift')
        text = contained(probe, 101 if side == 'baseline' else 0, reader, 'rust/'+side+'/probe')
        require(row['namespace_domain_id'] == probe['domain_id'] and row['cleanup_status'] == 'confirmed' and row['eligible_for_agent_run'] is True and row['containment'] == probe['containment'], 'Rust summary contradicts command containment')
        domains.append(probe['domain_id'])
        wanted = 'FAILED' if side == 'baseline' else 'ok'
        for n in [1,2]:
            name = 'handlers::non_exhaustive_let::tests::regression_23336_'+str(n)
            require(re.search(r'test '+re.escape(name)+r' \.\.\. '+wanted+r'\b', text), 'Rust named test missing/wrong result')
            if side == 'baseline':
                require(re.search(r"thread '"+re.escape(name)+r"' \(\d+\) panicked at", text), 'Rust baseline missing each expected panic')
        require('running 2 tests' in text and ('test result: FAILED. 0 passed; 2 failed; 0 ignored;' if side == 'baseline' else 'test result: ok. 2 passed; 0 failed; 0 ignored;') in text, 'Rust exact test counts mismatch')
        rows[side] = {'tests':2,'passed':0 if side == 'baseline' else 2,'failed':2 if side == 'baseline' else 0,'archive_sha256':pin['archive_sha256'],'hidden_probe_sha256':hidden,'lock_sha256':lock,'namespace':probe['domain_id']}
    expected_patch = ''.join(''.join(difflib.unified_diff(captured['baseline'][p].decode().splitlines(keepends=True), captured['reference'][p].decode().splitlines(keepends=True), fromfile='a/'+p, tofile='b/'+p)) for p in sorted(changed_paths))
    require(patch.decode() == expected_patch, 'Rust reference patch differs from archived source delta')
    locate = preparation(reader, 'rust/baseline/toolchain-location')
    require(locate['command'] == ['rustup','which','rustc','--toolchain','1.98.1'], 'Rust toolchain location command drift')
    reg = reader.json('rust/reference/regressions.json')
    suffix[-3] = 'handlers::non_exhaustive_let::tests'
    require(reg['command'] == prefix+suffix, 'Rust family regression filter drift')
    text = contained(reg, 0, reader, 'rust/reference/regressions')
    names = re.findall(r'^test (handlers::non_exhaustive_let::tests::\S+) \.\.\. ok$', text, flags=re.M)
    require(len(names) == len(set(names)) == 16 and 'test result: ok. 16 passed; 0 failed; 0 ignored;' in text, 'Rust family regression count/result mismatch')
    require(summary['results']['reference']['regressions_verified'] is True and summary['results']['reference']['regressions_domain_id'] == reg['domain_id'], 'Rust regression summary contradiction')
    require(summary['results']['baseline']['preparation_environment']['CARGO_HOME'] == summary['results']['reference']['preparation_environment']['CARGO_HOME'], 'Rust cache preparation differs between sides')
    domains.append(reg['domain_id'])
    require(len(set(domains)) == 3, 'Rust execution domains reused')
    return {'verified':True,'sides':rows,'reference_family_regressions':16,'reference_patch_sha256':digest(patch),'materialization_proof':'producer-bound full source archive and identical hidden handler/lock; local archived patch delta and unchanged hidden production prefix checked; exported workspaces not included'}


def jest_counts(report, oracle_names, phase, side):
    require(report['wasInterrupted'] is False and report['numRuntimeErrorTestSuites'] == 0 and report['numTotalTests'] == 5 and report['numTotalTestSuites'] == 1, 'Jest infrastructure error/incomplete tests')
    active = [n for n in oracle_names if n.startswith('contract ' if phase == 'requirement' else 'regression ')]
    failed = 3 if phase == 'requirement' and side == 'base' else 0
    require(report['numFailedTests'] == failed and report['numPassedTests'] == (0 if failed else len(active)) and report['numPendingTests'] == 5-len(active) and report['success'] is (failed == 0), 'Jest behavioral counts mismatch')
    require(report['numTodoTests'] == report['numPendingTestSuites'] == 0 and report['numFailedTestSuites'] == (1 if failed else 0) and report['numPassedTestSuites'] == (0 if failed else 1), 'Jest suite result/count mismatch')
    require(len(report['testResults']) == 1, 'Jest suite count mismatch')
    require(report['testResults'][0]['status'] == ('failed' if failed else 'passed'), 'Jest individual suite result mismatch')
    assertions = report['testResults'][0]['assertionResults']
    require(len(assertions) == 5 and {a['fullName'] for a in assertions} == set(oracle_names), 'Jest labels differ from frozen oracle')
    for a in assertions:
        state = ('failed' if failed else 'passed') if a['fullName'] in active else 'pending'
        require(a['status'] == state, 'Jest individual result mismatch')
        if state == 'failed':
            require(a['failureMessages'] and all('Not yet implemented' in msg for msg in a['failureMessages']), 'Jest baseline is not expected missing native hook failure')
        else:
            require(not a['failureMessages'], 'unexpected Jest failure messages')
    return {'passed':report['numPassedTests'],'failed':failed,'pending':report['numPendingTests']}


def js(reader):
    root = 'eval/qualification/l5-real/js/'
    capture = source_json(root+'capture.json'); oracle = source(root+'oracles/XraiExternalStoreContract-test.js'); oracle_hash = digest(oracle)
    freeze = source_json('docs/relatorios/logs/L5-continuacao/corpus-js/third-warning/freeze-checks.json')
    require(freeze['new_oracle_sha256'] == oracle_hash and freeze['source_hashes']['eval/scripts/verify_l5_js_oracle.py'] == digest(source('eval/scripts/verify_l5_js_oracle.py')) and any(c['name'] == 'oracle-guard' and c['exit'] == 0 for c in freeze['commands']), 'frozen transition source guard not verified/current')
    oracle_names = re.findall(r"test\('([^']+)'", oracle.decode())
    require(len(oracle_names) == 5 and "toErrorDev('An update to Stateful inside a test was not wrapped in act')" in oracle.decode(), 'transition/warning control absent')
    base = capture['snapshots']['base']; head = capture['snapshots']['head']
    for s in [base,head]:
        require(s['archive_sha256'] == digest(source(s['archive'])), 'JS source archive mismatch')
    lock = base['setup_and_evidence']['yarn.lock']['sha256']; executor = digest(source('eval/scripts/run_l5_js.py'))
    patched = {p:head['setup_and_evidence'][p]['sha256'] for p in capture['reference_patch_paths']}
    package_bytes = source(root+'setup/react-is-17.0.2.tgz')
    with tarfile.open(ROOT/root/'setup/react-is-17.0.2.tgz') as tree:
        bootstrap_files = {str(PurePosixPath(*PurePosixPath(m.name).parts[1:])):digest(tree.extractfile(m).read()) for m in tree if m.isfile()}
    domains, nodes, rows = [], [], {}
    for side in ['base','reference']:
        prefix = 'js/'+side+'/'
        probe = reader.json(prefix+'probe.json')
        require(probe['executor_source_sha256'] == executor and probe['oracle_source_sha256'] == oracle_hash, 'JS executor/oracle differs from frozen source')
        require(probe['side'] == side and probe['platform'].startswith('Linux-') and probe['machine'] == 'x86_64' and probe['verified'] is True and probe['admitted'] is False and probe['competitive_runs_allowed'] is False, 'JS producer status/platform invalid')
        require(probe['lock_before'] == probe['lock_after'] == lock, 'JS lock changed')
        require(probe['configuration'] == {'NODE_ENV':'development','RELEASE_CHANNEL':'experimental','VARIANT':'true','config':'scripts/jest/config.source-www.js'}, 'JS recorded configuration drift')
        material = probe['materialization']
        require(material['side'] == side and material['base_commit'] == base['commit'] and material['reference_commit'] == (head['commit'] if side == 'reference' else None), 'JS source commits mismatch')
        require(material['full_base_archive_sha256'] == base['archive_sha256'] and material['yarn_lock_sha256'] == lock and material['evaluator_probe_sha256'] == oracle_hash and material['reference_source_sha256'] == (patched if side == 'reference' else {}), 'JS exact reference materialization pin mismatch')
        boot = reader.json(prefix+'bootstrap.json')
        require(boot == probe['bootstrap'], 'JS bootstrap export differs from probe')
        require(boot['archive_sha256'] == digest(package_bytes) and boot['registry_metadata_sha256'] == digest(source(root+'setup/react-is-17.0.2.registry.json')) and boot['omitted_postinstall_sha256'] == digest(source(root+'setup/upstream-downloadReactIsForPrettyFormat.js')), 'JS bootstrap provenance mismatch')
        integrity = 'sha512-'+base64.b64encode(hashlib.sha512(package_bytes).digest()).decode()
        require(boot['archive_integrity'] == integrity == source_json(root+'setup/react-is-17.0.2.registry.json')['dist']['integrity'], 'JS bootstrap integrity mismatch')
        require(boot['package'] == 'react-is' and boot['version'] == '17.0.2' and boot['required_range'] == '^17.0.1' and boot['pretty_format_version'] == '26.6.2' and boot['files'] == bootstrap_files and boot['lock_before'] == boot['lock_after'] == lock and boot['network_used'] is False and boot['production_modified'] is False and boot['oracle_modified'] is False, 'JS bootstrap contents/setup drift')
        require(hex_digest(probe['node_executable_sha256']), 'invalid Node executable digest')
        nodes.append(probe['node_executable_sha256']); phases = probe['phases']
        require([p['name'] for p in phases] == ['requirement','regression'], 'JS phase set/order drift')
        row = {}
        for phase in phases:
            name = phase['name']; expected_exit = 1 if side == 'base' and name == 'requirement' else 0
            require(phase['receipt'] == name+'-harness.json' and phase['jest_report'] == name+'-jest.json' and phase['expected_exit'] == phase['actual_exit'] == expected_exit and all(phase[k] is True for k in ['teardown_verified','behavioral_result_verified','verified']), 'JS phase claimed result invalid')
            harness = reader.json(prefix+name+'-harness.json')
            contained(harness, expected_exit, reader, timeout=300)
            require(phase['execution_status'] == harness['execution_status'], 'JS phase status contradicts harness')
            expected_command = ['/usr/bin/env','HOME=/workspace','TMPDIR=/tmp','NODE_ENV=development','RELEASE_CHANNEL=experimental','VARIANT=true','/workspace/.xrai-node','./scripts/jest/jest.js','--config','./scripts/jest/config.source-www.js','--runInBand','--json','--outputFile=.xrai-jest-'+name+'.json','--testNamePattern='+('^contract ' if name == 'requirement' else '^regression '),'XraiExternalStoreContract-test']
            require(harness['command'] == expected_command and harness['phase'] == 'qualification-'+name, 'JS command/config/filter drift')
            require(phase['jest_report_sha256'] == digest(reader.raw(prefix+name+'-jest.json')), 'Jest report digest mismatch')
            row[name] = jest_counts(reader.json(prefix+name+'-jest.json'), oracle_names, name, side)
            domains.append(harness['domain_id'])
        rows[side] = row
    require(len(set(domains)) == 4 and len(set(nodes)) == 1, 'JS namespace reused or Node bytes differ between sides')
    return {'verified':True,'sides':rows,'oracle_sha256':oracle_hash,'node_reported_sha256':nodes[0],'transition_guard':'frozen local source guard passed; runtime ordinary transition negative control included in the two passed regressions','materialization_proof':'producer-bound full base archive plus exact two reference production source digests; exported workspaces not included'}


def reconcile(directory, commit, run_id, only='both', overrides=None):
    reader = Reader(directory, overrides); run = reader.json('run.json'); artifacts = reader.json('artifacts.json')
    require(re.fullmatch('[0-9a-f]{7,40}', commit) is not None and re.fullmatch('[0-9a-f]{40}', run['headSha']) is not None and run['headSha'].startswith(commit), 'run code commit mismatch')
    require(run['databaseId'] == run_id and run['status'] == 'completed' and run['url'] == 'https://github.com/wkoch/xrai/actions/runs/'+str(run_id), 'run identity/status/provenance mismatch')
    families = ['rust','js'] if only == 'both' else [only]; results = {}; exports = {}
    for family in families:
        job_name = 'L5 real '+('Rust' if family == 'rust' else 'JavaScript')+' behavioral pair'
        jobs = [j for j in run['jobs'] if j['name'] == job_name]
        require(len(jobs) == 1 and jobs[0]['status'] == 'completed' and jobs[0]['conclusion'] == 'success', family+' CI job not completed successfully')
        records = [a for a in artifacts['artifacts'] if a['name'] == 'l5-real-'+family]
        require(len(records) == 1, 'ambiguous/missing export artifact '+family)
        a = records[0]
        require(a['workflow_run']['id'] == run_id and a['workflow_run']['head_sha'] == run['headSha'] and a['expired'] is False and re.fullmatch('sha256:[0-9a-f]{64}', a['digest']), 'artifact run/head/digest provenance mismatch')
        require(a['url'] == 'https://api.github.com/repos/wkoch/xrai/actions/artifacts/'+str(a['id']), 'artifact repository/identity mismatch')
        exports[family] = {'artifact_id':a['id'],'github_reported_zip_digest':a['digest'],'job_id':jobs[0]['databaseId'],'zip_bytes_independently_verified':False}
        archive = Path(directory)/('l5-real-'+family+'.zip')
        if archive.exists():
            raw = reader.raw(archive.name); require('sha256:'+digest(raw) == a['digest'], 'export ZIP digest mismatch')
            with zipfile.ZipFile(archive) as tree:
                require(len(tree.namelist()) == len(set(tree.namelist())) <= 100 and sum(m.file_size for m in tree.infolist()) <= 64*1024*1024, 'oversized/duplicate export ZIP')
                exported_root = reader.root/family
                require(exported_root.is_dir() and not exported_root.is_symlink(), 'unsafe family export directory')
                exported = set()
                for path in exported_root.rglob('*'):
                    require(not path.is_symlink() and (path.is_dir() or path.is_file()), 'symlink or nonregular family export entry')
                    if path.is_file():
                        exported.add(path.relative_to(exported_root).as_posix())
                        require(len(exported) <= 100, 'oversized family export file set')
                zipped = {name for name in tree.namelist() if not name.endswith('/')}
                require(exported == zipped, 'family export file set differs from ZIP members')
                for name in tree.namelist():
                    if name.endswith('/'): continue
                    rel = PurePosixPath(name)
                    require(not rel.is_absolute() and '..' not in rel.parts, 'unsafe exported ZIP member')
                    require(tree.getinfo(name).file_size <= 16*1024*1024, 'oversized ZIP member')
                    require(reader.raw(family+'/'+name) == tree.read(name), 'exported file differs from verified ZIP member')
            exports[family]['zip_bytes_independently_verified'] = True
            exports[family]['complete_file_set_verified'] = True
            exports[family]['file_count'] = len(zipped)
        results[family] = rust(reader) if family == 'rust' else js(reader)
    return {'schema':'xrai.eval.l5.corpus-data-reconcile.v1','verified':True,'run_id':run_id,'code_commit':run['headSha'],'families':results,'export_provenance':exports,'input_sha256':reader.hashes,'verifier_sha256':digest(Path(__file__).read_bytes()),'sources_sha256':{p:digest(source(p)) for p in ['eval/scripts/run_real_rust_probes.py','eval/scripts/run_vertical_probes.py','eval/scripts/run_l5_js.py','eval/scripts/verify_l5_js_oracle.py','crates/xrai-eval/harness/supervisor.py']},'data_only':True,'admitted':False,'competitive_runs_allowed':False,'limits':['producer receipt consistency is not independent observation of the past process or workspace','metadata must be obtained by trusted GitHub export; supplied JSON is not authenticated by this offline verifier','without original ZIP, extracted file hashes are recorded but not cryptographically bound to GitHub-reported ZIP digest','native executable bytes are reported by producers; binaries are not retained in these corpus exports','Rust family regressions run on reference only; no baseline-family or full upstream suite claim','no agent success, incremental A-to-B proof, full semantic coverage or corpus admission inferred']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path); parser.add_argument('--commit', required=True); parser.add_argument('--run', type=int, required=True); parser.add_argument('--only', choices=['both','rust','js'], default='both')
    args = parser.parse_args()
    try:
        report = reconcile(args.directory, args.commit, args.run, args.only)
    except (ValueError,KeyError,OSError,TypeError,zipfile.BadZipFile) as error:
        print(json.dumps({'verified':False,'data_only':True,'admitted':False,'error':str(error)})); return 1
    print(json.dumps(report, indent=2)); return 0


if __name__ == '__main__':
    sys.exit(main())
