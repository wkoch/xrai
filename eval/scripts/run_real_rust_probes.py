#!/usr/bin/env python3
"""Trusted evaluator probes for RA23422; Linux disposable CI domain only.

This guard is not containment. The calling harness/CI provides the disposable domain.
Never executes the upstream project on the known local macOS host.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import platform
import shutil
import sys

from collect_real_rust import CASE, inventory, members, sha
from run_vertical_probes import run_process, succeeded
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "crates/xrai-eval/harness"))
from runner import execute
from supervisor import verify_receipt


def contained(command, workspace, logs, name):
    record = execute(command, workspace, timeout=600, output_limit=1024 * 1024,
                     phase="upstream_behavioral_probe", arbitrary_agent=True)
    verify_receipt(record)
    logs.mkdir(parents=True, exist_ok=True)
    (logs / (name + ".json")).write_text(json.dumps(record, indent=2) + "\n")
    parts = []
    for stream in ["stdout", "stderr"]:
        raw = base64.b64decode(record[stream]["base64"], validate=True)
        (logs / (name + "." + stream + ".log")).write_bytes(raw)
        parts.append(raw)
    clean = record["eligible_for_agent_run"] and record["cleanup_status"] == "confirmed" and not any(record[s]["truncated"] for s in ["stdout", "stderr"])
    return record, b"\n".join(parts).decode("utf-8", "replace"), clean


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--domain-id", required=True, help="External disposable domain receipt identity")
    args = parser.parse_args()
    if platform.system() != "Linux" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("requires disposable Linux GitHub Actions domain supplied by harness; no local upstream execution")
    if args.output.exists():
        raise ValueError("new output required; preserve previous attempts")
    args.output.mkdir(parents=True)
    work = args.output / "work"
    work.mkdir()
    summary = {"domain_id": args.domain_id, "guard_is_containment": False,
               "execution_domain": "harness bubblewrap user/PID/network namespace, confirmed teardown per command",
               "platform": platform.platform(), "machine": platform.machine(), "results": {},
               "vertical_pair_verified": False, "admitted": False, "competitive_runs_allowed": False,
               "runner_sha256": sha(Path(__file__).read_bytes()),
               "bounded_process_runner_sha256": sha((Path(__file__).parent / "run_vertical_probes.py").read_bytes())}
    try:
        for side in ["baseline", "reference"]:
            expected = json.loads((CASE / (side + "-inventory.json")).read_text())
            archive = CASE / (side + ".tar.gz")
            if inventory(archive) != expected:
                raise ValueError(side + " source inventory mismatch")
            if shutil.disk_usage(args.output).free < 2 * 1024 ** 3:
                raise ValueError("less than 2GiB before fresh upstream build")
            checkout = (work / side).resolve()
            checkout.mkdir(parents=True)
            for name, blob, mode in members(archive):
                out = checkout / name
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(blob)
                out.chmod(mode)
            lock_before = sha((checkout / "Cargo.lock").read_bytes())
            hidden = CASE / "oracles/non_exhaustive_let.rs"
            (checkout / "crates/ide-diagnostics/src/handlers/non_exhaustive_let.rs").write_bytes(hidden.read_bytes())
            logs = args.output / side
            env = dict(os.environ)
            env.update(RUSTUP_TOOLCHAIN="1.98.1", CARGO_TARGET_DIR=str((work / (side + "-target")).resolve()),
                       CARGO_BUILD_JOBS="2", CARGO_PROFILE_DEV_DEBUG="0", CARGO_PROFILE_TEST_DEBUG="0",
                       CARGO_HOME=str((work / "_cargo").resolve()))
            tooling, _ = run_process(["cargo", "--version"], checkout, env, logs, "tooling")
            if not succeeded(tooling):
                raise ValueError("tooling unavailable")
            prepare, _ = run_process(["cargo", "fetch", "--locked"], checkout, env, logs, "prepare")
            if not succeeded(prepare):
                raise ValueError("dependency preparation failed")
            toolchain = (work / "_toolchain").resolve()
            if not toolchain.exists():
                which, text = run_process(["rustup", "which", "rustc", "--toolchain", "1.98.1"], checkout, env, logs, "toolchain-location")
                if not succeeded(which):
                    raise ValueError("Rust toolchain unavailable")
                origin = Path(Path(which["streams"]["stdout"]["path"]).read_text().strip()).resolve().parents[1]
                # Copies, never writable host hardlinks. Toolchain/cache reside inside sandbox.
                shutil.copytree(origin, toolchain, symlinks=False)
                copied_files = [p for p in toolchain.rglob("*") if p.is_file()]
                summary["toolchain_copy"] = {"file_count": len(copied_files), "source": str(origin),
                                             "copies_no_hardlinks": True,
                                             "cargo_sha256": sha((toolchain / "bin/cargo").read_bytes()),
                                             "rustc_sha256": sha((toolchain / "bin/rustc").read_bytes())}
            command_prefix = ["/usr/bin/env", "PATH=/workspace/_toolchain/bin:/usr/bin:/bin",
                              "CARGO_WORKSPACE_DIR=/workspace/" + side,
                              "CARGO_HOME=/workspace/_cargo", "CARGO_TARGET_DIR=/workspace/" + side + "-target",
                              "RUSTC=/workspace/_toolchain/bin/rustc", "CARGO_BUILD_JOBS=2",
                              "CARGO_PROFILE_DEV_DEBUG=0", "CARGO_PROFILE_TEST_DEBUG=0", "/workspace/_toolchain/bin/cargo"]
            cargo = ["test", "--manifest-path", "/workspace/" + side + "/Cargo.toml", "--locked", "--offline", "-p", "ide-diagnostics"]
            probe, text, clean = contained(command_prefix + cargo + ["regression_23336", "--", "--nocapture"], work.resolve(), logs, "probe")
            names = ["regression_23336_1", "regression_23336_2"]
            if side == "baseline":
                verified = clean and probe["exit_code"] == 101 and "panicked at" in text and all(n in text for n in names) and "2 failed" in text
            else:
                verified = clean and probe["exit_code"] == 0 and all(n in text for n in names) and "2 passed" in text
            entry = {"source_archive_sha256": expected["archive_sha256"], "hidden_test_sha256": sha(hidden.read_bytes()),
                     "namespace_domain_id": probe["domain_id"], "containment": probe["containment"],
                     "cleanup_status": probe["cleanup_status"], "eligible_for_agent_run": probe["eligible_for_agent_run"],
                     "preparation_environment": {k: env[k] for k in ["RUSTUP_TOOLCHAIN", "CARGO_HOME", "CARGO_TARGET_DIR", "CARGO_BUILD_JOBS", "CARGO_PROFILE_DEV_DEBUG", "CARGO_PROFILE_TEST_DEBUG"]},
                     "lock_sha256_before": lock_before, "lock_sha256_after": sha((checkout / "Cargo.lock").read_bytes()),
                     "probe_verified": verified}
            summary["results"][side] = entry
            if entry["lock_sha256_before"] != entry["lock_sha256_after"] or not verified:
                raise ValueError(side + " did not reproduce required behavioral result")
            if side == "reference":
                reg, text, clean = contained(command_prefix + cargo + ["handlers::non_exhaustive_let::tests", "--", "--nocapture"], work.resolve(), logs, "regressions")
                entry["regressions_verified"] = clean and reg["exit_code"] == 0 and "test result: ok." in text and "0 failed" in text and "running 0 tests" not in text
                entry["regressions_domain_id"] = reg["domain_id"]
                if not entry["regressions_verified"]:
                    raise ValueError("reference regressions failed/incomplete")
            # Own targets only, after all relevant command receipts are preserved.
            shutil.rmtree(work / (side + "-target"))
        summary["vertical_pair_verified"] = True
    except (ValueError, OSError, KeyboardInterrupt) as exc:
        summary["error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if summary["vertical_pair_verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
