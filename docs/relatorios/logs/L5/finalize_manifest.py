"""Bind the integrated source generation and preserved baseline to local receipts."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
destination = ROOT / "docs/relatorios/logs/L5/integration/source-manifest-final.json"
if destination.exists():
    raise SystemExit("existing evidence is immutable")


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def digest(content):
    return hashlib.sha256(content).hexdigest()


changed = git("diff", "--name-only", "HEAD").decode().splitlines()
untracked = git("ls-files", "--others", "--exclude-standard").decode().splitlines()
prefixes = ("crates/", "eval/context/", "eval/workers/", "eval/scripts/",
            "eval/qualification/", "docs/contracts/", ".github/")
sources = sorted({path for path in changed + untracked if path.startswith(prefixes)})
sources += ["docs/relatorios/logs/L5/collect.py", "docs/relatorios/logs/L5/finalize_manifest.py"]
tracked = git("ls-files").decode().splitlines()
allowed_existing = {"crates/xrai-eval/src/lib.rs", "docs/contracts/m1.md",
                    "eval/reports/m0-agent-readiness.md", "eval/reports/m0-workers-persistent.md"}
preserved = [path for path in tracked
             if (path in {"Cargo.toml", "Cargo.lock"}
                 or path.startswith(("crates/", "eval/", "docs/contracts/")))
             and path not in allowed_existing]
baseline = git("rev-parse", "HEAD").decode().strip()
historical = {}
for path in sorted(set(preserved)):
    previous = git("show", f"{baseline}:{path}")
    current = (ROOT / path).read_bytes()
    if previous != current:
        raise SystemExit(f"protected baseline changed: {path}")
    historical[path] = digest(current)
receipts = sorted((ROOT / "docs/relatorios/logs/L5/integration").glob("*.json"))
document = {
    "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "base_commit": baseline,
    "scope": "Integrated source/config/fixtures; native CI reconciled in subsequent receipt",
    "source_sha256": {path: digest((ROOT / path).read_bytes()) for path in sources},
    "protected_baseline_sha256": historical,
    "receipt_sha256": {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in receipts},
}
destination.write_text(json.dumps(document, indent=2) + "\n")
print(json.dumps({"sources": len(sources), "preserved": len(historical),
                  "receipts": len(receipts), "manifest": str(destination.relative_to(ROOT))}))
