"""Independent C03 receipt counterproofs. Never launch or import upstream code.

Real-export tests run only with XRAI_STATE_EVENT_PROOF or --proof-dir. The
small local records below exercise byte/frame validation, not native execution.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import verify_state_event as v

PROOF = os.environ.get("XRAI_STATE_EVENT_PROOF")


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def edit_json(path, change):
    value = v.decode(path.read_bytes())
    change(value)
    path.write_bytes(json_bytes(value))


def transcript(directory):
    return [v.decode(line) for line in (directory / "transcript.jsonl").read_bytes().splitlines()]


def rewrite_responses(directory, predicate, change):
    """Alter native response and all raw-frame SHA/stdout bindings consistently."""
    rows = transcript(directory)
    changed = 0
    for index, row in enumerate(rows):
        response = v.decode(base64.b64decode(row["response_base64"], validate=True))
        if predicate(index, response):
            change(response)
            raw = json_bytes(response)
            row["response_base64"] = base64.b64encode(raw).decode()
            row["response_sha256"] = v.sha(raw)
            changed += 1
    if not changed:
        raise AssertionError("counterproof did not reach an actual retained response")
    (directory / "transcript.jsonl").write_bytes(b"".join(json_bytes(row) for row in rows))
    (directory / "stdout.jsonl").write_bytes(b"".join(base64.b64decode(row["response_base64"]) for row in rows))
    final = v.decode(base64.b64decode(rows[-1]["response_base64"]))
    edit_json(directory / "process.json", lambda process: process.update(closed_response=final))


def snapshot_record():
    """Own illustrative record; never represented as a native snapshot proof."""
    input_value = {"files": {"source.rs": "pub fn target() {}\n"}, "root": "source.rs",
                   "edition": "2024", "configuration": {}, "rules": "rust-r3-v1"}
    fp = v.native_hash(v.rust_json([input_value["edition"], {}]))
    producer = "illustrative-local-record-not-native-proof"
    snapshot_id = "snap_" + v.native_hash(v.rust_json([input_value, producer]))
    evidence = {"file_id": "fi_" + v.native_hash(b"source.rs"), "snapshot_id": snapshot_id,
                "source_hash": v.native_hash(input_value["files"]["source.rs"].encode()),
                "path": "source.rs", "start": 0, "end": 18}
    snapshot = {"snapshot_id": snapshot_id, "configuration_id": "cfg_" + fp,
                "configuration_fingerprint": fp, "producer_fingerprint": producer,
                "input": input_value, "declarations": [{"id": "own-declaration", "evidence": evidence}],
                "imports": [], "modules": {}, "gaps": [], "references": [], "scopes": [],
                "coverage": {"source.rs": "illustrative"}, "bindings": [], "conditions": []}
    return input_value, snapshot


class DataOnlyStructureTests(unittest.TestCase):
    def test_duplicate_json_fields_rejected(self):
        with self.assertRaises(ValueError): v.decode(b'{"state":"unknown","state":"resolved"}')

    def test_illustrative_record_only_validates_structure(self):
        inputs, snapshot = snapshot_record()
        v.validate_snapshot(snapshot, inputs)

    def test_collection_type_must_be_complete(self):
        inputs, snapshot = snapshot_record()
        snapshot["coverage"] = []
        with self.assertRaises(ValueError): v.validate_snapshot(snapshot, inputs)

    def test_missing_diagnostics_container_rejected(self):
        inputs, snapshot = snapshot_record()
        del snapshot["gaps"]
        with self.assertRaises(ValueError): v.validate_snapshot(snapshot, inputs)

    def test_configuration_fingerprint_recomputed(self):
        inputs, snapshot = snapshot_record()
        snapshot["configuration_fingerprint"] = "forged"
        with self.assertRaises(ValueError): v.validate_snapshot(snapshot, inputs)

    def test_evidence_wrong_source_hash_rejected(self):
        inputs, snapshot = snapshot_record()
        snapshot["declarations"][0]["evidence"]["source_hash"] = "0" * 64
        with self.assertRaises(ValueError): v.validate_snapshot(snapshot, inputs)

    def test_evidence_boolean_span_rejected(self):
        inputs, snapshot = snapshot_record()
        snapshot["declarations"][0]["evidence"]["start"] = True
        with self.assertRaises(ValueError): v.validate_snapshot(snapshot, inputs)

    def test_unproven_resolved_target_rejected(self):
        inputs, snapshot = snapshot_record()
        resolution = {"state": "resolved", "target_id": "nonexistent", "candidate_ids": [],
                      "method": "semantic_resolution", "dependencies": [snapshot["snapshot_id"]],
                      "evidence": [snapshot["declarations"][0]["evidence"]]}
        with self.assertRaises(ValueError): v.validate_snapshot(snapshot, inputs, resolution)

    def test_unknown_cannot_promote_target(self):
        inputs, snapshot = snapshot_record()
        resolution = {"state": "unknown", "target_id": "own-declaration", "candidate_ids": [],
                      "method": "semantic_resolution", "dependencies": [snapshot["snapshot_id"]]}
        with self.assertRaises(ValueError): v.validate_snapshot(snapshot, inputs, resolution)


@unittest.skipUnless(PROOF, "real retained event export not supplied; no native execution claim")
class RealExportCounterproofs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = Path(PROOF)
        if not cls.proof.is_dir():
            raise ValueError("declared real export path does not exist")
        cls.verified = v.verify(cls.proof)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xrai-state-receipt-counterproof-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "export"
        shutil.copytree(self.proof, self.directory)

    def rejected(self):
        with self.assertRaises((ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError)):
            v.verify(self.directory)

    def incremental(self, predicate, change):
        rewrite_responses(self.directory / "incremental", predicate, change)

    def test_positive_recompute_exact_receipt(self):
        recomputed = v.verify(self.directory)
        self.assertEqual(recomputed, self.verified)
        report = self.directory / "verification.json"
        if report.exists(): self.assertEqual(recomputed, v.decode(report.read_bytes()))

    def test_cold_b_is_not_warmed_a(self):
        edit_json(self.directory / "inputs/a.json", lambda a: a.update(v.decode((self.directory / "inputs/b.json").read_bytes())))
        self.rejected()

    def test_changed_pid_inside_live_session_rejected(self):
        self.incremental(lambda i, r: i == 2, lambda r: r["response"].update(pid=r["response"]["pid"] + 1))
        self.rejected()

    def test_changed_index_session_rejected(self):
        self.incremental(lambda i, r: i == 2, lambda r: r["response"].update(session_id="0" * 64))
        self.rejected()

    def test_restarted_generation_rejected(self):
        self.incremental(lambda i, r: r.get("status") == "ok" and r["response"]["generation"] == 2,
                         lambda r: r["response"].update(generation=1))
        self.rejected()

    def test_extra_export_path_rejected(self):
        (self.directory / "unexpected-source.rs").write_bytes(b"untracked bytes")
        self.rejected()

    def test_sequence_relabel_rejected(self):
        path = self.directory / "incremental/transcript.jsonl"
        rows = transcript(path.parent)
        rows[2]["sequence"] = 900
        path.write_bytes(b"".join(json_bytes(r) for r in rows))
        self.rejected()

    def test_wrong_revision_cannot_be_accepted(self):
        self.incremental(lambda i, r: r.get("status") == "error",
                         lambda r: r.update(status="ok", diagnostic="accepted despite stale revision"))
        self.rejected()

    def test_supplemental_event_cannot_fill_required_quota(self):
        edit_json(self.directory / "receipt.json", lambda r: r.update(event_role="supplemental"))
        self.rejected()

    def test_case_swap_rejected(self):
        edit_json(self.directory / "receipt.json", lambda r: r.update(task_id="L5-Rust-RA-23422"))
        self.rejected()

    def test_native_binary_byte_swap_rejected(self):
        path = self.directory / "native-bin/semantics-session"
        raw = path.read_bytes()
        # copytree preserves the retained binary's 0500 mode. Make only this
        # disposable counterproof clone writable; never alter original export.
        path.chmod(0o600)
        path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        self.rejected()

    def test_configuration_swap_with_input_rehash_rejected(self):
        path = self.directory / "inputs/b.json"
        edit_json(path, lambda b: b.update(edition="2021"))
        edit_json(self.directory / "receipt.json", lambda r: r["input_sha256"].update({"b.json": v.sha(path.read_bytes())}))
        self.rejected()

    def test_missing_coverage_with_frame_rehash_rejected(self):
        self.incremental(lambda i, r: r.get("status") == "ok" and r["response"]["operation"] == "snapshot" and
                         r["response"]["result"]["input"]["edition"] == "2024",
                         lambda r: r["response"]["result"].pop("coverage"))
        self.rejected()

    def test_missing_diagnostics_with_frame_rehash_rejected(self):
        self.incremental(lambda i, r: r.get("status") == "ok" and r["response"]["operation"] == "snapshot" and
                         r["response"]["result"]["input"]["edition"] == "2024",
                         lambda r: r["response"]["result"].pop("gaps"))
        self.rejected()

    def test_unknown_removed_with_frame_rehash_rejected(self):
        self.incremental(lambda i, r: r.get("status") == "ok" and r["response"]["operation"] == "query" and
                         r["response"]["generation"] == 2 and r["response"]["result"]["resolution"]["state"] == "unknown",
                         lambda r: r["response"]["result"]["resolution"].pop("reason"))
        self.rejected()

    def test_truncated_protocol_frame_rejected(self):
        path = self.directory / "incremental/transcript.jsonl"
        rows = transcript(path.parent)
        raw = base64.b64decode(rows[2]["response_base64"])
        shortened = raw[:-1]
        rows[2]["response_base64"] = base64.b64encode(shortened).decode()
        rows[2]["response_sha256"] = v.sha(shortened)
        path.write_bytes(b"".join(json_bytes(row) for row in rows))
        (path.parent / "stdout.jsonl").write_bytes(b"".join(base64.b64decode(row["response_base64"]) for row in rows))
        self.rejected()

    def test_self_asserted_verification_cannot_replace_proof(self):
        (self.directory / "verification.json").write_bytes(json_bytes({"verified": True, "required_event_executed": True}))
        edit_json(self.directory / "incremental/process.json", lambda p: p.update(wrapper_reaped=False))
        self.rejected()

    def test_self_asserted_admission_flag_rejected(self):
        edit_json(self.directory / "receipt.json", lambda r: r.update(admitted=True))
        self.rejected()

    def test_hash_report_cannot_hide_snapshot_divergence(self):
        self.incremental(lambda i, r: r.get("status") == "ok" and r["response"]["operation"] == "snapshot" and
                         r["response"]["result"]["input"]["edition"] == "2024",
                         lambda r: r["response"]["result"].update(gaps=[{"reason": "mutated-after-result"}]))
        (self.directory / "verification.json").write_bytes(json_bytes({"verified": True, "hashes_match": True}))
        self.rejected()

    def test_independent_rebuild_cannot_reuse_process_identity(self):
        left = v.decode((self.directory / "incremental/process.json").read_bytes())["pid"]
        edit_json(self.directory / "rebuild/process.json", lambda p: p.update(pid=left))
        self.rejected()

    def test_producer_source_hash_substitution_rejected(self):
        edit_json(self.directory / "receipt.json", lambda r: r["source_sha256"].update({"eval/scripts/verify_state_event.py": "0" * 64}))
        self.rejected()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--proof-dir")
    args, remaining = parser.parse_known_args()
    if args.proof_dir:
        PROOF = args.proof_dir
        RealExportCounterproofs.__unittest_skip__ = False
    unittest.main(argv=[sys.argv[0], *remaining])
