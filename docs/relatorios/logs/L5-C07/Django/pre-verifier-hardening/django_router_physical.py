#!/usr/bin/env python3
"""Prospective Django v2 physical proof; never imports Django on the host."""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

from django_router_verify import ARCHIVE, ROOT, archive_tree, canonical, decode, read_owned, require, sha

CASE = ROOT / 'eval/qualification/django-router-v2'
FREEZE_SHA = 'b15a9b8ccb6975918c1b0461a355e204517428a072ea4028ddd1977a191a4765'
BOUND = 1024 * 1024


def prepared(root=ROOT):
    base = 'eval/qualification/django-router-v2/'
    raw = read_owned(root, base + 'freeze.json', BOUND)
    require(sha(raw) == FREEZE_SHA, 'v2 freeze fingerprint changed')
    freeze = decode(raw)
    data = {}
    for row in freeze['inputs']:
        raw = read_owned(root, row['path'], 16 * BOUND)
        require(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'frozen v2 input changed')
        require(row['path'] not in data, 'duplicate frozen v2 input')
        data[row['path']] = raw
    archive = read_owned(root, ARCHIVE, 16 * BOUND)
    require(sha(archive) == freeze['archive_sha256'], 'captured Django archive changed')
    files = archive_tree(archive)
    require(len(files) == 7084, 'full captured checkout count')
    policy = read_owned(root, 'eval/qualification/django-router-v1/agent/policy.py', BOUND)
    require(data[base + 'agent/policy.py'] == policy, 'v1 policies must retain exact bytes')
    a = decode(data[base + 'agent/deployment.json'])
    b = decode(data[base + 'evaluator/reference.json'])
    require(a['router_order'] == ['primary', 'scoped'] and b['router_order'] == ['scoped', 'primary'], 'frozen orders')
    require({k: v for k, v in a.items() if k != 'router_order'} ==
            {k: v for k, v in b.items() if k != 'router_order'}, 'only order intervention permitted')
    require(a['models'][-1]['model_name'] == 'legacyentry' and a['models'][-1]['managed'] is False,
            'public unmanaged legacy model')
    oracle = decode(data[base + 'evaluator/oracle.json'])
    require(len(oracle['main_cells']) == 12 and len(oracle['physical_controls']) == 4, 'fixed physical matrix')
    return freeze, data, files


def lock():
    return decode((CASE / 'setup.lock.json').read_bytes())


