"""Reconcile the published code generation, CI jobs and independent artifact checks."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
CODE = "e4cd4d47090ca93715e82c4623a6a2463af3bdb4"
destination = HERE / "native-receipt.json"
if destination.exists():
    raise SystemExit("existing evidence is immutable")
run = json.loads((HERE / "run-completed.json").read_text())
assert run["headSha"] == CODE and run["conclusion"] == "success"
assert {job["name"] for job in run["jobs"]} == {
    "aarch64-apple-darwin", "x86_64-unknown-linux-gnu", "Documentary contracts"}
assert all(job["conclusion"] == "success" for job in run["jobs"])
manifest = json.loads((ROOT / "docs/relatorios/logs/L5/integration/source-manifest-final.json").read_text())
for path, expected in manifest["source_sha256"].items():
    published = subprocess.check_output(["git", "show", f"{CODE}:{path}"], cwd=ROOT)
    assert hashlib.sha256(published).hexdigest() == expected
    assert (ROOT / path).read_bytes() == published
contexts = {}
for host in ("macos", "linux"):
    for name in ("removed-consumer", "central-hunk"):
        receipt = json.loads((ROOT / f"docs/relatorios/logs/L5/integration/ci-context-{host}-{name}.json").read_text())
        assert receipt["exit_code"] == 0
        result = json.loads(receipt["stdout"])
        assert result["verified"]
        contexts[f"{host}/{name}"] = result
resources = json.loads((HERE / "resource-native-review.json").read_text())
assert resources["verified"] is True
hosts = {}
for directory in sorted((HERE / "artifacts").iterdir()):
    rows = re.findall(r"test result: ok. (\d+) passed; (\d+) failed; (\d+) ignored", (directory / "workspace-tests.log").read_text())
    assert rows and all(int(row[1]) == 0 for row in rows)
    harness = (directory / "harness-tests.log").read_text()
    assert "Ran 50 tests" in harness and "OK (skipped=" in harness
    hosts[directory.name] = {
        "environment": json.loads((directory / "environment.json").read_text()),
        "workspace_passed": sum(int(row[0]) for row in rows),
        "workspace_ignored": sum(int(row[2]) for row in rows),
        "harness_cases": 50,
        "harness_passed": 50 - int(re.search(r"OK \(skipped=(\d+)\)", harness)[1]),
        "harness_skipped": int(re.search(r"OK \(skipped=(\d+)\)", harness)[1]),
    }
files = [path for path in HERE.rglob("*") if path.is_file() and path != destination]
document = {
    "schema": "xrai.eval.l5.native-receipt.v1",
    "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "code_commit": CODE, "run": run["databaseId"], "url": run["url"],
    "all_three_jobs_succeeded": True,
    "source_generation_matches_published_code": len(manifest["source_sha256"]),
    "hosts": hosts, "independent_context_verification": contexts,
    "resource_review": "resource-native-review.json",
    "resource_review_sha256": hashlib.sha256((HERE / "resource-native-review.json").read_bytes()).hexdigest(),
    "file_sha256": {str(path.relative_to(HERE)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)},
    "limits": ["macOS runner is 15.7.9, not literal 15.0", "Experimental development captures and synthetic resource classes",
               "D1 remains 0/32; four new dossiers remain 0/4; M0-06 and M0-09 remain open",
               "Executables were not uploaded; binary hashes cannot be recomputed offline from absent bytes"],
}
destination.write_text(json.dumps(document, indent=2) + "\n")
print(json.dumps({"run": run["databaseId"], "commit": CODE, "hosts": hosts,
                  "independent_context_checks": len(contexts), "hashed_files": len(files)}))
