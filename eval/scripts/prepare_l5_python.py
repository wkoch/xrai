#!/usr/bin/env python3
"""Capture/verify a controlled Python contract from pinned full sources, data only."""
import argparse
import difflib
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / 'eval/qualification/l5-real/python'
COMMIT = '156ef141f3b270edb06c8ae9af37c55253c0aabe'
MODULES = ['sklearn/utils/_set_output.py', 'sklearn/pipeline.py', 'sklearn/compose/_column_transformer.py']
EXCLUDED = {'tests', 'test', 'externals', 'datasets', 'data', 'benchmarks', 'examples', 'doc', 'docs'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_archive(path):
    files = {}
    with tarfile.open(path) as tree:
        for member in tree:
            p = PurePosixPath(member.name)
            if not p.parts or p.parts[0] != 'scikit-learn-' + COMMIT or p.is_absolute() or '..' in p.parts:
                raise ValueError('unsafe archive path or root')
            if member.isdir():
                continue
            name = str(PurePosixPath(*p.parts[1:]))
            if not member.isfile() or name in files:
                raise ValueError('nonregular/duplicate source member')
            files[name] = tree.extractfile(member).read()
    return files


def production(path, data):
    p = PurePosixPath(path)
    if not p.parts or p.parts[0] != 'sklearn' or p.suffix not in {'.py', '.pyx', '.pxd'}:
        return False
    if EXCLUDED.intersection(p.parts) or p.name.startswith('test_'):
        return False
    return not any(m in data[:2048].lower() for m in (b'code generated', b'automatically generated', b'do not edit'))


def reference(files):
    result = {p: files[p] for p in MODULES}
    adapter = '''class MaskedArrayAdapter:
    container_lib = "masked"

    def create_container(self, X_output, X_original, columns, inplace=True):
        return np.ma.array(X_output, copy=not inplace)

    def is_supported_container(self, X):
        return np.ma.isMaskedArray(X)

    def rename_columns(self, X, columns):
        return X

    def hstack(self, Xs):
        return np.ma.hstack(Xs)


'''
    key = MODULES[0]
    text = result[key].decode()
    text = text.replace('class ContainerAdaptersManager:', adapter + 'class ContainerAdaptersManager:', 1)
    text = text.replace('ADAPTERS_MANAGER.register(PolarsAdapter())', 'ADAPTERS_MANAGER.register(PolarsAdapter())\nADAPTERS_MANAGER.register(MaskedArrayAdapter())', 1)
    result[key] = text.encode()
    key = MODULES[2]
    text = result[key].decode()
    old = '            if adapter and all(adapter.is_supported_container(X) for X in Xs):\n'
    new = old + '                if adapter.container_lib == "masked":\n                    return adapter.hstack(Xs)\n'
    if text.count(old) != 1:
        raise ValueError('reference anchor count differs')
    result[key] = text.replace(old, new, 1).encode()
    return result


def prepare(write=False):
    archive = CASE / 'sources/base.tar.gz'
    files = read_archive(archive)
    if json.loads((CASE/'provenance/commit.json').read_text())['sha'] != COMMIT:
        raise ValueError('commit provenance differs')
    if b'BSD' not in files['COPYING']:
        raise ValueError('license differs')
    inventory = [{'path': p, 'bytes': len(v), 'sha256':sha(v), 'production':production(p,v),
                  'nonempty_lines':sum(bool(x.strip()) for x in v.splitlines()) if production(p,v) else 0}
                 for p,v in sorted(files.items())]
    content = (json.dumps(inventory,sort_keys=True)+'\n').encode()
    inventory_path = CASE/'sources/base-inventory.json.gz'
    if write:
        inventory_path.write_bytes(gzip.compress(content,mtime=0))
    elif gzip.decompress(inventory_path.read_bytes()) != content:
        raise ValueError('inventory differs from complete archive')
    replacements = reference(files)
    patch = ''.join(''.join(difflib.unified_diff(files[p].decode().splitlines(True), replacements[p].decode().splitlines(True),fromfile='a/'+p,tofile='b/'+p)) for p in MODULES)
    patch_path = CASE/'oracles/reference.patch'
    if write:
        patch_path.write_text(patch)
        for p,v in replacements.items():
            target = CASE/'oracles/reference-sources'/p
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(v)
    elif patch_path.read_bytes() != patch.encode() or any((CASE/'oracles/reference-sources'/p).read_bytes() != v for p,v in replacements.items()):
        raise ValueError('reference differs from controlled frozen contract')
    receipt = {'schema_version':'xrai.eval.l5.python.capture.v1','repository':'scikit-learn/scikit-learn', 'commit':COMMIT,
               'task_type':'controlled_contract_change','historical_bug_claim':False,
               'archive_url':'https://codeload.github.com/scikit-learn/scikit-learn/tar.gz/'+COMMIT,
               'archive_sha256':sha(archive.read_bytes()), 'complete_regular_files':len(files),
               'inventory_sha256':sha(inventory_path.read_bytes()),'inventory_content_sha256':sha(content),
               'production_files':sum(r['production'] for r in inventory),'production_nonempty_lines':sum(r['nonempty_lines'] for r in inventory),
               'excluded_parts':sorted(EXCLUDED), 'method':'allowlisted sklearn .py/.pyx/.pxd; nonempty byte lines; externals/tests/datasets excluded; comments included ADR021',
               'required_modules':{p:sha(files[p]) for p in MODULES},
               'setup_sha256':{p:sha(files[p]) for p in ['pyproject.toml','COPYING','sklearn/__init__.py','sklearn/__check_build/__init__.py']},
               'input_sha256':sha((CASE/'agent/input.md').read_bytes()),'oracle_sha256':sha((CASE/'oracles/probe.py').read_bytes()),
               'reference_patch_sha256':sha(patch.encode()),'reference_sources_sha256':{p:sha(v) for p,v in replacements.items()},
               'dependency_lock_sha256':sha((CASE/'setup.lock.json').read_bytes()),
               'admitted':False,'qualified':False,'comparative_execution_allowed':False,
               'prepare_source_sha256':sha(Path(__file__).read_bytes())}
    if receipt['production_nonempty_lines'] < 50000 and receipt['production_files'] < 500:
        raise ValueError('production size floor not reached')
    path=CASE/'capture.json'
    if write:
        path.write_text(json.dumps(receipt,indent=2)+'\n')
    elif json.loads(path.read_text()) != receipt:
        raise ValueError('capture receipt differs')
    return receipt


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','verify'])
    args=parser.parse_args()
    print(json.dumps(prepare(args.mode=='prepare'),indent=2))
