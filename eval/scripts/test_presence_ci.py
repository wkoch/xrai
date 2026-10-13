"""CI metadata/ZIP envelope negatives; illustrative envelopes are not native proof."""
import io
import json
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

import reconcile_presence_ci as c


def envelopes():
    run_id, head, artifact_id = 101, "a" * 40, 202
    run = {"id": run_id, "head_sha": head, "head_branch": "main", "run_attempt": 1,
           "path": c.WORKFLOW, "event": "workflow_dispatch", "status": "completed",
           "conclusion": "success", "repository": {"full_name": c.REPOSITORY},
           "html_url": f"https://github.com/{c.REPOSITORY}/actions/runs/{run_id}"}
    job = {"id": 303, "name": c.JOB, "run_id": run_id, "head_sha": head, "run_attempt": 1,
           "started_at": "2026-10-12T21:00:00Z", "completed_at": "2026-10-12T21:02:00Z",
           "status": "completed", "conclusion": "success", "labels": ["ubuntu-24.04"],
           "html_url": f"https://github.com/{c.REPOSITORY}/actions/runs/{run_id}/job/303",
           "steps": [{"name": name, "number": i + 1, "status": "completed", "conclusion": "success",
                      "started_at": "2026-10-12T21:01:00Z", "completed_at": "2026-10-12T21:01:01Z"}
                     for i, name in enumerate(c.REQUIRED_STEP_ORDER)]}
    artifact = {"id": artifact_id, "name": c.ARTIFACT, "expired": False, "digest": "sha256:" + "0" * 64,
                "created_at": "2026-10-12T21:01:01Z",
                "size_in_bytes": 100, "workflow_run": {"id": run_id, "head_sha": head, "head_branch": "main"},
                "archive_download_url": f"https://api.github.com/repos/{c.REPOSITORY}/actions/artifacts/{artifact_id}/zip"}
    return run, {"total_count": 1, "jobs": [job]}, {"total_count": 1, "artifacts": [artifact]}


def bundle(extra=()):
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(c.BUNDLE_FILES): archive.writestr(name, b"{}\n")
            archive.writestr("events/js/receipt.json", b"illustrative not native proof\n")
            for name, raw in extra: archive.writestr(name, raw)
    return buffer.getvalue()


class MetadataEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.run, self.jobs, self.artifacts = envelopes()

    def checked(self):
        return c.metadata(self.run, self.jobs, self.artifacts, 101, "a" * 40, 202)

    def rejected(self):
        with self.assertRaises(ValueError): self.checked()

    def test_illustrative_envelope_structure_only(self):
        self.assertEqual(self.checked()[0]["id"], 303)

    def test_failed_job_rejected(self):
        self.jobs["jobs"][0]["conclusion"] = "failure"; self.rejected()

    def test_failed_required_step_rejected(self):
        self.jobs["jobs"][0]["steps"][0]["conclusion"] = "failure"; self.rejected()

    def test_missing_required_step_rejected(self):
        self.jobs["jobs"][0]["steps"].pop(); self.rejected()

    def test_renamed_workflow_rejected(self):
        self.run["path"] = ".github/workflows/ci.yml"; self.rejected()

    def test_unknown_extra_step_rejected(self):
        self.jobs["jobs"][0]["steps"].append({"name": "Different execution", "number": 99, "status": "completed", "conclusion": "success"}); self.rejected()

    def test_changed_branch_rejected(self):
        self.run["head_branch"] = "other"; self.rejected()

    def test_changed_repository_rejected(self):
        self.run["repository"]["full_name"] = "example/xrai"; self.rejected()

    def test_changed_native_head_rejected(self):
        self.jobs["jobs"][0]["head_sha"] = "b" * 40; self.rejected()

    def test_wrong_trigger_rejected(self):
        self.run["event"] = "push"; self.rejected()

    def test_wrong_attempt_rejected(self):
        self.run["run_attempt"] = 2; self.rejected()

    def test_boolean_attempt_rejected(self):
        self.run["run_attempt"] = True; self.rejected()

    def test_reordered_required_steps_rejected(self):
        steps = self.jobs["jobs"][0]["steps"]
        steps[0]["name"], steps[1]["name"] = steps[1]["name"], steps[0]["name"]
        self.rejected()

    def test_job_attempt_missing_rejected(self):
        self.jobs["jobs"][0].pop("run_attempt")
        with self.assertRaises(KeyError): self.checked()

    def test_paginated_job_envelope_rejected(self):
        self.jobs["total_count"] = 2; self.rejected()

    def test_wrong_runner_rejected(self):
        self.jobs["jobs"][0]["labels"] = ["macos-15"]; self.rejected()

    def test_expired_artifact_rejected(self):
        self.artifacts["artifacts"][0]["expired"] = True; self.rejected()

    def test_artifact_from_other_run_rejected(self):
        self.artifacts["artifacts"][0]["workflow_run"]["id"] = 999; self.rejected()

    def test_artifact_from_previous_attempt_time_rejected(self):
        self.artifacts["artifacts"][0]["created_at"] = "2026-10-12T20:59:59Z"
        self.rejected()

    def test_other_explicit_artifact_rejected(self):
        self.artifacts["artifacts"][0]["id"] = 999; self.rejected()

    def test_invalid_digest_rejected(self):
        self.artifacts["artifacts"][0]["digest"] = "sha256:invented"; self.rejected()


