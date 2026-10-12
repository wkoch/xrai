"""Data-only counterproofs against the actual retained GitHub exports."""
import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("new_corpus", HERE / "reconcile_new_corpus.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExportCounterproofs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / "exports"
        shutil.copytree(HERE / "ci-next-first", self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def reject_metadata(self, filename, edit):
        path = self.directory / filename
        value = json.loads(path.read_text())
        edit(value)
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            module.reconcile(self.directory)

    def test_wrong_code_commit(self):
        self.reject_metadata("run.json", lambda x: x.update(headSha="0" * 40))

    def test_wrong_run(self):
        self.reject_metadata("run.json", lambda x: x.update(databaseId=1))

    def test_failed_family_job(self):
        self.reject_metadata("run.json", lambda x: x["jobs"][0].update(conclusion="failure"))

    def test_duplicate_artifact(self):
        self.reject_metadata("artifacts.json", lambda x: x["artifacts"].__setitem__(0, copy.deepcopy(x["artifacts"][1])))

    def test_self_asserted_zip_digest(self):
        self.reject_metadata("artifacts.json", lambda x: x["artifacts"][0].update(digest="sha256:" + "0" * 64))

    def test_artifact_from_other_commit(self):
        self.reject_metadata("artifacts.json", lambda x: x["artifacts"][0]["workflow_run"].update(head_sha="0" * 40))

    def export_metadata(self):
        return next(a for a in json.loads((self.directory / "artifacts.json").read_text())["artifacts"] if a["name"] == "l5-real-python")

    def test_extra_extracted_file(self):
        (self.directory / "python" / "unrecorded.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "closure"):
            module.verify_export(self.directory, "python", self.export_metadata())

    def test_changed_report(self):
        (self.directory / "python" / "base" / "requirement-tests.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "differ"):
            module.verify_export(self.directory, "python", self.export_metadata())

    def test_missing_report(self):
        (self.directory / "python" / "base" / "requirement-tests.json").unlink()
        with self.assertRaisesRegex(ValueError, "differ"):
            module.verify_export(self.directory, "python", self.export_metadata())

    def test_zip_corrupted(self):
        path = self.directory / "l5-real-python.zip"
        path.write_bytes(path.read_bytes() + b"untrusted")
        with self.assertRaisesRegex(ValueError, "integrity"):
            module.verify_export(self.directory, "python", self.export_metadata())

    def test_symbolic_link_export(self):
        (self.directory / "python" / "unrecorded").symlink_to(self.directory / "run.json")
        with self.assertRaisesRegex(ValueError, "nonregular"):
            module.verify_export(self.directory, "python", self.export_metadata())

    def test_original_zip_closure(self):
        result = module.verify_export(self.directory, "python", self.export_metadata())
        self.assertEqual(result["files"], 13)


if __name__ == "__main__":
    unittest.main()
