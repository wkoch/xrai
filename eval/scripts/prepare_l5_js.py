#!/usr/bin/env python3
"""Replay a read-only React capture; never executes captured project code."""
from __future__ import annotations
import argparse
import collections
import difflib
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / 'eval/qualification/l5-real/js'
COMMITS = {'base': '77912d9a05d7a90287fabdec76486f25869b2981',
           'head': '06f98c168060ef0213526a1aee696a568cec7f54'}
RUNTIME_PACKAGES = frozenset('react react-reconciler react-dom react-server react-client react-refresh react-is react-cache scheduler shared use-sync-external-store use-subscription'.split())
EXCLUDED_PARTS = frozenset('__tests__ __mocks__ __fixtures__ fixtures test tests test-utils benchmarks third_party vendor generated npm forks'.split())
REQUIRED = ['packages/react/src/ReactHooks.js',
            'packages/react-reconciler/src/ReactFiberHooks.new.js',
            'packages/react-reconciler/src/ReactFiberWorkLoop.new.js']
PATCH_PATHS = ['packages/react-reconciler/src/ReactFiberHooks.new.js',
               'packages/react-reconciler/src/ReactFiberHooks.old.js']
SETUP = ['package.json', 'yarn.lock', 'babel.config.js', 'scripts/jest/jest-cli.js',
         'scripts/jest/config.source-www.js', 'scripts/jest/config.base.js',
         'scripts/jest/preprocessor.js', 'LICENSE']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def excluded(path, data):
    p = PurePosixPath(path)
    if len(p.parts) < 3 or p.parts[0] != 'packages' or p.parts[1] not in RUNTIME_PACKAGES or p.suffix != '.js':
        return 'outside_allowlisted_runtime_js'
    if any(x.lower() in EXCLUDED_PARTS for x in p.parts) or '-test' in p.name or '.test.' in p.name:
        return 'test_doc_vendor_generated_or_fork_path'
    if p.name.endswith('.old.js'):
        return 'duplicate_legacy_reconciler_variant'
    if b'@generated' in data or b'DO NOT EDIT' in data:
        return 'generated_marker'
    if b'@flow' not in data[:2000] and b'Copyright' not in data[:2000]:
        return 'unconfirmed_runtime_source'
    return None


def count_comment_filtered(data):
    """Additional diagnostic, not the ADR021 nonempty-line floor metric."""
    result = 0
    block = False
    for line in data.splitlines():
        s = line.strip()
        if block:
            if b'*/' in s:
                block = False
            continue
        if s.startswith(b'/*'):
            block = b'*/' not in s
            continue
        if s and not s.startswith((b'//', b'*')):
            result += 1
    return result


