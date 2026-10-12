"""Counterchecks on the frozen public lineage and evaluator separation."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('real_rust_capture', ROOT / 'eval/scripts/collect_real_rust.py')
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)


class RustCapture(unittest.TestCase):
    def reject(self, mutate):
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory) / 'case'
            shutil.copytree(V.CASE, case)
            mutate(case)
            with patch.object(V, 'CASE', case), self.assertRaises(ValueError):
                V.verify()

    def test_public_lineage_cannot_be_relabelled(self):
        def change(case):
            path = case / 'case.json'
            data = json.loads(path.read_text())
            data['baseline']['commit'] = '0' * 40
            path.write_text(json.dumps(data))
        self.reject(change)

    def test_reference_patch_is_bound_to_capture(self):
        self.reject(lambda case: (case / 'oracles/reference.patch').write_text('forged patch'))

    def test_hidden_probe_cannot_edit_production_even_with_updated_digest(self):
        def change(case):
            probe = case / 'oracles/non_exhaustive_let.rs'
            probe.write_bytes(b'fn forged() {}\n' + probe.read_bytes())
            path = case / 'oracles/probe-plan.json'
            plan = json.loads(path.read_text())
            plan['hidden_test']['sha256'] = V.sha(probe.read_bytes())
            path.write_text(json.dumps(plan))
        self.reject(change)


if __name__ == '__main__':
    unittest.main()