class ArchiveEnvelopeTests(unittest.TestCase):
    def test_illustrative_archive_only_checks_safe_container(self):
        members = c.zip_members(bundle())
        self.assertEqual(set(members), c.BUNDLE_FILES | {"events/js/receipt.json"})
        # This intentionally incomplete event is never passed as native proof.

    def test_duplicate_member_rejected(self):
        with self.assertRaises(ValueError): c.zip_members(bundle([("batch.json", b"duplicate")]))

    def test_traversal_rejected(self):
        with self.assertRaises(ValueError): c.zip_members(bundle([("../escape", b"outside")]))

    def test_absolute_member_rejected(self):
        with self.assertRaises(ValueError): c.zip_members(bundle([("/escape", b"outside")]))

    def test_backslash_alias_rejected(self):
        with self.assertRaises(ValueError): c.zip_members(bundle([("event\\alias", b"outside")]))

    def test_unknown_extra_file_rejected(self):
        with self.assertRaises(ValueError): c.zip_members(bundle([("extra", b"outside")]))

    def test_symlink_member_rejected(self):
        info = zipfile.ZipInfo("events/js/linked")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(ValueError): c.zip_members(bundle([(info, b"../../escape")]))

    def test_zip_member_size_bound(self):
        with patch.object(c, "MAX_MEMBER_BYTES", 4):
            with self.assertRaises(ValueError): c.zip_members(bundle())

    def test_zip_total_size_bound(self):
        with patch.object(c, "MAX_TOTAL_BYTES", 5):
            with self.assertRaises(ValueError): c.zip_members(bundle())

    def test_zip_count_bound(self):
        with patch.object(c, "MAX_MEMBERS", 2):
            with self.assertRaises(ValueError): c.zip_members(bundle())

    def test_extra_empty_directory_rejected(self):
        with self.assertRaises(ValueError): c.zip_members(bundle([("unexpected/", b"")]))

    def test_file_directory_collision_rejected(self):
        with self.assertRaises(ValueError): c.zip_members(bundle([("events/js/receipt.json/nested", b"nested")]))

    def test_export_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "link").symlink_to("/does-not-exist")
            with self.assertRaises(ValueError): c.directory_members(directory)

    def test_export_extra_empty_directory_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "empty").mkdir()
            with self.assertRaises(ValueError): c.directory_members(directory)

    def test_private_extraction_preserves_all_bytes(self):
        members = c.zip_members(bundle())
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "export"
            c.safe_export(members, destination)
            self.assertEqual(c.directory_members(destination), members)

    def test_reconciliation_rejects_api_digest_mismatch_before_native_validation(self):
        run, jobs, artifacts = envelopes()
        raw = bundle()
        artifacts["artifacts"][0]["size_in_bytes"] = len(raw)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name, value in [("run.json", run), ("jobs.json", jobs), ("artifacts.json", artifacts)]:
                (directory / name).write_text(json.dumps(value))
            (directory / "original.zip").write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "original ZIP digest"):
                c.reconcile(directory, 101, "a" * 40, 202)


if __name__ == "__main__": unittest.main()
