"""Reconcile native L4 receipts against the published source and pinned profiles."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'crates/xrai-eval/harness'))
sys.path.insert(0, str(ROOT / 'eval/scripts'))
from agent_ledger import replay_versioned
from verify_records import verify as verify_baseline
from verify_semantics import verify as verify_semantics


def read(path):
    return json.loads(path.read_text())


run = read(EVIDENCE / 'ci-native-run.json')
assert run['headSha'] == '1d2d40a221dad1a5ec9188158dbc624f329023c7'
assert run['conclusion'] == 'success' and len(run['jobs']) == 3
assert all(job['conclusion'] == 'success' for job in run['jobs'])
manifest = read(EVIDENCE / 'implementation-manifest.json')
for path, expected in manifest['source_sha256'].items():
    actual = hashlib.sha256(subprocess.check_output(['git', 'show', f"{run['headSha']}:{path}"], cwd=ROOT)).hexdigest()
    assert actual == expected, path
hosts = []
for host in ['x86_64-unknown-linux-gnu', 'aarch64-apple-darwin']:
    native = EVIDENCE / 'ci-native' / ('native-' + host)
    environment = read(native / 'environment.json')
    log = re.sub(r'\x1b\[[0-9;]*m', '', (native / 'workspace-tests.log').read_text())
    counts = {}
    for module, expected in [('workers', 13), ('workers_persistent', 20), ('semantics_spike', 10)]:
        match = re.search(r'Running tests/' + module + r'\.rs.*?test result: ok\. (\d+) passed', log, re.S)
        assert match and int(match[1]) == expected, module
        counts[module] = expected
    assert 'Ran 50 tests' in (native / 'harness-tests.log').read_text()
    assert verify_baseline(native / 'baseline')['count'] == 20
    original = read(native / 'baseline/D0-RS-01.json')
    measurements = {}
    for name in ['offline-derived', 'fake-complete', 'fake-unknown-charge', 'fake-retry-unknown-prior', 'fake-budget-incident']:
        measurements[name] = replay_versioned(read(native / 'measurement' / (name + '.json')), original=original)
    unknown = measurements['fake-unknown-charge']['accounting']
    assert unknown['observed_cost_micro_usd'] is None and unknown['retained_reservation_micro_usd'] == 500
    summary = read(native / 'measurement/summary.json')
    assert summary['legacy_count'] == 20 and summary['paid_provider_calls'] == 0
    for name, expected in summary['implementation_sha256'].items():
        assert hashlib.sha256((ROOT / 'crates/xrai-eval/harness' / name).read_bytes()).hexdigest() == expected
    worker = read(native / 'workers-persistent.json')
    assert worker['protocol'] == 'XRW2' and len(worker['samples']) == 28 and worker['direct_equivalent'] == 29
    assert len(worker['healthy_workers']) == 2 and all(row['direct_equal'] for row in worker['samples'])
    assert len({row['dialect'] for row in worker['samples']}) == 7
    for pid, incarnation in worker['healthy_workers'].items():
        rows = [row for row in worker['samples'] if row['pid'] == int(pid)]
        assert len(rows) > 1 and all(row['incarnation'] == incarnation for row in rows)
    failure = worker['failure']
    assert failure['attempts'] == 2 and failure['healthy_after_failure']
    assert failure['before_pid'] in failure['retired_reaped']
    assert failure['before_pid'] != failure['replacement_pid'] and failure['before_incarnation'] != failure['replacement_incarnation']
    assert worker['reservation']['held_ticket_bytes'] > 0 and worker['reservation']['after_transfer_bytes'] == 0
    assert all(worker[key] is None for key in ['cpu_user_seconds', 'cpu_system_seconds', 'sampled_peak_sum_rss'])
    semantics = {}
    for matrix, output in [('rust-r1-r2', 'semantics-fixtures'), ('tokio-development', 'semantics-tokio'), ('rust-counterproofs', 'semantics-counterproofs')]:
        semantics[matrix] = verify_semantics(ROOT / 'eval/semantics' / (matrix + '.json'), native / (output + '.json'))
    for matrix, count, resolvable in [('rust-r1-r2', 33, 18), ('tokio-development', 4, 3), ('rust-counterproofs', 6, 0)]:
        assert semantics[matrix]['correct'] == count and semantics[matrix]['resolvable_correct'] == resolvable
    hosts.append({'host': host, 'environment': environment, 'rust_tests': counts,
                  'harness_tests': 50, 'baseline_replayed': 20,
                  'controlled_content_tokens': measurements['offline-derived']['controlled_content_tokens'],
                  'persistent_equivalent': 29, 'semantics': semantics,
                  'cpu_rss_proved': False, 'literal_macos_15_0_proved': False})
print(json.dumps({'status': 'native_L4_receipts_verified', 'code_commit': run['headSha'],
                  'run_url': run['url'], 'hosts': hosts, 'competitive_runs_allowed': False}, indent=2))
