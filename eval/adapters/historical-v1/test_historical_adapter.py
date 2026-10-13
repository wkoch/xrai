"""Historical provenance remains strict while the current architectural plan can move."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('historical_adapter',HERE/'verify.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class HistoricalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.members=m.capture();cls.provenance=m.provenance()
    def root_copy(self,root):
        for path,raw in self.members.items():
            target=Path(root)/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        for path in (m.PROVENANCE,m.SNAPSHOT):
            target=Path(root)/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(m.owned(m.ROOT,path))
        (Path(root)/m.PLAN).write_bytes(m.owned(m.ROOT,m.PLAN))
    def test_original_plan_hash_matches_original_receipt(self):
        receipt=m.decode(self.members['docs/relatorios/logs/L5-C04/adapter/receipt.json'])
        self.assertEqual(m.sha(self.members[m.PLAN]),receipt['source_hashes'][m.PLAN]);self.assertEqual(receipt['source_hashes'][m.PLAN],m.PLAN_SHA)
    def test_isolated_original_full_result_recomposed(self):
        result=m.run_capsule(self.members)
        self.assertEqual(len(result['fixtures']),7);self.assertEqual(result['comparator_refusals'],8)
        self.assertEqual(m.canonical(result),m.canonical(m.decode(self.members[m.RESULT])))
    def test_current_plan_is_not_historical_plan_binding(self):
        result=m.verify();self.assertFalse(result['current_plan_binding_claimed'])
        self.assertNotEqual(result['current_plan_sha256'],result['historical_plan_sha256'])
    def test_old_direct_entry_still_refuses_current_plan(self):
        process=subprocess.run([sys.executable,'-I','-B',str(m.ROOT/m.VERIFIER)],capture_output=True,timeout=30)
        self.assertEqual(process.returncode,1);self.assertIn(b'current own source bytes changed since receipt',process.stderr)
    def test_current_plan_can_move_without_rewriting_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            self.root_copy(d);(Path(d)/m.PLAN).write_bytes(b'legitimate new architect plan\n')
            self.assertTrue(m.verify(d)['verified'])
    def test_original_plan_snapshot_altered_refused(self):
        with tempfile.TemporaryDirectory() as d:
            self.root_copy(d);(Path(d)/m.SNAPSHOT).write_bytes(b'changed original snapshot\n')
            with self.assertRaises(ValueError):m.capture(d)
    def test_current_own_code_altered_refused(self):
        with tempfile.TemporaryDirectory() as d:
            self.root_copy(d);(Path(d)/'crates/xrai-eval/harness/agent_adapter_protocol.py').write_bytes(b'raise RuntimeError("injected")\n')
            with self.assertRaises(ValueError):m.capture(d)
    def test_current_transitive_code_altered_refused(self):
        with tempfile.TemporaryDirectory() as d:
            self.root_copy(d);(Path(d)/'eval/scripts/materialize_task.py').write_bytes(b'raise RuntimeError("injected support")\n')
            with self.assertRaises(ValueError):m.capture(d)
    def test_original_receipt_altered_refused(self):
        with tempfile.TemporaryDirectory() as d:
            self.root_copy(d);p=Path(d)/'docs/relatorios/logs/L5-C04/adapter/receipt.json';value=m.decode(p.read_bytes());value['agent_runs']=1;p.write_bytes(m.canonical(value)+b'\n')
            with self.assertRaises(ValueError):m.capture(d)
    def test_provenance_cannot_authorize_substituted_code(self):
        with tempfile.TemporaryDirectory() as d:
            self.root_copy(d);p=Path(d)/m.PROVENANCE;value=m.decode(p.read_bytes());value['closure']['crates/xrai-eval/harness/agent_adapter_protocol.py']['sha256']='0'*64;p.write_bytes(m.canonical(value))
            with self.assertRaises(ValueError):m.capture(d)
    def test_capsule_missing_extra_or_alias_refused(self):
        for action in ('missing','extra','alias'):
            members=copy.deepcopy(self.members)
            if action=='missing':members.pop(m.VERIFIER)
            elif action=='extra':members['unknown.py']=b'raise RuntimeError("injected")'
            else:members['eval/adapters/experimental-v1/../experimental-v1/verify.py']=members.pop(m.VERIFIER)
            with self.assertRaises(ValueError):m.run_capsule(members)
    def test_capsule_arbitrary_substituted_code_refused_before_execution(self):
        members=copy.deepcopy(self.members);members[m.VERIFIER]=b'raise RuntimeError("not allowed source")\n'
        with self.assertRaises(ValueError):m.run_capsule(members)
    def test_capsule_snapshot_or_fixture_altered_refused(self):
        for path in (m.PLAN,'eval/adapters/experimental-v1/completed-bm25.jsonl'):
            members=copy.deepcopy(self.members);members[path]+=b'changed'
            with self.assertRaises(ValueError):m.run_capsule(members)
    def test_symlink_and_oversize_sources_refused(self):
        with tempfile.TemporaryDirectory() as d:
            self.root_copy(d);p=Path(d)/m.SNAPSHOT;p.unlink();p.symlink_to(m.HERE/'original-PLANO-DE-IMPLEMENTACAO.md')
            with self.assertRaises(ValueError):m.capture(d)
            p.unlink();p.write_bytes(b'x'*(m.MAX_MEMBER+1))
            with self.assertRaises(ValueError):m.capture(d)
    def test_verification_keeps_capture_and_sources_identical(self):
        before=m.capture();m.verify();self.assertEqual(before,m.capture())
    def test_duplicate_and_nonfinite_json_refused(self):
        for raw in (b'{"a":1,"a":1}',b'[NaN]',b'[Infinity]'):
            with self.assertRaises(ValueError):m.decode(raw)


if __name__=='__main__':unittest.main()
