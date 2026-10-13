#!/usr/bin/env python3
"""E02 prospective state allocation and factual progress; data only.

Historical descriptors, slot references and native receipts remain immutable.
This consumer maps their identities explicitly; planning never admits a task.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION = ROOT / 'eval/qualification'
BASE_PLAN = 'eval/qualification/l5-slot-plan.json'
BASE_PLAN_SHA = 'ec4f37722ba944af7ef29004b77594a5414df5d8a5625dc4abd6e560aff7765b'
PLAN = 'eval/qualification/l5-slot-plan-v2.json'
ASSIGNMENT = 'eval/qualification/l5-state-assignment-v2.json'
PROGRESS = 'eval/qualification/state-progress-v2.json'
PROOF_DIRECTORY = 'docs/relatorios/logs/L5-C03/native-proof'
RUST_RUN = 38309739709
RUST_HEAD = '4972f0285915a37d044d0d2bee30a32eecaffb30'
RUST_ARTIFACT = 11773539273
FAMILIES = ('Rust', 'TSJS', 'Python', 'Go')
CASES = (
    ('rust', 'Rust', 'Rust', 'rust-lang/rust-analyzer', 'L5-STATE-Rust-STDX-EDITION',
     '78cb26abf5d189d866a9fadfcc462a0c8c18d4d35acce05ced85f2be25a85d0a'),
    ('js', 'TSJS', 'JavaScript', 'facebook/react', 'L5-STATE-TSJS-SOURCE-AVAILABILITY',
     'd2ed15309db714d776429680c591336e9693c9d55f3f5b94cfa861c6fcced08a'),
    ('python', 'Python', 'Python', 'scikit-learn/scikit-learn', 'L5-STATE-Python-SOURCE-AVAILABILITY',
     'bb7d2d2a765d86b28b9c91724221d1219df931f1c7b44fa55a758a230e25fc42'),
    ('go', 'Go', 'Go', 'go-gitea/gitea', 'L5-STATE-Go-SOURCE-AVAILABILITY',
     '0a85e6222ae5a9a8db3fd08d2dda85b42b58b90667d50aaa766d4db6fff4c8c2'),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def same_json(left, right):
    """JSON booleans and integers are distinct despite Python equality."""
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == \
        json.dumps(right, sort_keys=True, separators=(',', ':'), allow_nan=False)


def decode(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + value)))


def receipt(path, root=ROOT):
    return {'path': path, 'sha256': sha((root / path).read_bytes())}


def bind(value, *, root=ROOT, path=None, digest=None):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'exact artifact receipt fields')
    name = value['path']
    require(isinstance(name, str) and name and not name.startswith('/') and '\\' not in name and
            ':' not in name and all(part not in ['', '.', '..'] for part in name.split('/')), 'artifact path alias/escape')
    require(isinstance(value['sha256'], str) and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'artifact case hash required')
    require(path is None or name == path, 'artifact identity mismatch')
    require(digest is None or value['sha256'] == digest, 'frozen artifact hash relabeled')
    candidate = root / name
    require(candidate.resolve().is_relative_to(root.resolve()) and
            all(not parent.is_symlink() for parent in [candidate, *candidate.parents] if parent.is_relative_to(root)),
            'artifact symlink/escape')
    require(candidate.is_file(), 'artifact unavailable: ' + name)
    raw = candidate.read_bytes()
    require(sha(raw) == value['sha256'], 'artifact fingerprint mismatch: ' + name)
    return raw


def expected_plan(base):
    """Only the E02 changes are authorized in version 2; no silent compensation."""
    result = deepcopy(base)
    result.update(schema='xrai.eval.qualification.slot-plan.v2', plan_version=2,
                  status='conditional_planning_with_explicit_deficit',
                  base_plan={'path': BASE_PLAN, 'sha256': BASE_PLAN_SHA})
    result['authority'].append('docs/relatorios/REVISAO-L5-C03.md#2-e02--conciliar-tarefa-congelada-e-slot-de-admissão')
    for slot in result['slots']:
        if slot['kind'] == 'state_config':
            slot['target']['incremental_same_process'] = slot['slot_id'].endswith('-2')
        if slot['slot_id'] == 'L5-SLOT-Rust-state_config-2':
            slot['target']['multi_module'] = False
    result['projection'] = {'complex': 16, 'public_historical': 16, 'multi_module': 19,
                            'by_repository': dict(Counter(s['repository_target'] for s in result['slots']))}
    result['planning_deficits'] = {'multi_module': {'projected': 19, 'required': 20, 'missing': 1,
        'compensating_task': None, 'status': 'pending_selection_and_qualification',
        'reason': 'Rust rand.rs is unitary; two captured files do not demonstrate a necessary semantic relation.'}}
    result['allocation_globally_satisfactory'] = False
    result['limits'].append('E02 transfers required events without changing frozen task IDs or receipts; 19/20 multimodule projection blocks global admission.')
    return result


def expected_assignment(plan, *, root=ROOT):
    return {'schema': 'xrai.eval.qualification.state-assignment.v2', 'version': 2,
            'plan_version': 2, 'status': 'prospective_allocation_not_admission',
            'plan': receipt(PLAN, root), 'base_plan': {'path': BASE_PLAN, 'sha256': BASE_PLAN_SHA},
            'admitted_tasks': 0, 'competitive_runs_allowed': False,
            'bindings': [{'task_id': task, 'family': family, 'language': language,
                          'repository': repository, 'original_slot_id': f'L5-SLOT-{family}-state_config-1',
                          'canonical_slot_id': f'L5-SLOT-{family}-state_config-2',
                          'descriptor': {'path': f'eval/qualification/state-events/{folder}/descriptor.json', 'sha256': digest},
                          'required_event': True, 'aliases': []}
                         for folder, family, language, repository, task, digest in CASES]}


def validate_allocation(plan, assignment, *, root=ROOT):
    """Validate the bijection and deficits, without trusting completion flags."""
    require(plan.get('schema') == 'xrai.eval.qualification.slot-plan.v2' and
            type(plan.get('plan_version')) is int and plan['plan_version'] == 2, 'prospective plan version')
    base = decode(bind(plan['base_plan'], root=root, path=BASE_PLAN, digest=BASE_PLAN_SHA))
    slots = plan['slots']
    require(len(slots) == 32 and len({s['slot_id'] for s in slots}) == 32, 'exactly 32 unique canonical slots')
    counts = Counter(s['repository_target'] for s in slots)
    require(max(counts.values()) <= 4, 'repository exceeds four primary slots')
    require(all(type(flag) is bool for slot in slots for flag in slot['target'].values()), 'boolean planning targets')
    multi = sum(slot['target']['multi_module'] for slot in slots)
    require(multi == 19 and plan['projection']['multi_module'] == multi, 'multimodule projection is 19, never a false quota of 20')
    require(same_json(plan, expected_plan(base)), 'plan differs from the explicit E02 allocation; compensation requires a new evidenced revision')
    require(assignment.get('schema') == 'xrai.eval.qualification.state-assignment.v2' and
            type(assignment.get('version')) is int and assignment['version'] == 2 and
            type(assignment.get('plan_version')) is int and assignment['plan_version'] == 2,
            'assignment/plan version')
    bind(assignment['plan'], root=root, path=PLAN)
    require(same_json(decode(bind(assignment['plan'], root=root)), plan), 'assignment plan fingerprint')
    bind(assignment['base_plan'], root=root, path=BASE_PLAN, digest=BASE_PLAN_SHA)
    entries = assignment['bindings']
    require(len(entries) == 4 and len({e['task_id'] for e in entries}) == 4 and
            len({e['canonical_slot_id'] for e in entries}) == 4 and
            len({e['original_slot_id'] for e in entries}) == 4, 'task-slot assignment must be a bijection')
    require({e['family'] for e in entries} == set(FAMILIES), 'one required event per family')
    by_slot = {s['slot_id']: s for s in slots}
    expected = expected_assignment(plan, root=root)
    expected_by_task = {e['task_id']: e for e in expected['bindings']}
    for entry in entries:
        require(entry['task_id'] in expected_by_task, 'unknown frozen case')
        original = expected_by_task[entry['task_id']]
        require(entry.get('aliases') == [], 'aliases are not new task identities')
        require(same_json(entry, original), 'frozen case/repository/language/slot/hash binding mismatch')
        descriptor = decode(bind(entry['descriptor'], root=root, path=original['descriptor']['path'], digest=original['descriptor']['sha256']))
        require((descriptor['task_id'], descriptor['slot_id'], descriptor['family'], descriptor['repository'],
                 descriptor['kind'], descriptor['event_role']) ==
                (entry['task_id'], entry['original_slot_id'], entry['family'], entry['repository'], 'state_config', 'required'),
                'frozen descriptor identity or role mismatch')
        require(descriptor['prepared'] is True and descriptor['complex'] is False and
                descriptor['individual_eligible'] is False and descriptor['admitted'] is False,
                'preparation does not imply qualification/admission')
        for artifact, info in descriptor['artifacts'].items():
            raw = bind({'path': str(Path(entry['descriptor']['path']).parent / artifact), 'sha256': info['sha256']}, root=root)
            require(type(info['bytes']) is int and len(raw) == info['bytes'], 'frozen case artifact byte count')
        target = by_slot[entry['canonical_slot_id']]
        require((target['family'], target['language_target'], target['repository_target'], target['kind']) ==
                (entry['family'], entry['language'], entry['repository'], 'state_config'), 'canonical repository/language/family conflict')
        require(target['target']['incremental_same_process'] is True and
                by_slot[entry['original_slot_id']]['target']['incremental_same_process'] is False,
                'required event obligation was not transferred')
    require(same_json(assignment, expected), 'assignment fields/order/admission differ from the explicit versioned map')
    return {'schema': 'xrai.eval.qualification.state-assignment.verification.v2',
            'assignment_valid': True, 'prepared': 4, 'planning_only': True,
            'plan_projection': plan['projection'], 'planning_deficits': plan['planning_deficits'],
            'allocation_globally_satisfactory': False, 'admitted_tasks': 0, 'competitive_runs_allowed': False}


def derive_progress(plan, assignment, *, root=ROOT):
    """Recompute preparation, C02 eligibility and the authentic historical event."""
    require(root == ROOT, 'factual verifiers require the real repository root')
    import prepare_state_events
    import reconcile_state_ci
    import verify_c02
    preparation = prepare_state_events.verify()
    require(preparation['prepared_required_events'] == 4, 'four frozen state preparations required')
    matrix_receipt = plan['factual_progress']
    matrix = decode(bind(matrix_receipt, root=root, path='eval/qualification/c02-status-matrix.json'))
    for source in matrix['sources']:
        bind(source, root=root)
    require(matrix == verify_c02.reconcile(), 'C02 evidence differs from the recomputed current historical matrix')
    require(matrix['summary']['eligible_tasks'] == 8 and matrix['summary']['admitted_tasks'] == 0,
            'E02 preserves eight individual tasks and zero global admission')
    proof = reconcile_state_ci.reconcile(root / PROOF_DIRECTORY, RUST_RUN, RUST_HEAD, RUST_ARTIFACT)
    stored_proof = receipt(PROOF_DIRECTORY + '/reconciliation.json', root)
    require(proof == decode(bind(stored_proof, root=root)), 'retained Rust proof differs from complete native/ZIP/API recomputation')
    event = proof['native_verification']
    rust = assignment['bindings'][0]
    require((event['task_id'], event['slot_id'], event['descriptor_sha256'], event['family']) ==
            (rust['task_id'], rust['original_slot_id'], rust['descriptor']['sha256'], 'Rust') and
            event['required_event_executed'] is True, 'Rust event differs from the frozen original case')
    tasks = [{'task_id': row['task_id'], 'family': row['family'], 'original_slot_id': row['original_slot_id'],
              'canonical_slot_id': row['canonical_slot_id'], 'prepared': True,
              'operational_event_proven': row['family'] == 'Rust', 'individual_eligible': False,
              'globally_admitted': False, 'proof': stored_proof if row['family'] == 'Rust' else None,
              'eligibility_blockers': ['natural task search/context and rubric qualification',
                                       'independent second reader and complete dossier criteria']}
             for row in assignment['bindings']]
    return {'schema': 'xrai.eval.qualification.state-progress.v2', 'data_only': True,
            'assignment': receipt(ASSIGNMENT, root), 'plan': receipt(PLAN, root),
            'c02_matrix': matrix_receipt, 'historical_rust_proof': stored_proof,
            'tasks': tasks,
            'summary': {'state_tasks_prepared': 4, 'required_events_operationally_proven': 1,
                        'new_state_dossiers_individually_eligible': 0, 'individual_eligible_tasks': 8,
                        'admitted_tasks': 0, 'primary_tasks_required': 32,
                        'competitive_runs_allowed': False,
                        'conditional_projection': matrix['summary']['conditional_projection'],
                        'required_event_by_family': {family: int(family == 'Rust') for family in FAMILIES},
                        'multi_module_planning_projection': 19, 'multi_module_planning_required': 20,
                        'multi_module_planning_deficit': 1},
            'blockers': ['multimodule allocation projects 19/20; compensating task pending',
                         'required operational events missing for TSJS/Python/Go',
                         'state dossiers remain individually unqualified', 'global corpus remains 0/32'],
            'limits': ['Original prepared executed=false flags are historical preparation, not current event counts.',
                       'Historical Rust event uses its original slot; only prospective admission consumes the map.',
                       'Original CI acquisition authenticated by its caller; local metadata is not a signature.',
                       'No native/upstream execution or new acquisition; all verification reads retained bytes.',
                       'Operational proof does not establish semantic accuracy, complexity, multimodule qualification or performance.']}


def verify(*, root=ROOT, progress=None):
    """Factual snapshot consumer: supplied progress is compared, never trusted."""
    plan = decode((root / PLAN).read_bytes())
    assignment = decode((root / ASSIGNMENT).read_bytes())
    allocation = validate_allocation(plan, assignment, root=root)
    actual = derive_progress(plan, assignment, root=root)
    retained = decode((root / PROGRESS).read_bytes()) if progress is None else progress
    require(same_json(retained, actual), 'derived state progress differs from recomputed evidence')
    return {'allocation': allocation, 'progress': actual, 'verified': True,
            'data_only': True, 'admitted_tasks': 0, 'competitive_runs_allowed': False}


def apply_assignment(rows, assignment):
    """Return canonical slots only after explicit frozen identity validation.

