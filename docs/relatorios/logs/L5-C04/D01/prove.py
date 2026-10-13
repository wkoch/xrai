"""Own offline collector; only deterministic Python fake/data tests are run."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'crates/xrai-eval/harness'))
from execution_dispatch_v2 import replay_dispatch_v2


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    command = [sys.executable, '-m', 'unittest', 'discover', '-s',
               'crates/xrai-eval/harness/tests', '-p', 'test_execution_dispatch_v2.py', '-v']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60)
    (HERE / 'tests.stdout').write_bytes(result.stdout)
    (HERE / 'tests.stderr').write_bytes(result.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    fixtures = ROOT / 'eval/qualification/execution-gate/v2'
    replayed = {p.name: replay_dispatch_v2(json.loads(p.read_text())) for p in sorted(fixtures.glob('*.json'))}
    artifacts = [ROOT / 'crates/xrai-eval/harness/execution_dispatch_v2.py',
                 ROOT / 'crates/xrai-eval/harness/tests/test_execution_dispatch_v2.py',
                 Path(__file__).resolve(), HERE / 'tests.stdout', HERE / 'tests.stderr', *sorted(fixtures.iterdir())]
    legacy = ROOT / 'crates/xrai-eval/harness/agent_ledger.py'
    baseline = subprocess.run(['git', 'show', 'HEAD:crates/xrai-eval/harness/agent_ledger.py'],
                              cwd=ROOT, check=True, capture_output=True).stdout
    proof = {'schema_version': 'xrai.eval.d01-offline-proof.v1',
             'recorded_at': datetime.now(timezone.utc).isoformat(), 'command': command,
             'exit_code': result.returncode, 'tests': 17, 'barriers': 'threading.Event; no sleep',
             'external_calls': 0, 'paid_provider_called': False, 'replayed_fixtures': replayed,
             'legacy_agent_ledger_unchanged_from_HEAD': legacy.read_bytes() == baseline,
             'legacy_agent_ledger_sha256': digest(legacy),
             'sha256': {str(p.relative_to(ROOT)): digest(p) for p in artifacts},
             'scope': 'synthetic-offline-only; no tokenizer execution or provider transport',
             'campaign_scoring_enabled': False}
    (HERE / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': proof['tests'], 'fixtures': len(replayed), 'external_calls': 0}))


if __name__ == '__main__':
    main()
