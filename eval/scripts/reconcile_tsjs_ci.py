#!/usr/bin/env python3
"""Reconcile authenticated TSJS API/ZIP bytes as data; never run retained binaries.

Caller acquires API and ZIP through authenticated GitHub access. These JSON
snapshots are contextual evidence, not a signature from an arbitrary caller.
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
import verify_tsjs_semantics as semantics

REPOSITORY = "wkoch/xrai"
WORKFLOW = ".github/workflows/l5-tsjs-semantics.yml"
JOB = "C04 captured TSJS relative semantics"
ARTIFACT = "c04-tsjs-semantics"
REQUIRED_STEP_ORDER = [
    "Run actions/checkout@v6", "Run actions/setup-python@v6",
    "Install pinned verification tooling", "Build owned TSJS analyzer",
    "Prove frozen TSJS labels and real relation", "Reject adversarial TSJS substitutions",
    "Preserve exact TSJS proof and native bytes",
]
REQUIRED_STEPS = set(REQUIRED_STEP_ORDER)
LIFECYCLE_STEPS = {"Set up job", "Post Run actions/setup-python@v6", "Post Run actions/checkout@v6", "Complete job"}
BUNDLE_FILES = {"collector.json", "toolchain.txt", "receipt-tests.stdout", "receipt-tests.stderr"}
MAX_ZIP_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 128
SOURCE_PATHS = {
    "crates/xrai-eval/src/tsjs_semantics.rs", "crates/xrai-eval/src/bin/tsjs-semantics.rs",
    "crates/xrai-eval/src/worker_spike.rs", "crates/xrai-eval/src/parsing_spike.rs",
    "crates/xrai-eval/queries/javascript.scm", "crates/xrai-eval/queries/typescript.scm",
    "eval/scripts/verify_tsjs_semantics.py", "eval/scripts/run_tsjs_semantics.py",
    "eval/semantics/tsjs/labels.json", "eval/semantics/tsjs/freeze-before-resolver.json",
    "Cargo.lock", "crates/xrai-eval/parsing-provenance.json",
}

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
         job["conclusion"] == "success" and "ubuntu-24.04" in job["labels"], "successful exact Ubuntu TSJS job")
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
    upload = next(step for step in steps if step["name"] == "Preserve exact TSJS proof and native bytes")
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
    need(top == BUNDLE_FILES and all(name in BUNDLE_FILES or name.startswith("event/") for name in result),
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
    names = ["run.json", "jobs.json", "artifacts.json"]
    raw_metadata = {name: (directory / name).read_bytes() for name in names}
    run, jobs, artifacts = [semantics.strict_json(raw_metadata[name]) for name in names]
    job, artifact = metadata(run, jobs, artifacts, run_id, head, artifact_id, attempt)
    original = (directory / "original.zip").read_bytes()
    need(sha(original) == artifact["digest"][7:] and len(original) == artifact["size_in_bytes"], "original ZIP API digest/size")
    members = zip_members(original)
    need(directory_members(directory / "export") == members, "export differs from exact original ZIP")
    labels = semantics.labels()
    expected_event = {"event/receipt.json", "event/verification.json", "event/invocations.json", "event/native-bin/tsjs-semantics"}
    expected_event |= {"event/outputs/" + case["id"] + ".json" for case in labels["cases"]}
    need(set(members) == BUNDLE_FILES | expected_event, "complete native outputs and metadata closure")
    binary = members["event/native-bin/tsjs-semantics"]
    need(binary.startswith(b"\x7fELF") and 4096 <= len(binary) <= MAX_MEMBER_BYTES, "retained regular Linux native executable bytes")
    receipt = semantics.strict_json(members["event/receipt.json"])
    need(set(receipt) == {"schema_version", "binary_sha256", "source_sha256", "code_commit", "run_id", "platform", "machine", "cases", "upstream_executed", "calls_to_upstream_compiler", "owned_analyzer_only", "global_admission"}, "typed native receipt closure")
    need(receipt["schema_version"] == "xrai.eval.tsjs.native-receipt.v1" and receipt["binary_sha256"] == sha(binary), "receipt actual executable identity")
    need(receipt["code_commit"] == head and str(receipt["run_id"]) == str(run_id) and
         isinstance(receipt["platform"], str) and receipt["platform"].startswith("Linux-") and receipt["machine"] == "x86_64", "native environment belongs to API head/run/Linux")
    need(receipt["upstream_executed"] is False and receipt["owned_analyzer_only"] is True and
         receipt["global_admission"] is False and type(receipt["calls_to_upstream_compiler"]) is int and receipt["calls_to_upstream_compiler"] == 0,
         "owned analyzer execution scope")
    need(set(receipt["source_sha256"]) == SOURCE_PATHS and
         all(sha((semantics.ROOT / path).read_bytes()) == digest for path, digest in receipt["source_sha256"].items()), "consumed source/labels/lock/provenance fingerprint")
    cases = labels["cases"]
    need(type(receipt["cases"]) is int and receipt["cases"] == len(cases), "native case count")
    invocations = semantics.strict_json(members["event/invocations.json"])
    need(isinstance(invocations, list) and len(invocations) == len(cases), "all native invocation receipts")
    for case, invocation in zip(cases, invocations):
        need(set(invocation) == {"case", "input_sha256", "exit_code", "stderr_sha256", "stdout_sha256", "elapsed_seconds"}, "typed invocation receipt")
        need(invocation["case"] == case["id"] and type(invocation["exit_code"]) is int and invocation["exit_code"] == 0 and
             invocation["stderr_sha256"] == sha(b"") and invocation["input_sha256"] == sha(semantics.compact(case["input"])) and
             invocation["stdout_sha256"] == sha(members["event/outputs/" + case["id"] + ".json"]), "consumed input and complete native output invocation binding")
        need(type(invocation["elapsed_seconds"]) in [int, float] and 0 <= invocation["elapsed_seconds"] <= 30, "bounded native invocation duration")
    toolchain = members["toolchain.txt"].decode()
    need("rustc 1.98.1" in toolchain and "host: x86_64-unknown-linux-gnu" in toolchain, "pinned Rust compiler and Linux host receipt")
    tests = members["receipt-tests.stderr"].decode()
    need(members["receipt-tests.stdout"] == b"" and re.search(r"Ran 22 tests in [0-9.]+s\n\nOK\n", tests) is not None and "skipped" not in tests,
         "all actual snapshot adversarial checks ran and passed")
    with tempfile.TemporaryDirectory(prefix="xrai-tsjs-ci-reconcile-") as temporary:
        safe = Path(temporary) / "export"; safe_export(members, safe)
        recomputed = semantics.verify_outputs(safe / "event/outputs")
    need(recomputed == semantics.strict_json(members["event/verification.json"]) == semantics.strict_json(members["collector.json"]),
         "complete retained and data-only recomputed native results differ")
    return {"schema_version": "xrai.eval.tsjs.authenticated-ci-reconciliation.v1", "verified": True, "data_only": True,
            "run_id": run_id, "run_attempt": attempt, "code_commit": head, "repository": REPOSITORY, "workflow": WORKFLOW,
            "job_id": job["id"], "artifact_id": artifact_id, "artifact_name": ARTIFACT,
            "artifact_zip_sha256": sha(original), "artifact_zip_bytes": len(original), "exact_zip_export_files": len(members),
            "metadata_sha256": {name: sha(raw) for name, raw in raw_metadata.items()},
            "export_file_sha256": {name: sha(raw) for name, raw in sorted(members.items())},
            "native_verification": recomputed, "actual_native_binary_sha256": sha(binary),
            "reconciler_source_sha256": sha(Path(__file__).read_bytes()), "global_admission": False,
            "limits": ["Original API/ZIP authenticated acquisition is performed by caller; arbitrary local JSON is not a signature.",
                       "Retained binary is hashed and never executed by this reconciler.",
                       "Cargo version was not separately printed in this first workflow; the pinned Rust toolchain/build step supplies configuration provenance.",
                       "Experimental reference subset only; callable targets, other dialects and D1 remain unqualified."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("directory", type=Path)
    parser.add_argument("--run-id", type=int, required=True); parser.add_argument("--head", required=True)
    parser.add_argument("--artifact-id", type=int, required=True); parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(reconcile(args.directory, args.run_id, args.head, args.artifact_id, args.attempt), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