A future qualified dossier may retain the frozen event identity under
incremental_event.state_assignment. This does not qualify that dossier.
"""
    lookup = {entry['task_id']: entry for entry in assignment['bindings']}
    require(len(lookup) == len(assignment['bindings']), 'duplicate mapped task')
    require(len({row['id'] for row in rows}) == len(rows), 'duplicate admission task identity')
    canonical_slots, seen = {}, set()
    for row in rows:
        event = row.get('incremental_event')
        if not event or not event.get('state_assignment'):
            continue
        ref = event['state_assignment']
        require(event.get('role', 'required') == 'required', 'supplemental event cannot fill the mapped required slot')
        require(set(ref) == {'version', 'task_id', 'original_slot_id', 'canonical_slot_id', 'descriptor_sha256'},
                'exact admission state-assignment reference fields')
        require(type(ref['version']) is int and ref['version'] == 2 and ref['task_id'] in lookup, 'unknown assignment version/case')
        mapped = lookup[ref['task_id']]
        require((ref['original_slot_id'], ref['canonical_slot_id'], ref['descriptor_sha256']) ==
                (mapped['original_slot_id'], mapped['canonical_slot_id'], mapped['descriptor']['sha256']), 'admission frozen case/hash/slot mismatch')
        require(row['kind'] == 'state_config' and
                (row['family'], row['language'], row['repository']) ==
                (mapped['family'], mapped['language'], mapped['repository']), 'admission task repository/language/kind conflict')
        require(mapped['canonical_slot_id'] not in seen, 'duplicate state alias/canonical admission slot')
        seen.add(mapped['canonical_slot_id'])
        canonical_slots[row['id']] = mapped['canonical_slot_id']
    return canonical_slots


def admission(rows, *, root=ROOT, check_artifacts=True):
    """Prospective admission entry point; preserve the historical v1 consumer."""
    facts = verify(root=root)
    assignment = decode((root / ASSIGNMENT).read_bytes())
    canonical_slots = apply_assignment(rows, assignment)
    require(set(canonical_slots.values()) == {entry['canonical_slot_id'] for entry in assignment['bindings']},
            'E02 admission requires four explicitly mapped required events')
    require(facts['allocation']['allocation_globally_satisfactory'],
            'E02 admission blocked: multimodule allocation projects 19/20; task compensation pending')
    require(facts['progress']['summary']['required_events_operationally_proven'] == 4,
            'E02 admission blocked: four real required events not proven')
    from verify_qualified import validate
    return validate(rows, root=root / 'eval', check_artifacts=check_artifacts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-admission-readiness', action='store_true')
    args = parser.parse_args()
    result = verify()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    if args.require_admission_readiness:
        return not result['allocation']['allocation_globally_satisfactory']
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
