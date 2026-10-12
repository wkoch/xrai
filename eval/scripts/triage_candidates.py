#!/usr/bin/env python3
"""Measure complete pinned upstream archives; no build/case readiness is inferred."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import gzip
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {'.rs', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.py', '.pyx', '.pxd', '.go'}
EXCLUDED_PARTS = {'tests', 'test', '__tests__', 'testdata', 'fixtures', 'docs', 'doc', 'documentation', 'examples', 'example', 'benches', 'benchmarks', 'vendor', 'vendored', 'node_modules', 'dist', 'build', 'generated', '.git', 'target', 'typings'}


def classify(path, data):
    name = path.name.lower()
    if path.suffix not in EXTENSIONS:
        return 'not_production_source_extension'
    if any(part.lower() in EXCLUDED_PARTS for part in path.parts):
        return 'excluded_directory'
    if name.startswith(('test_', 'test.', 'zz_generated.', 'generated_')) or name.endswith(('_test.go', '.test.ts', '.test.js', '.spec.ts', '.spec.js', '_test.py', '_tests.rs')):
        return 'test_filename'
    prefix = data[:2048].lower()
    if b'code generated' in prefix or b'@generated' in prefix or b'automatically generated' in prefix or b'do not edit' in prefix:
        return 'generated_marker'
    return None


def measure(candidate, cache):
    repository = candidate['repository']
    result = dict(candidate)
    try:
        commit = candidate.get('commit')
        if not commit:
            output = subprocess.run(['git', 'ls-remote', 'https://github.com/' + repository + '.git', 'HEAD'], check=True, capture_output=True, text=True, timeout=60).stdout
            commit = output.split()[0]
        if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
            raise ValueError('candidate must have full immutable commit')
        result['commit'] = commit
        url = 'https://codeload.github.com/' + repository + '/tar.gz/' + commit
        archive = cache / (repository.replace('/', '--') + '-' + commit + '.tar.gz')
        if not archive.exists():
            with urllib.request.urlopen(url, timeout=120) as response:
                archive.write_bytes(response.read())
        blob = archive.read_bytes()
        files, excluded, licenses, manifest = [], {}, [], False
        with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tar:
            for member in tar:
                if not member.isfile():
                    continue
                path = PurePosixPath(*PurePosixPath(member.name).parts[1:])
                data = tar.extractfile(member).read()
                if path.name.lower().startswith(('license', 'copying')):
                    licenses.append(str(path))
                if str(path) == candidate['build_manifest']:
                    manifest = True
                    result['build_manifest_sha256'] = hashlib.sha256(data).hexdigest()
                    text = data.decode('utf-8')
                    if path.name == 'package.json':
                        package = json.loads(text)
                        result['declared_tool_versions'] = {k: package.get(k) for k in ('engines', 'packageManager')}
                        result['declared_scripts'] = package.get('scripts', {})
                    else:
                        result['declared_manifest_constraints'] = [line for line in text.splitlines() if any(k in line for k in ('rust-version', 'requires-python', 'go 1.', 'toolchain', 'build-backend'))]
                reason = classify(path, data)
                if reason:
                    excluded[reason] = excluded.get(reason, 0) + 1
                    continue
                files.append({'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'nonempty_lines': sum(bool(line.strip()) for line in data.splitlines())})
        file_count = len(files)
        lines = sum(f['nonempty_lines'] for f in files)
        result.update({'archive_url': url, 'archive_sha256': hashlib.sha256(blob).hexdigest(), 'archive_bytes': len(blob), 'complete_checkout': True,
                       'production_files': file_count, 'production_nonempty_lines': lines, 'production_manifest_sha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
                       'license_files': licenses, 'build_manifest_found': manifest, 'excluded_file_counts': excluded,
                       'production_manifest': files,
                       'size_floor_met': lines >= 50000 or file_count >= 500,
                       'status': 'size_eligible_build_probe_case_review_pending' if lines >= 50000 or file_count >= 500 else 'discarded_size_floor',
                       'build_execution': 'not_run', 'probe_execution': 'not_run', 'selected_tasks': 0,
                       'semantic_production_classification': 'conservative_path_and_generated_marker_filter_requires_second_reader'})
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        result.update({'status': 'triage_failed', 'error': str(error), 'selected_tasks': 0})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'qualification/candidate-triage.json')
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    candidates = json.loads((ROOT / 'qualification/candidates.json').read_text())['candidates']
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda c: measure(c, args.cache), candidates))
    manifest_dir = args.output.parent / 'production-manifests'
    manifest_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        if 'production_manifest' in result:
            data = gzip.compress(json.dumps(result.pop('production_manifest'), sort_keys=True).encode(), mtime=0)
            path = manifest_dir / (result['repository'].replace('/', '--') + '.json.gz')
            path.write_bytes(data)
            result['production_manifest_artifact'] = {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    payload = {'schema_version': 1, 'recorded_at': datetime.now(timezone.utc).isoformat(),
               'measurement_method': 'complete GitHub archive at full SHA; nonempty byte lines of source extensions after explicit path/name/generated-prefix exclusions; test blocks inside production Rust files remain a conservative classification limitation',
               'exclusions': sorted(EXCLUDED_PARTS), 'extensions': sorted(EXTENSIONS), 'candidates': results,
               'qualified_tasks': 0, 'competitive_runs_allowed': False}
    args.output.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    print(json.dumps([{k: row.get(k) for k in ('repository', 'commit', 'status', 'production_files', 'production_nonempty_lines')} for row in results], indent=2))


if __name__ == '__main__':
    main()