def wheel_tree(raw):
    require(len(raw) <= BOUND, 'wheel compressed bound')
    data = {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(len(archive.infolist()) <= 1024, 'wheel members bound')
        for row in archive.infolist():
            p = PurePosixPath(row.filename)
            require(not p.is_absolute() and '\\' not in row.filename and ':' not in row.filename and
                    all(x not in ('', '.', '..') for x in row.filename.rstrip('/').split('/')),
                    'wheel traversal/alias')
            if row.is_dir():
                continue
            mode = row.external_attr >> 16 & 0o170000
            require(mode in (0, 0o100000) and row.filename not in data, 'nonregular/duplicate wheel entry')
            total += row.file_size
            require(0 <= row.file_size <= BOUND and total <= 8 * BOUND, 'expanded wheel bound')
            data[row.filename] = archive.read(row)
    require(any('LICENSE' in name.upper() for name in data), 'wheel license missing')
    return data


def acquire(cache):
    """Install phase: acquire bounded pinned bytes, never invoke package code."""
    cache.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in lock()['packages']:
        destination = cache / item['filename']
        require(not destination.is_symlink(), 'wheel cache symlink')
        if not destination.exists():
            with urllib.request.urlopen(item['url'], timeout=60) as response:
                raw = response.read(item['bytes'] + 1)
            require(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'wheel acquisition fingerprint')
            destination.write_bytes(raw)
        raw = destination.read_bytes()
        require(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'cached wheel fingerprint')
        members = wheel_tree(raw)
        rows.append({**item, 'licenses': {n: sha(v) for n, v in members.items() if 'LICENSE' in n.upper()},
                     'downloaded_package_executed': False})
    return rows


def inventory(directory):
    result = {}
    for path in sorted(directory.rglob('*')):
        require(not path.is_symlink(), 'inventory symlink')
        if path.is_file():
            result[str(path.relative_to(directory))] = {'bytes': path.stat().st_size, 'sha256': sha(path.read_bytes())}
    return result


def setup(workspace, cache, files, data):
    require(platform.system() == 'Linux' and platform.machine() == 'x86_64' and
            platform.python_version() == lock()['python'], 'pinned disposable Linux Python required')
    workspace.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        path = workspace / 'checkout' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    for category in ('agent', 'evaluator'):
        base = 'eval/qualification/django-router-v2/' + category + '/'
        destination = workspace / ('public' if category == 'agent' else 'private')
        destination.mkdir()
        for name, raw in data.items():
            if name.startswith(base):
                path = destination / name[len(base):]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
    # A deliberately hostile link is visible to the agent, but its evaluator
    # target is absent from the agent mount namespace.
    (workspace / 'public/private-link').symlink_to('/private/oracle.json')
    deps = workspace / 'dependencies'
    deps.mkdir()
    wheel_rows = acquire(cache)
    for row in wheel_rows:
        for name, raw in wheel_tree((cache / row['filename']).read_bytes()).items():
            path = deps / name
            require(not path.exists(), 'dependency collision')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    runtime = workspace / 'runtime'
    (runtime / 'bin').mkdir(parents=True)
    (runtime / 'lib').mkdir()
    executable = Path(sys.executable).resolve()
    shutil.copy2(executable, runtime / 'bin/python3')
    stdlib = Path(sys.base_prefix) / 'lib/python3.13'
    shutil.copytree(stdlib, runtime / 'lib/python3.13',
                    ignore=shutil.ignore_patterns('site-packages', '__pycache__'), symlinks=False)
    for library in (Path(sys.base_prefix) / 'lib').glob('libpython3.13.so*'):
        if library.is_file():
            shutil.copy2(library, runtime / 'lib' / library.name)
    import sqlite3  # trusted stdlib version observation in Linux setup only
    runtime_hashes = inventory(runtime)
    require(any(n.endswith('LICENSE.txt') for n in runtime_hashes), 'runtime Python license missing')
    # Inventory exact dynamic dependencies of trusted Python and its stdlib
    # extensions before executing captured framework code. ldd never targets
    # captured upstream ELF; dependency wheels are pure Python.
    dynamic = {}
    for path in [executable, *stdlib.rglob('*.so')]:
        answer = subprocess.run(['/usr/bin/ldd', str(path)], env={'PATH': '/usr/bin:/bin', 'LANG': 'C'},
                                capture_output=True, timeout=5, check=True).stdout.decode()
        for name in re.findall(r'(/[^\s()]+)', answer):
            resolved = Path(name).resolve()
            if resolved.is_file():
                dynamic[str(resolved)] = {'bytes': resolved.stat().st_size, 'sha256': sha(resolved.read_bytes())}
    sqlite = {n: row for n, row in dynamic.items() if 'libsqlite3' in n}
    require(sqlite, 'SQLite dynamic dependency inventory missing')
    licenses = {}
    for folder in ('libsqlite3-0', 'libc6', 'libssl3t64', 'libffi8', 'zlib1g', 'libbz2-1.0', 'liblzma5'):
        path = Path('/usr/share/doc') / folder / 'copyright'
        if path.is_file():
            licenses[str(path)] = {'sha256': sha(path.read_bytes()), 'content': path.read_text(errors='replace')}
    require(any('libsqlite3-0' in n for n in licenses), 'SQLite system license missing')
    return {'schema': 'xrai.eval.django-router.runtime.v2', 'before_upstream_execution': True,
            'python_version': platform.python_version(), 'sqlite_version': sqlite3.sqlite_version,
            'python_executable': str(executable),
            'python_executable_sha256': sha(executable.read_bytes()),
            'runtime_files': runtime_hashes, 'dependency_files': inventory(deps), 'wheels': wheel_rows,
            'dynamic_libraries': dynamic, 'sqlite_libraries': sqlite, 'system_licenses': licenses,
            'setup_lock_sha256': sha((CASE / 'setup.lock.json').read_bytes()),
            'executor_source_sha256': sha(Path(__file__).read_bytes()),
            'oracle_source_sha256': sha((CASE / 'evaluator/physical_oracle.py').read_bytes()),
            'source_pin': lock()['source_pin'], 'source_files': inventory(workspace / 'checkout'),
            'no_site_packages_inherited': True, 'framework_imported_during_setup': False}


def command(phase):
    require(phase in ('agent', 'a', 'b', 'controls'), 'unknown phase')
    args = ['/usr/bin/bwrap', '--unshare-all', '--unshare-user', '--die-with-parent', '--new-session']
    for folder in ('/usr', '/bin', '/lib', '/lib64'):
        args += ['--ro-bind', folder, folder]
    args += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
             '--ro-bind', '/workspace/checkout', '/checkout',
             '--ro-bind', '/workspace/runtime', '/runtime',
             '--ro-bind', '/workspace/dependencies', '/dependencies',
             '--ro-bind', '/workspace/public', '/public',
             '--size', str(lock()['phase_policy']['scratch_tmpfs_bytes']), '--tmpfs', '/scratch',
             '--chdir', '/scratch', '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin',
             '--setenv', 'LANG', 'C.UTF-8', '--setenv', 'HOME', '/scratch',
             '--setenv', 'TMPDIR', '/scratch', '--setenv', 'LD_LIBRARY_PATH', '/runtime/lib']
    if phase != 'agent':
        args += ['--ro-bind', '/workspace/private', '/private']
    policy = lock()['phase_policy']
    script = '/public/visibility_probe.py' if phase == 'agent' else '/private/physical_oracle.py'
    launch = ('import sys,resource,runpy;'
              'assert sys.prefix=="/runtime",sys.prefix;'
              'assert all(p.startswith("/runtime/") for p in sys.path),sys.path;'
              'resource.setrlimit(resource.RLIMIT_AS,({m},{m}));'
              'resource.setrlimit(resource.RLIMIT_NPROC,({p},{p}));'
              'resource.setrlimit(resource.RLIMIT_FSIZE,({d},{d}));'
              'sys.argv={argv!r};runpy.run_path({script!r},run_name="__main__")').format(
                  m=policy['rlimit_address_space_bytes'], p=policy['rlimit_processes_per_uid'],
                  d=policy['rlimit_file_bytes'], argv=[script, phase], script=script)
    args += ['--', '/runtime/bin/python3', '-I', '-S', '-B', '-c', launch]
    return args


