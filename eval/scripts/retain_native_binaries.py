#!/usr/bin/env python3
"""Preserve measured executable bytes and a verifiable per-run manifest."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess

BINARIES = ('parsing-spike', 'worker-spike', 'worker-persistent',
            'worker-benchmark', 'semantics-spike', 'context-spike')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def retain(source, destination):
    if destination.exists():
        raise ValueError('immutable destination already exists')
    inputs = [(name, source / name) for name in BINARIES]
    for _, path in inputs:
        if not path.is_file() or path.is_symlink():
            raise ValueError('missing regular executable: ' + str(path))
    destination.mkdir(parents=True)
    entries = []
    for name, path in inputs:
        copy = destination / name
        shutil.copy2(path, copy)
        if sha(copy) != sha(path):
            raise ValueError('copy differs: ' + name)
        entries.append({'name': name, 'bytes': copy.stat().st_size,
                        'sha256': sha(copy), 'mode': copy.stat().st_mode & 0o777})
    manifest = {'format': 'l5-native-executables-v1', 'system': platform.system(),
                'machine': platform.machine(), 'platform': platform.platform(),
                'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'rustc_verbose': subprocess.check_output(['rustc', '--version', '--verbose'], text=True),
                'executables': entries}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return verify(destination)


def verify(destination):
    manifest = json.loads((destination / 'manifest.json').read_text())
    if manifest['format'] != 'l5-native-executables-v1':
        raise ValueError('unknown manifest format')
    if [e['name'] for e in manifest['executables']] != list(BINARIES):
        raise ValueError('incomplete executable set')
    for entry in manifest['executables']:
        path = destination / entry['name']
        if path.is_symlink() or not path.is_file():
            raise ValueError('executable is not a regular file')
        if path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
            raise ValueError('executable bytes differ: ' + entry['name'])
    return {'verified': True, 'code_commit': manifest['code_commit'],
            'executables': manifest['executables']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('target/release'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify(args.output) if args.verify else retain(args.source, args.output), indent=2))
