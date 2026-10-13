"""Own structural/data checks; does not run old probes or paid providers."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import campaign_preflight as campaign


def fixture_facts(events=1):
    return {'facts': {'verified': True, 'data_only': True,
        'allocation': {'allocation_globally_satisfactory': False},
        'progress': {'summary': {'state_tasks_prepared': 4, 'required_events_operationally_proven': events,
            'new_state_dossiers_individually_eligible': 0, 'individual_eligible_tasks': 8,
            'admitted_tasks': 0, 'primary_tasks_required': 32,
            'required_event_by_family': {'Rust': 1, 'TSJS': int(events == 4), 'Python': int(events == 4), 'Go': int(events == 4)},
            'multi_module_planning_projection': 19, 'multi_module_planning_required': 20}}},
        'admission': {'accepted': False, 'reason': 'four explicitly mapped required events missing'}}


class CampaignPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xrai-factual-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.names = ('eval/tasks/challenge-qualified.jsonl', 'owned/source.py')
        for name, raw in [(self.names[0], b''), (self.names[1], b'OWNED TEST DATA\n')]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.paths = mock.patch.object(campaign, 'closure_paths', return_value=self.names)
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.snapshot = campaign.CampaignSnapshot.capture(root=self.root)

    def test_snapshot_owns_bytes_and_manifest_has_no_mutable_authority(self):
        manifest = self.snapshot.manifest
        manifest['files'][self.names[1]]['sha256'] = '0' * 64
        self.assertNotEqual(manifest, self.snapshot.manifest)
        self.assertIs(type(self.snapshot.entries), tuple)
        self.assertTrue(all(type(raw) is bytes for _, raw in self.snapshot.entries))
        self.assertEqual(self.snapshot.fingerprint, campaign.sha(campaign.canonical(self.snapshot.manifest)))

    def test_existing_file_mutation_refused(self):
        (self.root / self.names[1]).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.snapshot.assert_current()

    def test_current_callback_cannot_mask_mutated_real_files(self):
        old = dict(self.snapshot.entries)
        (self.root / self.names[1]).write_bytes(b'changed real bytes')
        with mock.patch.object(campaign, '_recompute') as worker:
            with self.assertRaises(ValueError):
                campaign.preflight(self.snapshot, current=lambda: old)
            worker.assert_not_called()

    def test_factual_worker_rejects_alternative_execution_root(self):
        with self.assertRaisesRegex(ValueError, 'configured owned project root'):
            campaign._recompute(self.snapshot, [])

    def test_changed_file_closure_refused(self):
        with mock.patch.object(campaign, 'closure_paths', return_value=self.names + ('new/file',)):
            with self.assertRaises(ValueError):
                self.snapshot.assert_current()

    def test_current_callback_requires_exact_actual_bytes(self):
        correct = dict(self.snapshot.entries)
        self.snapshot.assert_current(current=lambda: correct)
        for invalid in [True, {'ready': True}, {'admitted': 32}, {self.names[0]: b''},
                        {**correct, self.names[1]: b'altered'}, {**correct, 'extra': b'data'}]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.snapshot.assert_current(current=lambda: invalid)

    def test_immutable_constructor_rejects_mutable_duplicate_and_escape(self):
        for entries in [[('file', b'x')], (('file', bytearray(b'x')),),
                        (('file', b'x'), ('file', b'x')), (('../escape', b'x'),)]:
            with self.assertRaises(ValueError):
                campaign.CampaignSnapshot(self.root, entries)

    def test_capture_bounds(self):
        with mock.patch.object(campaign, 'MAX_FILE_BYTES', 1):
            with self.assertRaises(ValueError):
                campaign.CampaignSnapshot.capture(root=self.root)
        with mock.patch.object(campaign, 'MAX_BYTES', 1):
            with self.assertRaises(ValueError):
                campaign.CampaignSnapshot(self.root, self.snapshot.entries)

    def test_private_materialization_is_exact_and_fresh(self):
        target = self.root / 'private-copy'
        self.snapshot.materialize(target)
        for name, raw in self.snapshot.entries:
            self.assertEqual((target / name).read_bytes(), raw)
        with self.assertRaises(ValueError):
            self.snapshot.materialize(target)

    def test_mutation_before_factual_worker_is_not_consumed(self):
        (self.root / self.names[1]).write_bytes(b'changed')
        with mock.patch.object(campaign, '_recompute') as worker:
            with self.assertRaises(ValueError):
                campaign.preflight(self.snapshot)
            worker.assert_not_called()

    def test_mutation_during_recomposition_is_refused(self):
        def mutate(snapshot, rows):
            (self.root / self.names[1]).write_bytes(b'changed during worker')
            return fixture_facts()
        with mock.patch.object(campaign, '_recompute', side_effect=mutate):
            with self.assertRaises(ValueError):
                campaign.preflight(self.snapshot)

    def test_diagnostic_uses_recomputed_facts_and_admission_refusal(self):
        facts = fixture_facts()
        with mock.patch.object(campaign, '_recompute', return_value=facts) as worker:
            result = campaign.preflight(self.snapshot, rows=[])
            worker.assert_called_once_with(self.snapshot, [])
        self.assertFalse(result['accepted'])
        self.assertIn('19/20', result['dimensions']['allocation'])
        self.assertIn('0/32', result['dimensions']['corpus'])
        self.assertIn('1/4', result['dimensions']['events'])
        self.assertEqual(result['dimensions']['admission'], facts['admission']['reason'])
        self.assertEqual(result['snapshot_sha256'], self.snapshot.fingerprint)
        self.assertEqual(result['external_calls'], 0)
        self.assertFalse(result['paid_provider_enabled'])

    def test_four_event_facts_update_diagnostic_without_releasing_provider(self):
        with mock.patch.object(campaign, '_recompute', return_value=fixture_facts(events=4)):
            result = campaign.preflight(self.snapshot)
        self.assertNotIn('events', result['dimensions'])
        self.assertEqual(result['factual_summary']['required_events_operationally_proven'], 4)
        self.assertFalse(result['accepted'])
        self.assertIn('provider', result['dimensions'])
        self.assertIn('authorization', result['dimensions'])
        self.assertIn('budget', result['dimensions'])
        self.assertIn('state_dossiers', result['dimensions'])

    def test_caller_rows_and_ready_flags_do_not_override_facts(self):
        rows = [{'ready': True, 'admitted': 32}]
        with mock.patch.object(campaign, '_recompute', return_value=fixture_facts()):
            result = campaign.preflight(self.snapshot, rows=rows)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['factual_summary']['admitted_tasks'], 0)
        with self.assertRaises(TypeError):
            campaign.preflight(self.snapshot, ready=True)

    def test_explicit_rows_require_list_of_objects(self):
        for rows in [True, {'admitted': 32}, [32], [True]]:
            with self.assertRaises(ValueError):
                campaign.preflight(self.snapshot, rows=rows)

    def test_worker_unverified_and_extra_fields_refused(self):
        for mode in ['flag', 'extra']:
            value = fixture_facts()
            if mode == 'flag':
                value['facts']['verified'] = 1
            else:
                value['ready'] = True
            with mock.patch.object(campaign, '_recompute', return_value=value):
                with self.assertRaises(ValueError):
                    campaign.preflight(self.snapshot)

    def test_json_duplicate_and_nonfinite_flags_refused(self):
        for raw in [b'{"ready":false,"ready":true}', b'{"value":NaN}']:
            with self.assertRaises(ValueError):
                campaign.decode(raw)

    def test_worker_calls_real_admission_entrypoint(self):
        facts = fixture_facts()['facts']
        rows = self.root / 'rows.json'
        rows.write_text('[]')
        allocation = mock.Mock()
        allocation.verify.return_value = facts
        allocation.admission.side_effect = ValueError('actual admission gate refusal')
        with mock.patch.dict('sys.modules', {'verify_state_assignment': allocation}):
            result = campaign._worker(rows)
        allocation.verify.assert_called_once_with()
        allocation.admission.assert_called_once_with([])
        self.assertEqual(result['admission'], {'accepted': False, 'reason': 'actual admission gate refusal'})


if __name__ == '__main__':
    unittest.main()
