#!/usr/bin/env python3
"""Rebuild evaluator-only vertical baselines/references; never admit a competitive run."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone

from materialize_task import ROOT, safe_path, source_files
from prepare_vertical_sources import regular_tree

TIMEOUT = 600
STREAM_LIMIT = 1024 * 1024
DISK_HEADROOM = 2 * 1024 * 1024 * 1024
VERSIONS = {'cargo': 'cargo 1.98.1', 'rustc': 'rustc 1.98.1', 'python': 'Python 3.15.0',
            'node': 'v26.11.1', 'npm': '11.20.0', 'go': 'go version go1.27.2'}
ENV_KEYS = ('RUSTUP_TOOLCHAIN', 'CARGO_TARGET_DIR', 'GOCACHE', 'GOMODCACHE', 'GOTOOLCHAIN',
            'GOMAXPROCS', 'GOFLAGS', 'GOPROXY', 'GOSUMDB', 'PYTHONPATH',
            'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_bytes(path, expected):
    data = path.read_bytes()
    if sha(data) != expected:
        raise ValueError(f'fingerprint mismatch: {path}')
    return data


def kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_process(command, cwd, env, output, name, timeout=TIMEOUT):
    """Bound files and wait; killpg is auxiliary, not a disposable-domain proof."""
    started = time.monotonic()
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    observed = {'stdout': 0, 'stderr': 0}
    digests = {key: hashlib.sha256() for key in buffers}
    error, cleanup, code = None, 'not_started', None
    process = None
    selector = selectors.DefaultSelector()
    try:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        for key, stream in [('stdout', process.stdout), ('stderr', process.stderr)]:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, key)
        deadline = started + timeout
        final_drain = None
        while selector.get_map() or process.poll() is None:
            now = time.monotonic()
            if now >= deadline and error is None:
                error = 'timeout'
                kill_group(process)
                final_drain = now + 0.5
            if process.poll() is not None and final_drain is None:
                kill_group(process)
                final_drain = now + 0.5
            if final_drain is not None and now >= final_drain:
                break
            for entry, _ in selector.select(0.05):
                chunk = os.read(entry.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(entry.fileobj)
                    entry.fileobj.close()
                    continue
                key = entry.data
                observed[key] += len(chunk)
                digests[key].update(chunk)
                room = STREAM_LIMIT - len(buffers[key])
                buffers[key].extend(chunk[:max(0, room)])
        code = process.wait(timeout=5)
        cleanup = 'child_reaped_pipes_closed' if not selector.get_map() else 'inconclusive_open_pipes'
    except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        if process is not None:
            kill_group(process)
            try:
                code = process.wait(timeout=5)
                cleanup = 'child_reaped_after_error'
            except subprocess.TimeoutExpired:
                cleanup = 'inconclusive_child_wait'
    finally:
        for entry in list(selector.get_map().values()):
            entry.fileobj.close()
        selector.close()
    streams = {}
    output.mkdir(parents=True, exist_ok=True)
    for key, data in buffers.items():
        path = output / f'{name}.{key}.log'
        path.write_bytes(data)
        streams[key] = {'path': str(path), 'captured_bytes': len(data),
                        'observed_bytes': observed[key], 'captured_sha256': sha(data),
                        'observed_sha256': digests[key].hexdigest(),
                        'truncated': observed[key] > len(data)}
    record = {'command': list(map(str, command)), 'cwd': str(cwd),
              'environment': {key: env[key] for key in ENV_KEYS if key in env},
              'timeout_seconds': timeout, 'stream_limit_bytes': STREAM_LIMIT,
              'elapsed_seconds': time.monotonic() - started, 'exit_code': code,
              'error': error, 'cleanup_status': cleanup,
              'containment': 'trusted evaluator build/probe; process group auxiliary only',
              'streams': streams}
    (output / f'{name}.json').write_text(json.dumps(record, indent=2) + '\n')
    if error and error.startswith('KeyboardInterrupt'):
        raise KeyboardInterrupt('cancelled; process receipt preserved')
    return record, b'\n'.join(bytes(value) for value in buffers.values()).decode('utf-8', 'replace')


def succeeded(record):
    return record['exit_code'] == 0 and record['error'] is None and record['cleanup_status'] == 'child_reaped_pipes_closed'


def require_command(command, cwd, env, output, name):
    record, text = run_process(command, cwd, env, output, name)
    if not succeeded(record):
        raise ValueError(f'preparation/tooling failed: {name} (see retained receipt)')
    return record, text


def materialize_base(case, destination, manifest):
    snapshot = manifest['snapshots'][case['repository'] + '@' + case['baseline_commit']]
    if snapshot['repository'] != case['repository'] or snapshot['commit'] != case['baseline_commit']:
        raise ValueError('baseline snapshot identity mismatch')
    archive = ROOT / str(safe_path(snapshot['archive']))
    if snapshot.get('upstream_archive') != case['upstream_baseline']:
        raise ValueError('normalized baseline upstream pin mismatch')
    blob = checked_bytes(archive, snapshot['sha256'])
    expected = {entry['path']: entry for entry in source_files(snapshot)}
    seen = set()
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tree:
        for member in tree:
            name = str(safe_path(member.name))
            if not member.isfile() or member.issym() or member.islnk() or '.git' in Path(name).parts or name in seen:
                raise ValueError('baseline must be unique regular files without Git state')
            data = tree.extractfile(member).read()
            if name not in expected or sha(data) != expected[name]['sha256'] or len(data) != expected[name]['bytes']:
                raise ValueError('baseline inventory/file fingerprint mismatch: ' + name)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(member.mode & 0o777)
            seen.add(name)
    if seen != set(expected) or len(seen) != snapshot['file_count']:
        raise ValueError('incomplete baseline tree')
    return {'archive': str(archive), 'sha256': snapshot['sha256'], 'files': len(seen),
            'commit': case['baseline_commit'], 'normalization': snapshot['materialization_policy']}


def materialize_reference(case, destination, cache):
    archive = cache / (case['key'] + '-reference.tar.gz')
    blob = checked_bytes(archive, case['upstream_reference']['sha256'])
    files, links = regular_tree(blob)
    for name, (data, mode) in files.items():
        target = destination / str(safe_path(name))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(mode & 0o777)
    return {'archive': str(archive), 'sha256': sha(blob), 'files': len(files),
            'commit': case['reference_commit'], 'materialized_links': links,
            'normalization': 'xrai.complete.regular-files.internal-link-copy.v1'}


def hidden_files(key, checkout):
    directory = ROOT / 'qualification/vertical/oracles' / key
    mapping = {'tokio': [('sync_mutex.rs', 'tokio/tests/sync_mutex.rs'), ('Cargo.lock', 'Cargo.lock')],
               'django': [('test_jsonfield.py', 'tests/model_fields/test_jsonfield.py')],
               'prometheus': [('queue_manager_test.go', 'storage/remote/queue_manager_test.go')],
               'typescript': []}[key]
    receipts = []
    for name, target in mapping:
        data = (directory / name).read_bytes()
        (checkout / target).write_bytes(data)
        receipts.append({'evaluator_path': str(directory / name), 'checkout_path': target, 'sha256': sha(data)})
    if key == 'typescript':
        path = directory / 'probe.cjs'
        receipts.append({'evaluator_path': str(path), 'checkout_path': None, 'sha256': sha(path.read_bytes())})
    return receipts


def tools_for(key):
    return {'tokio': ['cargo', 'rustc'], 'typescript': ['node', 'npm'],
            'django': ['python'], 'prometheus': ['go']}[key]


def tool_readiness(key, args, output):
    tools, receipts = {}, []
    env = dict(os.environ)
    env['GOTOOLCHAIN'] = 'local'
    env['RUSTUP_TOOLCHAIN'] = '1.98.1'
    for tool in tools_for(key):
        requested = getattr(args, tool)
        executable = shutil.which(requested)
        if executable is None:
            raise ValueError('required tool unavailable: ' + requested)
        executable = str(Path(executable).absolute())
        command = [executable, 'version' if tool == 'go' else '--version']
        record, text = require_command(command, output, env, output, 'tool-' + tool)
        observed = text.strip()
        version_matches = (observed.startswith(VERSIONS[tool] + (' (' if tool in {'cargo', 'rustc'} else ' '))
                           if tool in {'cargo', 'rustc', 'go'} else observed == VERSIONS[tool])
        if not version_matches:
            raise ValueError(f'tool version mismatch: {tool}; require {VERSIONS[tool]}, observed {text.strip()}')
        tools[tool] = executable
        receipts.append(record)
    return tools, receipts


def python_dependency_check(directory):
    # Check imported modules, not stale/duplicate dist-info metadata in tooling.
    return """import asgiref,sqlparse,json,hashlib
