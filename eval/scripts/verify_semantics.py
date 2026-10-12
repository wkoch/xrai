#!/usr/bin/env python3
"""Independent source/identity/labels verifier for ADR025 development receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import blake3


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def digest(value):
    return blake3.blake3(value).hexdigest()


def verify(matrix_path, output_path):
    matrix = json.loads(Path(matrix_path).read_text())
    output = json.loads(Path(output_path).read_text())
    rows = output["rows"]
    assert len(rows) == len(matrix["cases"])
    assert len({r["id"] for r in rows}) == len(rows)
    correct = resolvable_correct = resolvable = false_promotions = 0
    for label, row in zip(matrix["cases"], rows, strict=True):
        assert label["id"] == row["id"]
        snapshot = row["snapshot"]
        inp = snapshot["input"]
        assert inp["files"] == label["files"]
        assert inp["edition"] == label["edition"]
        assert inp["configuration"] == label["configuration"]
        assert inp["rules"] == label["rules"]
        assert inp["root"] == label.get("root", "src/lib.rs")
        assert snapshot["snapshot_id"] == "snap_" + digest(canonical([inp, snapshot["producer_fingerprint"]]))
        assert snapshot["configuration_fingerprint"] == digest(canonical([inp["edition"], inp["configuration"]]))
        assert snapshot["configuration_id"] == "cfg_" + snapshot["configuration_fingerprint"]
        declarations = {d["id"]: d for d in snapshot["declarations"]}
        assert len(declarations) == len(snapshot["declarations"])
        for decl in declarations.values():
            ev = decl["evidence"]
            identity = f'{snapshot["snapshot_id"]}:{ev["path"]}:{ev["start"]}:{ev["end"]}:{decl["module"]}:{decl["namespace"]}:{decl["name"]}'
            assert decl["id"] == "sym_" + digest(identity.encode())
            assert inp["files"][ev["path"]].encode()[ev["start"]:ev["end"]].decode() == decl["name"]
        def traverse(value):
            if isinstance(value, dict):
                if {"snapshot_id", "path", "source_hash", "start", "end", "file_id"} <= value.keys():
                    assert value["snapshot_id"] == snapshot["snapshot_id"]
                    source = inp["files"][value["path"]].encode()
                    assert value["source_hash"] == digest(source)
                    assert value["file_id"] == "fi_" + digest(value["path"].encode())
                    assert 0 <= value["start"] <= value["end"] <= len(source)
                    source[:value["start"]].decode(); source[:value["end"]].decode()
                if {"state", "target_id", "candidate_ids", "method", "dependencies"} <= value.keys():
                    assert value["state"] in ("resolved", "candidate", "unknown", "external")
                    assert value["method"] == "semantic_resolution"
                    if value["state"] == "resolved":
                        assert value["target_id"] in declarations and not value["candidate_ids"]
                        assert value["evidence"] and value["dependencies"]
                    elif value["state"] == "candidate":
                        assert value["target_id"] is None and value["candidate_ids"]
                        assert all(i in declarations for i in value["candidate_ids"])
                    else:
                        assert value["target_id"] is None and not value["candidate_ids"]
                    assert all(snapshot["snapshot_id"] in dep for dep in value["dependencies"])
                for child in value.values(): traverse(child)
            elif isinstance(value, list):
                for child in value: traverse(child)
        traverse(snapshot); traverse(row["result"])
        result = row["result"]
        decl = declarations.get(result["target_id"])
        target = None if decl is None else f'{decl["evidence"]["path"]}:{decl["module"] + "::" if decl["module"] else ""}{decl["name"]}'
        okay = result["state"] == label["expected_state"] and target == label["expected_target"]
        assert row["correct"] == okay
        assert row["expected_state"] == label["expected_state"]
        assert row["expected_target"] == label["expected_target"]
        correct += okay
        resolvable += label["expected_state"] == "resolved"
        resolvable_correct += label["expected_state"] == "resolved" and okay
        false_promotions += result["state"] == "resolved" and not okay
    assert output["correct"] == correct == len(rows)
    assert output["cases"] == len(rows)
    assert output["resolvable"] == resolvable
    assert output["resolvable_correct"] == resolvable_correct
    assert output["false_promotions"] == false_promotions == 0
    if "source_archive" in matrix:
        archive = Path(matrix["source_archive"])
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == matrix["archive_sha256"]
        with tarfile.open(archive) as tar:
            for label in matrix["cases"]:
                for path, source in label["files"].items():
                    assert tar.extractfile(path).read() == source.encode()
            manifest = tar.extractfile(matrix["captured_edition_manifest"]).read()
            assert hashlib.sha256(manifest).hexdigest() == matrix["manifest_sha256"]
            assert b'edition = "2021"' in manifest
    return {"cases": len(rows), "resolvable": resolvable, "resolvable_correct": resolvable_correct, "correct": correct, "false_promotions": false_promotions}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix"); parser.add_argument("output")
    args = parser.parse_args()
    print(json.dumps(verify(args.matrix, args.output), sort_keys=True))
