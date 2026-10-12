#!/usr/bin/env python3
"""Normalize complete pinned upstream trees into the regular-file corpus format.

Internal file symlinks become copies of their target bytes with explicit receipts.
No member is omitted, no out-of-tree target or directory link is accepted. These
are materialized checkouts, not byte-identical Git archives or atomic live trees.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import posixpath
import tarfile

from materialize_task import ROOT, safe_path
from triage_candidates import classify, EXCLUDED_PARTS


def regular_tree(blob):
    members = {}
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tree:
        for member in tree:
            name = str(PurePosixPath(*PurePosixPath(member.name).parts[1:]))
            if name == '.' or member.isdir():
                continue
            safe_path(name)
            if name in members or '.git' in PurePosixPath(name).parts:
                raise ValueError('duplicate or forbidden upstream entry')
            if member.isfile():
                members[name] = ('file', tree.extractfile(member).read(), member.mode)
            elif member.issym():
                target = posixpath.normpath(str(PurePosixPath(name).parent / member.linkname))
                safe_path(target)
                members[name] = ('symlink', target, member.mode)
            else:
                raise ValueError('unsupported upstream entry: ' + name)
    def resolve(name, seen):
        if name in seen or name not in members:
            raise ValueError('cyclic, directory or missing symlink target: ' + name)
        kind, content, mode = members[name]
        if kind == 'file':
            return content, mode
        return resolve(content, seen | {name})
    files, links = {}, []
    for name, (kind, target, _) in members.items():
        content, mode = resolve(name, set())
        files[name] = (content, mode)
        if kind == 'symlink':
            links.append({'path': name, 'original_target': target,
                          'materialized_sha256': hashlib.sha256(content).hexdigest(),
                          'policy': 'internal file target bytes; no production file omitted'})
    return files, links


def archive_bytes(files):
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb', mtime=0, filename='') as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as tree:
            for name, (data, mode) in sorted(files.items()):
                member = tarfile.TarInfo(name)
                member.size, member.mode, member.mtime = len(data), mode & 0o777, 0
                tree.addfile(member, io.BytesIO(data))
    return buffer.getvalue()


def prepare(cache):
    selected = json.loads((ROOT / 'qualification/vertical/selection.json').read_text())['cases']
    manifest_path = ROOT / 'sources/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    receipts = []
    for case in selected:
        blob = (cache / (case['key'] + '-base.tar.gz')).read_bytes()
        if hashlib.sha256(blob).hexdigest() != case['upstream_baseline']['sha256']:
            raise ValueError('upstream baseline fingerprint mismatch')
        files, links = regular_tree(blob)
        packed = archive_bytes(files)
        relative = 'sources/archives/vertical-' + case['key'] + '-' + case['baseline_commit'] + '.tar.gz'
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(packed)
        entries = [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                   for name, (data, _) in sorted(files.items())]
        licenses = [name for name in sorted(files)
                    if PurePosixPath(name).name.lower().startswith(('license', 'copying'))]
        if not licenses:
            raise ValueError('full snapshot license missing')
        production = {name: sum(bool(line.strip()) for line in data.splitlines())
                      for name, (data, _) in files.items() if classify(Path(name), data) is None}
        snapshot = case['repository'] + '@' + case['baseline_commit']
        inventory_path = 'sources/manifests/vertical-' + case['key'] + '.json.gz'
        inventory_bytes = gzip.compress(json.dumps(entries, sort_keys=True).encode(), mtime=0)
        inventory = ROOT / inventory_path
        inventory.parent.mkdir(parents=True, exist_ok=True)
        inventory.write_bytes(inventory_bytes)
        manifest['snapshots'][snapshot] = {
            'repository': case['repository'], 'commit': case['baseline_commit'],
            'license_spdx': case['license_spdx'], 'license_files': licenses,
            'archive': relative, 'sha256': hashlib.sha256(packed).hexdigest(),
            'archive_bytes': len(packed), 'source_bytes': sum(x['bytes'] for x in entries),
            'file_count': len(entries), 'files_artifact': {
                'path': inventory_path, 'sha256': hashlib.sha256(inventory_bytes).hexdigest()},
            'upstream_archive': case['upstream_baseline'],
            'materialization_policy': 'xrai.complete.regular-files.internal-link-copy.v1',
            'materialized_links': links}
        manifest['repositories']['vertical:' + case['key']] = {
            'family': case['family'], 'url': 'https://github.com/' + case['repository'] + '.git',
            'commit': case['baseline_commit'], 'version_ref': case['baseline_commit'],
            'license_spdx': case['license_spdx'], 'license_files': licenses,
            'provenance': case['origin_url'],
            'rebuild': ['download the hash-bound upstream_baseline in vertical/selection.json',
                        'python3 eval/scripts/prepare_vertical_sources.py --cache <cache>']}
        receipts.append({'id': case['id'], 'snapshot': snapshot, 'archive': relative,
                         'sha256': hashlib.sha256(packed).hexdigest(),
                         'files': len(entries), 'materialized_links': links,
                         'production_files': len(production),
                         'production_nonempty_lines': sum(production.values()),
                         'measurement_method': 'xrai.production.path-marker.v1',
                         'exclusions': sorted(EXCLUDED_PARTS),
                         'semantic_classification': 'path marker count; second reader must assess required modules; embedded tests are a known count limitation'})
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    path = ROOT / 'qualification/vertical/source-receipts.json'
    path.write_text(json.dumps({'schema_version': 1, 'cases': receipts}, indent=2) + '\n')
    return receipts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps([{k: r[k] for k in ('id', 'files', 'production_files', 'production_nonempty_lines')}
                      for r in prepare(args.cache)], indent=2))
