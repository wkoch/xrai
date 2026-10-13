#!/usr/bin/env python3
"""Reconcile authentic API snapshots and original source-presence artifact ZIP; data only.

The caller obtains the API/ZIP bytes through authenticated GitHub access. This
tool checks their internal bindings; it does not cryptographically authenticate
JSON supplied by an arbitrary party, launch the retained binary or run upstream.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import stat
import tempfile
import zipfile
from pathlib import Path

import verify_presence_event as event

REPOSITORY = "wkoch/xrai"
WORKFLOW = ".github/workflows/l5-presence-events.yml"
JOB = "C04 JS Python Go retained-index presence"
ARTIFACT = "c04-source-presence"
REQUIRED_STEP_ORDER = [
    "Run actions/checkout@v6", "Run actions/setup-python@v6",
    "Install pinned verification tooling", "Verify frozen source-only descriptors",
    "Build owned presence inventory", "Prove three frozen retained-index events",
    "Reject adversarial source presence substitutions",
    "Preserve exact source events and native bytes",
]
REQUIRED_STEPS = set(REQUIRED_STEP_ORDER)
LIFECYCLE_STEPS = {"Set up job", "Post Run actions/setup-python@v6",
                   "Post Run actions/checkout@v6", "Complete job"}
BUNDLE_FILES = {"preparation.json", "toolchain.txt", "batch.json",
                "receipt-tests.stdout", "receipt-tests.stderr"}
MAX_ZIP_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 128


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def metadata(run, jobs, artifacts, run_id, head, artifact_id, attempt=1):
    """Check raw GitHub API run/jobs/artifacts envelopes, never caller flags."""
    need(type(run_id) is int and run_id > 0 and type(artifact_id) is int and artifact_id > 0 and
         type(attempt) is int and attempt > 0 and re.fullmatch(r"[0-9a-f]{40}", head), "explicit provenance identifiers")
    need(run["id"] == run_id and type(run["id"]) is int and run["head_sha"] == head and
         run["head_branch"] == "main" and type(run["run_attempt"]) is int and run["run_attempt"] == attempt and
         run["path"] == WORKFLOW and run["event"] == "workflow_dispatch" and
         run["status"] == "completed" and run["conclusion"] == "success" and
         run["repository"]["full_name"] == REPOSITORY, "successful exact workflow/head/run/attempt/repository")
    need(run["html_url"] == f"https://github.com/{REPOSITORY}/actions/runs/{run_id}", "run URL binding")
    need(type(jobs["total_count"]) is int and jobs["total_count"] == len(jobs["jobs"]) == 1, "complete single-job API envelope")
    job = jobs["jobs"][0]
    need(job["name"] == JOB and job["run_id"] == run_id and job["head_sha"] == head and
         type(job["run_attempt"]) is int and job["run_attempt"] == attempt and job["status"] == "completed" and
         job["conclusion"] == "success" and "ubuntu-24.04" in job["labels"], "successful exact Ubuntu state-event job")
    need(type(job["id"]) is int and job["id"] > 0, "job identity")
    need(job["html_url"] == f"https://github.com/{REPOSITORY}/actions/runs/{run_id}/job/{job['id']}", "job URL binding")
    steps = job["steps"]
    names = [step["name"] for step in steps]
    need(len(names) == len(set(names)) and REQUIRED_STEPS <= set(names) <= REQUIRED_STEPS | LIFECYCLE_STEPS,
         "exact required workflow steps and lifecycle closure")
    need([name for name in names if name in REQUIRED_STEPS] == REQUIRED_STEP_ORDER, "required workflow step order")
    need(all(step["status"] == "completed" and step["conclusion"] == "success" and
             type(step["number"]) is int and step["number"] > 0 for step in steps), "every workflow step successful")
    numbers = [step["number"] for step in steps]
    need(numbers == sorted(set(numbers)), "workflow step sequence uniqueness")
    need(type(artifacts["total_count"]) is int and artifacts["total_count"] == len(artifacts["artifacts"]), "complete artifact API envelope")
    selected = [artifact for artifact in artifacts["artifacts"] if artifact["id"] == artifact_id]
    need(len(selected) == 1, "explicit original artifact identity")
    artifact = selected[0]
    need(artifact["name"] == ARTIFACT and artifact["expired"] is False and
         re.fullmatch(r"sha256:[0-9a-f]{64}", artifact["digest"]) and
         type(artifact["size_in_bytes"]) is int and 0 < artifact["size_in_bytes"] <= MAX_ZIP_BYTES,
         "live bounded original ZIP artifact")
    wr = artifact["workflow_run"]
    need(wr["id"] == run_id and wr["head_sha"] == head and wr["head_branch"] == "main", "artifact belongs to exact run/head/branch")
    need(artifact["archive_download_url"] == f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip", "artifact download URL binding")
    def instant(value):
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        need(parsed.tzinfo is not None and parsed.utcoffset() == datetime.timedelta(0), "API timestamp must identify UTC")
        return parsed
    upload = next(step for step in steps if step["name"] == "Preserve exact source events and native bytes")
    need(instant(job["started_at"]) <= instant(upload["started_at"]) <= instant(artifact["created_at"]) <=
         instant(upload["completed_at"]) <= instant(job["completed_at"]), "artifact timestamp belongs to exact attempt upload/job")
    return job, artifact


def zip_members(raw):
    """Read bounded regular members; reject aliasing before any extraction."""
    import io
    need(0 < len(raw) <= MAX_ZIP_BYTES, "original ZIP byte bound")
    result, seen, directories, total = {}, set(), set(), 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        need(0 < len(infos) <= MAX_MEMBERS, "ZIP member count bound")
        for member in infos:
            name = member.filename
            need(name not in seen, "duplicate ZIP member")
            seen.add(name)
            need(name and not name.startswith("/") and "\\" not in name and ":" not in name and
                 not any(ord(c) < 32 for c in name), "ZIP absolute/drive/control path")
            pieces = name[:-1].split("/") if name.endswith("/") else name.split("/")
            need(all(piece not in ["", ".", ".."] for piece in pieces), "ZIP traversal or path alias")
            mode = member.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if member.is_dir():
                need(kind in [0, stat.S_IFDIR] and member.file_size == 0, "ZIP nonregular directory")
                directories.add(name)
                continue
            need(kind in [0, stat.S_IFREG] and not member.flag_bits & 1, "ZIP symlink/special/encrypted member")
            need(0 <= member.file_size <= MAX_MEMBER_BYTES, "ZIP member byte bound")
            total += member.file_size
            need(total <= MAX_TOTAL_BYTES, "ZIP expansion byte bound")
            content = archive.read(member)
            need(len(content) == member.file_size, "ZIP member length mismatch")
            result[name] = content
    for name in result:
        ancestors = ["/".join(name.split("/")[:i]) for i in range(1, len(name.split("/")))]
        need(not any(ancestor in result for ancestor in ancestors), "ZIP file-directory collision")
    need(all(any(name.startswith(directory) for name in result) for directory in directories), "ZIP extra empty directory")
    top = {name for name in result if "/" not in name}
    need(top == BUNDLE_FILES and all(name in BUNDLE_FILES or any(name.startswith("events/" + family + "/") for family in ["js", "python", "go"]) for name in result),
         "known workflow bundle file closure")
    return result


def directory_members(directory):
    need(directory.is_dir() and not directory.is_symlink(), "export must be an ordinary directory")
    result, directories = {}, set()
    for path in directory.rglob("*"):
        need(not path.is_symlink(), "export symlink")
        if path.is_dir():
            directories.add(path.relative_to(directory).as_posix() + "/")
            continue
        need(path.is_file(), "export nonregular file")
        result[path.relative_to(directory).as_posix()] = path.read_bytes()
    need(all(any(name.startswith(subdir) for name in result) for subdir in directories), "export extra empty directory")
    return result


def safe_export(members, destination):
    """Extract already-validated ZIP bytes into a fresh private directory."""
    need(not destination.exists(), "safe export destination must be fresh")
    destination.mkdir()
    for name, content in members.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def reconcile(directory, run_id, head, artifact_id, attempt=1):
    directory = Path(directory)
    metadata_bytes = {name: (directory / name).read_bytes() for name in ["run.json", "jobs.json", "artifacts.json"]}
    run, jobs, artifacts = [event.decode(metadata_bytes[name]) for name in ["run.json", "jobs.json", "artifacts.json"]]
    job, artifact = metadata(run, jobs, artifacts, run_id, head, artifact_id, attempt)
    original = (directory / "original.zip").read_bytes()
    need(sha(original) == artifact["digest"][7:] and len(original) == artifact["size_in_bytes"], "original ZIP digest/byte size differs from API")
    members = zip_members(original)
    # Verify the captured export byte-for-byte, then consume an independent copy
    # made from the original ZIP; mutable exported paths are never proof authority.
    need(directory_members(directory / "export") == members, "extracted export differs from exact original ZIP closure")
    with tempfile.TemporaryDirectory(prefix="xrai-state-ci-reconcile-") as temp:
        safe = Path(temp) / "export"
        safe_export(members, safe)
        recomputed = {}
        batch = event.decode(members["batch.json"])
        need(set(batch) == {"schema", "events", "admitted", "competitive_runs_allowed"} and
             batch["schema"] == "xrai.eval.c04.presence-batch.v1" and
             batch["admitted"] is False and batch["competitive_runs_allowed"] is False and
             set(batch["events"]) == {"js", "python", "go"}, "exact complete batch")
        for family in ["js", "python", "go"]:
            recomputed[family] = event.verify(safe / "events" / family)
            need(event.same(recomputed[family], event.decode(members[f"events/{family}/verification.json"])) and
                 event.same(recomputed[family], batch["events"][family]), "retained/recomputed complete verification differs")
            receipt = event.decode(members[f"events/{family}/receipt.json"])
            environment = receipt["environment"]
            need(environment["github_sha"] == head and str(environment["github_run_id"]) == str(run_id) and
                 recomputed[family]["code_commit"] == head and str(recomputed[family]["run_id"]) == str(run_id), "receipt environment differs from exact API head/run")
        need(len({value["descriptor_sha256"] for value in recomputed.values()}) == 3,
             "three distinct original frozen cases")
    return {"schema_version": "xrai.eval.c04.presence-ci-reconciliation.v1",
            "verified": True, "data_only": True, "run_id": run_id, "run_attempt": attempt,
            "code_commit": head, "repository": REPOSITORY, "workflow": WORKFLOW,
            "job_id": job["id"], "artifact_id": artifact_id, "artifact_name": ARTIFACT,
            "artifact_zip_sha256": sha(original), "artifact_zip_bytes": len(original),
            "exact_zip_export_files": len(members),
            "metadata_sha256": {name: sha(raw) for name, raw in metadata_bytes.items()},
            "export_file_sha256": {name: sha(raw) for name, raw in sorted(members.items())},
            "native_verification": recomputed,
            "reconciler_source_sha256": sha(Path(__file__).read_bytes()),
            "native_code_provenance": "Native producer source bindings verified unchanged; data-only reconciler provenance is recorded separately by its own source hash.",
            "admitted": False, "competitive_runs_allowed": False,
            "limits": ["Caller authenticates the original GitHub API/ZIP acquisition; local JSON is not a signature.",
                       "Retained native binary is hashed, never executed by this reconciler.",
                       "Only captured source presence is proven; parsing and semantics remain unknown and dossiers unqualified."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--artifact-id", type=int, required=True)
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(reconcile(args.directory, args.run_id, args.head, args.artifact_id, args.attempt), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
