"""E02 data-only counterproofs; no native/upstream execution."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import verify_state_assignment as v


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xrai-e02-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for path in [v.BASE_PLAN, v.PLAN, v.ASSIGNMENT]:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(v.ROOT / path, target)
        for folder, *_ in v.CASES:
            destination = self.root / f'eval/qualification/state-events/{folder}'
            shutil.copytree(v.ROOT / f'eval/qualification/state-events/{folder}', destination)
        self.plan = v.decode((self.root / v.PLAN).read_bytes())
        self.assignment = v.decode((self.root / v.ASSIGNMENT).read_bytes())

    def validate(self):
        return v.validate_allocation(self.plan, self.assignment, root=self.root)

    def reject(self):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            self.validate()

    def test_explicit_mapping_preserves_original_and_repository_balance(self):
        result = self.validate()
        self.assertEqual(result['prepared'], 4)
        self.assertEqual(result['plan_projection']['multi_module'], 19)
        self.assertTrue(result['planning_only'])
        self.assertFalse(result['allocation_globally_satisfactory'])
        self.assertEqual(result['planning_deficits']['multi_module']['missing'], 1)
        for binding in self.assignment['bindings']:
            descriptor = v.decode((self.root / binding['descriptor']['path']).read_bytes())
            self.assertEqual(descriptor['slot_id'], binding['original_slot_id'])
            self.assertNotEqual(binding['canonical_slot_id'], descriptor['slot_id'])
            self.assertEqual(descriptor['executed'], False)
        self.assertEqual(set(result['plan_projection']['by_repository'].values()), {4})

    def test_conflicting_repository(self):
        self.assignment['bindings'][0]['repository'] = 'tokio-rs/tokio'
        self.reject()

    def test_conflicting_javascript_typescript(self):
        self.assignment['bindings'][1]['language'] = 'TypeScript'
        self.reject()

    def test_conflicting_family(self):
        self.assignment['bindings'][2]['family'] = 'Go'
        self.reject()

    def test_duplicate_canonical_slot(self):
        self.assignment['bindings'][1]['canonical_slot_id'] = self.assignment['bindings'][0]['canonical_slot_id']
        self.reject()

    def test_duplicate_task(self):
        self.assignment['bindings'][1]['task_id'] = self.assignment['bindings'][0]['task_id']
        self.reject()

    def test_duplicate_original_slot(self):
        self.assignment['bindings'][1]['original_slot_id'] = self.assignment['bindings'][0]['original_slot_id']
        self.reject()

    def test_aliases_not_extra_tasks(self):
        self.assignment['bindings'][0]['aliases'] = [self.assignment['bindings'][0]['task_id']] * 2
        self.reject()

    def test_missing_case_hash(self):
        del self.assignment['bindings'][0]['descriptor']['sha256']
        self.reject()

    def test_changed_descriptor_hash_cannot_repin_case(self):
        path = self.root / self.assignment['bindings'][0]['descriptor']['path']
        descriptor = v.decode(path.read_bytes())
        descriptor['slot_id'] = self.assignment['bindings'][0]['canonical_slot_id']
        path.write_text(json.dumps(descriptor))
        self.assignment['bindings'][0]['descriptor']['sha256'] = v.sha(path.read_bytes())
        self.reject()

    def test_frozen_artifact_mutation(self):
        path = self.root / 'eval/qualification/state-events/js/a.json'
        path.write_bytes(path.read_bytes() + b' ')
        self.reject()

    def test_symlink_artifact_refused(self):
        path = self.root / 'eval/qualification/state-events/js/a.json'
        replacement = self.root / 'alias.json'
        path.rename(replacement)
        path.symlink_to(replacement)
        self.reject()

    def test_path_alias(self):
        self.assignment['bindings'][0]['descriptor']['path'] = 'eval/qualification/state-events/rust/../rust/descriptor.json'
        self.reject()

    def test_five_primary_slots_per_repository(self):
        self.plan['slots'][4]['repository_target'] = 'rust-lang/rust-analyzer'
        self.reject()

    def test_duplicate_plan_slot(self):
        self.plan['slots'][1]['slot_id'] = self.plan['slots'][0]['slot_id']
        self.reject()

    def test_false_twenty_modules(self):
        next(s for s in self.plan['slots'] if s['slot_id'] == 'L5-SLOT-Rust-state_config-2')['target']['multi_module'] = True
        self.plan['projection']['multi_module'] = 20
        self.reject()

    def test_compensation_in_other_two_file_case_is_not_evidence(self):
        next(s for s in self.plan['slots'] if s['slot_id'] == 'L5-SLOT-TSJS-state_config-2')['target']['multi_module'] = True
        self.plan['projection']['multi_module'] = 20
        self.reject()

    def test_deficit_cannot_be_hidden(self):
        self.plan['planning_deficits'] = {}
        self.reject()

    def test_deficit_cannot_be_declared_satisfactory(self):
        self.plan['allocation_globally_satisfactory'] = True
        self.reject()

    def test_complex_target_cannot_be_invented(self):
        next(s for s in self.plan['slots'] if s['slot_id'] == 'L5-SLOT-Rust-state_config-2')['target']['complex'] = True
        self.reject()

    def test_required_event_not_transferred(self):
        for s in self.plan['slots']:
            if s['slot_id'] == 'L5-SLOT-Go-state_config-1':
                s['target']['incremental_same_process'] = True
        self.reject()

    def test_boolean_version_is_not_integer_version(self):
        self.assignment['version'] = True
        self.reject()

    def test_integer_flag_cannot_impersonate_boolean(self):
        self.assignment['bindings'][0]['required_event'] = 1
        self.reject()

    def test_plan_digest_mismatch(self):
        self.assignment['plan']['sha256'] = '0' * 64
        self.reject()

    def test_json_duplicate_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate JSON'):
            v.decode(b'{"version":2,"version":2}')

    def test_json_nonfinite_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonfinite JSON'):
            v.decode(b'{"version":NaN}')


class ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.assignment = v.decode((v.ROOT / v.ASSIGNMENT).read_bytes())
        self.plan = v.decode((v.ROOT / v.PLAN).read_bytes())
        self.progress = v.decode((v.ROOT / v.PROGRESS).read_bytes())

    def rows(self):
        return [{'id': 'Q1-state-' + entry['family'], 'family': entry['family'], 'language': entry['language'],
                 'repository': entry['repository'], 'kind': 'state_config',
                 'incremental_event': {'role': 'required', 'state_assignment': {
                     'version': 2, 'task_id': entry['task_id'], 'original_slot_id': entry['original_slot_id'],
                     'canonical_slot_id': entry['canonical_slot_id'], 'descriptor_sha256': entry['descriptor']['sha256']}}}
                for entry in self.assignment['bindings']]

    def test_explicit_admission_map(self):
        self.assertEqual(set(v.apply_assignment(self.rows(), self.assignment).values()),
                         {entry['canonical_slot_id'] for entry in self.assignment['bindings']})

    def test_admission_conflicting_repo(self):
        rows = self.rows(); rows[0]['repository'] = 'tokio-rs/tokio'
        with self.assertRaisesRegex(ValueError, 'repository/language'):
            v.apply_assignment(rows, self.assignment)

    def test_admission_duplicate_alias(self):
        rows = self.rows(); rows.append(deepcopy(rows[0])); rows[-1]['id'] = 'Q1-state-alias'
        with self.assertRaisesRegex(ValueError, 'duplicate state alias'):
            v.apply_assignment(rows, self.assignment)

    def test_admission_duplicate_task_identity(self):
        rows = self.rows(); rows[1]['id'] = rows[0]['id']
        with self.assertRaisesRegex(ValueError, 'duplicate admission task'):
            v.apply_assignment(rows, self.assignment)

    def test_presence_original_ci_reconciler_is_consumed(self):
        import prepare_state_events, reconcile_state_ci, reconcile_presence_ci, verify_c02
        matrix = v.decode((v.ROOT / self.plan['factual_progress']['path']).read_bytes())
        rust = v.decode((v.ROOT / self.progress['historical_rust_proof']['path']).read_bytes())
        false_proof = v.decode((v.ROOT / self.progress['presence_proof']['path']).read_bytes())
        false_proof['native_verification']['go']['required_event_executed'] = False
        with patch.object(prepare_state_events,'verify',return_value={'prepared_required_events':4}), \
             patch.object(verify_c02,'reconcile',return_value=matrix), \
             patch.object(reconcile_state_ci,'reconcile',return_value=rust), \
             patch.object(reconcile_presence_ci,'reconcile',return_value=false_proof) as consumed:
            with self.assertRaisesRegex(ValueError,'original ZIP/API recomputation'):
                v.derive_progress(self.plan,self.assignment)
            consumed.assert_called_once_with(v.ROOT/v.PRESENCE_PROOF_DIRECTORY,
                v.PRESENCE_RUN,v.PRESENCE_HEAD,v.PRESENCE_ARTIFACT)

    def test_supplemental_event_cannot_fill_required_slot(self):
        rows = self.rows(); rows[0]['incremental_event']['role'] = 'supplemental'
        with self.assertRaisesRegex(ValueError, 'supplemental event'):
            v.apply_assignment(rows, self.assignment)

    def test_admission_original_hash_cannot_be_changed(self):
        rows = self.rows(); rows[0]['incremental_event']['state_assignment']['descriptor_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'frozen case/hash'):
            v.apply_assignment(rows, self.assignment)

    def test_admission_deficit_blocks_before_legacy_consumer(self):
        facts = {'allocation': {'allocation_globally_satisfactory': False}, 'progress': self.progress}
        with patch.object(v, 'verify', return_value=facts), patch('verify_qualified.validate') as legacy:
            with self.assertRaisesRegex(ValueError, '19/20'):
                v.admission(self.rows())
            legacy.assert_not_called()

    def test_admission_cannot_skip_mapping(self):
        facts = {'allocation': {'allocation_globally_satisfactory': False}, 'progress': self.progress}
        with patch.object(v, 'verify', return_value=facts), patch('verify_qualified.validate') as legacy:
            with self.assertRaisesRegex(ValueError, 'four explicitly mapped'):
                v.admission([])
            legacy.assert_not_called()

    def test_forged_progress_flags_not_authority(self):
        forged = deepcopy(self.progress)
        forged['summary']['required_events_operationally_proven'] += 1
        forged['tasks'][1]['operational_event_proven'] = True
        with patch.object(v, 'derive_progress', return_value=self.progress):
            with self.assertRaisesRegex(ValueError, 'recomputed evidence'):
                v.verify(progress=forged)

    def test_progress_integer_does_not_impersonate_true(self):
        forged = deepcopy(self.progress)
        forged['tasks'][0]['operational_event_proven'] = 1
        with patch.object(v, 'derive_progress', return_value=self.progress):
            with self.assertRaisesRegex(ValueError, 'recomputed evidence'):
                v.verify(progress=forged)

    def test_preparer_executed_zero_is_not_actual_event_count(self):
        self.assertEqual(self.progress['summary']['required_events_operationally_proven'], 4)
        self.assertEqual(self.progress['summary']['required_event_by_family'], {'Rust': 1, 'TSJS': 1, 'Python': 1, 'Go': 1})
        self.assertEqual(self.progress['summary']['new_state_dossiers_individually_eligible'], 0)
        self.assertEqual(self.progress['summary']['individual_eligible_tasks'], 8)

    def test_rust_proof_reconciler_is_consumed_not_retained_boolean(self):
        import prepare_state_events
        import reconcile_state_ci
        import verify_c02
        matrix = v.decode((v.ROOT / self.plan['factual_progress']['path']).read_bytes())
        false_proof = v.decode((v.ROOT / self.progress['historical_rust_proof']['path']).read_bytes())
        false_proof['native_verification']['required_event_executed'] = False
        with patch.object(prepare_state_events, 'verify', return_value={'prepared_required_events': 4}), \
             patch.object(verify_c02, 'reconcile', return_value=matrix), \
             patch.object(reconcile_state_ci, 'reconcile', return_value=false_proof) as reconciler:
            with self.assertRaisesRegex(ValueError, 'complete native/ZIP/API recomputation'):
                v.derive_progress(self.plan, self.assignment)
            reconciler.assert_called_once_with(v.ROOT / v.PROOF_DIRECTORY, v.RUST_RUN, v.RUST_HEAD, v.RUST_ARTIFACT)


if __name__ == '__main__':
    unittest.main()
