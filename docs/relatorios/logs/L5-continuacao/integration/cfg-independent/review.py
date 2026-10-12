#!/usr/bin/env python3
"""Independent, supplementary cfg cases; runs only the project's own spike."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name, value):
    path = OUT / name
    assert not path.exists(), name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

# These expected states are fixed independently before executing the binary.
on = {"feature:on": "known:true", "feature:off": "known:false"}
specs = [
    ("unsupported-first-any", 'any(broken(option), feature="on")', None, on),
    ("unsupported-last-any", 'any(feature="on", broken(option))', None, on),
    ("unsupported-first-all", 'all(broken(option), feature="off")', None, on),
    ("unsupported-last-all", 'all(feature="off", broken(option))', None, on),
    ("unsupported-deep-any", 'any(feature="on", not(all(unix, broken(option))))', None, on),
    ("unsupported-deep-all", 'all(feature="off", any(unix, broken(option)))', None, on),
    ("invalid-not-empty", 'any(feature="on", not())', None, on),
    ("invalid-not-two", 'all(feature="off", not(unix, windows))', None, on),
    ("unsupported-raw-string", 'any(feature="on", feature=r"text")', None, on),
    ("unsupported-numeric-value", 'all(feature="off", feature=17)', None, on),
    ("unsupported-escape", 'any(feature="on", feature="a\\t")', None, on),
    ("unsupported-invalid-key", 'any(feature="on", 17="x")', None, on),
    ("unsupported-extra-comma", 'all(feature="off",,unix)', None, on),
    ("unsupported-unknown-op", 'any(feature="on", xor(unix,windows))', None, on),
    ("valid-trailing-comma-any", 'any(feature="on", unix,)', True, on),
    ("valid-trailing-comma-all", 'all(feature="off", unix,)', False, on),
    ("valid-not-unknown", 'not(unix)', None, on),
    ("valid-any-empty", 'any()', False, {}),
    ("valid-all-empty", 'all()', True, {}),
    ("valid-all-unknown", 'all(feature="on", unix)', None, on),
    ("valid-any-unknown", 'any(feature="off", unix)', None, on),
    ("valid-closed-family", 'not(feature="missing")', True, {"closed:feature":"true"}),
    ("valid-nested-known", 'not(all(feature="off", unix))', True, on),
    ("valid-nested-unknown", 'not(any(feature="off", unix))', None, on),
]
matrix = {"schema_version": 2, "profile": "rust-r3-v1", "cases": []}
for ident, predicate, state, config in specs:
    matrix["cases"].append({"id":ident,"files":{"src/lib.rs":f"#[cfg({predicate})] pub fn target() {{}}"},"root":"src/lib.rs","edition":"2021","configuration":config,"rules":"rust-r3-v1","module":"","path":"target","namespace":"value","expected_state":"resolved" if state is True else "unknown","expected_target":"src/lib.rs:target" if state is True else None,"expected_condition":"known_true" if state is True else "known_false" if state is False else "not_evaluated"})
write("matrix.json", matrix)
paths = ["crates/xrai-eval/src/semantics_spike.rs", "crates/xrai-eval/src/semantics_spike/r3.rs", "crates/xrai-eval/src/bin/semantics-spike.rs", "eval/scripts/verify_semantics.py", "eval/semantics/r3/counterproofs-cfg.json"]
sources = {p:sha(ROOT/p) for p in paths}
binary = ROOT / "target/debug/semantics-spike"
write("labels-first.json", {"at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"matrix_sha256":sha(OUT/"matrix.json"),"sources":sources,"binary_sha256":sha(binary),"main_denominator_unchanged":[34,16]})
command = [str(binary), str(OUT/"matrix.json")]
run = subprocess.run(command, capture_output=True)
(OUT/"run.stdout").write_bytes(run.stdout)
(OUT/"run.stderr").write_bytes(run.stderr)
assert run.returncode == 0, run.stderr
output = json.loads(run.stdout)
spec = importlib.util.spec_from_file_location("independent_verifier", ROOT / "eval/scripts/verify_semantics.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
verified = verifier.verify(OUT/"matrix.json", OUT/"run.stdout")
rows = []
for label, row, (_, predicate, expected, config) in zip(matrix["cases"],output["rows"],specs,strict=True):
    assert verifier.evaluate_cfg(predicate,config) is expected, label["id"]
    conditions = row["snapshot"]["conditions"]
    assert len(conditions)==1, label["id"]
    assert conditions[0]["state"]==label["expected_condition"], label["id"]
    gap = any(g["reason"]=="configuration_not_evaluated" and g["evidence"]==conditions[0]["evidence"] for g in row["snapshot"]["gaps"])
    assert gap == (expected is None), label["id"]
    rows.append({"id":label["id"],"condition":conditions[0]["state"],"result":row["result"]["state"],"configuration_gap":gap})
assert {p:sha(ROOT/p) for p in paths} == sources
write("verification.json",{"at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"command":command,"exit":run.returncode,"stdout_sha256":sha(OUT/"run.stdout"),"stderr_sha256":sha(OUT/"run.stderr"),"verified":verified,"rows":rows,"scope":"24 supplementary cfg cases only; original 34/16 denominator unchanged; no upstream execution or full-compiler equivalence claim"})
print(json.dumps(verified,sort_keys=True))
