#!/usr/bin/env python3
"""Materialize only allowlisted baseline files and public input into an empty directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def tasks():
    return [json.loads(line) for name in ("dev.jsonl", "challenge-dev.jsonl") for line in (ROOT / "tasks" / name).read_text(encoding="utf-8").splitlines()]


def safe_path(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or ".." in p.parts or "\\" in name:
        raise ValueError(f"unsafe relative path: {name!r}")
    return p


def materialize(task_id, destination):
    rows = [t for t in tasks() if t["id"] == task_id]
    if len(rows) != 1:
        raise ValueError(f"unknown/nonunique task {task_id}")
    task = rows[0]
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("destination must be empty: never copy the evaluator workspace")
    destination.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "sources" / "manifest.json").read_text(encoding="utf-8"))
    snapshot = manifest["snapshots"][task["input"]["snapshot"]]
    archive = ROOT / snapshot["archive"]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != snapshot["sha256"]:
        raise ValueError("source archive hash mismatch")
    workspace = destination / "workspace"
    workspace.mkdir()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            name = safe_path(member.name)
            if not member.isfile() or member.issym() or member.islnk():
                raise ValueError("source archive must contain regular files only")
            if ".git" in name.parts or name.parts[0] in {"oracles", "reports", "tasks"}:
                raise ValueError("forbidden baseline entry")
            target = workspace / str(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(member).read())
            target.chmod(member.mode & 0o777)
    if snapshot.get('supplementary_license'):
        notice = snapshot['supplementary_license']
        data = (ROOT / notice['path']).read_bytes()
        if hashlib.sha256(data).hexdigest() != notice['sha256']:
            raise ValueError('supplementary license hash mismatch')
        (workspace / 'UPSTREAM-LICENSE-SUPPLEMENTARY').write_bytes(data)
    for operation in task["input"].get("state_changes", []):
        target = workspace / str(safe_path(operation["path"]))
        old = target.stat().st_mtime_ns if target.exists() else 946684800000000000
        if operation["kind"] == "remove":
            target.unlink()
        elif operation["kind"] == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(operation["content"], encoding="utf-8", newline="\n")
            if operation.get("preserve_mtime"):
                os.utime(target, ns=(old, old))
        else:
            raise ValueError("unknown state change")
    request = {"id": task["id"], "family": task["family"], "language": task["language"], "prompt": task["input"]["prompt"], "context_policy": task["input"].get("context_policy", {}), "state_changes": task["input"].get("state_changes", [])}
    if "proposed_diff" in task["input"]:
        data = (ROOT / task["input"]["proposed_diff"]).read_bytes()
        (destination / "proposed.diff").write_bytes(data)
        request["proposed_diff"] = "proposed.diff"
    (destination / "request.json").write_text(json.dumps(request, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return {"task": task_id, "workspace_files": sum(p.is_file() for p in workspace.rglob("*")), "reference_patches_copied": 0, "oracle_files_copied": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(materialize(args.task_id, args.destination)))
