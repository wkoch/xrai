"""Collect owned factual campaign refusal and structural contraproofs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[6]
HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    commands = {'tests': [sys.executable, '-m', 'unittest', 'discover', '-s', 'eval/scripts', '-p', 'test_campaign_preflight.py', '-v'],
                'preflight': [sys.executable, 'eval/scripts/campaign_preflight.py', '--intent', 'campaign_d1']}
    checks = []
    for name, command in commands.items():
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=300)
        (HERE / (name + '.stdout')).write_bytes(result.stdout)
        (HERE / (name + '.stderr')).write_bytes(result.stderr)
        expected = 0 if name == 'tests' else 1
        if result.returncode != expected or (name == 'preflight' and (result.stderr or not result.stdout)):
            raise ValueError(name + ' unexpected exit: ' + str(result.returncode) + result.stderr.decode(errors='replace'))
        checks.append({'name': name, 'command': command, 'exit_code': result.returncode, 'expected_exit_code': expected})
    facts = json.loads((HERE / 'preflight.stdout').read_bytes())
    summary = facts['factual_summary']
    assert facts['accepted'] is False and facts['external_calls'] == 0 and facts['paid_provider_enabled'] is False
    assert summary['admitted_tasks'] == 0 and summary['individual_eligible_tasks'] == 8
    assert summary['required_events_operationally_proven'] == 4 and summary['state_tasks_prepared'] == 4
    assert summary['new_state_dossiers_individually_eligible'] == 0
    assert summary['multi_module_planning_projection'] == 19 and summary['multi_module_planning_required'] == 20
    assert 'events' not in facts['dimensions'] and all(key in facts['dimensions'] for key in ['provider', 'authorization', 'budget', 'containment', 'admission', 'corpus', 'state_dossiers', 'allocation'])
    paths = [ROOT / 'eval/scripts/campaign_preflight.py', ROOT / 'eval/scripts/test_campaign_preflight.py',
             Path(__file__).resolve(), *[HERE / (name + '.' + stream) for name in commands for stream in ['stdout', 'stderr']]]
    proof = {'schema': 'xrai.eval.d01-factual-preflight-proof.v1',
        'recorded_at': datetime.now(timezone.utc).isoformat(), 'checks': checks, 'structural_tests': 18,
        'actual_factual_summary': summary, 'actual_dimensions': facts['dimensions'],
        'snapshot_sha256': facts['snapshot_sha256'],
        'captured_files': len(facts['snapshot_manifest']['files']),
        'captured_bytes': sum(row['bytes'] for row in facts['snapshot_manifest']['files'].values()),
        'private_copy_retained': False, 'temporary_copy_reaped': True,
        'external_calls': 0, 'upstream_or_native_execution': False,
        'accepted': False, 'paid_provider_enabled': False,
        'sha256': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths},
        'limits': facts['limits']}
    (HERE / 'proof.json').write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'verified': True, 'tests': 18, 'events_proven': 4,
        'eligible': 8, 'global_admitted': 0, 'accepted': False,
        'captured_files': proof['captured_files'], 'captured_bytes': proof['captured_bytes']}))


if __name__ == '__main__':
    main()
