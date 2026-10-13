#!/usr/bin/env python3
"""Freeze real captured lexical universes, labels and matrix before algorithm."""
from __future__ import annotations
import datetime
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).resolve().parent
LOG = ROOT / 'docs/relatorios/logs/L5-C04/lexical'
RETRIEVER = ROOT / 'crates/xrai-eval/harness/lexical_retrieval.py'
SPECS = {
    'Rust': {'archive': 'eval/qualification/l5-real/rust/baseline.tar.gz', 'sha256': '539f90cd750eff4df257d2ff01d9552da7f57201daa493d5afe4b8daaf1e4e9f',
             'repository': 'rust-lang/rust-analyzer', 'commit': '3a5f65784a90278fa1de97fe89a7a529dd44765a', 'prefix': 'crates/stdx/src/', 'extension': '.rs', 'licenses': ['LICENSE-MIT', 'LICENSE-APACHE']},
    'TSJS': {'archive': 'eval/qualification/l5-real/js/sources/base.tar.gz', 'sha256': 'b589b94f327ee6a48ab809d9477f9926341b2980676a9b89cb1a4f6ea783afd6',
             'repository': 'facebook/react', 'commit': '77912d9a05d7a90287fabdec76486f25869b2981', 'prefix': 'packages/react/src/', 'extension': '.js', 'licenses': ['LICENSE']},
    'Python': {'archive': 'eval/qualification/l5-real/python/sources/base.tar.gz', 'sha256': '70f9d47a3aba04faf22b150075283b0a4311f8b665bf2ab3e447cd5c3685b70b',
               'repository': 'scikit-learn/scikit-learn', 'commit': '156ef141f3b270edb06c8ae9af37c55253c0aabe', 'prefix': 'sklearn/metrics/', 'extension': '.py', 'licenses': ['COPYING']},
    'Go': {'archive': 'eval/qualification/l5-real/go/sources/base.tar.gz', 'sha256': '3cd918c96a563db6a64e8c9717d556097240de799f9f0948ba50060e6143c190',
           'repository': 'go-gitea/gitea', 'commit': '8eefa1f6dedf2488db2c9e12c916e8e51f673160', 'prefix': 'modules/util/', 'extension': '.go', 'licenses': ['LICENSE']},
}
QUERIES = [
    ('Rust', 'RS-01', 'Locate shuffle for mutable slices and its random index callback.', 'crates/stdx/src/rand.rs', 'pub fn shuffle'),
    ('Rust', 'RS-02', 'Locate the panic context stack frame guard that sets a panic hook.', 'crates/stdx/src/panic_context.rs', 'pub fn enter'),
    ('Rust', 'RS-03', 'Where does streaming_output read stdout and stderr until the child exits?', 'crates/stdx/src/process.rs', 'pub fn streaming_output'),
    ('TSJS', 'JS-01', 'Locate resolveDispatcher and the invalid hook call error.', 'packages/react/src/ReactHooks.js', 'function resolveDispatcher'),
    ('TSJS', 'JS-02', 'Locate cloneElement when children, ref and key are overridden.', 'packages/react/src/ReactElement.js', 'export function cloneElement'),
    ('TSJS', 'JS-03', 'Where does the lazy initializer track pending, resolved or rejected payload state?', 'packages/react/src/ReactLazy.js', 'function lazyInitializer'),
    ('Python', 'PY-01', 'Locate roc_auc_score and max_fpr for ranking scores.', 'sklearn/metrics/_ranking.py', 'def roc_auc_score'),
    ('Python', 'PY-02', 'Locate precision_recall_fscore_support handling average, beta and zero_division.', 'sklearn/metrics/_classification.py', 'def precision_recall_fscore_support'),
    ('Python', 'PY-03', 'Locate mean_squared_error for regression and sample weights.', 'sklearn/metrics/_regression.py', 'def mean_squared_error'),
    ('Go', 'GO-01', 'Locate SanitizeURL handling URL user credentials.', 'modules/util/url.go', 'func SanitizeURL'),
    ('Go', 'GO-02', 'Locate FileURLToPath converting file URLs and rejecting invalid authorities.', 'modules/util/path.go', 'func FileURLToPath'),
    ('Go', 'GO-03', 'Where does ShellEscape quote unsafe shell characters?', 'modules/util/shellquote.go', 'func ShellEscape'),
]


