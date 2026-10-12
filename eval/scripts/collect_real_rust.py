#!/usr/bin/env python3
"""Offline, source-only capture/materialization of the L5 rust-analyzer case.

No upstream commands execute here. Production counts are deliberately lower bounds:
each Rust file is cut at its first cfg(test)/test attribute, and comment-looking lines
are excluded. Everything after that point remains in the complete agent checkout.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "eval/qualification/l5-real/rust"
EXCLUDED = {"tests", "test", "test_data", "testdata", "fixtures", "generated", "vendor",
            "vendored", "doc", "docs", "documentation", "examples", "example", "benches",
            "benchmarks", "target", "build", "dist", "node_modules", ".git", "__tests__"}
TEST = re.compile(r"^\s*#\s*\[\s*(?:cfg\s*\(\s*test\s*\)|test\s*\])")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def members(archive):
    """Yield complete upstream regular files, rejecting dangerous/incomplete trees."""
    seen = set()
    prefix = None
    internal_links = {"AGENTS.md": "CLAUDE.md", "lib/lsp-server/LICENSE-APACHE": "LICENSE-APACHE",
                      "lib/lsp-server/LICENSE-MIT": "LICENSE-MIT"}
    with tarfile.open(archive, "r:gz") as tree:
        for member in tree:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("unsafe archive path")
            if prefix is None:
                prefix = path.parts[0]
            if path.parts[0] != prefix:
                raise ValueError("multiple archive roots")
            name = str(PurePosixPath(*path.parts[1:]))
            if member.isdir():
                continue
            if name in seen or ".git" in path.parts:
                raise ValueError("not a unique regular upstream file")
            seen.add(name)
            if member.issym() and name in internal_links:
                target = tree.getmember(prefix + "/" + internal_links[name])
                if not target.isfile():
                    raise ValueError("internal link must target a regular file")
                # Only the three frozen upstream links are normalized; no filesystem follow.
                expected_link = "CLAUDE.md" if name == "AGENTS.md" else "../../" + internal_links[name]
                if member.linkname != expected_link:
                    raise ValueError("unexpected pinned internal link target")
                yield name, tree.extractfile(target).read(), target.mode & 0o777
            elif member.isfile() and not member.islnk():
                yield name, tree.extractfile(member).read(), member.mode & 0o777
            else:
                raise ValueError("unsupported archive entry")


def measure(name, blob):
    path = PurePosixPath(name)
    if path.suffix != ".rs" or not path.parts or path.parts[0] != "crates" or set(path.parts) & EXCLUDED:
        return 0, "excluded_path_or_non_rust"
    # Generated files are excluded even when stored under a production directory.
    text = blob.decode("utf-8")
    if re.search(r"(?im)^.*(?:generated (?:code|file)|do not edit|automatically generated)", text[:2000]):
        return 0, "generated_header"
    kept = []
    stopped = False
    for line in text.splitlines():
        if TEST.match(line):
            stopped = True
            break
        stripped = line.strip()
        if stripped and not stripped.startswith(("//", "/*", "*", "*/")):
            kept.append(line)
    return len(kept), "rust_prefix_before_first_test" if stopped else "rust_no_test_marker"


def inventory(archive):
    rows = []
    for name, blob, mode in members(archive):
        count, reason = measure(name, blob)
        rows.append({"path": name, "bytes": len(blob), "sha256": sha(blob), "mode": mode,
                     "production_nonempty_lower_bound": count, "measurement_reason": reason})
    rows.sort(key=lambda x: x["path"])
    return {"archive_sha256": sha(archive.read_bytes()), "archive_bytes": archive.stat().st_size,
            "file_count": len(rows), "source_bytes": sum(x["bytes"] for x in rows),
            "production_files_lower_bound": sum(x["production_nonempty_lower_bound"] > 0 for x in rows),
            "production_nonempty_lines_lower_bound": sum(x["production_nonempty_lower_bound"] for x in rows),
            "method": "xrai.rust.production.conservative-prefix.v1", "path_exclusions": sorted(EXCLUDED),
            "materialization_policy": "complete upstream tree; three pinned internal symlinks copied from verified regular targets, no links retained",
            "inline_test_policy": "Discard suffix starting at first cfg(test) or test attribute, even if production follows; remove comment-looking lines. Lower bound, not exact LOC.",
            "files": rows}


def verify():
    selection = json.loads((CASE / 'case.json').read_text())
    provenance = ROOT / 'docs/relatorios/logs/L5-continuacao/corpus-rust'
    commit = json.loads((provenance / 'commit-reference.json').read_text())
    if (commit['sha'] != selection['reference']['commit'] or
            commit['parents'][0]['sha'] != selection['baseline']['commit']):
        raise ValueError('captured public parent/head mismatch')
    receipts = {}
    for side in ('baseline', 'reference'):
        info = selection[side]
        actual = inventory(CASE / info['archive'])
        expected = json.loads((CASE / info['inventory']).read_text())
        with tarfile.open(CASE / info['archive']) as tree:
            roots = {PurePosixPath(m.name).parts[0] for m in tree}
        if roots != {'rust-analyzer-' + info['commit']}:
            raise ValueError(side + ' archive commit root mismatch')
        if actual != expected:
            raise ValueError(side + ' inventory mismatch')
        if not (actual['production_files_lower_bound'] >= 500 or
                actual['production_nonempty_lines_lower_bound'] >= 50000):
            raise ValueError(side + ' production floor not met')
        receipts[side] = {k: actual[k] for k in ('archive_sha256', 'file_count',
            'production_files_lower_bound', 'production_nonempty_lines_lower_bound')}
    if sha((CASE / selection['request']['path']).read_bytes()) != selection['request']['sha256']:
        raise ValueError('request fingerprint mismatch')
    source = dict((name, blob) for name, blob, _ in members(CASE / selection['baseline']['archive']))
    for module in selection['production_modules']:
        blob = source[module['path']]
        if sha(blob) != module['source_sha256'] or blob[module['byte_start']:module['byte_end']].decode() != module['anchor']:
            raise ValueError('module evidence mismatch')
    oracle = json.loads((CASE / 'oracles/oracle.json').read_text())
    plan = json.loads((CASE / 'oracles/probe-plan.json').read_text())
    patch = (CASE / oracle['patch']['path']).read_bytes()
    hidden = (CASE / plan['hidden_test']['path']).read_bytes()
    if sha(patch) != oracle['patch']['sha256'] or sha(hidden) != plan['hidden_test']['sha256']:
        raise ValueError('evaluator patch/probe fingerprint mismatch')
    reference = dict((name, blob) for name, blob, _ in members(CASE / selection['reference']['archive']))
    probe_path = plan['hidden_test']['copied_to']
    if not (hidden.split(b'#[cfg(test)]')[0] == source[probe_path].split(b'#[cfg(test)]')[0]
            == reference[probe_path].split(b'#[cfg(test)]')[0]):
        raise ValueError('hidden probe modifies production code')
    changed = [p for p in source if source[p] != reference[p] and p != probe_path]
    expected_patch = ''.join(''.join(difflib.unified_diff(source[p].decode().splitlines(keepends=True),
            reference[p].decode().splitlines(keepends=True), fromfile='a/' + p, tofile='b/' + p)) for p in sorted(changed))
    if patch.decode() != expected_patch:
        raise ValueError('production reference patch differs from captured delta')
    return {'verified': True, 'snapshots': receipts, 'admitted': False,
            'behavioral_proof': 'separate Linux evaluator receipts required'}


def materialize(destination):
    """Fresh baseline input only: no evaluator oracle, patch, captures, or provenance."""
    selection = json.loads((CASE / "case.json").read_text())
    expected = json.loads((CASE / "baseline-inventory.json").read_text())
    archive = CASE / selection["baseline"]["archive"]
    if inventory(archive) != expected:
        raise ValueError("baseline inventory mismatch")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("destination must be empty")
    workspace = destination / "workspace"
    workspace.mkdir(parents=True)
    for name, blob, mode in members(archive):
        output = workspace / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(blob)
        output.chmod(mode)
    request = json.loads((CASE / "request.json").read_text())
    (destination / "request.json").write_text(json.dumps(request, indent=2, ensure_ascii=False) + "\n")
    return {"files": expected["file_count"], "source_bytes": expected["source_bytes"],
            "baseline_commit": selection["baseline"]["commit"], "oracle_files_copied": 0,
            "reference_files_copied": 0, "state": "cold_baseline_A", "incremental_proof": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("inventory")
    capture.add_argument("archive", type=Path)
    sub.add_parser("verify")
    mat = sub.add_parser("materialize")
    mat.add_argument("destination", type=Path)
    args = parser.parse_args()
    result = (inventory(args.archive) if args.command == "inventory" else
              verify() if args.command == "verify" else materialize(args.destination))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
