#!/usr/bin/env python3
"""Refresh committed grammar/runtime source fingerprints and upstream legal notices.
Run after cargo fetch. Cargo verifies registry archives against Cargo.lock checksums.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[3]
CRATE = ROOT / 'crates/xrai-eval'
NAMES = ('tree-sitter', 'tree-sitter-language', 'tree-sitter-rust', 'tree-sitter-javascript', 'tree-sitter-typescript', 'tree-sitter-python', 'tree-sitter-go')


def generate():
    metadata = json.loads(subprocess.check_output(['cargo', 'metadata', '--locked', '--format-version', '1'], cwd=ROOT))
    lock = tomllib.loads((ROOT / 'Cargo.lock').read_text())
    checksums = {(p['name'], p['version']): p.get('checksum') for p in lock['package']}
    rows = []
    notices = CRATE / 'licenses/parsing'
    notices.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        package = next(p for p in metadata['packages'] if p['name'] == name)
        directory = Path(package['manifest_path']).parent
        fingerprints = {}
        for path in sorted(directory.rglob('*')):
            if path.is_file() and (path.suffix in ('.c', '.h') or path.name == 'node-types.json'):
                fingerprints[str(path.relative_to(directory))] = hashlib.sha256(path.read_bytes()).hexdigest()
        legal = []
        for path in sorted(directory.rglob('*')):
            if path.is_file() and path.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')):
                source_path = str(path.relative_to(directory))
                target = notices / f'{name}-{package["version"]}-{source_path.replace("/", "--")}'
                target.write_bytes(path.read_bytes())
                legal.append({'path': str(target.relative_to(CRATE)), 'source_path': source_path, 'scope': 'optional wasm libc; not compiled for native targets' if source_path.startswith('src/wasm-stdlib/') else 'native package or incorporated component', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'text': path.read_text(encoding='utf-8')})
        if not legal:
            target = notices / f'{name}-{package["version"]}-LICENSE'
            if not target.is_file():
                raise RuntimeError(f'missing legal notice: {name}')
            legal.append({'path': str(target.relative_to(CRATE)), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'upstream_url': f'https://raw.githubusercontent.com/tree-sitter/{name}/v{package["version"]}/LICENSE', 'source_path': 'LICENSE', 'scope': 'native grammar package', 'text': target.read_text(encoding='utf-8')})
        rows.append({'crate': name, 'version': package['version'], 'license': package['license'], 'license_scope': 'registry package declaration; nested component notices also apply', 'repository': package['repository'], 'registry_archive_sha256': checksums[(name, package['version'])], 'native_source_sha256': fingerprints, 'legal_notices': legal})
    output = CRATE / 'parsing-provenance.json'
    output.write_text(json.dumps({'schema': 'm0-parser-provenance-v1', 'packages': rows}, indent=2) + '\n')
    print(json.dumps({'packages': len(rows), 'output': str(output)}))


if __name__ == '__main__':
    generate()