def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def capture():
    """Only pinned archives are read; never import, build or execute source."""
    universes, retained = [], {}
    for family, spec in SPECS.items():
        raw = (ROOT / spec['archive']).read_bytes()
        if sha(raw) != spec['sha256']: raise ValueError('immutable archive changed')
        selected, omitted, licenses = {}, [], {}
        full_count = 0
        with tarfile.open(fileobj=__import__('io').BytesIO(raw), mode='r:gz') as tree:
            for member in tree:
                if not member.isfile(): continue
                full_count += 1
                path = member.name.split('/', 1)[1] if '/' in member.name else ''
                if path in spec['licenses']:
                    data = tree.extractfile(member).read()
                    asset = f'licenses/{family}/{path}'
                    retained[asset] = data; licenses[path] = {'asset': asset, 'sha256': sha(data), 'bytes': len(data)}
                if not path.startswith(spec['prefix']): continue
                reason = None
                if not path.endswith(spec['extension']): reason = 'outside_selected_extension'
                elif any(p in ['tests', '__tests__'] for p in path.split('/')) or path.endswith('_test.go'): reason = 'separate_test_path'
                if reason:
                    omitted.append({'path': path, 'bytes': member.size, 'reason': reason}); continue
                data = tree.extractfile(member).read(); data.decode('utf-8')
                if path in selected: raise ValueError('duplicate selected source')
                asset = f'sources/{family}/{path}'
                retained[asset] = data
                selected[path] = {'asset': asset, 'sha256': sha(data), 'bytes': len(data)}
        if set(licenses) != set(spec['licenses']): raise ValueError('license closure')
        universes.append({'family': family, 'repository': spec['repository'], 'commit': spec['commit'],
                          'archive': {'path': spec['archive'], 'sha256': spec['sha256']},
                          'capture_prefix': spec['prefix'], 'capture_extension': spec['extension'],
                          'files': dict(sorted(selected.items())), 'licenses': licenses,
                          'file_count': len(selected), 'source_bytes': sum(f['bytes'] for f in selected.values()),
                          'full_archive_regular_files': full_count, 'omitted_inside_prefix': sorted(omitted, key=lambda v:v['path']),
                          'omitted_outside_prefix_count': full_count - len(selected) - len(omitted),
                          'coverage': 'exact captured subtree production paths only; outside prefix and separate tests omitted',
                          'limits': ['Full selected file bytes, including inline tests/comments/docs; no production LOC claim.',
                                     'Flow/compile tags/conditional syntax are source text; no parser/semantic/build configuration claim.',
                                     'A lexical absence is limited to this captured scope, never whole-repository absence.']})
    manifest = {'schema': 'xrai.eval.lexical.captured-sources.v1', 'data_only': True, 'universes': universes,
                'input_policy': 'Only files under the explicit per-family source allowlist enter retrievers; labels/oracles/patches/licenses stay evaluator-only.',
                'capture_rationale': 'Complete production source extensions within four existing utility/API subtrees; no hit-based file selection or method-specific universe.'}
    query_rows, labels = [], []
    by_family = {u['family']: u for u in universes}
    for family, qid, text, path, anchor in QUERIES:
        data = retained[by_family[family]['files'][path]['asset']]
        needle = anchor.encode()
        if data.count(needle) != 1: raise ValueError('single explicit human-labelled declaration anchor')
        start = data.index(needle)
        query_rows.append({'query_id': qid, 'family': family, 'query': text})
        labels.append({'query_id': qid, 'family': family, 'relevant_path': path,
                       'anchor': {'start': start, 'end': start + len(needle), 'sha256': sha(needle)},
                       'source_sha256': sha(data), 'expected': 'lexical_source_retrieval_not_semantic_resolution'})
    for family in SPECS:
        qid = family + '-ABSENT'; text = 'qzvksndpwbf467901'
        if any(text.encode() in retained[f['asset']] for f in by_family[family]['files'].values()): raise ValueError('negative string appears in capture')
        query_rows.append({'query_id': qid, 'family': family, 'query': text})
        labels.append({'query_id': qid, 'family': family, 'relevant_path': None, 'anchor': None,
                       'expected': 'no_lexical_match_within_captured_scope'})
    config = {'schema': 'xrai.eval.lexical.frozen-protocol.v1',
              'methods': ['bm25', 'tfidf_cosine'], 'k1': 1.2, 'b': 0.75,
              'chunk_lines': 40, 'overlap_lines': 10, 'path_term_weight': 3,
              'tokenization': 'unicode words; preserve folded whole identifiers plus camelCase/PascalCase/snake_case components; path and body terms',
              'selection': 'descending score then path/start/end; skip overlapping source spans; no zero-score hits',
              'top_k': 5, 'max_wire_bytes': 65536, 'repetitions': 2, 'seed': 20261012,
              'metrics': ['file_hit_at_1', 'file_hit_at_3', 'file_hit_at_5', 'file_reciprocal_rank', 'anchor_covered_at_5', 'negative_empty'],
              'limits': ['scripted_retrieval only; no agent/model/tokenizer/provider/semantic precision/performance claim',
                         'No threshold is a gate; misses remain evidence. No tuning or relabelling after results.']}
    matrix = [{'query_id': q['query_id'], 'family': q['family'], 'method': method, 'repetition': repeat,
               'order': n * 4 + mi * 2 + repeat, 'seed': config['seed']}
              for n,q in enumerate(query_rows) for mi,method in enumerate(config['methods']) for repeat in range(2)]
    retained.update({'manifest.json': encoded(manifest), 'queries.json': encoded(query_rows),
                     'expected-labels.json': encoded({'schema': 'xrai.eval.lexical.labels.v1', 'label_author': 'implementer/e02_allocation',
                                                     'independent_second_reader': 'pending', 'labels': labels}),
                     'protocol.json': encoded(config), 'matrix.json': encoded(matrix)})
    return retained


