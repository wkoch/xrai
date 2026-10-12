#!/usr/bin/env python3
"""Check 12 independent regression probes in isolated evaluator checkouts, without any agent."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from materialize_task import ROOT, materialize, tasks


def run(command, directory, environment=None):
    process = subprocess.run(command, cwd=directory, env=environment, capture_output=True, text=True, timeout=120)
    return {"command": command, "exit_code": process.returncode, "stdout": process.stdout[-3000:], "stderr": process.stderr[-3000:]}


def probe(task, workspace, python_dependencies):
    oracle = json.loads((ROOT / task['agent_success_criteria']['oracle']).read_text(encoding="utf-8"))
    src = ROOT / oracle['executable_probe']
    dst = workspace / src.name
    shutil.copyfile(src, dst)
    family = task['family']
    if family == 'Rust':
        lib = run(['rustc', '--crate-type', 'lib', '--crate-name', 'upstream', '--edition=2021', 'src/lib.rs', '-o', 'libupstream.rlib'], workspace)
        if lib['exit_code']:
            return [lib]
        compile_probe = run(['rustc', '--edition=2021', str(dst), '--extern', 'upstream=libupstream.rlib', '-o', 'oracle_probe'], workspace)
        if compile_probe['exit_code']:
            return [lib, compile_probe]
        return [lib, compile_probe, run([str(workspace / 'oracle_probe')], workspace)]
    if family == 'TSJS':
        if src.suffix == '.ts':
            (workspace / 'tsconfig.oracle.json').write_text(json.dumps({'compilerOptions': {'strict': True, 'noEmit': True, 'target': 'ES2015', 'moduleResolution': 'Node16', 'module': 'Node16'}, 'files': ['probe.ts']}), encoding="utf-8", newline="\n")
            return [run(['tsc', '--project', 'tsconfig.oracle.json'], workspace)]
        return [run(['node', 'probe.js'], workspace)]
    if family == 'Python':
        env = dict(os.environ)
        env['PYTHONPATH'] = os.pathsep.join([str(workspace / 'src'), str(workspace), str(python_dependencies)])
        return [run([sys.executable, 'probe.py'], workspace, env)]
    env = dict(os.environ, GOPROXY='off', GOSUMDB='off', GOCACHE=str(workspace.parent / 'go-cache'))
    return [run(['go', 'test', '-run', '^TestOracle$', '-count=1', '.'], workspace, env)]


def verify(python_dependencies):
    results = []
    for task in tasks():
        oracle = json.loads((ROOT / task['agent_success_criteria']['oracle']).read_text(encoding="utf-8"))
        if 'executable_probe' not in oracle:
            continue
        with tempfile.TemporaryDirectory(prefix='xrai-oracle-') as temp:
            dest = Path(temp) / 'task'
            materialize(task['id'], dest)
            workspace = dest / 'workspace'
            baseline = probe(task, workspace, python_dependencies)
            is_review = task['kind'] == 'review'
            change = ROOT / (task['input']['proposed_diff'] if is_review else oracle['reference_patch']['path'])
            application = run(['git', 'apply', str(change)], workspace)
            changed = probe(task, workspace, python_dependencies) if application['exit_code'] == 0 else []
            passed_baseline = all(r['exit_code'] == 0 for r in baseline)
            passed_changed = bool(changed) and all(r['exit_code'] == 0 for r in changed)
            expected_baseline = is_review
            expected_changed = not is_review
            passed = application['exit_code'] == 0 and passed_baseline == expected_baseline and passed_changed == expected_changed
            # Compiler failure must identify the intended API/typing mismatch, not missing tooling.
            if any(r['exit_code'] == 127 for r in baseline + changed):
                passed = False
            results.append({'task': task['id'], 'kind': task['kind'], 'expected_baseline_pass': expected_baseline, 'expected_changed_pass': expected_changed, 'baseline': baseline, 'apply_patch': application, 'changed': changed, 'passed': passed})
    return {'schema_version': 1, 'mode': 'local regression probes, no model sessions', 'checks': len(results), 'passed': sum(r['passed'] for r in results), 'failures': sum(not r['passed'] for r in results), 'results': results, 'agent_success_measured': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--python-dependencies', type=Path, default=Path('/private/tmp/xrai-corpus-pydeps'))
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    result = verify(args.python_dependencies)
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in result.items() if k != 'results'}))
    sys.exit(bool(result['failures']))