def stream(turn, name):
    row = turn[name]
    raw = base64.b64decode(row['base64'], validate=True)
    require(type(row['captured_bytes']) is int and type(row['observed_bytes']) is int and
            len(raw) == row['captured_bytes'] == row['observed_bytes'] and
            sha(raw) == row['sha256'] and row['truncated'] is False, 'complete raw stream required')
    return raw


def validate_result(report, phase, oracle, hashes):
    require(report['phase'] == phase and report['oracle_executed'] is True and
            report['provider_used'] is False and report['qualified'] is False and report['admitted'] is False,
            'physical receipt scope')
    require(report['python_version'] == lock()['python'], 'runtime version mismatch')
    rows = oracle['physical_controls'] if phase == 'controls' else [r for r in oracle['main_cells'] if r['state'] == phase]
    cells = report['cells']
    require(len(cells) == len(rows), 'physical cell completeness')
    key = (lambda r: (r['control'], r['alias'])) if phase == 'controls' else (lambda r: (r['app'], r['model'], r['alias']))
    expected = {key(r): r for r in rows}
    require(len({key(r) for r in cells}) == len(cells) and set(map(key, cells)) == set(expected), 'physical cell identities')
    for row in cells:
        want = expected[key(row)]
        require(type(row['creates_table']) is bool and row['creates_table'] == want['creates_table'], 'physical table truth mismatch')
        require(row['historical_model'] is True and row['real_database_forwards'] is True and row['real_schema_editor'] is True, 'real captured operation required')
        require(row['sentinel'] == [[phase + ':' + row['alias']]], 'sentinel drift')
        events = row['router_events_during_operation']
        if phase != 'controls':
            require(row['table'] == want['table'] and row['router_consulted'] is want['router_consulted'] and
                    row['isolated_router_allows'] is want['isolated_router_allows'], 'model/router order proof')
            require(row['model_can_migrate'] is (row['model'] != 'legacyentry'), 'model gate mismatch')
        require(type(events) is list and len(events) == int(row['router_consulted']), 'router observation cardinality')
        if events:
            require(events[0] == {'alias': row['alias'], 'app': row['app'], 'model_name': row['model'],
                                  'answer': row['creates_table']}, 'observed real router decision')
    db = report['database_files']
    require(len(db) == 2 and {r['alias'] for r in db} == {'default', 'reporting'} and
            len({r['inode'] for r in db}) == 2 and all(type(r['inode']) is int and r['inode'] > 0 for r in db), 'distinct physical databases')
    require(report['module_origins'] == hashes, 'captured imports identity')
    expected_config = CASE / ('agent/deployment.json' if phase == 'a' else 'evaluator/reference.json')
    require(report['configuration_sha256'] == sha(expected_config.read_bytes()) and
            report['policy_sha256'] == sha((CASE / 'agent/policy.py').read_bytes()), 'configuration/policy binding')
    reference = {(r['app'], r['model'], r['alias']): r['creates_table'] for r in oracle['main_cells'] if r['state'] == 'b'}
    requirement = all(row['creates_table'] == reference.get(key(row)) for row in cells) if phase != 'controls' else None
    return {'oracle_executed': True, 'requirement_satisfied': requirement, 'cells_verified': len(cells),
            'baseline_divergence_cells': 2 if phase == 'a' else 0, 'multimodule': False,
            'qualified': False, 'admitted': False}


