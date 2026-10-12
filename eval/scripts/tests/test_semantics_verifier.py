import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("semantic_verifier", ROOT / "eval/scripts/verify_semantics.py")
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)
MATRIX = ROOT / "eval/semantics/rust-r1-r2.json"
RECEIPT = ROOT / "docs/relatorios/logs/L4/semantics/rust-r1-r2.json"


class SemanticVerifierTests(unittest.TestCase):
    def reject(self, mutate):
        data = json.loads(RECEIPT.read_text())
        mutate(data)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "changed.json"
            output.write_text(json.dumps(data))
            with self.assertRaises((AssertionError, UnicodeDecodeError, KeyError)):
                VERIFIER.verify(MATRIX, output)

    def test_original_receipt(self):
        result = VERIFIER.verify(MATRIX, RECEIPT)
        self.assertEqual(result["resolvable_correct"], 18)
        self.assertEqual(result["false_promotions"], 0)

    def test_cross_snapshot_evidence(self):
        self.reject(lambda d: d["rows"][0]["result"]["evidence"][0].update(snapshot_id="snap_wrong"))

    def test_changed_source_hash(self):
        self.reject(lambda d: d["rows"][0]["result"]["evidence"][0].update(source_hash="0" * 64))

    def test_out_of_bounds(self):
        self.reject(lambda d: d["rows"][0]["result"]["evidence"][0].update(end=10**9))

    def test_forged_summary(self):
        self.reject(lambda d: d.update(resolvable_correct=17))

    def test_unknown_promoted_to_fact(self):
        def mutate(d):
            row = d["rows"][2]
            row["result"]["state"] = "resolved"
            row["result"]["target_id"] = row["snapshot"]["declarations"][0]["id"]
        self.reject(mutate)

    def test_configuration_mismatch(self):
        self.reject(lambda d: d["rows"][0]["snapshot"]["input"]["configuration"].update(feature="host-inherited"))


if __name__ == "__main__":
    unittest.main()
