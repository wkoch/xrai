#!/usr/bin/env python3
"""Data-only counterproofs for the bounded E02 inventory."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

PATH = Path(__file__).with_name('e02_compensation.py')
spec = importlib.util.spec_from_file_location('e02_compensation', PATH)
e02 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e02)


class E02CompensationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = e02.derive()
        cls.freeze, cls.data = e02.frozen_inputs()
        cls.plan = e02.decode(cls.data['eval/qualification/l5-slot-plan-v2.json'])
        cls.assignment = e02.decode(cls.data['eval/qualification/l5-state-assignment-v2.json'])
        cls.matrix = e02.decode(cls.data['eval/qualification/c02-status-matrix.json'])
        cls.protocol = e02.decode(cls.data[e02.PREFIX + 'protocol.json'])

    def verify_mutation(self, mutate):
        record = deepcopy(self.record)
        mutate(record)
        with self.assertRaises(ValueError):
            e02.verify(record)

    def request(self, task=None, slot=None):
        return {'task_id': task or self.record['candidates'][0]['task_id'],
                'slot_id': slot or self.record['candidates'][0]['canonical_slot_id']}

    def assess(self, request):
        return e02.assess_request(request, self.record['candidates'], self.plan['slots'])

    def test_exact_replay(self):
        self.assertEqual(e02.verify(self.record), self.record)

    def test_scope_and_quota_derived(self):
        self.assertEqual(len(self.record['candidate_slot_checks']), 384)
        self.assertEqual(self.record['projection']['multi_module'], 19)
        self.assertEqual(self.record['missing_multi_module'], 1)
        self.assertEqual(self.record['compensations_available_in_frozen_scope'], 0)
        self.assertTrue(all(not r['accepted_compensation'] for r in self.record['candidate_slot_checks']))

    def test_eight_existing_tasks_already_credited(self):
        for candidate in self.record['candidates'][:8]:
            self.assertTrue(candidate['already_credited_in_projection'])
            result = self.assess(self.request(candidate['task_id'], candidate['canonical_slot_id']))
            self.assertTrue(result['compatible_kind_family_repository'])
            self.assertIn('already_credited_multimodule_slot', result['blocking_reasons'])
            self.assertEqual(result['projection_delta'], 0)

    def test_copy_is_unknown_task(self):
        with self.assertRaisesRegex(ValueError, 'copied alias'):
            self.assess(self.request(self.record['candidates'][0]['task_id'] + '-copy'))

    def test_alias_field_rejected(self):
        request = self.request()
        request['alias'] = request['task_id']
        with self.assertRaisesRegex(ValueError, 'aliases forbidden'):
            self.assess(request)

    def test_multimodule_boolean_is_not_evidence(self):
        request = self.request()
        request['multi_module'] = True
        with self.assertRaisesRegex(ValueError, 'flags/aliases forbidden'):
            self.assess(request)

    def test_claimed_new_lineage_is_not_identity(self):
        request = self.request()
        request['lineage'] = 'controlled:invented-independent-task'
        with self.assertRaises(ValueError):
            self.assess(request)

    def test_relabel_correction_as_review_is_conflict(self):
        candidate = self.record['candidates'][4]
        result = self.assess(self.request(candidate['task_id'], 'L5-SLOT-Rust-review-1'))
        self.assertIn('task_kind_conflict', result['blocking_reasons'])
        self.assertFalse(result['accepted_compensation'])

    def test_repository_conflict(self):
        result = self.assess(self.request(slot='L5-SLOT-Rust-correction-2'))
        self.assertIn('repository_conflict', result['blocking_reasons'])

    def test_family_conflict(self):
        result = self.assess(self.request(slot='L5-SLOT-Go-control-1'))
        self.assertIn('family_conflict', result['blocking_reasons'])

    def test_javascript_not_typescript_by_family_alias(self):
        candidate = self.record['candidates'][5]
        self.assertEqual(candidate['language'], 'JavaScript')
        slots = deepcopy(self.plan['slots'])
        slot = next(s for s in slots if s['slot_id'] == candidate['canonical_slot_id'])
        slot['language_target'] = 'TypeScript'
        result = e02.assess_request(self.request(candidate['task_id'], candidate['canonical_slot_id']), self.record['candidates'], slots)
        self.assertIn('language_conflict', result['blocking_reasons'])
        self.assertFalse(result['compatible_language'])
        self.assertFalse(result['accepted_compensation'])

    def test_unknown_slot(self):
        with self.assertRaisesRegex(ValueError, 'unknown canonical slot'):
            self.assess(self.request(slot='L5-SLOT-Rust-correction-5'))

    def test_duplicate_task_placement(self):
        requests = [self.request(), self.request(slot='L5-SLOT-Rust-control-1')]
        with self.assertRaisesRegex(ValueError, 'multiple independent tasks'):
            e02.assess_requests(requests, self.record['candidates'], self.plan['slots'])

    def test_duplicate_slot_placement(self):
        requests = [self.request(), self.request(self.record['candidates'][4]['task_id'])]
        with self.assertRaisesRegex(ValueError, 'one task per slot'):
            e02.assess_requests(requests, self.record['candidates'], self.plan['slots'])

    def test_empty_proposal(self):
        with self.assertRaises(ValueError):
            e02.assess_requests([], self.record['candidates'], self.plan['slots'])

    def test_proposal_bound(self):
        with self.assertRaises(ValueError):
            e02.assess_requests([self.request()] * 33, self.record['candidates'], self.plan['slots'])

    def test_single_file_state_not_multimodule(self):
        candidate = self.record['candidates'][8]
        self.assertEqual(len(candidate['production_units']), 1)
        self.assertIn('single_production_unit', candidate['blocking_reasons'])
        self.assertFalse(candidate['compensation_available'])

    def test_two_files_presence_not_relation_credit(self):
        for candidate in self.record['candidates'][9:]:
            self.assertEqual(len(candidate['production_units']), 2)
            self.assertIn('presence_oracle_does_not_require_cross_unit_relation', candidate['blocking_reasons'])
            self.assertFalse(candidate['compensation_available'])

    def test_literal_import_export_not_necessary_to_presence_task(self):
        self.assertEqual(len(self.record['literal_witnesses']), 2)
        for witness in self.record['literal_witnesses']:
            self.assertFalse(witness['necessary_to_frozen_presence_task'])
            self.assertFalse(witness['semantic_resolution_proven'])
            self.assertEqual(witness['qualification_credit'], 0)
            self.assertNotEqual(witness['anchors'][0]['path'], witness['anchors'][1]['path'])

    def test_fifth_repository_slot_rejected(self):
        plan = deepcopy(self.plan)
        plan['slots'][-1]['repository_target'] = plan['slots'][0]['repository_target']
        with self.assertRaisesRegex(ValueError, 'four primary slots'):
            e02.validate_layout(plan)

    def test_extra_slot_rejected(self):
        plan = deepcopy(self.plan)
        plan['slots'].append(deepcopy(plan['slots'][0]))
        with self.assertRaisesRegex(ValueError, '32 unique'):
            e02.validate_layout(plan)

    def test_duplicate_canonical_slot_rejected(self):
        plan = deepcopy(self.plan)
        plan['slots'][-1]['slot_id'] = plan['slots'][0]['slot_id']
        with self.assertRaisesRegex(ValueError, '32 unique'):
            e02.validate_layout(plan)

    def test_false_twentieth_projection(self):
        plan = deepcopy(self.plan)
        next(s for s in plan['slots'] if not s['target']['multi_module'])['target']['multi_module'] = True
        with self.assertRaisesRegex(ValueError, 'flags are not evidence'):
            e02.validate_layout(plan)

    def test_projection_report_not_authority(self):
        plan = deepcopy(self.plan)
        plan['projection']['multi_module'] = 20
        with self.assertRaisesRegex(ValueError, 'reported quota'):
            e02.validate_layout(plan)

    def test_bool_integer_confusion(self):
        plan = deepcopy(self.plan)
        plan['slots'][0]['target']['multi_module'] = 1
        with self.assertRaisesRegex(ValueError, 'boolean'):
            e02.validate_layout(plan)

    def test_eligibility_flag_in_result(self):
        self.verify_mutation(lambda r: r.update(new_eligible_tasks=1))

    def test_admission_flag_in_result(self):
        self.verify_mutation(lambda r: r.update(admitted_tasks=1, competitive_runs_allowed=True))

    def test_inventory_false_compensation(self):
        self.verify_mutation(lambda r: r['candidates'][0].update(compensation_available=True))

    def test_receipt_scope_not_truncated(self):
        self.verify_mutation(lambda r: r['input_receipts'].pop())

    def test_invented_relation_credit(self):
        self.verify_mutation(lambda r: r['literal_witnesses'][0].update(qualification_credit=1))

    def test_old_lineage_changed_in_result(self):
        self.verify_mutation(lambda r: r['candidates'][0].update(lineage='synthetic:new'))

    def clone_inputs(self, root):
        for path, raw in self.data.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        freeze = root / e02.PREFIX / 'freeze.json'
        freeze.write_bytes((e02.ROOT / e02.PREFIX / 'freeze.json').read_bytes())

    def test_historical_source_byte_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.clone_inputs(root)
            p = root / 'eval/qualification/state-events/python/b.json'
            p.write_bytes(p.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'fingerprint changed'):
                e02.derive(root)

    def test_reanchored_input_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.clone_inputs(root)
            p = root / e02.PREFIX / 'freeze.json'
            freeze = e02.decode(p.read_bytes())
            freeze['inputs'][0]['sha256'] = '0' * 64
            p.write_text(json.dumps(freeze))
            with self.assertRaisesRegex(ValueError, 'fingerprint changed'):
                e02.derive(root)

    def test_symlink_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.clone_inputs(root)
            p = root / 'eval/qualification/state-events/python/b.json'
            backup = root / 'backup.json'
            shutil.move(p, backup)
            p.symlink_to(backup)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                e02.derive(root)

    def test_duplicate_json_key_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            e02.decode(b'{"task_id":"a", "task_id":"b"}')

    def test_nonfinite_json_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            e02.decode(b'{"gain":NaN}')

    def test_path_alias_rejected(self):
        for path in ('/tmp/a', '../a', 'x/./a', 'x//a', 'x\\a', 'a:b'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                e02.read_bound(e02.ROOT, path)


if __name__ == '__main__':
    unittest.main()
