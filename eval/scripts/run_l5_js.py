#!/usr/bin/env python3
"""Prepare React evaluator workspaces and run frozen probes in Linux containment."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / 'eval/qualification/l5-real/js'
HIDDEN = 'packages/react-reconciler/src/__tests__/XraiExternalStoreContract-test.js'
PATCH_PATHS = ['packages/react-reconciler/src/ReactFiberHooks.new.js',
               'packages/react-reconciler/src/ReactFiberHooks.old.js']
REACT_IS_SHA256 = '9b1850c05b4fc08e9b814a201281a103a7651ac46500dce7b6bedd0865963eb1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bootstrap(workspace):
    """Offline data extraction reproducing the captured pretty-format postinstall.

    Yarn workspaces otherwise link pretty-format's react-is dependency to raw
    Flow/ES module production sources before Jest's transformer can start.
    Never execute the omitted postinstall or install a floating semver version.
    """
    workspace = workspace.resolve()
    capture = json.loads((CASE / 'capture.json').read_text())
    expected_lock = capture['snapshots']['base']['setup_and_evidence']['yarn.lock']['sha256']
    before = sha((workspace / 'yarn.lock').read_bytes())
    if before != expected_lock:
        raise ValueError('bootstrap dependency lock differs from captured setup')
    upstream_script = workspace / 'scripts/yarn/downloadReactIsForPrettyFormat.js'
    if upstream_script.read_bytes() != (CASE / 'setup/upstream-downloadReactIsForPrettyFormat.js').read_bytes():
        raise ValueError('captured postinstall source differs from bootstrap pin')
    metadata = json.loads((CASE / 'setup/react-is-17.0.2.registry.json').read_text())
    archive = CASE / 'setup/react-is-17.0.2.tgz'
    data = archive.read_bytes()
    integrity = 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode()
    if (sha(data) != REACT_IS_SHA256 or metadata['name'] != 'react-is' or
            metadata['version'] != '17.0.2' or metadata['license'] != 'MIT' or
            metadata['dist']['integrity'] != integrity or
            metadata['dist']['shasum'] != hashlib.sha1(data).hexdigest()):
        raise ValueError('pinned react-is integrity mismatch')
    pretty = workspace / 'node_modules/pretty-format'
    if not pretty.resolve().is_relative_to(workspace):
        raise ValueError('pretty-format escapes evaluator workspace')
    package = json.loads((pretty / 'package.json').read_text())
    if package['name'] != 'pretty-format' or package['version'] != '26.6.2' or package['dependencies']['react-is'] != '^17.0.1':
        raise ValueError('pretty-format dependency differs from frozen setup')
    target = pretty / 'node_modules/react-is'
    if target.is_symlink() or not target.resolve().is_relative_to(workspace):
        raise ValueError('react-is bootstrap target is not contained')
    files = {}
    with tarfile.open(archive) as tree:
        for member in tree:
            name = PurePosixPath(member.name)
            if not name.parts or name.parts[0] != 'package' or name.is_absolute() or '..' in name.parts:
                raise ValueError('unsafe react-is archive path')
            if member.isdir():
                continue
            path = str(PurePosixPath(*name.parts[1:]))
            if not member.isfile() or len(name.parts) < 2 or path in files:
                raise ValueError('unsafe react-is archive member')
            files[path] = tree.extractfile(member).read()
    pinned_package = json.loads(files['package.json'])
    if pinned_package['name'] != 'react-is' or pinned_package['version'] != '17.0.2' or b'MIT License' not in files['LICENSE']:
        raise ValueError('react-is package identity or license mismatch')
    if target.exists():
        if any(p.is_symlink() for p in target.rglob('*')):
            raise ValueError('existing react-is bootstrap contains symlink')
        actual = {str(p.relative_to(target)):p for p in target.rglob('*') if not p.is_dir()}
        if set(actual) != set(files) or any(p.is_symlink() or p.read_bytes() != files[n] for n,p in actual.items()):
            raise ValueError('existing react-is bootstrap differs from pinned archive')
    else:
        for name, content in files.items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    after = sha((workspace / 'yarn.lock').read_bytes())
    if before != after:
        raise ValueError('bootstrap modified dependency lock')
    receipt = {'schema_version':'xrai.eval.l5.js.bootstrap.v1',
               'method':'offline pinned data extraction; no captured hooks executed',
               'omitted_postinstall':'scripts/yarn/downloadReactIsForPrettyFormat.js',
               'omitted_postinstall_sha256':sha(upstream_script.read_bytes()),
               'package':'react-is', 'version':'17.0.2', 'required_range':'^17.0.1',
               'pretty_format_version':package['version'],
               'registry_metadata_sha256':sha((CASE/'setup/react-is-17.0.2.registry.json').read_bytes()),
               'registry_url':'https://registry.npmjs.org/react-is/17.0.2',
               'archive_sha256':sha(data), 'archive_integrity':integrity,
               'target':'node_modules/pretty-format/node_modules/react-is',
               'files':{name:sha(content) for name,content in sorted(files.items())},
               'lock_before':before,'lock_after':after,'network_used':False,
               'production_modified':False,'oracle_modified':False}
    (workspace / '.xrai-bootstrap.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def materialize(destination, side):
    """No captured code executes; agent supplier must omit hidden evaluator files."""
    capture = json.loads((CASE / 'capture.json').read_text())
    archive = ROOT / capture['snapshots']['base']['archive']
    if sha(archive.read_bytes()) != capture['snapshots']['base']['archive_sha256']:
        raise ValueError('base archive fingerprint mismatch')
    destination.mkdir(parents=True, exist_ok=False)
    seen = set()
    with tarfile.open(archive) as tree:
        for member in tree:
            p = PurePosixPath(member.name)
            if p.parts[0] != 'react-' + capture['snapshots']['base']['commit']:
                raise ValueError('archive root mismatch')
            if member.isdir():
                continue
            name = PurePosixPath(*p.parts[1:])
            if not member.isfile() or name.is_absolute() or '..' in name.parts or str(name) in seen:
                raise ValueError('unsafe archive member')
            seen.add(str(name))
            target = destination / str(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tree.extractfile(member).read())
            target.chmod(member.mode & 0o777)
    patch_hashes = {}
    if side == 'reference':
        archive = ROOT / capture['snapshots']['head']['archive']
        if sha(archive.read_bytes()) != capture['snapshots']['head']['archive_sha256']:
            raise ValueError('head archive fingerprint mismatch')
        with tarfile.open(archive) as tree:
            for path in PATCH_PATHS:
                member = tree.getmember('react-' + capture['snapshots']['head']['commit'] + '/' + path)
                data = tree.extractfile(member).read()
                if sha(data) != capture['snapshots']['head']['setup_and_evidence'][path]['sha256']:
                    raise ValueError('reference source fingerprint mismatch')
                (destination / path).write_bytes(data)
                patch_hashes[path] = sha(data)
    source = (CASE / 'oracles/XraiExternalStoreContract-test.js').read_bytes()
    (destination / HIDDEN).write_bytes(source)
    receipt = {'side':side, 'base_commit':capture['snapshots']['base']['commit'],
               'reference_commit':capture['snapshots']['head']['commit'] if side == 'reference' else None,
               'full_base_archive_sha256':capture['snapshots']['base']['archive_sha256'],
               'reference_policy':'only the two production modules changed; upstream test changes not applied',
               'reference_source_sha256':patch_hashes, 'evaluator_probe_sha256':sha(source),
               'warning':'evaluator workspace only; hidden oracle must never enter a comparative agent workspace',
               'yarn_lock_sha256':sha((destination / 'yarn.lock').read_bytes())}
    (destination / '.xrai-materialization.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def probe(workspace, node, side, output, timeout):
    if platform.system() != 'Linux':
        raise ValueError('arbitrary upstream execution requires disposable Linux harness domain; macOS denied')
    sys.path.insert(0, str(ROOT / 'crates/xrai-eval/harness'))
    from runner import execute
    from supervisor import verify_receipt, confirmed_receipt
    workspace = workspace.resolve()
    output.mkdir(parents=True, exist_ok=False)
    bootstrap_receipt = bootstrap(workspace)
    (output / 'bootstrap.json').write_text(json.dumps(bootstrap_receipt, indent=2)+'\n')
    source_node = node.resolve()
    local_node = workspace / '.xrai-node'
    shutil.copy2(source_node, local_node)
    local_node.chmod(0o755)
    before = sha((workspace / 'yarn.lock').read_bytes())
    phases = []
    for name, pattern, expected_count in [('requirement','^contract ',3), ('regression','^regression ',2)]:
        result_name = f'.xrai-jest-{name}.json'
        # adapters.sandbox binds the host checkout at /workspace; only argv[0]
        # is normalized, so nested executable arguments must use namespace paths.
        command = ['/usr/bin/env', 'HOME=/workspace', 'TMPDIR=/tmp',
                   'NODE_ENV=development', 'RELEASE_CHANNEL=experimental', 'VARIANT=true',
                   '/workspace/.xrai-node', './scripts/jest/jest.js', '--config', './scripts/jest/config.source-www.js',
                   '--runInBand', '--json', '--outputFile='+result_name,
                   '--testNamePattern='+pattern, 'XraiExternalStoreContract-test']
        run = execute(command, workspace, timeout=timeout, output_limit=1024*1024,
                      phase='qualification-'+name, arbitrary_agent=True)
        (output / (name+'-harness.json')).write_text(json.dumps(run, indent=2)+'\n')
        verify_receipt(run)
        teardown_verified = confirmed_receipt(run) and run['eligible_for_agent_run']
        report_path = workspace / result_name
        report = json.loads(report_path.read_text()) if report_path.is_file() else None
        if report is not None:
            shutil.copyfile(report_path, output / (name+'-jest.json'))
        errors = '\n'.join(message for suite in (report or {}).get('testResults',[]) for x in suite.get('assertionResults',[]) for message in x.get('failureMessages',[]))
        expected_exit = 1 if name == 'requirement' and side == 'base' else 0
        behavioral = bool(report and report.get('numTotalTests') == 5 and
                          report.get('numFailedTests') == (3 if expected_exit else 0) and
                          report.get('numPassedTests') == (0 if expected_exit else expected_count) and
                          report.get('numPendingTests') == 5-expected_count)
        # An infrastructure failure is never evidence that the contract was absent.
        if expected_exit:
            behavioral = behavioral and 'Not yet implemented' in errors
        phase = {'name':name, 'expected_exit':expected_exit, 'actual_exit':run['exit_code'],
                 'execution_status':run['execution_status'], 'teardown_verified':teardown_verified,
                 'behavioral_result_verified':behavioral,
                 'jest_report_sha256':sha(report_path.read_bytes()) if report_path.is_file() else None,
                 'receipt':name+'-harness.json', 'jest_report':name+'-jest.json' if report else None}
        phase['verified'] = bool(teardown_verified and run['exit_code'] == expected_exit and behavioral)
        phases.append(phase)
    after = sha((workspace / 'yarn.lock').read_bytes())
    receipt = {'schema_version':'xrai.eval.l5.js.probe.v1', 'side':side,
               'platform':platform.platform(), 'machine':platform.machine(),
               'node_executable_sha256':sha(local_node.read_bytes()),
               'executor_source_sha256':sha(Path(__file__).read_bytes()),
               'oracle_source_sha256':sha((CASE/'oracles/XraiExternalStoreContract-test.js').read_bytes()),
               'materialization':json.loads((workspace/'.xrai-materialization.json').read_text()),
               'bootstrap':bootstrap_receipt,
               'configuration':{'NODE_ENV':'development','RELEASE_CHANNEL':'experimental','VARIANT':'true','config':'scripts/jest/config.source-www.js'},
               'lock_before':before,'lock_after':after,'phases':phases,
               'verified':all(p['verified'] for p in phases) and before == after,
               'admitted':False,'competitive_runs_allowed':False}
    (output/'probe.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest='action',required=True)
    m=s.add_parser('materialize');m.add_argument('--workspace',type=Path,required=True);m.add_argument('--side',choices=['base','reference'],required=True)
    r=s.add_parser('probe');r.add_argument('--workspace',type=Path,required=True);r.add_argument('--side',choices=['base','reference'],required=True);r.add_argument('--node',type=Path,required=True);r.add_argument('--output',type=Path,required=True);r.add_argument('--timeout',type=float,default=300)
    a=p.parse_args()
    result=materialize(a.workspace,a.side) if a.action=='materialize' else probe(a.workspace,a.node,a.side,a.output,a.timeout)
    print(json.dumps(result,indent=2))
    return 0 if a.action=='materialize' or result['verified'] else 1

if __name__=='__main__':
    raise SystemExit(main())
