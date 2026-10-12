"""Data-only counterproofs for independently frozen C03-B state descriptors."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import prepare_state_events as p


class StatePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = {family: p.compose(family) for family in p.SPECS}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.compose_patch = patch.object(p, "compose", side_effect=lambda family: copy.deepcopy(self.cache[family]))
        self.compose_patch.start()
        self.addCleanup(self.compose_patch.stop)
        p.prepare(self.directory)

    def mutate(self, family, name, change):
        path = self.directory / family / name
        value = json.loads(path.read_text())
        change(value)
        path.write_bytes(p.encoded(value))

    def test_complete_independent_preparation(self):
        result = p.verify(self.directory)
        self.assertEqual(result["prepared_required_events"], 4)
        self.assertEqual(result["executed_required_events"], 0)
        self.assertEqual(result["individual_eligibility_delta"], 0)
        descriptors = [json.loads((self.directory / f / "descriptor.json").read_text()) for f in p.SPECS]
        self.assertEqual(len({d["change_lineage"] for d in descriptors}), 4)
        self.assertTrue(all(not d["derived_from"] and not d["complex"] for d in descriptors))

    def test_required_event_cannot_be_supplemental(self):
        self.mutate("rust", "descriptor.json", lambda d: d.update(event_role="supplemental"))
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_relabelling_case_is_rejected(self):
        self.mutate("rust", "descriptor.json", lambda d: d.update(task_id="L5-Rust-RA-23422"))
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_cold_b_cannot_be_a(self):
        shutil.copyfile(self.directory / "rust/b.json", self.directory / "rust/a.json")
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_executed_flag_is_not_preparation(self):
        self.mutate("go", "descriptor.json", lambda d: d.update(executed=True))
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_global_admission_flag_is_rejected(self):
        self.mutate("python", "descriptor.json", lambda d: d.update(admitted=True))
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_missing_parse_requirement_is_rejected(self):
        self.mutate("rust", "descriptor.json", lambda d: d.pop("parsing_requirement"))
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_removed_unknown_field_is_rejected(self):
        self.mutate("rust", "oracle.json", lambda d: d["answers"].pop("no_such_random_helper"))
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_stale_result_relabel_is_rejected(self):
        self.mutate("js", "oracle.json", lambda d: d["answers"]["restored-source"].update(b=d["answers"]["restored-source"]["a"]))
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_rehashed_oracle_does_not_authorize_changed_labels(self):
        self.mutate("rust", "oracle.json", lambda d: d["answers"]["seed"].update(b={"state": "unknown", "target": None}))
        changed = (self.directory / "rust/oracle.json").read_bytes()
        self.mutate("rust", "descriptor.json", lambda d: d["artifacts"]["oracle.json"].update(sha256=p.sha(changed), bytes=len(changed)))
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_changed_archive_is_rejected_before_tar_parsing(self):
        fake = self.directory / "changed-upstream.tar.gz"
        fake.write_bytes(b"different source archive")
        spec = {**p.SPECS["rust"], "archive": str(fake)}
        with self.assertRaisesRegex(ValueError, "pinned upstream archive changed"):
            p.source_bytes(spec)

    def test_missing_artifact_is_rejected(self):
        (self.directory / "go/b.json").unlink()
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_extra_source_is_rejected(self):
        (self.directory / "go/extra.go").write_text("package util")
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_extra_family_is_rejected(self):
        (self.directory / "other-family").mkdir()
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_family_directory_symlink_is_rejected(self):
        actual = self.directory / "rust"
        relocated = self.directory.parent / (self.directory.name + "-relocated-rust")
        shutil.move(actual, relocated)
        self.addCleanup(shutil.rmtree, relocated)
        actual.symlink_to(relocated, target_is_directory=True)
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_symlink_is_rejected(self):
        target = self.directory / "go/a.json"
        target.unlink()
        target.symlink_to(self.directory / "go/b.json")
        with self.assertRaises(ValueError): p.verify(self.directory)

    def test_prepare_refuses_to_rewrite_frozen_oracle(self):
        self.mutate("python", "oracle.json", lambda d: d.update(labels_frozen_before_results=False))
        with self.assertRaises(ValueError): p.prepare(self.directory)

    def test_same_bytes_and_same_config_not_an_event(self):
        for family, artifacts in self.cache.items():
            a, b = (json.loads(artifacts[x]) for x in ("a.json", "b.json"))
            self.assertNotEqual(a, b, family)
            if family == "rust":
                self.assertEqual(a["files"], b["files"])
                self.assertNotEqual(a["edition"], b["edition"])
            else:
                self.assertEqual(set(b["files"]) - set(a["files"]), {p.SPECS[family]["paths"][1]})


if __name__ == "__main__":
    unittest.main()