def capture(side, write):
    archive = CASE / 'sources' / f'{side}.tar.gz'
    rows, selected, excluded_counts, seen = [], {}, collections.Counter(), set()
    with tarfile.open(archive, 'r:gz') as tree:
        for member in tree:
            name = PurePosixPath(member.name)
            if not name.parts or name.parts[0] != 'react-' + COMMITS[side]:
                raise ValueError('upstream root/commit mismatch')
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('non-regular archive member requires explicit materialization policy')
            path = str(PurePosixPath(*name.parts[1:]))
            if name.is_absolute() or '..' in name.parts or path in seen:
                raise ValueError('unsafe or duplicate archive path')
            seen.add(path)
            data = tree.extractfile(member).read()
            reason = excluded(path, data)
            excluded_counts[reason or 'included'] += 1
            rows.append({'path': path, 'bytes': len(data), 'sha256': sha(data),
                         'production': reason is None, 'exclusion': reason,
                         'production_nonempty_lines': 0 if reason else sum(bool(x.strip()) for x in data.splitlines()),
                         'comment_filtered_diagnostic': 0 if reason else count_comment_filtered(data)})
            if path in set(REQUIRED + PATCH_PATHS + SETUP):
                selected[path] = data
    if not set(REQUIRED + PATCH_PATHS + SETUP).issubset(selected):
        raise ValueError('missing required capture/setup/license')
    if b'MIT License' not in selected['LICENSE']:
        raise ValueError('MIT license not found')
    inventory_content = (json.dumps(sorted(rows, key=lambda r:r['path']), sort_keys=True) + '\n').encode()
    inventory_path = CASE / 'sources' / f'{side}-inventory.json.gz'
    if write:
        inventory = gzip.compress(inventory_content, mtime=0)
        inventory_path.write_bytes(inventory)
    else:
        # Compression bytes differ across pinned Python/zlib runtimes. Bind the
        # retained gzip digest and independently recompute its decoded content.
        inventory = inventory_path.read_bytes()
        try:
            decoded = gzip.decompress(inventory)
        except (OSError, EOFError) as error:
            raise ValueError('captured inventory compression invalid') from error
        if decoded != inventory_content:
            raise ValueError('captured inventory content mismatch')
    proof = {'commit': COMMITS[side], 'archive': str(archive.relative_to(ROOT)), 'archive_sha256': sha(archive.read_bytes()),
             'upstream_url': f'https://codeload.github.com/facebook/react/tar.gz/{COMMITS[side]}',
             'inventory': str(inventory_path.relative_to(ROOT)), 'inventory_sha256': sha(inventory),
             'complete_regular_files': len(rows), 'source_bytes': sum(r['bytes'] for r in rows),
             'production_js_files': sum(r['production'] for r in rows),
             'production_nonempty_lines': sum(r['production_nonempty_lines'] for r in rows),
             'comment_filtered_diagnostic': sum(r['comment_filtered_diagnostic'] for r in rows),
             'excluded_counts': dict(sorted(excluded_counts.items())),
             'setup_and_evidence': {k: {'bytes':len(v), 'sha256':sha(v)} for k,v in sorted(selected.items())}}
    proof['eligible_floor'] = proof['production_js_files'] >= 500 or proof['production_nonempty_lines'] >= 50000
    if not proof['eligible_floor']:
        raise ValueError('React fails ADR021 operational floor')
    return proof, selected


def prepare(write=True):
    commit = json.loads((CASE / 'provenance/commit.json').read_text())
    if commit['sha'] != COMMITS['head'] or [x['sha'] for x in commit['parents']] != [COMMITS['base']]:
        raise ValueError('historical parent/head mismatch')
    base, b = capture('base', write)
    head, h = capture('head', write)
    if b['yarn.lock'] != h['yarn.lock'] or b['package.json'] != h['package.json']:
        raise ValueError('setup changed: adjust frozen dependency comparison')
    patch = ''.join(''.join(difflib.unified_diff(b[p].decode().splitlines(keepends=True), h[p].decode().splitlines(keepends=True),
                   fromfile='a/' + p, tofile='b/' + p)) for p in PATCH_PATHS)
    patch_path = CASE / 'oracles/reference.patch'
    if write:
        patch_path.write_text(patch)
    elif patch_path.read_bytes() != patch.encode():
        raise ValueError('reference patch differs from captured production delta')
    receipt = {'schema_version': 'xrai.eval.l5.js.capture.v1', 'repository': 'facebook/react',
               'slot': 'L5-SLOT-TSJS-contract_change-2', 'language': 'JavaScript (Flow annotations, not TypeScript)',
               'method': 'xrai.production.react.runtime-js.conservative.v1',
               'method_source_sha256': sha(Path(__file__).read_bytes()),
               'measurement_definition': 'ADR021 nonempty production source lines, comments included; old implementation copies and forks excluded. Comment-filtered count is diagnostic only.',
               'allowlisted_runtime_packages': sorted(RUNTIME_PACKAGES), 'excluded_path_parts': sorted(EXCLUDED_PARTS),
               'snapshots': {'base':base, 'head':head},
               'reference_patch_sha256': sha(patch.encode()), 'reference_patch_paths': PATCH_PATHS,
               'qualification_status': 'curated_candidate_probes_and_independent_review_pending', 'admitted': False}
    capture_path = CASE / 'capture.json'
    if write:
        capture_path.write_text(json.dumps(receipt, indent=2) + '\n')
    elif json.loads(capture_path.read_text()) != receipt:
        raise ValueError('capture receipt differs from recomputed sources, digests or production floor')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=['prepare','verify'], default='prepare')
    args = parser.parse_args()
    print(json.dumps(prepare(write=args.mode == 'prepare'), indent=2))