def verify():
    expected = capture()
    for path, raw in expected.items():
        target = DEST / path
        if not target.is_file() or target.is_symlink() or target.read_bytes() != raw:
            raise ValueError('frozen lexical input changed: ' + path)
    return {'verified': True, 'data_only': True, 'files': len(expected),
            'artifact_sha256': {path:sha(raw) for path,raw in sorted(expected.items())}}


def freeze():
    if RETRIEVER.exists(): raise ValueError('freeze must precede new retrieval implementation')
    expected = capture()
    for name, data in expected.items():
        path = DEST / name; path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != data: raise ValueError('refuse to rewrite frozen lexical assets')
        path.write_bytes(data)
    stamp = {'schema': 'xrai.eval.lexical.pre-implementation-freeze.v1',
             'frozen_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'retriever_source_existed': RETRIEVER.exists(), 'results_existed': (LOG / 'benchmark.json').exists(),
             'inputs': verify(), 'freezer_source_sha256': sha(Path(__file__).read_bytes()),
             'native_upstream_execution': False, 'new_downloads': 0}
    receipt = LOG / 'freeze-before-algorithm.json'
    if receipt.exists(): raise ValueError('freeze receipt already exists')
    receipt.write_bytes(encoded(stamp))
    print(encoded(stamp).decode(), end='')


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','verify']);a=p.parse_args()
    freeze() if a.action=='freeze' else print(encoded(verify()).decode(),end='')
