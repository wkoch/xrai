#!/usr/bin/env python3
"""Native M0-05 proof; evaluator Python is outside the sandbox, stdin contains sources.
The sandbox sees one executable, OS libraries, empty HOME/PATH, and no network.
Linux requires bubblewrap. macOS requires the OS sandbox-exec command.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import re
import shutil
import socket
import subprocess
import tempfile
import time

DIALECTS = ('rust', 'javascript', 'jsx', 'typescript', 'tsx', 'python', 'go')
ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parents[1] / 'tests/fixtures/parsing'


def run_proof(binary, output):
    host = platform.system()
    if host not in ('Darwin', 'Linux'):
        raise RuntimeError('M0-05 supports only Linux and macOS')
    inspection = ['/usr/bin/otool', '-L', str(binary)] if host == 'Darwin' else ['/usr/bin/ldd', str(binary)]
    inspected = subprocess.run(inspection, text=True, capture_output=True, check=True)
    abi = subprocess.run(['/usr/bin/otool', '-l', str(binary)], text=True, capture_output=True, check=True).stdout if host == 'Darwin' else subprocess.run(['getconf', 'GNU_LIBC_VERSION'], text=True, capture_output=True, check=True).stdout
    with tempfile.TemporaryDirectory(prefix='xrai-parsing-clean-') as tmp:
        clean = Path(tmp).resolve()
        tmp = str(clean)
        copied = clean / 'parsing-spike'
        shutil.copy2(binary, copied)
        if host == 'Darwin':
            sandbox = shutil.which('sandbox-exec')
            if not sandbox:
                raise RuntimeError('sandbox-exec unavailable: autonomy proof pending')
            rules = '(subpath "/System")(subpath "/usr/lib")(literal "/")'
            profile = '(version 1)(deny default)(allow process-fork)(allow process-exec (literal ' + json.dumps(str(copied)) + '))(allow sysctl-read)(allow mach-lookup)(allow file-read-metadata)(allow file-map-executable ' + rules + ' (literal ' + json.dumps(str(copied)) + '))(allow file-read* ' + rules + ' (subpath ' + json.dumps(tmp) + '))(allow file-read* file-write* (literal "/dev/null"))'
            prefix = [sandbox, '-p', profile, str(copied)]
        else:
            sandbox = shutil.which('bwrap')
            if not sandbox:
                raise RuntimeError('bubblewrap unavailable: autonomy proof pending')
            prefix = [sandbox, '--unshare-all', '--die-with-parent', '--new-session', '--clearenv', '--dir', '/work', '--dir', '/usr', '--ro-bind', '/usr/lib', '/usr/lib']
            for path in ('/lib', '/lib64'):
                if Path(path).exists():
                    prefix += ['--ro-bind', path, path]
            prefix += ['--ro-bind', str(copied), '/work/parsing-spike', '--proc', '/proc', '--dev', '/dev', '--chdir', '/work', '--setenv', 'PATH', '/absent', '--setenv', 'HOME', '/work', '/work/parsing-spike']
        env = {'PATH': '/absent', 'HOME': tmp, 'TMPDIR': tmp, 'LANG': 'C', 'LC_ALL': 'C'}
        results = []
        def execute(args, source=b''):
            start = time.perf_counter_ns()
            result = subprocess.run(prefix + args, input=source, capture_output=True, env=env, timeout=15)
            return result, (time.perf_counter_ns() - start) / 1e6
        result, startup = execute(['inventory'])
        if result.returncode:
            raise RuntimeError(f'sandbox inventory failed ({result.returncode}): {result.stderr.decode(errors="replace")}')
        inventory = json.loads(result.stdout)
        with tempfile.NamedTemporaryFile(prefix='xrai-evaluator-canary-') as canary, socket.socket() as server:
            canary.write(b'evaluator-only'); canary.flush()
            server.bind(('127.0.0.1', 0)); server.listen()
            blocked, _ = execute(['isolation-check', canary.name, str(server.getsockname()[1])])
            assert blocked.returncode == 0, blocked.stderr.decode(errors='replace')
            isolation_check = json.loads(blocked.stdout)
            assert all(isolation_check.values())

        for dialect in DIALECTS:
            for state, expected in (('valid', 0), ('incomplete', 2)):
                source = (FIXTURES / f'{dialect}.{state}').read_bytes()
                result, elapsed = execute(['parse', dialect], source)
                if result.returncode != expected:
                    raise AssertionError((dialect, state, result.returncode, result.stderr.decode(errors='replace')))
                parsed = json.loads(result.stdout)
                assert parsed['complete'] == (state == 'valid')
                assert parsed['source_bytes'] == len(source)
                assert parsed['tree'] and parsed['node_count'] > 0
                if state == 'valid':
                    assert parsed['query_matches'] > 0
                if state == 'incomplete':
                    assert parsed['diagnostics']
                    for diagnostic in parsed['diagnostics']:
                        assert 0 <= diagnostic['start_byte'] <= diagnostic['end_byte'] <= len(source)
                        assert diagnostic['start_line'] >= 1
                results.append({'dialect': dialect, 'state': state, 'source_sha256': hashlib.sha256(source).hexdigest(), 'elapsed_ms_including_sandbox': elapsed, 'exit_code': result.returncode, 'parsed': parsed})
        runtimes = ['node', 'python', 'go', 'git', 'cc']
        os_release = Path('/etc/os-release').read_text() if host == 'Linux' else ''
        baseline = host == 'Linux' and platform.machine() == 'x86_64' and 'glibc 2.39' in abi and 'VERSION_ID="24.04"' in os_release
        if host == 'Darwin':
            assert re.search(r'\bminos\s+15\.0\b', abi), 'deployment target is not macOS 15.0'
            os_version = subprocess.run(['/usr/bin/sw_vers', '-productVersion'], capture_output=True, text=True, check=True).stdout.strip()
            # A runner with newer patch-level 15.x is evidence of 15.x, not literal 15.0.
            baseline = platform.machine() == 'arm64' and os_version == '15.0'
        else:
            os_version = os_release
        report = {'schema': 'm0-packaging-proof-v1', 'host': host, 'architecture': platform.machine(), 'os_version': os_version, 'baseline_exactly_executed': baseline, 'binary_bytes': copied.stat().st_size, 'binary_sha256': hashlib.sha256(copied.read_bytes()).hexdigest(), 'clean_directory_entries': [p.name for p in clean.iterdir()], 'auxiliary_runtimes_in_path': {runtime: shutil.which(runtime, path=env['PATH']) for runtime in runtimes}, 'network_policy': 'deny default/network' if host == 'Darwin' else 'unshared network namespace', 'sandbox': sandbox, 'dynamic_libraries': inspected.stdout, 'abi_inspection': abi, 'inventory': inventory, 'isolation_negative_probes': isolation_check, 'startup_ms_including_sandbox': startup, 'children_max_rss_bytes_including_sandbox_and_abi_inspection': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * (1 if host == 'Darwin' else 1024), 'fixtures': results, 'paid_campaign_executed': False}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        print(json.dumps({'output': str(output), 'fixtures': len(results), 'binary_bytes': report['binary_bytes'], 'baseline_exactly_executed': baseline}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run_proof(args.binary.resolve(), args.output.resolve())


if __name__ == '__main__':
    main()