def run(cache, output):
    require(platform.system() == 'Linux' and os.environ.get('GITHUB_ACTIONS') == 'true',
            'captured Django executes only disposable Linux CI')
    require(shutil.which('bwrap') is not None, 'required domain unavailable')
    freeze, data, files = prepared()
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(ROOT / 'crates/xrai-eval/harness'))
    from runner import execute
    from supervisor import verify_receipt, confirmed_receipt
    start = time.monotonic()
    temp = Path(tempfile.mkdtemp(prefix='xrai-django-v2-'))
    workspace = temp / 'workspace'
    bootstrap = setup(workspace, cache, files, data)
    (output / 'runtime-before.json').write_text(json.dumps(bootstrap, indent=2) + '\n')
    (output / 'freeze-before.json').write_bytes((CASE / 'freeze.json').read_bytes())
    (output / 'setup-lock-before.json').write_bytes((CASE / 'setup.lock.json').read_bytes())
    oracle = decode((CASE / 'evaluator/oracle.json').read_bytes())
    origins = {name: {'path': '/checkout/' + name.replace('.', '/') + '.py',
                     'sha256': sha(files[name.replace('.', '/') + '.py'])}
               for name in ['django.db.migrations.operations.models', 'django.db.migrations.operations.base',
                            'django.db.utils', 'django.db.models.options']}
    origins['policy'] = {'path': '/public/policy.py', 'sha256': sha((CASE / 'agent/policy.py').read_bytes())}
    phases = []
    for phase in ('agent', 'a', 'b', 'controls'):
        require(time.monotonic() - start < 240, 'batch budget must leave full next-process ceiling')
        if phase == 'b':
            (workspace / 'public/deployment.json').write_bytes((CASE / 'evaluator/reference.json').read_bytes())
        run_receipt = execute(command(phase), workspace, timeout=60, output_limit=BOUND,
                              phase='django-v2-' + phase, arbitrary_agent=True)
        (output / (phase + '-harness.json')).write_text(json.dumps(run_receipt, indent=2) + '\n')
        verify_receipt(run_receipt)
        require(confirmed_receipt(run_receipt) and run_receipt['eligible_for_agent_run'],
                'domain teardown unconfirmed; workspace retained')
        raw = stream(run_receipt, 'stdout')
        stderr = stream(run_receipt, 'stderr')
        (output / (phase + '.stdout')).write_bytes(raw)
        (output / (phase + '.stderr')).write_bytes(stderr)
        require(run_receipt['execution_status'] == 'ok' and run_receipt['exit_code'] == 0, 'contained oracle/probe failed')
        report = decode(raw)
        (output / (phase + '-report.json')).write_text(json.dumps(report, indent=2) + '\n')
        if phase == 'agent':
            require(report['private_reads_denied'] is True and report['checkout_readonly'] is True and
                    all(report['public_readable'].values()) and all(r['readable'] is False for r in report['attacks']),
                    'effective agent visibility failed')
            result = {'visibility_verified': True, 'private_reads_attempted': len(report['attacks'])}
        else:
            result = validate_result(report, phase, oracle, origins)
        phases.append({'phase': phase, 'result': result, 'domain_id': run_receipt['domain_id'],
                       'teardown_confirmed': True, 'stdout_sha256': sha(raw), 'stderr_sha256': sha(stderr)})
    unchanged = (inventory(workspace / 'checkout') == bootstrap['source_files'] and
                 inventory(workspace / 'runtime') == bootstrap['runtime_files'] and
                 inventory(workspace / 'dependencies') == bootstrap['dependency_files'] and
                 all(sha(Path(p).read_bytes()) == r['sha256'] for p, r in bootstrap['dynamic_libraries'].items()))
    require(unchanged, 'runtime/captured source changed across execution')
    result = {'schema': 'xrai.eval.django-router.physical-pair.v2', 'freeze_sha256': FREEZE_SHA,
              'phases': phases, 'source_runtime_dependencies_unchanged': True,
              'physical_cells': 12, 'physical_controls': 4, 'oracle_executed': True,
              'baseline_requirement_satisfied': False, 'reference_requirement_satisfied': True,
              'model_veto_observed_before_router': True, 'public_agent_visibility_verified': True,
              'elapsed_batch_seconds': time.monotonic() - start,
              'phase_policy': lock()['phase_policy'], 'multimodule': False, 'projection': 19,
              'individual_eligible': False, 'qualified': False, 'admitted': False, 'provider_used': False}
    require(result['elapsed_batch_seconds'] <= 300, 'batch ceiling')
    (output / 'pair.json').write_text(json.dumps(result, indent=2) + '\n')
    shutil.rmtree(temp)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['verify', 'fetch', 'run'])
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.mode == 'verify':
        freeze, data, files = prepared()
        result = {'candidate_prepared': True, 'frozen_inputs': len(data), 'source_files': len(files),
                  'freeze_sha256': FREEZE_SHA, 'oracle_executed': False, 'physical_cells_planned': 12,
                  'physical_controls_planned': 4, 'multimodule': False, 'projection': 19,
                  'qualified': False, 'admitted': False}
    elif args.mode == 'fetch':
        require(args.cache is not None, 'cache required')
        result = acquire(args.cache)
    else:
        require(args.cache is not None and args.output is not None, 'cache and fresh output required')
        result = run(args.cache, args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
