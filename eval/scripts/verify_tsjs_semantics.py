#!/usr/bin/env python3
"""Data-only verifier for frozen experimental ESM labels and native snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import blake3

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / 'eval/semantics/tsjs/labels.json'
FREEZE = LABELS.with_name('freeze-before-resolver.json')
RESOLVER = ROOT / 'crates/xrai-eval/src/tsjs_semantics.rs'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def labels():
    frozen = strict_json(FREEZE.read_bytes())
    raw = LABELS.read_bytes()
    if sha(raw) != frozen['labels_sha256'] or frozen['resolver_implementation_present'] is not False:
        raise ValueError('labels freeze binding')
    for rel, digest in frozen['files'].items():
        if sha((LABELS.parent / rel).read_bytes()) != digest:
            raise ValueError(f'frozen real source changed: {rel}')
    data = strict_json(raw)
    if len(data['cases']) != frozen['cases'] or len({c['id'] for c in data['cases']}) != len(data['cases']):
        raise ValueError('label case closure')
    if sum(c['resolvable_labeled_before_implementation'] for c in data['cases']) != frozen['resolvable']:
        raise ValueError('pre-labeled denominator changed')
    return data


def canonical_input(value):
    if set(value) != {'profile', 'configuration', 'files'}:
        raise ValueError('input closure')
    files = {}
    for path, source in sorted(value['files'].items()):
        if set(source) != {'dialect', 'source'}:
            raise ValueError('source closure')
        files[path] = {'dialect': source['dialect'], 'source': source['source']}
    return {'profile': value['profile'], 'configuration': dict(sorted(value['configuration'].items())), 'files': files}


def snapshot(value, input_value):
    required = {'schema_version', 'snapshot_id', 'producer_fingerprint', 'producer_components', 'input', 'scopes', 'bindings', 'exports', 'gaps', 'references', 'coverage'}
    if set(value) != required or value['schema_version'] != 'xrai.eval.tsjs.snapshot.v1':
        raise ValueError('snapshot closure')
    expected_input = canonical_input(input_value)
    if value['input'] != input_value:
        raise ValueError('consumed input changed')
    components = value['producer_components']
    if set(components) != {s['dialect'] for s in input_value['files'].values()}:
        raise ValueError('grammar producer closure')
    grammar_vectors = {}
    for dialect, digest in sorted(components.items()):
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError('grammar fingerprint')
        grammar_vectors[dialect] = list(bytes.fromhex(digest))
    producer = blake3.blake3(compact(['xrai-tsjs-lexical-v1', 'captured-relative-exact-v1', grammar_vectors, RESOLVER.read_text()])).hexdigest()
    sid = blake3.blake3(compact([expected_input, producer])).hexdigest()
    if value['producer_fingerprint'] != producer or value['snapshot_id'] != sid:
        raise ValueError('source/config/dialects/resolver/grammar fingerprint')
    if set(value['coverage']) != set(input_value['files']):
        raise ValueError('coverage closure')
    for field in ['scopes', 'bindings', 'exports', 'gaps', 'references']:
        if not isinstance(value[field], list):
            raise ValueError(f'{field} missing')
    scopes = value['scopes']
    for index, scope in enumerate(scopes):
        if scope['id'] != index or type(scope['id']) is not int:
            raise ValueError('scope identity')
        parent = scope['parent']
        if parent is not None and (type(parent) is not int or not 0 <= parent < index):
            raise ValueError('scope parent')
    def evidence(item):
        if set(item) != {'snapshot_id', 'file_id', 'path', 'source_hash', 'start', 'end', 'role'}:
            raise ValueError('evidence closure')
        path = item['path']
        if path not in input_value['files']:
            raise ValueError('evidence foreign source')
        source = input_value['files'][path]['source'].encode()
        if item['snapshot_id'] != sid or item['file_id'] != 'fi_' + blake3.blake3(path.encode()).hexdigest() or item['source_hash'] != blake3.blake3(source).hexdigest():
            raise ValueError('evidence identity')
        start, end = item['start'], item['end']
        if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(source):
            raise ValueError('evidence span')
        source[:start].decode(); source[:end].decode()
    def visit(item):
        if isinstance(item, dict):
            if 'source_hash' in item:
                evidence(item)
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(value)
    positions = set()
    for ref in value['references']:
        ev = ref['evidence']; key = (ev['path'], ev['start'])
        if key in positions:
            raise ValueError('duplicate reference position')
        positions.add(key)
        if input_value['files'][ev['path']]['source'].encode()[ev['start']:ev['end']].decode() != ref['name']:
            raise ValueError('reference text')
        if type(ref['scope']) is not int or not 0 <= ref['scope'] < len(scopes):
            raise ValueError('reference scope')
        for which in ['resolution', 'callable']:
            resolution = ref[which]
            if set(resolution) != {'state', 'target', 'binding_id', 'evidence', 'dependencies', 'diagnostic'}:
                raise ValueError('resolution closure')
            if not isinstance(resolution['dependencies'], list) or sid not in resolution['dependencies'] or producer not in resolution['dependencies']:
                raise ValueError('resolution dependencies')
            if not resolution['evidence'] or resolution['evidence'][0] != ev:
                raise ValueError('reference occurrence evidence')
            if resolution['state'] == 'unknown':
                if resolution['target'] is not None or resolution['binding_id'] is not None:
                    raise ValueError('unknown promoted')
            elif resolution['state'] == 'resolved':
                bound = [b for b in value['bindings'] if b['id'] == resolution['binding_id']]
                if len(bound) != 1 or resolution['target'] != f"{bound[0]['path']}:{bound[0]['name']}":
                    raise ValueError('target declaration')
                roles = [e['role'] for e in resolution['evidence']]
                if roles not in [['reference', 'declaration'], ['reference', 'import', 'export', 'declaration']]:
                    raise ValueError('complete lexical chain')
                if resolution['evidence'][-1] != bound[0]['evidence']:
                    raise ValueError('declaration evidence')
                if roles[1] == 'import':
                    imports = [b for b in value['bindings'] if b['kind'] == 'import' and b['name'] == ref['name'] and b['path'] == ev['path'] and b['evidence'] == resolution['evidence'][1]]
                    exports = [e for e in value['exports'] if e['evidence'] == resolution['evidence'][2]]
                    if len(imports) != 1 or len(exports) != 1 or exports[0]['local'] != bound[0]['name'] or imports[0]['imported_name'] != exports[0]['name']:
                        raise ValueError('import/export/declaration link')
            else:
                raise ValueError('resolution state')
        if ref['callable']['state'] != 'unknown':
            raise ValueError('unsupported callable promotion')
    return value


def verify_outputs(directory):
    data = labels(); directory = Path(directory)
    expected = {case['id'] + '.json' for case in data['cases']}
    actual = {p.name for p in directory.glob('*.json')}
    if actual != expected:
        raise ValueError('case outputs closure')
    resolved = 0; false_promotions = 0; queried = 0
    files = {}; losses = []
    for case in data['cases']:
        path = directory / (case['id'] + '.json'); raw = path.read_bytes()
        out = snapshot(strict_json(raw), case['input']); files[path.name] = sha(raw)
        for q in case['queries']:
            refs = [r for r in out['references'] if r['evidence']['path'] == q['path'] and r['evidence']['start'] == q['offset']]
            if len(refs) != 1:
                raise ValueError(f"query occurrence absent: {case['id']}")
            r = refs[0]; queried += 1
            if r['callable']['state'] != q['callable']:
                raise ValueError('callable label')
            if q['state'] == 'unknown' and r['resolution']['state'] == 'resolved':
                false_promotions += 1
            if q['state'] == 'resolved':
                if r['resolution']['state'] == 'resolved' and r['resolution']['target'] == q['target']:
                    resolved += 1
                else:
                    losses.append({'case': case['id'], 'expected': q['target'], 'actual': r['resolution']})
    denominator = sum(case['resolvable_labeled_before_implementation'] for case in data['cases'])
    if false_promotions or resolved / denominator < data['threshold_resolvable_reference']:
        raise ValueError(f'P2 labels failed: {resolved}/{denominator}; false_promotions={false_promotions}')
    real = next(c for c in data['cases'] if c.get('real_source'))
    out = strict_json((directory / (real['id'] + '.json')).read_bytes())
    q = real['queries'][0]
    ref = next(r for r in out['references'] if r['evidence']['path'] == q['path'] and r['evidence']['start'] == q['offset'])
    if ref['resolution']['state'] != 'resolved' or ref['resolution']['target'] != q['target']:
        raise ValueError('real useful relation not demonstrated')
    return {'schema_version': 'xrai.eval.tsjs.verification.v1', 'verified': True, 'data_only': True, 'experimental': True, 'labels_sha256': sha(LABELS.read_bytes()), 'cases': len(data['cases']), 'queries': queried, 'reference_resolved': resolved, 'prelabeled_resolvable_denominator': denominator, 'reference_recall': resolved / denominator, 'false_promotions': false_promotions, 'callable_targets_promoted': 0, 'real_relation_verified': True, 'losses': losses, 'outputs_sha256': files, 'global_admission': False, 'grammar_fingerprints_verified_against_retained_binary_by_ci_reconciler': False}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--outputs'); p.add_argument('--labels-only', action='store_true'); args = p.parse_args()
    if args.labels_only:
        data = labels(); result = {'verified': True, 'data_only': True, 'cases': len(data['cases']), 'resolver_executed': False, 'labels_sha256': sha(LABELS.read_bytes())}
    elif args.outputs:
        result = verify_outputs(args.outputs)
    else:
        p.error('--outputs or --labels-only required')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
