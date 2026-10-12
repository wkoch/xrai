"""Read-only verification of freshly downloaded native CI artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'eval/scripts'))
from retain_native_binaries import verify as verify_binaries
from verify_context import verify as verify_context
from verify_semantics import verify as verify_semantics
from verify_worker_measurement import verify as verify_workers


def reconcile(directory, commit):
    results = {}
    for host in ['x86_64-unknown-linux-gnu', 'aarch64-apple-darwin']:
        native = directory / ('native-' + host)
        manifest = json.loads((native / 'binaries/manifest.json').read_text())
        assert manifest['code_commit'] == commit
        assert 'host: ' + host in manifest['rustc_verbose']
        binaries = verify_binaries(native / 'binaries')
        contexts = {name: verify_context(ROOT / 'eval/context' / (name + '-input.json'),
                    native / ('context-' + name + '.json'))
                    for name in ['removed-consumer', 'central-hunk', 'r3-binding']}
        semantics = {}
        for name in ['rust-r3', 'counterproofs-r3', 'counterproofs-extra', 'counterproofs-cfg',
                     'tokio-test-development', 'incremental-events', 'p3-consumer']:
            semantics[name] = verify_semantics(ROOT / 'eval/semantics/r3' / (name + '.json'),
                                               native / 'r3' / (name + '-completed.stdout'))
        for name, source in [('fixtures', 'rust-r1-r2'), ('tokio', 'tokio-development'),
                             ('counterproofs', 'rust-counterproofs')]:
            semantics['legacy-' + name] = verify_semantics(ROOT / 'eval/semantics' / (source + '.json'),
                                                           native / ('semantics-' + name + '.json'))
        results[host] = {'environment': json.loads((native / 'environment.json').read_text()),
                         'binaries': binaries, 'contexts': contexts, 'semantics': semantics,
                         'worker_resources': verify_workers(native / 'worker-resources'),
                         'artifact_files': {str(p.relative_to(native)): hashlib.sha256(p.read_bytes()).hexdigest()
                                            for p in sorted(native.rglob('*')) if p.is_file()}}
    return {'verified': True, 'code_commit': commit, 'targets': results,
            'scope': 'native experimental receipts and retained bytes; no competitive admission'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('immutable output already exists')
    result = reconcile(args.directory, args.commit)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'verified': True, 'targets': list(result['targets'])}))
