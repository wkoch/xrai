import importlib.util
import json
import copy
import hashlib
from pathlib import Path
import unittest
import tempfile

SCRIPT=Path(__file__).resolve().parents[1]/'verify_slot_plan.py'
SPEC=importlib.util.spec_from_file_location('slot_plan_verifier',SCRIPT)
V=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(V)

class SlotPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan=json.loads((V.ROOT/'eval/qualification/l5-slot-plan.json').read_bytes())
    def rejects(self,pattern):
        with self.assertRaisesRegex(ValueError,pattern): V.validate(self.plan)
    def test_valid_allocation_is_not_admission(self):
        result=V.validate(self.plan)
        self.assertTrue(result['allocation_consistent'])
        self.assertEqual(result['admitted_tasks'],0)
        self.assertFalse(result['competitive_runs_allowed'])
        proof_ready=(V.ROOT/'docs/relatorios/logs/L5-C02/ci-next-first/verification.json').exists()
        self.assertEqual(result['conditional_deficits']['additional_complex'],11 if proof_ready else 13)
        self.assertEqual(result['factual_summary']['eligible_tasks'],8 if proof_ready else 6)
        self.assertEqual(result['new_dossiers_delivered'],4 if proof_ready else 2)
        self.assertEqual(result['factual_summary']['new_dossiers_curated_reviewed'],4)
        self.assertEqual(result['multi_module_targets'],20)
    def test_false_admission(self):
        self.plan['admitted_tasks']=32; self.rejects('false admission')
    def test_competition_enabled(self):
        self.plan['competitive_runs_allowed']=True; self.rejects('false admission')
    def test_duplicate_slot(self):
        self.plan['slots'][1]['slot_id']=self.plan['slots'][0]['slot_id']; self.rejects('duplicate slot')
    def test_incorrect_count(self):
        self.plan['slots'].pop(); self.rejects('exactly32')
    def test_repo_over_cap(self):
        rows=[s for s in self.plan['slots'] if s['family']=='Rust']
        rows[1]['repository_target']=rows[0]['repository_target']; self.rejects('max four')
    def test_stratum_violation(self):
        self.plan['slots'][1]['kind']='review'; self.rejects('family strata')
    def test_pilot_relabeling(self):
        self.plan['slots'][0]['existing_evidence']['complex']=True; self.rejects('pilot evidence promoted')
    def test_new_slot_fake_evidence(self):
        self.plan['slots'][1]['existing_evidence']={'complex':True}; self.rejects('new slot claims')
    def test_noncomplex_target_distribution(self):
        self.plan['slots'][1]['target']['complex']=False; self.rejects('four complex targets')
    def test_controls_cannot_fill_quotas(self):
        next(s for s in self.plan['slots'] if s['kind']=='control')['target']['multi_module']=True
        self.rejects('control inflates')
    def test_historical_floor(self):
        self.plan['slots'][1]['target']['public_historical']=False; self.rejects('four historical')
    def test_multi_module_floor(self):
        next(s for s in self.plan['slots'] if s['family']=='Rust' and s['kind']=='state_config' and s['repository_target']=='rust-lang/rust-analyzer')['target']['multi_module']=False
        self.rejects('20 noncontrol')
    def test_incremental_cold_not_silent_substitute(self):
        next(s for s in self.plan['slots'] if s['family']=='Rust' and s['target']['incremental_same_process'])['target']['incremental_same_process']=False
        self.rejects('incremental event')
    def test_js_quota_not_imputed_to_typescript(self):
        for s in self.plan['slots']:
            if s['family']=='TSJS': s['language_target']='TypeScript'
        self.rejects('two JS and two TS')
    def test_js_module_evidence_pending_explicit(self):
        next(r for r in self.plan['repositories'] if r['repository']=='facebook/react')['language_evidence_status']='JS_assumed'
        self.rejects('JS production evidence')
    def test_new_dossiers_not_delivered(self):
        self.plan['new_dossiers']['completed']+=1; self.rejects('falsely delivered')
    def test_dossier_targets_distinct(self):
        work=self.plan['new_dossiers']['next_slots']; work[1]=work[0]; self.rejects('four new dossier targets')
    def test_production_size_not_claimed_proven(self):
        self.plan['repositories'][0]['size_floor_status']='proven'; self.rejects('conditional size')
    def test_deficits_cannot_hide_remaining_work(self):
        self.plan['conditional_deficits']['new_dossiers_remaining']+=1; self.rejects('deficits mismatch')
    def test_artifact_tamper(self):
        self.plan['pilot_artifact']['sha256']='0'*64; self.rejects('pilot artifact hash')
    def test_boolean_targets_not_integer_estimates(self):
        self.plan['slots'][1]['target']['complex']=1; self.rejects('target types')
    def test_factual_matrix_hash_tamper(self):
        self.plan['factual_progress']['sha256']='0'*64; self.rejects('pilot artifact hash')
    def test_factual_progress_cannot_be_inferred_from_target_count(self):
        self.plan.pop('factual_progress'); self.rejects('deficits mismatch')
    def test_rehashed_factual_claims_must_match_underlying_dossiers(self):
        matrix=json.loads((V.ROOT/self.plan['factual_progress']['path']).read_bytes())
        def eligibility(row):
            row['individually_eligible']=False
            row['states']['review']={'status':'pending','receipts':[]}
            row['states']['individual_eligibility']={'eligible':False,'blockers':['review_not_verified']}
        mutations=[lambda r:r.update(complex=True),lambda r:r.update(family='Go'),
                   lambda r:r.update(source='l5_real_dossier'),lambda r:r.update(historical=False),
                   lambda r:r.update(multi_module=False),eligibility]
        # Rehash the manipulated report/plan together; the verifier must still
        # reject them by recomputing actual retained dossier evidence.
        spec=importlib.util.spec_from_file_location('test_c02_summary',V.ROOT/'eval/scripts/verify_c02.py')
        c02=importlib.util.module_from_spec(spec);spec.loader.exec_module(c02)
        for change in mutations:
            altered=copy.deepcopy(matrix);change(altered['tasks'][0])
            altered['summary']=c02.summarize(altered['tasks'])
            with self.subTest(mutation=change),tempfile.TemporaryDirectory(dir=V.ROOT/'eval/qualification') as temp:
                path=Path(temp)/'matrix.json';raw=json.dumps(altered).encode();path.write_bytes(raw)
                plan=copy.deepcopy(self.plan)
                plan['factual_progress']={'path':path.relative_to(V.ROOT).as_posix(),'sha256':hashlib.sha256(raw).hexdigest()}
                plan['conditional_deficits']=altered['summary']['conditional_projection']
                plan['new_dossiers']['completed']=altered['summary']['new_dossiers_individually_eligible']
                with self.assertRaisesRegex(ValueError,'differs from recomputed dossier evidence'):
                    V.validate(plan)
    def test_pending_controlled_behavior_cannot_be_promoted_by_rehashed_counts(self):
        matrix=json.loads((V.ROOT/self.plan['factual_progress']['path']).read_bytes())
        row=next(r for r in matrix['tasks'] if r['family']=='Python' and r['source']=='l5_real_dossier')
        # A verified Rust receipt is never a proof for the controlled Python
        # task, including after the real Python proof has become available.
        rust_behavior=copy.deepcopy(next(r for r in matrix['tasks'] if r['id']=='L5-Rust-RA-23422')['states']['behavior'])
        row['states']['behavior']=rust_behavior
        row['states']['individual_eligibility']={'eligible':True,'blockers':[]}
        row['individually_eligible']=True
        spec=importlib.util.spec_from_file_location('test_controlled_summary',V.ROOT/'eval/scripts/verify_c02.py')
        c02=importlib.util.module_from_spec(spec);spec.loader.exec_module(c02)
        matrix['summary']=c02.summarize(matrix['tasks'])
        with tempfile.TemporaryDirectory(dir=V.ROOT/'eval/qualification') as temp:
            path=Path(temp)/'matrix.json';raw=json.dumps(matrix).encode();path.write_bytes(raw)
            plan=copy.deepcopy(self.plan)
            plan['factual_progress']={'path':path.relative_to(V.ROOT).as_posix(),'sha256':hashlib.sha256(raw).hexdigest()}
            plan['conditional_deficits']=matrix['summary']['conditional_projection']
            plan['new_dossiers']['completed']=matrix['summary']['new_dossiers_individually_eligible']
            with self.assertRaisesRegex(ValueError,'differs from recomputed dossier evidence'):
                V.validate(plan)

if __name__=='__main__': unittest.main()
