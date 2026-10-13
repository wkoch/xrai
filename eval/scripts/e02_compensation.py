#!/usr/bin/env python3
"""Bounded E02 candidate/slot audit. Reads captured data; never admits tasks."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'eval/qualification/e02-compensation-v1/'
FREEZE_SHA = 'f39ac4d5ba3089089aa79cdb94e0dac297aa15afeee069f5ec18dea394bd3996'
MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def read_bound(root, path, digest=None, size=None):
    require(type(path) is str and path and '\\' not in path and ':' not in path and
            all(p not in ('', '.', '..') for p in path.split('/')), 'noncanonical path')
    candidate = root / path
    require(candidate.resolve().is_relative_to(root.resolve()) and
            all(not p.is_symlink() for p in [candidate, *candidate.parents] if p.is_relative_to(root)),
            'symlink or path escape')
    require(candidate.is_file() and candidate.stat().st_size <= MAX_FILE, 'file bound or missing input')
    raw = candidate.read_bytes()
    if digest is not None:
        require(type(digest) is str and re.fullmatch('[a-f0-9]{64}', digest), 'invalid digest')
        require(hashlib.sha256(raw).hexdigest() == digest, 'input fingerprint changed: ' + path)
    if size is not None:
        require(type(size) is int and len(raw) == size, 'input byte count changed')
    return raw


def frozen_inputs(root=ROOT):
    raw = read_bound(root, PREFIX + 'freeze.json', FREEZE_SHA)
    freeze = decode(raw)
    require(freeze['schema'] == 'xrai.eval.e02.compensation-freeze.v1', 'freeze schema')
    receipts = freeze['inputs']
    require(len(receipts) == 43 and len({r['path'] for r in receipts}) == 43, 'exact frozen scope')
    data = {}
    total = 0
    for r in receipts:
        require(set(r) == {'path', 'sha256', 'bytes'}, 'receipt fields')
        value = read_bound(root, r['path'], r['sha256'], r['bytes'])
        total += len(value)
        require(total <= MAX_TOTAL, 'total input bound')
        data[r['path']] = value
    return freeze, data


def validate_layout(plan):
    slots = plan['slots']
    require(len(slots) == 32 and len({s['slot_id'] for s in slots}) == 32, '32 unique canonical slots required')
    counts = Counter(s['repository_target'] for s in slots)
    require(len(counts) == 8 and set(counts.values()) == {4}, 'four primary slots per each of eight repositories')
    for slot in slots:
        require(all(type(v) is bool for v in slot['target'].values()), 'boolean planning targets')
    multi = sum(s['target']['multi_module'] for s in slots)
    complex_count = sum(s['target']['complex'] for s in slots)
    historical = sum(s['target']['public_historical'] for s in slots)
    require((multi, complex_count, historical) == (19, 16, 16), 'frozen E02 layout changed; flags are not evidence')
    require(type(plan['projection']['multi_module']) is int and plan['projection']['multi_module'] == multi,
            'reported quota differs from derived quota')
    return {'multi_module': multi, 'complex': complex_count, 'public_historical': historical,
            'by_repository': dict(sorted(counts.items()))}


def make_candidates(data, protocol, plan, assignment, matrix):
    pilots = [decode(line) for line in data['eval/qualification/vertical/candidates.jsonl'].splitlines() if line.strip()]
    pilot_by_id = {r['id']: r for r in pilots}
    real = {folder: decode(data[f'eval/qualification/l5-real/{folder}/case.json'])
            for folder in protocol['state_folders']}
    rows = matrix['tasks']
    require([r['id'] for r in rows] == protocol['candidate_ids'] and len(rows) == 8, 'eight frozen qualified identities')
    require(len({r['change_lineage'] for r in rows}) == 8, 'duplicate lineage in frozen dossiers')
    slots = plan['slots']
    candidates = []
    for row in rows:
        require(row['individually_eligible'] is True and row['multi_module'] is True, 'historical qualification scope changed')
        compatible = [s for s in slots if (s['family'], s['repository_target'], s['kind']) ==
                      (row['family'], row['repository'], row['kind'])]
        require(len(compatible) == 1, 'ambiguous existing dossier slot')
        slot = compatible[0]
        require(slot['target']['multi_module'] is True, 'existing dossier was not already budgeted')
        if row['id'] in pilot_by_id:
            original = pilot_by_id[row['id']]
            modules = [m['path'] for m in original['production_modules']]
            relations = original['relations']
            source = 'eval/qualification/vertical/candidates.jsonl'
            language = original['language']
        else:
            folder = {'Rust': 'rust', 'TSJS': 'js', 'Python': 'python', 'Go': 'go'}[row['family']]
            original = real[folder]
            modules = ([m['path'] for m in original['production_modules']] if folder == 'rust'
                       else original['complexity']['required_production_modules'])
            if folder == 'rust':
                relations = original['relations']
            elif folder in ('js', 'go'):
                witness = decode(data[f'eval/qualification/l5-real/{folder}/oracles/source-relations.json'])
                relations = witness.get('edges', witness.get('relations', witness.get('evidence', [])))
            else:
                relations = original['complexity']['necessary_edges']
            source = f'eval/qualification/l5-real/{folder}/case.json'
            language = {'rust': 'Rust', 'js': 'JavaScript', 'python': 'Python', 'go': 'Go'}[folder]
        require(len(set(modules)) >= 2 and len(relations) >= 1, 'captured dossier relation evidence missing')
        candidates.append({'task_id': row['id'], 'lineage': row['change_lineage'], 'kind': row['kind'],
                           'family': row['family'], 'repository': row['repository'], 'language': language,
                           'canonical_slot_id': slot['slot_id'], 'source': source,
                           'production_units': modules, 'relation_basis': 'previously_qualified_dossier_bound_to_factual_matrix',
                           'individual_eligibility': 'previously_qualified_not_reexecuted',
                           'already_credited_in_projection': True, 'compensation_available': False,
                           'blocking_reasons': ['already_credited_multimodule_slot', 'duplicate_lineage_if_copied']})
    bindings = {r['task_id']: r for r in assignment['bindings']}
    for folder in protocol['state_folders']:
        prefix = f'eval/qualification/state-events/{folder}/'
        descriptor = decode(data[prefix + 'descriptor.json'])
        state_b = decode(data[prefix + 'b.json'])
        oracle = decode(data[prefix + 'oracle.json'])
        queries = decode(data[prefix + 'queries.json'])
        units = sorted(state_b['files'])
        require(descriptor['task_id'] in bindings and descriptor['individual_eligible'] is False, 'state qualification changed')
        binding = bindings[descriptor['task_id']]
        require(binding['repository'] == descriptor['repository'], 'state repository conflict')
        require(set(units) == set(descriptor['b_inventory']), 'state units differ from descriptor')
        for name in units:
            info = descriptor['b_inventory'][name]
            raw = state_b['files'][name].encode('utf-8')
            require(len(raw) == info['bytes'] and hashlib.sha256(raw).hexdigest() == info['sha256'], 'captured source bytes changed')
        if len(units) == 1:
            require(descriptor['capacity'] == 'rust-r3-v1-limited-root-lookup', 'single-unit profile')
            reason = 'single_production_unit'
        else:
            require(descriptor['capacity'] == 'captured-source-presence-v1' and
                    all(q['kind'] == 'source_presence' for q in queries) and
                    all(set(answer[side]) == {'available', 'sha256'} for answer in oracle['answers'].values() for side in ('a', 'b')),
                    'presence-only oracle scope')
            reason = 'presence_oracle_does_not_require_cross_unit_relation'
        candidates.append({'task_id': descriptor['task_id'], 'lineage': descriptor['change_lineage'],
                           'kind': descriptor['kind'], 'family': descriptor['family'], 'repository': descriptor['repository'],
                           'canonical_slot_id': binding['canonical_slot_id'], 'language': binding['language'], 'source': prefix + 'descriptor.json',
                           'production_units': units, 'relation_basis': 'not_demonstrated_by_frozen_task_oracle',
                           'individual_eligibility': 'not_qualified', 'already_credited_in_projection': False,
                           'compensation_available': False, 'blocking_reasons': [reason, 'individual_qualification_missing']})
    require(len({r['task_id'] for r in candidates}) == 12 and len({r['lineage'] for r in candidates}) == 12,
            'unique frozen candidate identities and lineages')
    return candidates


def literal_witnesses(data, protocol):
    result = []
    for witness in protocol['literal_witnesses']:
        state = decode(data[f"eval/qualification/state-events/{witness['folder']}/b.json"])
        anchors = []
        for side in ('from', 'to'):
            path = witness[side + '_path']
            raw = state['files'][path].encode('utf-8')
            needle = witness[side + '_needle'].encode('utf-8')
            require(raw.count(needle) == 1, 'literal witness must have one exact captured anchor')
            offset = raw.index(needle)
            anchors.append({'path': path, 'source_sha256': hashlib.sha256(raw).hexdigest(),
                            'byte_start': offset, 'byte_end': offset + len(needle),
                            'line': raw[:offset].count(b'\n') + 1, 'needle': witness[side + '_needle']})
        result.append({'folder': witness['folder'], 'anchors': anchors, 'meaning': witness['meaning'],
                       'semantic_resolution_proven': False, 'necessary_to_frozen_presence_task': False,
                       'qualification_credit': 0})
    return result


def assess_request(request, candidates, slots):
    require(type(request) is dict and set(request) == {'task_id', 'slot_id'}, 'proposal requires only frozen task and canonical slot; flags/aliases forbidden')
    by_task = {r['task_id']: r for r in candidates}
    by_slot = {r['slot_id']: r for r in slots}
    require(type(request['task_id']) is str and request['task_id'] in by_task, 'unknown task or copied alias')
    require(type(request['slot_id']) is str and request['slot_id'] in by_slot, 'unknown canonical slot')
    candidate, slot = by_task[request['task_id']], by_slot[request['slot_id']]
    reasons = []
    for source, target, reason in [('repository', 'repository_target', 'repository_conflict'),
                                   ('family', 'family', 'family_conflict'), ('kind', 'kind', 'task_kind_conflict'),
                                   ('language', 'language_target', 'language_conflict')]:
        if candidate[source] != slot[target]:
            reasons.append(reason)
    if slot['target']['multi_module']:
        reasons.append('slot_already_has_multimodule_target')
    reasons.extend(candidate['blocking_reasons'])
    return {'task_id': request['task_id'], 'slot_id': request['slot_id'],
            'compatible_kind_family_repository': not any(r.endswith('_conflict') for r in reasons),
            'compatible_language': candidate['language'] == slot['language_target'],
            'accepted_compensation': False, 'projection_delta': 0, 'blocking_reasons': reasons}


def assess_requests(requests, candidates, slots):
    require(type(requests) is list and 0 < len(requests) <= 32, 'bounded nonempty proposals')
    result = [assess_request(r, candidates, slots) for r in requests]
    require(len({r['task_id'] for r in requests}) == len(requests), 'one task cannot become multiple independent tasks')
    require(len({r['slot_id'] for r in requests}) == len(requests), 'one task per slot')
    return result


def derive(root=ROOT):
    freeze, data = frozen_inputs(root)
    protocol = decode(data[PREFIX + 'protocol.json'])
    plan = decode(data['eval/qualification/l5-slot-plan-v2.json'])
    assignment = decode(data['eval/qualification/l5-state-assignment-v2.json'])
    matrix = decode(data['eval/qualification/c02-status-matrix.json'])
    projection = validate_layout(plan)
    candidates = make_candidates(data, protocol, plan, assignment, matrix)
    requests = [assess_request({'task_id': r['task_id'], 'slot_id': s['slot_id']}, candidates, plan['slots'])
                for r in candidates for s in plan['slots']]
    return {'schema': 'xrai.eval.e02.compensation-inventory.v1', 'freeze_sha256': FREEZE_SHA,
            'input_receipts': deepcopy(freeze['inputs']), 'scope': protocol['scope'],
            'projection': projection, 'required_multi_module': 20, 'missing_multi_module': 1,
            'candidates': candidates, 'literal_witnesses': literal_witnesses(data, protocol),
            'candidate_slot_checks': requests, 'compensations_available_in_frozen_scope': 0,
            'previously_eligible_tasks': 8, 'new_eligible_tasks': 0, 'admitted_tasks': 0,
            'competitive_runs_allowed': False, 'allocation_globally_satisfactory': False,
            'next_action': 'Select an independent natural task requiring a cross-module relation and qualify its oracle/search universe/review before a prospective allocation revision.',
            'negative_scope': protocol['negative_scope']}


def verify(record=None, root=ROOT):
    expected = derive(root)
    if record is not None:
        require(canonical(record) == canonical(expected), 'inventory does not equal frozen input derivation')
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path)
    args = parser.parse_args()
    supplied = decode(args.inventory.read_bytes()) if args.inventory else None
    print(json.dumps(verify(supplied), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
