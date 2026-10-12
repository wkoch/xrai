#!/usr/bin/env python3
"""Materialize only allowlisted baseline files and public input into an empty directory."""
import argparse
import hashlib
import gzip
import io
import json
import os
import stat
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def source_files(snapshot, *, root=ROOT):
    """Legacy inline inventories and fingerprinted complete-tree inventories."""
    if 'files' in snapshot:
        return snapshot['files']
    receipt = snapshot['files_artifact']
    path = root / str(safe_path(receipt['path']))
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('source inventory escapes evaluator')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != receipt['sha256']:
        raise ValueError('source inventory fingerprint mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        decoded = stream.read(64 * 1024 * 1024 + 1)
    if len(decoded) > 64 * 1024 * 1024:
        raise ValueError('source inventory exceeds evaluator bound')
    return json.loads(decoded)


def tasks(dataset="development"):
    """Development is explicit; a competitive caller must request qualified."""
    names = {"development": ("dev.jsonl", "challenge-dev.jsonl"),
             "seed": ("challenge-dev.jsonl",), "qualified": ("challenge-qualified.jsonl",),
             "vertical": ("../qualification/vertical/candidates.jsonl",),
             "supplementary": ("supplementary.jsonl",)}
    if dataset not in names:
        raise ValueError("unknown dataset class")
    return [json.loads(line) for name in names[dataset] for line in
            (ROOT / "tasks" / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def safe_path(name):
    p = PurePosixPath(name)
    if not name or not p.parts or p.is_absolute() or ".." in p.parts or "\\" in name:
        raise ValueError(f"unsafe relative path: {name!r}")
    return p


def apply_event(task_id, workspace, *, dataset="development"):
    """Evaluator-only phase B. Apply to the existing workspace, never recreate A."""
    rows = [t for t in tasks(dataset) if t["id"] == task_id]
    if len(rows) != 1:
        raise ValueError(f"unknown/nonunique task {task_id}")
    workspace = Path(workspace)
    if workspace.is_symlink():
        raise ValueError("event workspace cannot be a symlink")
    workspace = workspace.resolve(strict=True)
    receipts = []
    root_fd = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for operation in rows[0]["input"].get("state_changes", []):
            old_data, old_stat, data, new_stat = event_operation(root_fd, operation)
            receipts.append({"path": operation["path"], "kind": operation["kind"],
                         "before_sha256": hashlib.sha256(old_data).hexdigest() if old_data is not None else None,
                         "after_sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
                         "before_bytes": len(old_data) if old_data is not None else None,
                         "after_bytes": len(data) if data is not None else None,
                         "before_mtime_ns": old_stat.st_mtime_ns if old_stat else None,
                         "after_mtime_ns": new_stat.st_mtime_ns if new_stat else None})
    finally:
        os.close(root_fd)
    return {"task": task_id, "phase": "B", "events": receipts}


def event_operation(root_fd, operation):
    """Use anchored directory descriptors: symlink swaps never redirect IO outside A."""
    parts = safe_path(operation["path"]).parts
    require_kind = operation["kind"]
    if require_kind not in {"write", "remove"}:
        raise ValueError("unknown state change")
    parent_fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            if require_kind == "write":
                try:
                    os.mkdir(part, dir_fd=parent_fd)
                except FileExistsError:
                    pass
            child_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = child_fd
        try:
            read_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
        except FileNotFoundError:
            old_data, old_stat = None, None
        else:
            with os.fdopen(read_fd, 'rb') as reader:
                old_stat = os.fstat(reader.fileno())
                if not stat.S_ISREG(old_stat.st_mode) or old_stat.st_nlink != 1 or old_stat.st_size > 64 * 1024 * 1024:
                    raise ValueError("event target must be a bounded regular file with no hardlinks")
                old_data = reader.read(64 * 1024 * 1024 + 1)
                if len(old_data) > 64 * 1024 * 1024:
                    raise ValueError("event target exceeds receipt bound")
        if require_kind == 'remove':
            os.unlink(parts[-1], dir_fd=parent_fd)
            return old_data, old_stat, None, None
        data = operation['content'].encode('utf-8')
        fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o666, dir_fd=parent_fd)
        with os.fdopen(fd, 'wb') as writer:
            current = os.fstat(writer.fileno())
            if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1:
                raise ValueError("event target must be a regular file with no hardlinks")
            os.ftruncate(writer.fileno(), 0)
            writer.write(data)
            writer.flush()
            if operation.get('preserve_mtime'):
                old = old_stat.st_mtime_ns if old_stat else 946684800000000000
                os.utime(writer.fileno(), ns=(old, old))
            new_stat = os.fstat(writer.fileno())
        return old_data, old_stat, data, new_stat
    except OSError as error:
        raise ValueError("event IO refused unsafe/inaccessible path") from error
    finally:
        os.close(parent_fd)


def materialize(task_id, destination, *, phase="cold", dataset="development"):
    if phase not in {"cold", "A"}:
        raise ValueError("phase must be cold or A")
    rows = [t for t in tasks(dataset) if t["id"] == task_id]
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
    if phase == "cold":
        apply_event(task_id, workspace, dataset=dataset)
    request = {"id": task["id"], "family": task["family"], "language": task["language"], "prompt": task["input"]["prompt"], "context_policy": task["input"].get("context_policy", {})}
    if "proposed_diff" in task["input"]:
        data = (ROOT / task["input"]["proposed_diff"]).read_bytes()
        (destination / "proposed.diff").write_bytes(data)
        request["proposed_diff"] = "proposed.diff"
    (destination / "request.json").write_text(json.dumps(request, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return {"task": task_id, "phase": phase, "state_class": "baseline_A" if phase == "A" else "cold_changed_checkout", "workspace_files": sum(p.is_file() for p in workspace.rglob("*")), "reference_patches_copied": 0, "oracle_files_copied": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--phase", choices=("cold", "A"), default="cold")
    parser.add_argument("--dataset", choices=("development", "seed", "qualified", "vertical", "supplementary"), default="development")
    args = parser.parse_args()
    print(json.dumps(materialize(args.task_id, args.destination, phase=args.phase, dataset=args.dataset)))
