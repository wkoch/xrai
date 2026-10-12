"""Offline L4-01 evidence from existing local transcripts and fake transport."""
import argparse
import json
from pathlib import Path

from agent_ledger import Ledger, fake_metadata, fake_receipt, fake_request, fake_session, readiness, replay_versioned
from offline_measurement import measure, tokenizer
from runner import canonical, sha


def demonstrate(baseline, output):
    baseline, output = Path(baseline), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records = sorted(baseline.glob('D0-*.json'))
    if len(records) != 20:
        raise ValueError('demonstration requires all20 existing D0 local transcripts')
    legacy = []
    for path in records:
        before = path.read_bytes()
        value = json.loads(before)
        result = replay_versioned(value)
        if path.read_bytes() != before:
            raise ValueError('historical transcript changed')
        legacy.append({'record': path.name, 'record_file_sha256': sha(before), 'replay': result})
    original = json.loads((baseline / 'D0-RS-01.json').read_text())
    derived = measure(original, tools=[{'name': 'read_source', 'input': {'path': 'relative_path'}}])
    fixtures = {'offline-derived': derived, 'fake-complete': fake_session(), 'fake-unknown-charge': fake_session(True)}
    retry = Ledger(fake_metadata(), 1000)
    retry.reserve('a1', 'c1', fake_request(), 500, timestamp=0)
    retry.send('a1', timestamp=1)
    retry.chunk('a1', b'partial', timestamp=2)
    retry.finish('a1', 'timeout', timestamp=3)
    retry.reserve('a2', 'c1', fake_request(), 500, timestamp=4, retry_of='a1')
    retry.send('a2', timestamp=5)
    retry.chunk('a2', b'fake retry completed', timestamp=6)
    retry.finish('a2', 'completed', timestamp=7)
    retry.receipt('a2', fake_receipt('fake-retry-receipt'), timestamp=8)
    fixtures['fake-retry-unknown-prior'] = retry.record()
    incident = Ledger(fake_metadata(), 1000)
    incident.reserve('a1', 'c1', fake_request(), 500, timestamp=0)
    incident.send('a1', timestamp=1)
    incident.finish('a1', 'completed', timestamp=2)
    excessive = fake_receipt('fake-budget-incident'); excessive['observed_charge_micro_usd'] = 600
    incident.receipt('a1', excessive, timestamp=3)
    incident.reserve('a2', 'c2', fake_request(), 500, timestamp=4)
    fixtures['fake-budget-incident'] = incident.record()
    results = {}
    for name, record in fixtures.items():
        results[name] = replay_versioned(record, original=original)
        (output / (name + '.json')).write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    ready = {'D0': readiness(), 'D1': readiness(dataset='D1'), 'macOS-D0': readiness(platform='Darwin')}
    (output / 'readiness.json').write_text(json.dumps(ready, indent=2) + '\n')
    _, profile = tokenizer()
    summary = {'schema_version': 'xrai.eval.measurement-demonstration.v1', 'legacy_count': len(legacy),
               'legacy_records': legacy, 'demonstrations': results, 'readiness': ready,
               'profile_fingerprint_sha256': profile['fingerprint_sha256'],
               'paid_provider_calls': 0, 'agent_success': None, 'competitive_cost': None,
               'historical_records_mutated': False,
               'implementation_sha256': {name: sha(Path(__file__).with_name(name).read_bytes())
                                         for name in ['offline_measurement.py', 'agent_ledger.py', 'demonstrate_measurement.py']}}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(demonstrate(args.baseline, args.output), indent=2, ensure_ascii=False))
