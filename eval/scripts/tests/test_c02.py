"""Own evaluator fixtures: distinct C02 units and fail-closed projections."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_c02 as V
from verify_qualified import validate
from test_qualification import synthetic_rows


class C02Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'evidence.json').write_text(json.dumps({'same_index': True, 'same_process': True,
                                                         'full_B_snapshot_equal': True}))
        self.proof = V.receipt('evidence.json', self.root)
        self.state = {'schema': 'xrai.eval.c02.state.v1',
            **{k: {'status': 'verified', 'receipts': [self.proof]} for k in ('curation', 'review', 'behavior')},
            'event': {'role': 'not_applicable', 'preparation': 'not_applicable', 'execution': 'not_applicable',
                      'descriptor': None, 'execution_receipt': None},
            'individual_eligibility': {'eligible': True, 'blockers': []},
            'global_admission': {'admitted': False, 'competitive_runs_allowed': False}}

    def reject(self, match, kind='correction'):
        with self.assertRaisesRegex(ValueError, match):
            V.validate_state(self.state, kind, root=self.root)

    def test_historical_pair_without_event_is_individually_eligible(self):
        for kind in ('correction', 'contract_change'):
            self.assertTrue(V.validate_state(self.state, kind, root=self.root))
        self.assertFalse(self.state['global_admission']['admitted'])

    def test_supplemental_prepared_unexecuted_does_not_block(self):
        self.state['event'].update(role='supplemental', preparation='prepared', execution='not_executed', descriptor=self.proof)
        self.assertTrue(V.validate_state(self.state, 'correction', root=self.root))

    def test_behavior_proof_does_not_resolve_pending_review(self):
        self.state['review'].update(status='pending', receipts=[])
        self.state['individual_eligibility'] = {'eligible': False, 'blockers': ['review_not_verified']}
        self.assertFalse(V.validate_state(self.state, 'contract_change', root=self.root))

    def test_missing_review_not_silently_eligible(self):
        self.state['review'].update(status='pending', receipts=[])
        self.reject('eligibility differs')

    def test_missing_hash_evidence_not_verified(self):
        self.state['behavior']['receipts'] = []
        self.reject('without evidence')

    def test_tampered_evidence_rejected(self):
        self.state['review']['receipts'] = [dict(self.proof, sha256='0'*64)]
        self.reject('hash mismatch')

    def test_escaping_receipt_rejected(self):
        self.state['review']['receipts'] = [dict(self.proof, path='../outside')]
        self.reject('state schema')

    def test_integer_eligibility_rejected(self):
        self.state['individual_eligibility']['eligible'] = 1
        self.reject('state schema')

    def test_global_admission_cannot_be_set_by_case(self):
        self.state['global_admission']['admitted'] = True
        self.reject('state schema')

    def test_required_event_not_allowed_on_correction(self):
        self.state['event'].update(role='required', preparation='prepared', execution='not_executed', descriptor=self.proof)
        self.reject('state_config')

    def test_other_state_task_can_be_configuration_without_selected_event(self):
        self.assertTrue(V.validate_state(self.state, 'state_config', root=self.root))

    def test_state_requires_prepared_descriptor_but_tracks_execution_separately(self):
        self.state['event'].update(role='required', preparation='not_prepared', execution='not_executed')
        self.state['individual_eligibility'] = {'eligible': False, 'blockers': ['required_event_not_prepared']}
        self.assertFalse(V.validate_state(self.state, 'state_config', root=self.root))
        self.state['event'].update(preparation='prepared', descriptor=self.proof)
        self.state['individual_eligibility'] = {'eligible': True, 'blockers': []}
        self.assertTrue(V.validate_state(self.state, 'state_config', root=self.root))
        self.assertEqual(self.state['event']['execution'], 'not_executed')

    def test_event_execution_receipt_cannot_be_inferred_from_plan(self):
        self.state['event'].update(role='supplemental', preparation='prepared', execution='verified', descriptor=self.proof)
        self.reject('execution needs')

    def test_event_execution_requires_same_index_and_full_snapshot(self):
        self.state['event'].update(role='supplemental', preparation='prepared', execution='verified', descriptor=self.proof,
                                   execution_receipt=self.proof)
        self.assertTrue(V.validate_state(self.state, 'correction', root=self.root))
        (self.root / 'evidence.json').write_text(json.dumps({'same_index': False, 'same_process': True,
                                                          'full_B_snapshot_equal': True}))
        changed = V.receipt('evidence.json', self.root)
        self.state['event']['descriptor'] = changed
        self.state['event']['execution_receipt'] = changed
        for dimension in ('curation', 'review', 'behavior'):
            self.state[dimension]['receipts'] = [changed]
        self.reject('continuity/full B')

    def rows(self):
        return [{'id': str(i), 'change_lineage': 'lineage'+str(i), 'repository': 'repo'+str(i),
                 'family': 'Rust', 'complex': i >= 3, 'historical': True, 'multi_module': True,
                 'individually_eligible': True, 'source': 'preserved_l3_pilot' if i < 4 else 'l5_real_dossier',
                 'states': copy.deepcopy(self.state)} for i in range(6)]

    def test_projection_is_six_eligible_never_six_admitted(self):
        rows = self.rows()
        rows[4]['states']['event'].update(role='supplemental', preparation='prepared', execution='not_executed', descriptor=self.proof)
        result = V.summarize(rows)
        self.assertEqual(result['eligible_tasks'], 6)
        self.assertEqual(result['conditional_projection'], {'additional_tasks': 26, 'additional_complex': 13,
                'additional_historical': 10, 'additional_multi_module': 14, 'new_dossiers_remaining': 2,
                'admission_deficit': 32})
        self.assertEqual(result['admitted_tasks'], 0)
        self.assertFalse(result['competitive_runs_allowed'])
        self.assertEqual(result['required_state_events_prepared']['Rust'], 0)

    def test_unfinished_dossier_cannot_reduce_projection(self):
        rows = self.rows()
        rows[5]['individually_eligible'] = False
        result = V.summarize(rows)
        self.assertEqual(result['conditional_projection']['additional_tasks'], 27)
        self.assertEqual(result['new_dossiers_behavior_verified'], 2)
        self.assertEqual(result['new_dossiers_individually_eligible'], 1)

    def test_duplicate_lineage_is_not_independent_task(self):
        rows = self.rows()
        rows[5]['change_lineage'] = rows[4]['change_lineage']
        with self.assertRaisesRegex(ValueError, 'lineage'):
            V.summarize(rows)

    def test_repository_fifth_task_rejected(self):
        rows = self.rows()
        for row in rows:
            row['repository'] = 'one-repo'
        with self.assertRaisesRegex(ValueError, 'repository cap'):
            V.summarize(rows)

    def test_supplemental_corrective_event_never_fills_family_quota(self):
        rows = synthetic_rows()
        event = rows[4].pop('incremental_event')
        rows[0]['incremental_event'] = dict(event, role='supplemental')
        rows[0]['input']['state_changes'] = rows[4]['input']['state_changes']
        with self.assertRaisesRegex(ValueError, 'Rust incremental event missing'):
            validate(rows, check_artifacts=False)

    def test_supplemental_contract_event_never_fills_family_quota(self):
        rows = synthetic_rows()
        event = rows[4].pop('incremental_event')
        rows[2]['incremental_event'] = dict(event, role='supplemental')
        with self.assertRaisesRegex(ValueError, 'Rust incremental event missing'):
            validate(rows, check_artifacts=False)

    def test_nonstate_event_cannot_be_labeled_required(self):
        rows = synthetic_rows()
        rows[0]['incremental_event'] = dict(rows[4]['incremental_event'], role='required')
        with self.assertRaisesRegex(ValueError, 'schema'):
            validate(rows, check_artifacts=False)

    def test_js_complexity_cannot_inflate_duplicate_or_unreviewed_modules(self):
        modules = ['packages/react/src/one.js', 'packages/react-reconciler/src/two.js',
                   'packages/react-reconciler/src/three.js']
        case = {'complexity': {'required_production_modules': modules,
                              'subsystems': ['packages/react', 'packages/react-reconciler']}}
        review = {'anchors_exact_digest_and_lines_verified': [{'path': m} for m in modules]}
        edges = {'relationships': [{'from': modules[0]+'::a', 'to': modules[1]+'::b', 'why_required': 'API'},
                                   {'from': modules[1]+'::b', 'to': modules[2]+'::c', 'why_required': 'schedule'}]}
        V.reviewed_js_modules(case, review, edges)
        for altered in ([modules[0], modules[1], modules[1]], [modules[0], modules[1], 'tests/new.js']):
            with self.subTest(modules=altered):
                case['complexity']['required_production_modules'] = altered
                with self.assertRaisesRegex(ValueError, 'reviewed production anchors'):
                    V.reviewed_js_modules(case, review, edges)

    def test_js_complexity_needs_actual_two_edge_chain(self):
        modules = ['packages/react/src/one.js', 'packages/react-reconciler/src/two.js',
                   'packages/react-reconciler/src/three.js']
        case = {'complexity': {'required_production_modules': modules,
                              'subsystems': ['packages/react', 'packages/react-reconciler']}}
        review = {'anchors_exact_digest_and_lines_verified': [{'path': m} for m in modules]}
        edges = {'relationships': [{'from': modules[0]+'::a', 'to': modules[1]+'::b', 'why_required': 'API'},
                                   {'from': modules[0]+'::a', 'to': modules[2]+'::c', 'why_required': 'other'}]}
        with self.assertRaisesRegex(ValueError, 'two-edge path'):
            V.reviewed_js_modules(case, review, edges)


if __name__ == '__main__':
    unittest.main()
