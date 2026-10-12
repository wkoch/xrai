#!/usr/bin/env python3
"""Independent source/identity/labels verifier for ADR025 development receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import re
import blake3


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def digest(value):
    return blake3.blake3(value).hexdigest()


def evaluate_cfg(text, config):
    text = text.strip()
    if "(" in text:
        op, rest = text.split("(", 1)
        if not rest.endswith(")"): return None
        body = rest[:-1]; parts=[]; depth=0; quoted=False; start=0
        for index, char in enumerate(body):
            if char == '"': quoted = not quoted
            elif not quoted and char == "(": depth += 1
            elif not quoted and char == ")": depth -= 1
            elif not quoted and char == "," and depth == 0:
                parts.append(body[start:index].strip()); start=index+1
            if depth < 0: return None
        if quoted or depth: return None
        if body[start:].strip(): parts.append(body[start:].strip())
        values=[evaluate_cfg(part,config) for part in parts]
        if op.strip()=="not" and len(values)==1: return None if values[0] is None else not values[0]
        if op.strip()=="all": return False if False in values else True if all(v is True for v in values) else None
        if op.strip()=="any": return True if True in values else False if all(v is False for v in values) else None
        return None
    match=re.fullmatch(r'([A-Za-z_][A-Za-z_0-9]*)\s*=\s*"([^"\\]*)"', text)
    if match: family,value=match.groups(); key=family+":"+value
    elif re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',text): family=key=text
    else: return None
    result=config.get(key)
    if result=="known:true": return True
    if result=="known:false": return False
    if result is None and config.get("closed:"+family)=="true": return False
    return None


def verify_snapshot(snapshot):
    inp = snapshot["input"]
    assert inp["rules"] in ("rust-r1-r2-v1", "rust-r3-v1")
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
    traverse(snapshot)
    scopes = snapshot["scopes"]
    assert [s["local_id"] for s in scopes] == list(range(len(scopes)))
    for scope in scopes:
        if "parent_scope_local_id" in scope:
            parent = scopes[scope["parent_scope_local_id"]]
            assert parent["local_id"] < scope["local_id"]
            assert parent["evidence"]["path"] == scope["evidence"]["path"]
            assert parent["evidence"]["start"] <= scope["evidence"]["start"] <= scope["evidence"]["end"] <= parent["evidence"]["end"]
    for binding in snapshot.get("bindings", []):
        assert inp["rules"] == "rust-r3-v1"
        assert binding["kind"] in ("let", "parameter")
        ev = binding["evidence"]
        source = inp["files"][ev["path"]].encode()
        assert source[ev["start"]:ev["end"]].decode().strip().removeprefix("mut ").strip() == binding["name"]
        scope = scopes[binding["scope_local_id"]]
        assert scope["evidence"]["path"] == ev["path"]
        assert binding["parent_scope_local_id"] == scope.get("parent_scope_local_id")
        assert scope["evidence"]["start"] <= binding["visible_start"] <= binding["visible_end"] <= scope["evidence"]["end"]
        if binding["kind"] == "let":
            assert binding["visible_start"] > ev["end"]
            if binding["initializer"] is not None:
                assert binding["initializer"]["end"] <= binding["visible_start"]
        if binding["function_path"] is not None:
            assert binding["kind"] == "let" and binding["initializer"] is not None
            init = binding["initializer"]
            assert source[init["start"]:init["end"]].decode() == binding["function_path"]
    for condition in snapshot.get("conditions", []):
        assert inp["rules"] == "rust-r3-v1"
        expected = evaluate_cfg(condition["predicate"], inp["configuration"])
        assert condition["state"] == ("known_true" if expected is True else "known_false" if expected is False else "not_evaluated")
        ev=condition["evidence"]
        assert inp["files"][ev["path"]].encode()[ev["start"]:ev["end"]].decode() == "#[cfg(" + condition["predicate"] + ")]"
        assert condition["inputs"] == sorted(set(condition["inputs"]))
    return declarations, traverse


def verify(matrix_path, output_path):
    matrix = json.loads(Path(matrix_path).read_text())
    output = json.loads(Path(output_path).read_text())
    assert matrix.get("profile", "rust-r1-r2-v1") in ("rust-r1-r2-v1", "rust-r3-v1")
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
        declarations, traverse = verify_snapshot(snapshot)
        traverse(row["result"])
        if label.get("query_file") is not None and row["result"]["state"] == "resolved":
            assert label["rules"] == "rust-r3-v1"
            occurrence = next(r for r in snapshot["references"] if r["evidence"]["path"] == label["query_file"] and r["evidence"]["start"] == label["query_start"] and r["path"] == label["path"])
            assert occurrence["resolution"] == row["result"] or all(e in occurrence["resolution"]["evidence"] for e in row["result"]["evidence"])
            assert occurrence["evidence"] in row["result"]["evidence"]
        if label["rules"] == "rust-r3-v1":
            for reference in snapshot["references"]:
                if reference["resolution"]["state"] == "resolved":
                    assert reference["evidence"] in reference["resolution"]["evidence"]
                    target = declarations[reference["resolution"]["target_id"]]
                    assert target["kind"] == "function_item"
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
    events = output.get("events", [])
    assert len(events) == len(matrix.get("events", []))
    for label, event in zip(matrix.get("events", []), events, strict=True):
        assert event["id"] == label["id"]
        assert event["before"]["input"] == label["a"]
        assert event["incremental"]["input"] == label["b"]
        assert event["rebuild"]["input"] == label["b"]
        assert event["generation_after"] == event["generation_before"] + 1
        assert event["incremental"] == event["rebuild"]
        assert event["before"]["snapshot_id"] != event["incremental"]["snapshot_id"]
        for name in ("before", "incremental", "rebuild"):
            verify_snapshot(event[name])
        labels_path = Path(matrix_path).with_name("incremental-labels.json")
        expected = json.loads(labels_path.read_text())["events"][event["id"]]
        for name, queries in expected.items():
            snap = event[name]; declarations = {d["id"]:d for d in snap["declarations"]}
            for path, wanted in queries.items():
                reference = next(r for r in snap["references"] if r["path"] == path)
                result = reference["resolution"]; decl = declarations.get(result["target_id"])
                target = None if decl is None else f'{decl["evidence"]["path"]}:{decl["module"] + "::" if decl["module"] else ""}{decl["name"]}'
                assert [result["state"],target] == wanted
    if "preregistered_resolvable" in matrix:
        assert resolvable == matrix["preregistered_resolvable"]
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
    return {"cases": len(rows), "resolvable": resolvable, "resolvable_correct": resolvable_correct, "correct": correct, "false_promotions": false_promotions, "events": len(events)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix"); parser.add_argument("output")
    args = parser.parse_args()
    print(json.dumps(verify(args.matrix, args.output), sort_keys=True))
