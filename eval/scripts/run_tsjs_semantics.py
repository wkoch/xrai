#!/usr/bin/env python3
"""Run only the owned native analyzer, in disposable Linux CI, on frozen data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
import verify_tsjs_semantics as verifier


def run(binary, output):
    if os.environ.get('GITHUB_ACTIONS') != 'true' or platform.system() != 'Linux':
        raise ValueError('native analyzer execution requires disposable Linux CI')
    data = verifier.labels(); output = Path(output); output.mkdir(parents=True, exist_ok=False)
    snapshots = output / 'outputs'; snapshots.mkdir()
    native = output / 'native-bin'; native.mkdir()
    retained_binary = native / 'tsjs-semantics'; shutil.copy2(binary, retained_binary)
    binary_sha = hashlib.sha256(retained_binary.read_bytes()).hexdigest()
    receipts = []
    for case in data['cases']:
        raw = json.dumps(case['input'], ensure_ascii=False, separators=(',', ':')).encode()
        start = time.monotonic()
        proc = subprocess.run([str(retained_binary.resolve())], input=raw, capture_output=True, timeout=30, check=False)
        receipts.append({'case': case['id'], 'input_sha256': hashlib.sha256(raw).hexdigest(), 'exit_code': proc.returncode, 'stderr_sha256': hashlib.sha256(proc.stderr).hexdigest(), 'stdout_sha256': hashlib.sha256(proc.stdout).hexdigest(), 'elapsed_seconds': time.monotonic() - start})
        (output / 'invocations.json').write_text(json.dumps(receipts, indent=2) + '\n')
        if proc.returncode != 0 or proc.stderr or len(proc.stdout) > 16 * 1024 * 1024:
            (output / (case['id'] + '.stderr')).write_bytes(proc.stderr)
            raise ValueError(f"owned analyzer failed {case['id']}: exit={proc.returncode}; stderr={proc.stderr.decode(errors='replace')}")
        (snapshots / (case['id'] + '.json')).write_bytes(proc.stdout)
    if hashlib.sha256(retained_binary.read_bytes()).hexdigest() != binary_sha:
        raise ValueError('binary changed during execution')
    result = verifier.verify_outputs(snapshots)
    (output / 'verification.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    sources = ['crates/xrai-eval/src/tsjs_semantics.rs', 'crates/xrai-eval/src/bin/tsjs-semantics.rs', 'crates/xrai-eval/src/worker_spike.rs', 'crates/xrai-eval/src/parsing_spike.rs', 'crates/xrai-eval/queries/javascript.scm', 'crates/xrai-eval/queries/typescript.scm', 'eval/scripts/verify_tsjs_semantics.py', 'eval/scripts/run_tsjs_semantics.py', 'eval/semantics/tsjs/labels.json', 'eval/semantics/tsjs/freeze-before-resolver.json', 'Cargo.lock', 'crates/xrai-eval/parsing-provenance.json']
    receipt = {'schema_version': 'xrai.eval.tsjs.native-receipt.v1', 'binary_sha256': binary_sha, 'source_sha256': {p: hashlib.sha256((verifier.ROOT / p).read_bytes()).hexdigest() for p in sources}, 'code_commit': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID'), 'platform': platform.platform(), 'machine': platform.machine(), 'cases': len(receipts), 'upstream_executed': False, 'calls_to_upstream_compiler': 0, 'owned_analyzer_only': True, 'global_admission': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return result


def main():
    p = argparse.ArgumentParser(); p.add_argument('--binary', required=True); p.add_argument('--output', required=True); args = p.parse_args()
    print(json.dumps(run(args.binary, args.output), indent=2))


if __name__ == '__main__':
    main()