from pathlib import Path
root=Path(%r).resolve()
result={}
for name,module,pin in [('asgiref',asgiref,'3.12.1'),('sqlparse',sqlparse,'0.5.4')]:
 path=Path(module.__file__).resolve()
 if module.__version__!=pin or not path.is_relative_to(root):
  raise RuntimeError('pinned dependency/module origin mismatch: '+name)
 result[name]={'version':module.__version__,'module':str(path),'module_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
print(json.dumps(result))
""" % str(directory.resolve())


def case_commands(key, phase, tools, checkout, args, env, output):
    prepare = []
    if key == 'tokio':
        if args.prepare_dependencies:
            prepare.append([tools['cargo'], 'fetch', '--locked'])
        command = [tools['cargo'], 'test', '--locked', '--offline', '-p', 'tokio', '--features', 'full', '--test', 'sync_mutex']
        if phase == 'baseline':
            command += ['mutex_fifo_with_coop_budget', '--', '--exact', '--nocapture']
        else:
            command += ['--', '--nocapture']
    elif key == 'typescript':
        if not args.prepare_dependencies:
            raise ValueError('fresh TypeScript checkout requires explicit --prepare-dependencies for npm ci')
        prepare += [[tools['npm'], 'ci', '--ignore-scripts', '--no-audit', '--no-fund'],
                    [tools['npm'], 'run', 'build:compiler']]
        command = [tools['node'], str(ROOT / 'qualification/vertical/oracles/typescript/probe.cjs')]
    elif key == 'django':
        if args.python_dependencies is None:
            raise ValueError('Django requires --python-dependencies with pinned asgiref/sqlparse')
        env['PYTHONPATH'] = str(checkout) + os.pathsep + str(args.python_dependencies.resolve())
        check = python_dependency_check(args.python_dependencies)

        record, _ = run_process([tools['python'], '-c', check], checkout, env, output, 'python-dependencies')
        if not succeeded(record):
            if not args.prepare_dependencies:
                raise ValueError('pinned Django dependencies unavailable; retained readiness failure')
            prepare.append([tools['python'], '-m', 'pip', 'install', '--no-input', '--no-deps', '--upgrade', '--target',
                            str(args.python_dependencies.resolve()), 'asgiref==3.12.1', 'sqlparse==0.5.4'])
        label = 'model_fields.test_jsonfield' + ('.TestQuerying.test_in_value_without_explicit_output_field' if phase == 'baseline' else '')
        command = [tools['python'], 'tests/runtests.py', label, '--settings=test_sqlite', '--parallel=1', '--verbosity=2']
    else:
        if args.prepare_dependencies:
            prepare.append([tools['go'], 'test', '-mod=readonly', '-p', '2', './storage/remote', '-run', '^$', '-count=1'])
        test = '^TestCalculateDesiredShardsDetail$' if phase == 'baseline' else '^TestCalculateDesiredShards'
        command = [tools['go'], 'test', '-mod=readonly', '-p', '2', './storage/remote', '-run', test, '-count=1', '-v']
    return prepare, command


def verdict(key, phase, record, text):
    if 'No space left on device' in text or 'ENOSPC' in text:
        return 'infrastructure_failure_enospc'
    if (record['error'] is not None or record['cleanup_status'] != 'child_reaped_pipes_closed'
            or any(stream['truncated'] for stream in record['streams'].values())):
        return 'infrastructure_failure'
    if phase == 'reference':
        markers = {'tokio': 'test result: ok.', 'typescript': '3 behavioral checks passed',
                   'django': 'Ran 129 tests', 'prometheus': '--- PASS: TestCalculateDesiredShards'}
        return 'reference_pass' if record['exit_code'] == 0 and markers[key] in text else 'reference_failure'
    markers = {'tokio': 'test mutex_fifo_with_coop_budget ... FAILED',
               'typescript': 'nullable union spread must not claim id always overwritten',
               'django': 'test_in_value_without_explicit_output_field',
               'prometheus': '--- FAIL: TestCalculateDesiredShardsDetail'}
    semantic = markers[key] in text
    if key == 'django':
        semantic = semantic and 'Ran 1 test' in text and 'FAILED (' in text
    return 'baseline_regression_reproduced' if record['exit_code'] not in (0, None) and semantic else 'baseline_not_reproduced_or_infrastructure_failure'


def execute_case(case, args, run_root, output, manifest):
    key = case['key']
    tools, tool_receipts = tool_readiness(key, args, output)
    result = {'id': case['id'], 'key': key, 'competitive_runs_allowed': False,
              'tool_receipts': tool_receipts, 'phases': []}
    for phase in ['baseline', 'reference']:
        directory = run_root / key / phase
        directory.mkdir(parents=True, exist_ok=False)
        logs = output / phase
        logs.mkdir()
        free_bytes = shutil.disk_usage(directory).free
        if free_bytes < DISK_HEADROOM:
            (logs / 'disk-readiness.json').write_text(json.dumps({'free_bytes': free_bytes, 'minimum_free_bytes': DISK_HEADROOM, 'status': 'insufficient_headroom'}, indent=2) + '\n')
            raise ValueError('insufficient disk headroom: need at least 2 GiB before each fresh checkout/build')
        source = materialize_base(case, directory, manifest) if phase == 'baseline' else materialize_reference(case, directory, args.cache)
        oracles = hidden_files(key, directory)
        env = dict(os.environ)
        env.update({'RUSTUP_TOOLCHAIN': '1.98.1', 'CARGO_TARGET_DIR': str(directory.parent / ('target-' + phase)),
                    'GOCACHE': str(directory.parent / ('gocache-' + phase)),
                    'GOMODCACHE': str(args.cache / 'gomodcache'), 'GOTOOLCHAIN': 'local',
                    'GOMAXPROCS': '2', 'GOFLAGS': '-mod=readonly',
                    'GOPROXY': 'https://proxy.golang.org' if args.prepare_dependencies else 'off',
                    'GOSUMDB': 'sum.golang.org' if args.prepare_dependencies else 'off',
                    'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD': '1'})
        prepare, command = case_commands(key, phase, tools, directory, args, env, logs)
        preparation = []
        locks_before = {name: sha((directory / name).read_bytes()) for name in ['Cargo.lock', 'package-lock.json', 'go.mod', 'go.sum'] if (directory / name).is_file()}
        row = {'phase': phase, 'source': source, 'hidden_oracles': oracles,
               'lock_sha256_before': locks_before, 'checkout': str(directory),
               'disk_free_before_materialization_bytes': free_bytes, 'preparation': preparation,
               'classification': 'pending_preparation_or_probe'}
        result['phases'].append(row)
        (output / 'case.json').write_text(json.dumps(result, indent=2) + '\n')
        for index, step in enumerate(prepare):
            record, text = run_process(step, directory, env, logs, 'prepare-' + str(index))
            preparation.append(record)
            (output / 'case.json').write_text(json.dumps(result, indent=2) + '\n')
            if not succeeded(record):
                row['classification'] = ('infrastructure_failure_enospc' if 'No space left on device' in text or 'ENOSPC' in text
                                         else 'infrastructure_preparation_failure')
                (output / 'case.json').write_text(json.dumps(result, indent=2) + '\n')
                raise ValueError(f'{row["classification"]}: preparation failed (see retained receipt)')
        locks_after_prepare = {name: sha((directory / name).read_bytes()) for name in locks_before}
        if locks_after_prepare != locks_before:
            row['lock_sha256_after_prepare'] = locks_after_prepare
            row['classification'] = 'infrastructure_lock_drift'
            (output / 'case.json').write_text(json.dumps(result, indent=2) + '\n')
            raise ValueError('preparation altered frozen upstream lock/go.mod/go.sum')
        if key == 'django' and preparation:
            require_command([tools['python'], '-c', python_dependency_check(args.python_dependencies)],
                            directory, env, logs, 'python-dependencies-after-prepare')
        record, text = run_process(command, directory, env, logs, 'probe')
        classification = verdict(key, phase, record, text)
        locks = {name: sha((directory / name).read_bytes()) for name in ['Cargo.lock', 'package-lock.json', 'go.mod', 'go.sum'] if (directory / name).is_file()}
        row.update({'lock_sha256': locks, 'probe': record, 'classification': classification})
        if locks != locks_before:
            row['classification'] = 'infrastructure_lock_drift'
        (output / 'case.json').write_text(json.dumps(result, indent=2) + '\n')
    result['status'] = 'vertical_pair_verified' if [r['classification'] for r in result['phases']] == ['baseline_regression_reproduced', 'reference_pass'] else 'vertical_pair_failed'
    (output / 'case.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', action='append', choices=['tokio', 'typescript', 'django', 'prometheus'])
    parser.add_argument('--cache', type=Path, default=Path('/private/tmp/xrai-l3-corpus'))
    parser.add_argument('--work-root', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--python-dependencies', type=Path)
    parser.add_argument('--prepare-dependencies', action='store_true', help='explicit local dependency installation/download; all commands retained')
    for tool, default in [('cargo', 'cargo'), ('rustc', 'rustc'), ('node', 'node'), ('npm', 'npm'), ('python', 'python3.15'), ('go', 'go')]:
        parser.add_argument('--' + tool, default=default)
    args = parser.parse_args()
    args.cache = args.cache.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    parent = args.work_root.resolve() if args.work_root else None
    if parent:
        parent.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix='xrai-vertical-fresh-', dir=parent))
    selection_path = ROOT / 'qualification/vertical/selection.json'
    selected = json.loads(selection_path.read_bytes())
    manifest = json.loads((ROOT / 'sources/manifest.json').read_bytes())
    summary = {'schema_version': 'xrai.eval.vertical.runner.v1',
               'recorded_at': datetime.now(timezone.utc).isoformat(),
               'selection_sha256': sha(selection_path.read_bytes()),
               'runner_sha256': sha(Path(__file__).read_bytes()),
               'competitive_runs_allowed': False, 'qualified_global_admission': False,
               'gate_policy': 'four evaluator pilots cannot open the 32-case gate',
               'run_root': str(run_root), 'fresh_checkouts': True,
               'prepare_dependencies_explicit': args.prepare_dependencies,
               'timeout_per_command_seconds': TIMEOUT, 'stream_limit_bytes': STREAM_LIMIT,
               'minimum_disk_headroom_per_phase_bytes': DISK_HEADROOM,
               'results': []}
    for case in selected['cases']:
        if args.case and case['key'] not in args.case:
            continue
        output = args.output / case['key']
        output.mkdir()
        try:
            result = execute_case(case, args, run_root, output, manifest)
        except (ValueError, OSError, KeyError, TypeError, tarfile.TarError, KeyboardInterrupt) as error:
            result = {'id': case['id'], 'key': case['key'], 'status': 'vertical_pair_failed',
                      'error': str(error), 'competitive_runs_allowed': False}
            # Keep any partially completed case.json/probe/preparation receipts.
            (output / 'failure.json').write_text(json.dumps(result, indent=2) + '\n')
        summary['results'].append(result)
        (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(case['key'] + ': ' + result['status'], flush=True)
        if result.get('error', '').startswith('cancelled;'):
            return 130
    return 0 if summary['results'] and all(row['status'] == 'vertical_pair_verified' for row in summary['results']) else 1


if __name__ == '__main__':
    sys.exit(main())
