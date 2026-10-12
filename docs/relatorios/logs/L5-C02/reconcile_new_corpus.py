"""Reconcile retained CI exports as data; never execute captured upstream code."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[4]
COMMIT = "e02370ab63aaf47356f986bd2a35c20adfe848f1"
RUN = 38294106923
EXPORTS = {
    "python": (11767189393, "da370edb40c9c3bcd0030bbecec0bf1d142a6dca5faafd44c5f58f903190a5a5", 114960944344, "L5 real Python behavioral pair"),
    "go": (11768465101, "9fbdfef0962e483310dc0ea983ed7e9077f4a0c33c64c8e972d492b5116449a0", 114960944638, "L5 real Go behavioral pair"),
}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_export(directory, family, metadata):
    artifact_id, digest, _, _ = EXPORTS[family]
    require(metadata["id"] == artifact_id and metadata["name"] == f"l5-real-{family}", "artifact identity")
    require(metadata["digest"] == "sha256:" + digest and not metadata["expired"], "official artifact digest")
    require(metadata["workflow_run"]["id"] == RUN and metadata["workflow_run"]["head_sha"] == COMMIT, "artifact run binding")
    archive = directory / f"l5-real-{family}.zip"
    require(sha(archive) == digest and archive.stat().st_size == metadata["size_in_bytes"], "ZIP integrity")
    extracted = directory / family
    paths = list(extracted.rglob("*"))
    require(all(not p.is_symlink() and (p.is_file() or p.is_dir()) for p in paths), "nonregular exported file")
    actual = {p.relative_to(extracted).as_posix() for p in paths if p.is_file()}
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        require(len(entries) < 200 and sum(i.file_size for i in entries) < 100_000_000, "ZIP bounds")
        names = []
        for i in entries:
            name = PurePosixPath(i.filename)
            require(not name.is_absolute() and ".." not in name.parts and str(name) == i.filename.rstrip("/"), "unsafe ZIP path")
            require(not stat.S_ISLNK(i.external_attr >> 16), "ZIP symlink")
            if not i.is_dir():
                mode = i.external_attr >> 16
                require(stat.S_IFMT(mode) in (0, stat.S_IFREG), "ZIP nonregular member")
                names.append(i.filename)
                require((extracted / i.filename).is_file() and (extracted / i.filename).read_bytes() == z.read(i), "extracted bytes differ from ZIP")
        require(len(names) == len(set(names)) and set(names) == actual, "export file closure")
    return {"artifact_id": artifact_id, "zip_sha256": digest, "zip_bytes": archive.stat().st_size, "files": len(names)}


def load_verifier(family):
    path = Path(__file__).with_name(f"verify_{family}_export.py")
    spec = importlib.util.spec_from_file_location(f"c02_{family}_export", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def reconcile(directory):
    directory = Path(directory)
    run = json.loads((directory / "run.json").read_text())
    require(run["databaseId"] == RUN and run["headSha"] == COMMIT, "frozen CI code binding")
    require(run["status"] == "completed" and run["conclusion"] == "success", "CI completion")
    require(run["url"] == f"https://github.com/wkoch/xrai/actions/runs/{RUN}", "CI repository")
    jobs = {j["databaseId"]: j for j in run["jobs"]}
    require(len(jobs) == len(run["jobs"]) == 2, "CI job set")
    artifacts = json.loads((directory / "artifacts.json").read_text())
    require(artifacts["total_count"] == len(artifacts["artifacts"]) == 2, "artifact set")
    exports = {a["name"]: a for a in artifacts["artifacts"]}
    require(set(exports) == {"l5-real-python", "l5-real-go"}, "artifact names")
    provenance, families = {}, {}
    for family, (_, _, job_id, job_name) in EXPORTS.items():
        job = jobs.get(job_id, {})
        require(job.get("name") == job_name and job.get("status") == "completed" and job.get("conclusion") == "success", "successful family job")
        provenance[family] = verify_export(directory, family, exports[f"l5-real-{family}"])
        families[family] = load_verifier(family).verify(directory / family)
        require(families[family].get("verified") is True, "family verification")
    sources = [Path(__file__), Path(__file__).with_name("verify_python_export.py"), Path(__file__).with_name("verify_go_export.py")]
    for family in families:
        sources += [ROOT / f"eval/qualification/l5-real/{family}/agent/input.md", ROOT / f"eval/qualification/l5-real/{family}/oracles/{'probe.py' if family == 'python' else 'xrai_url_contract_test.go'}"]
    # Case-specific fingerprints are verified by each independent family verifier.
    require(all(p.is_file() for p in sources), "missing verifier source fingerprint")
    return {"verified": True, "data_only": True, "run_id": RUN, "code_commit": COMMIT,
            "families": families, "export_provenance": provenance,
            "sources_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in sources},
            "admitted": False, "competitive_execution": False,
            "limits": ["Controlled contracts; no complete upstream suite or historical bug claim.",
                       "Runtime binary hashes are producer reports; binary bytes are not retained in these exports.",
                       "No state/config A-to-B proof; four family state/config cases remain to be selected.",
                       "Official metadata is retained from authenticated GitHub API; no offline signature attestation."]}


if __name__ == "__main__":
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("ci-next-first")
    print(json.dumps(reconcile(directory), indent=2, sort_keys=True))
