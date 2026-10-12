#!/usr/bin/env python3
"""C03-B pre-result freezing of independent real-source state tasks; data only.

No upstream import, parser, build or test runs here. Prepared descriptors are
not eligibility, semantic accuracy, an executed event or global admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "eval/qualification/state-events"
VERSION = "xrai.eval.real-state-event.prepared.v1"
ARCHIVE_HASHES = {
    "rust-lang/rust-analyzer": "539f90cd750eff4df257d2ff01d9552da7f57201daa493d5afe4b8daaf1e4e9f",
    "facebook/react": "b589b94f327ee6a48ab809d9477f9926341b2980676a9b89cb1a4f6ea783afd6",
    "scikit-learn/scikit-learn": "70f9d47a3aba04faf22b150075283b0a4311f8b665bf2ab3e447cd5c3685b70b",
    "go-gitea/gitea": "3cd918c96a563db6a64e8c9717d556097240de799f9f0948ba50060e6143c190",
}
SPECS = {
    "rust": {
        "family": "Rust", "repository": "rust-lang/rust-analyzer",
        "commit": "3a5f65784a90278fa1de97fe89a7a529dd44765a",
        "archive": "eval/qualification/l5-real/rust/baseline.tar.gz",
        "paths": ["crates/stdx/src/rand.rs"],
        "context": ["Cargo.toml", "crates/stdx/Cargo.toml", "LICENSE-MIT", "LICENSE-APACHE"],
        "event": "configured_edition_change", "capacity": "rust-r3-v1-limited-root-lookup",
        "input": "The indexing session uses the older edition while this workspace declares the newer edition. Update the session configuration to the workspace edition and refresh navigation for the randomization utilities. Keep an unavailable helper unavailable. Compare the refreshed state with a fresh index without closing the working session.",
    },
    "js": {
        "family": "TSJS", "repository": "facebook/react",
        "commit": "77912d9a05d7a90287fabdec76486f25869b2981",
        "archive": "eval/qualification/l5-real/js/sources/base.tar.gz",
        "paths": ["packages/react/src/ReactHooks.js", "packages/react/src/ReactCurrentDispatcher.js"],
        "context": ["LICENSE", "package.json"],
        "event": "source_availability_change", "capacity": "captured-source-presence-v1",
        "input": "A partial checkout contains the hooks source but lacks its dispatcher source. Refresh the captured checkout when the missing upstream source becomes available. Previously cached absence must change to availability, while an unrelated missing source stays missing. Keep the same session and compare its refreshed source state with a fresh capture.",
    },
    "python": {
        "family": "Python", "repository": "scikit-learn/scikit-learn",
        "commit": "156ef141f3b270edb06c8ae9af37c55253c0aabe",
        "archive": "eval/qualification/l5-real/python/sources/base.tar.gz",
        "paths": ["sklearn/metrics/__init__.py", "sklearn/metrics/_ranking.py"],
        "context": ["COPYING", "pyproject.toml"],
        "event": "source_availability_change", "capacity": "captured-source-presence-v1",
        "input": "The metrics package was captured without its ranking implementation. Refresh this incomplete capture when the ranking source becomes available. Remove the cached missing-source answer, preserve the other captured source and keep an unrelated missing source unavailable. Compare the refreshed session with a fresh capture; do not execute the package.",
    },
    "go": {
        "family": "Go", "repository": "go-gitea/gitea",
        "commit": "8eefa1f6dedf2488db2c9e12c916e8e51f673160",
        "archive": "eval/qualification/l5-real/go/sources/base.tar.gz",
        "paths": ["modules/util/url.go", "modules/util/path.go"],
        "context": ["LICENSE", "go.mod"],
        "event": "source_availability_change", "capacity": "captured-source-presence-v1",
        "input": "The captured utility package has URL utilities but is missing the path utilities source. Refresh the capture when that original source becomes available. A warmed missing-source answer must become available, the URL source must remain unchanged and an unrelated missing source must remain unavailable. Compare the same session after refresh with a new capture without building the repository.",
    },
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def inventory(files: dict[str, str]) -> dict[str, dict[str, object]]:
    return {path: {"sha256": sha(text.encode()), "bytes": len(text.encode())}
            for path, text in sorted(files.items())}


def source_bytes(spec: dict) -> tuple[dict[str, str], dict[str, str], dict]:
    archive = ROOT / spec["archive"]
    archive_hash = sha(archive.read_bytes())
    if archive_hash != ARCHIVE_HASHES[spec["repository"]]:
        raise ValueError("pinned upstream archive changed")
    wanted = set(spec["paths"] + spec["context"])
    sources = {}
    prefix = f"{spec['repository'].rsplit('/', 1)[1]}-{spec['commit']}/"
    with tarfile.open(archive, "r:gz") as capture:
        for member in capture.getmembers():
            if not member.name.startswith(prefix):
                continue
            path = member.name[len(prefix):]
            if path not in wanted:
                continue
            if path in sources or not member.isfile() or member.issym() or member.islnk():
                raise ValueError("source closure must contain unique regular files")
            stream = capture.extractfile(member)
            assert stream is not None
            sources[path] = stream.read().decode("utf-8")
    if set(sources) != wanted:
        raise ValueError(f"missing pinned source/context: {sorted(wanted - set(sources))}")
    files = {path: sources[path] for path in spec["paths"]}
    context = {path: sources[path] for path in spec["context"]}
    return files, context, {"path": spec["archive"], "sha256": archive_hash,
                            "commit": spec["commit"], "repository": spec["repository"]}


def compose(family: str) -> dict[str, bytes]:
    spec = SPECS[family]
    files, context, archive = source_bytes(spec)
    case_id = f"L5-STATE-{spec['family']}-{'STDX-EDITION' if family == 'rust' else 'SOURCE-AVAILABILITY'}"
    configuration = {"profile": spec["capacity"]}
    if family == "rust":
        if '\n edition = "2024"' not in "\n " + context["Cargo.toml"].replace("\n", "\n "):
            raise ValueError("workspace edition anchor changed")
        root = spec["paths"][0]
        a = {"files": files, "root": root, "edition": "2018", "configuration": {}, "rules": "rust-r3-v1"}
        b = {**a, "edition": "2024"}
        queries = [{"id": name, "module": "", "path": name, "namespace": "value"}
                   for name in ("seed", "shuffle", "no_such_random_helper")]
        answers = {name: {"a": {"state": "unknown", "target": None},
                          "b": {"state": "resolved", "target": f"{root}:{name}"}}
                   for name in ("seed", "shuffle")}
        answers["no_such_random_helper"] = {"a": {"state": "unknown", "target": None},
                                             "b": {"state": "unknown", "target": None}}
        delta = {"files_added": [], "files_removed": [], "files_changed": [],
                 "configuration_changed": {"edition": {"a": "2018", "b": "2024"}}}
        parse_requirement = "Tree-sitter Rust producer reports full snapshot coverage/gaps; no upstream code execution"
    else:
        added = spec["paths"][1]
        a = {"files": {spec["paths"][0]: files[spec["paths"][0]]}, "configuration": configuration}
        b = {"files": files, "configuration": configuration}
        absent = str(Path(added).parent / "xrai_missing_unrelated_source")
        queries = [{"id": "restored-source", "kind": "source_presence", "path": added},
                   {"id": "retained-source", "kind": "source_presence", "path": spec["paths"][0]},
                   {"id": "unrelated-absent", "kind": "source_presence", "path": absent}]
        answers = {q["id"]: {side: {"available": q["path"] in state["files"],
                                    "sha256": inventory(state["files"]).get(q["path"], {}).get("sha256")}
                               for side, state in (("a", a), ("b", b))} for q in queries}
        delta = {"files_added": [added], "files_removed": [], "files_changed": [], "configuration_changed": {}}
        parse_requirement = "none: source availability only; parse/semantic relations explicitly unknown, never omitted as proven"
    oracle = {"schema_version": VERSION, "task_id": case_id, "capacity": spec["capacity"],
              "labels_frozen_before_results": True, "answers": answers,
              "stale_control": "A answers for changed queries must differ from B expectations",
              "full_comparison": "complete declared snapshot, all queries, unknown/coverage/diagnostics preserved",
              "operational_normalization": ["session_id", "operation_id", "generation", "pid", "timing"],
              "no_normalization_of": ["source_hashes", "configuration", "unknown", "coverage", "diagnostics", "targets", "evidence", "dependencies"]}
    contents = {"a.json": encoded(a), "b.json": encoded(b), "queries.json": encoded(queries),
                "oracle.json": encoded(oracle), "agent/input.md": (spec["input"] + "\n").encode(),
                "context.json": encoded({"files": context, "inventory": inventory(context)})}
    descriptor = {"schema_version": VERSION, "task_id": case_id,
                  "slot_id": f"L5-SLOT-{spec['family']}-state_config-1", "family": spec["family"],
                  "kind": "state_config", "event_role": "required", "origin": "controlled_independent_state_task",
                  "change_lineage": f"controlled:{spec['repository']}:{spec['commit']}:{case_id}",
                  "derived_from": [], "repository": spec["repository"], "archive": archive,
                  "capacity": spec["capacity"], "event": spec["event"], "delta": delta,
                  "source_scope": "entire original selected production files; full upstream archive retained separately; no whole-repository semantic claim",
                  "a_inventory": inventory(a["files"]), "b_inventory": inventory(b["files"]),
                  "parsing_requirement": parse_requirement,
                  "complex": False, "complex_reason": "no claimed three-module/two-subsystem necessary chain",
                  "prepared": True, "executed": False, "individual_eligible": False,
                  "admitted": False, "global_admission_delta": 0,
                  "required_session_sequence": ["open_A", "warm_all_queries_A", "apply_B_same_index", "query_all_B", "snapshot_B", "independent_open_B", "compare_complete", "close_both"],
                  "receipt_policy": "descriptor is preparation only; cold B, restart, supplemental role and relabelled case cannot demonstrate the required event",
                  "artifacts": {path: {"sha256": sha(data), "bytes": len(data)} for path, data in contents.items()}}
    contents["descriptor.json"] = encoded(descriptor)
    contents["README.md"] = (f"# {case_id}\n\nPrepared independent controlled state task, frozen before execution. "
                               f"Capacity: `{spec['capacity']}`. No executed event, individual eligibility or D1 admission. "
                               "The archive is reused solely as original source data; this lineage is independent of the earlier correction/contract. "
                               "Input is agent-facing; oracle, context and descriptor are evaluator-only. "
                               "Rust changes declared edition configuration; the other families restore original source availability in incomplete captures. "
                               "TSJS React Flow source presence does not imply compatibility with captured-relative-exact-v1.\n").encode()
    return contents


def verify(directory: Path = DEST) -> dict:
    descriptors = []
    if directory.is_symlink() or {path.name for path in directory.iterdir()} != set(SPECS):
        raise ValueError("exact four independent family directories required")
    for family in SPECS:
        expected = compose(family)
        path = directory / family
        if path.is_symlink() or not path.is_dir():
            raise ValueError("family preparation must be an ordinary directory")
        actual = {str(p.relative_to(path)) for p in path.rglob("*") if p.is_file()}
        if actual != set(expected) or any(p.is_symlink() for p in path.rglob("*")):
            raise ValueError(f"{family}: missing, extra or linked preparation artifact")
        for name, data in expected.items():
            if (path / name).read_bytes() != data:
                raise ValueError(f"{family}: pinned preparation differs: {name}")
        descriptors.append({"family": SPECS[family]["family"],
                            "descriptor_sha256": sha(expected["descriptor.json"]),
                            "path": f"eval/qualification/state-events/{family}/descriptor.json"})
    return {"schema_version": VERSION, "verified": True, "prepared_required_events": 4,
            "executed_required_events": 0, "individual_eligibility_delta": 0,
            "global_admission_delta": 0, "data_only": True, "descriptors": descriptors}


def prepare(directory: Path = DEST) -> dict:
    for family in SPECS:
        for name, data in compose(family).items():
            path = directory / family / name
            if path.exists() and path.read_bytes() != data:
                raise ValueError("refuse to rewrite a frozen descriptor; create a distinct version")
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(data)
    return verify(directory)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"), nargs="?", default="verify")
    args = parser.parse_args()
    print(json.dumps(prepare() if args.action == "prepare" else verify(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
