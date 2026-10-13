#!/usr/bin/env python3
"""Prepared Django router dossier; source data and owned declarative model only.

Never imports captured Django, executes upstream code, or writes a database.
The declarative model is not a native behavioral oracle or eligibility proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[2]
BASE = 'eval/qualification/django-router-v1/'
FREEZE_SHA = 'f403b7a74e43e5175a01adfc997e501f4639b452047d4ae60cc99ab0b201b109'
ARCHIVE = 'eval/sources/archives/vertical-django-8abacfc36d755d8e762a4d2074601b8dc412bfee.tar.gz'
MANIFEST = 'eval/sources/manifests/vertical-django.json.gz'
MAX_MEMBER = 8 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def safe_name(name):
    require(type(name) is str and name and ':' not in name and '\\' not in name and
            all(p not in ('', '.', '..') for p in name.split('/')), 'noncanonical relative path')
    return name


def read_owned(root, name, maximum):
    safe_name(name)
    p = root / name
    require(p.resolve().is_relative_to(root.resolve()) and
            all(not q.is_symlink() for q in [p, *p.parents] if q.is_relative_to(root)), 'source symlink or escape')
    require(p.is_file() and p.stat().st_size <= maximum, 'missing or oversized input')
    return p.read_bytes()


def frozen_inputs(root=ROOT):
    raw = read_owned(root, BASE + 'freeze.json', 1024 * 1024)
    require(sha(raw) == FREEZE_SHA, 'freeze fingerprint')
    freeze = decode(raw)
    receipts = freeze['inputs']
    require(len(receipts) == 28 and len({r['path'] for r in receipts}) == 28, 'exact frozen dossier closure')
    data = {}
    for row in receipts:
        raw = read_owned(root, row['path'], 16 * 1024 * 1024)
        require(type(row['bytes']) is int and len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'frozen input changed')
        data[row['path']] = raw
    require(sum(map(len, data.values())) <= 32 * 1024 * 1024, 'frozen input aggregate bound')
    review = decode(data[BASE + 'evaluator/second-reader.json'])
    require(review['reviewer'] != review['author'] and review['status'] == 'accepted_with_documentation_corrections_before_freeze', 'independent static review')
    require(review['new_algorithm_outputs_seen'] == 0 and review['upstream_executed'] is False,
            'review occurred before outputs')
    require(datetime.fromisoformat(review['reviewed_at']) < datetime.fromisoformat(freeze['frozen_at']), 'review must precede freeze')
    return freeze, data


def archive_tree(raw):
    require(len(raw) <= 16 * 1024 * 1024, 'compressed archive bound')
    files = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for member in archive:
            name = safe_name(member.name)
            require(member.isfile() and name not in files and len(files) < 10000, 'regular unique bounded archive entries')
            require(0 <= member.size <= MAX_MEMBER, 'declared archive member bound')
            total += member.size
            require(total <= MAX_EXPANDED, 'declared expanded archive bound')
            with archive.extractfile(member) as stream:
                content = stream.read(MAX_MEMBER + 1)
            require(len(content) == member.size, 'actual archive member bound')
            files[name] = content
    return files


def classification(name, raw, exclusions):
    p = PurePosixPath(name)
    if p.suffix not in {'.rs', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.py', '.pyx', '.pxd', '.go'}:
        return 'not_production_source_extension'
    if any(part.lower() in exclusions for part in p.parts):
        return 'excluded_directory'
    name = p.name.lower()
    if name.startswith(('test_', 'test.', 'zz_generated.', 'generated_')) or name.endswith(('_test.go', '.test.ts', '.test.js', '.spec.ts', '.spec.js', '_test.py', '_tests.rs')):
        return 'test_filename'
    if any(marker in raw[:2048].lower() for marker in (b'code generated', b'@generated', b'automatically generated', b'do not edit')):
        return 'generated_marker'
    return None


def verify_capture(data):
    files = archive_tree(data[ARCHIVE])
    manifest = decode(gzip.decompress(data[MANIFEST]))
    current = [{'path': n, 'bytes': len(raw), 'sha256': sha(raw)} for n, raw in sorted(files.items())]
    require(canonical(current) == canonical(manifest), 'complete captured archive differs from retained manifest')
    universe = decode(data[BASE + 'search-universe.json'])
    rows = []
    excluded = Counter()
    for name, raw in sorted(files.items()):
        reason = classification(name, raw, universe['exclusions'])
        if reason:
            excluded[reason] += 1
        else:
            rows.append({'path': name, 'bytes': len(raw), 'sha256': sha(raw),
                         'nonempty_lines': sum(bool(x.strip()) for x in raw.splitlines())})
    require(canonical(rows) == canonical(universe['files']) and dict(excluded) == universe['excluded_counts'], 'full production search universe')
    require(len(rows) == 929 and sum(r['nonempty_lines'] for r in rows) == 143033, 'frozen search counts')
    for path, raw in data.items():
        for prefix in (BASE + 'sources/', BASE + 'evaluator/captured/'):
            if path.startswith(prefix):
                require(files.get(path[len(prefix):]) == raw, 'copied source is not exact archive data')
    return files, {'regular_files': len(files), 'production_files': len(rows),
                   'production_nonempty_lines': 143033, 'archive_sha256': sha(data[ARCHIVE]),
                   'archive_executed': False, 'classification': universe['classification']}


def source_anchors(files, obligations):
    anchors = []
    for row in obligations['modules']:
        raw = files[row['path']]
        require(sha(raw) == row['sha256'] and row['span_unit'] == 'one_based_inclusive_source_lines', 'source obligation units/hash')
        lines = raw.splitlines(keepends=True)
        start, end = row['span']
        require(type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), 'line span bound')
        window = b''.join(lines[start - 1:end])
        needle = row['needle'].encode('utf-8')
        require(window.count(needle) == 1, 'exact unique source span witness')
        byte_start = sum(map(len, lines[:start - 1])) + window.index(needle)
        anchors.append({'path': row['path'], 'sha256': sha(raw), 'span_unit': row['span_unit'],
                        'line_span': row['span'], 'byte_start': byte_start,
                        'byte_end': byte_start + len(needle), 'needle': row['needle']})
    for row in obligations['inheritance_literal_evidence']:
        raw = files[row['path']]
        needle = row['needle'].encode('utf-8')
        require(raw.count(needle) == 1, 'unique captured inheritance/import witness')
        offset = raw.index(needle)
        anchors.append({'path': row['path'], 'sha256': sha(raw), 'byte_start': offset,
                        'byte_end': offset + len(needle), 'line': raw[:offset].count(b'\n') + 1,
                        'needle': row['needle'], 'meaning': row['meaning']})
    return anchors


def reduce_policy(database_alias, model_can_migrate, router_returns):
    require(database_alias in ('default', 'reporting'), 'alias outside frozen two-database profile')
    require(type(model_can_migrate) is bool and type(router_returns) is list and len(router_returns) <= 16,
            'bounded explicit model/policy profile')
    require(all(v is None or type(v) is bool or v == 'method_absent' for v in router_returns),
            'nonboolean router result outside owned profile, not universal Django error')
    if not model_can_migrate:
        return {'creates_table': False, 'decisive_router_index': None, 'consulted_router_count': 0}
    calls = 0
    for index, result in enumerate(router_returns):
        if result == 'method_absent':
            continue
        calls += 1
        if result is not None:
            return {'creates_table': result, 'decisive_router_index': index, 'consulted_router_count': calls}
    return {'creates_table': True, 'decisive_router_index': None, 'consulted_router_count': calls}


def configured_returns(state, app, alias):
    require(type(app) is str and app and alias in state['databases'], 'explicit app and alias')
    require(set(state['databases']) == {'default', 'reporting'}, 'exact two database aliases')
    order = state['router_order']
    require(type(order) is list and len(order) == 2 and set(order) == {'primary', 'scoped'}, 'both immutable policy components exactly once')
    require(state['router_components'] == {'primary': 'policy.DefaultPolicy', 'scoped': 'policy.LedgerPolicy'}, 'immutable policy identities')
    result = []
    for component in order:
        result.append(alias == 'default' if component == 'primary' else alias == 'reporting' if app == 'ledger' else None)
    return result


def model_replay(data):
    states = {name: decode(data[BASE + f'evaluator/state-{name}.json']) for name in ('a', 'b')}
    oracle = decode(data[BASE + 'evaluator/oracle.json'])
    require(oracle['no_behavioral_receipt'] is True and oracle['independent_review'] == 'accepted_static_before_algorithm_by_root', 'declarative oracle only')
    require(len(oracle['main_cases']) == 8 and len(oracle['controls']) == 10, 'fixed preregistered cases')
    cases = []
    for row in oracle['main_cases']:
        state = states[row['state']]
        model = next(m for m in state['models'] if m['app_label'] == row['app_label'] and m['model_name'] == row['model_name'])
        gate = model['managed'] and not model['proxy'] and not model['swapped']
        actual = reduce_policy(row['database_alias'], gate, configured_returns(state, row['app_label'], row['database_alias']))
        actual['model_gate'] = gate
        require(canonical(actual) == canonical(row['expected']), 'declared main policy expectation mismatch')
        cases.append({'id': row['id'], 'owned_declarative_result': actual})
    controls = []
    for row in oracle['controls']:
        actual = reduce_policy(row['alias'], row['model_can_migrate'], row['router_returns'])
        require(canonical(actual) == canonical(row['expected']), 'declared control expectation mismatch')
        controls.append({'id': row['id'], 'owned_declarative_result': actual})
    require(states['a']['databases'] == states['b']['databases'] and states['a']['models'] == states['b']['models'] and
            states['a']['router_components'] == states['b']['router_components'], 'only routing configuration may change')
    require(states['a']['router_order'] != states['b']['router_order'], 'A/B configuration intervention required')
    require(decode(data[BASE + 'agent/deployment.json']) == states['a'], 'agent receives baseline, not reference')
    for app in ('ledger', 'catalog'):
        outcomes = {alias: reduce_policy(alias, True, configured_returns(states['b'], app, alias))['creates_table']
                    for alias in ('default', 'reporting')}
        require(outcomes == ({'default': False, 'reporting': True} if app == 'ledger' else {'default': True, 'reporting': False}), 'desired routing policy')
    return {'main': cases, 'controls': controls,
            'aba': {'configuration_sha256': [sha(data[BASE + f'evaluator/state-{s}.json']) for s in oracle['hypothetical_config_sequence']],
                    'live_session_executed': False},
            'other_apps_basis': 'literal predicate app_label != ledger; catalog representative, no empirical generalization',
            'framework_executed': False, 'actual_database_operations': 0}


def verify(record=None, root=ROOT):
    freeze, data = frozen_inputs(root)
    files, capture = verify_capture(data)
    case = decode(data[BASE + 'case.json'])
    require(case['slot_id'] == 'L5-SLOT-Python-state_config-1' and case['repository'] == 'django/django' and
            case['individual_eligible'] is False and case['admitted'] is False and case['multimodule_projection_credit'] == 0,
            'prepared dossier cannot promote quota/admission')
    slots = decode(data['eval/qualification/l5-slot-plan-v2.json'])['slots']
    slot = next(s for s in slots if s['slot_id'] == case['slot_id'])
    require((slot['family'], slot['repository_target'], slot['kind']) == ('Python', 'django/django', 'state_config'), 'prospective slot compatibility')
    require(Counter(s['repository_target'] for s in slots)['django/django'] == 4 and
            sum(s['target']['multi_module'] for s in slots) == 19, 'teto and deficit preserved')
    result = {'schema': 'xrai.eval.django-router.prepared-verification.v1', 'freeze_sha256': FREEZE_SHA,
              'capture': capture, 'static_second_reader': '/root', 'source_anchors': source_anchors(files, decode(data[BASE + 'evaluator/source-obligations.json'])),
              'python_semantic_resolution': 'unknown; exact literals/manual source review only',
              'declarative_replay': model_replay(data), 'candidate_prepared': True,
              'native_behavior_verified': False, 'individual_eligible': False, 'admitted': False,
              'multimodule_projection': 19, 'multimodule_projection_credit': 0,
              'competitive_runs_allowed': False, 'setup_readiness': decode(data[BASE + 'evaluator/setup-readiness.json'])}
    if record is not None:
        require(canonical(record) == canonical(result), 'prepared evidence differs from recomputation')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    supplied = decode(args.receipt.read_bytes()) if args.receipt else None
    print(json.dumps(verify(supplied), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
