#!/usr/bin/env python3
"""Recompute this offline consumer proof from repository-owned code only."""
import base64
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'crates/xrai-eval/harness'))
from execution_gate import (EvidenceSnapshot, preflight, DispatchSession,
                            OfflineAuthorization, FakeAdapter, FakeOutcome,
                            make_smoke_fixture)
from agent_ledger import canonical, sha, fake_request, fake_session, replay_agent


def session(manifest, evidence, *, budget=1000, outcomes=None, current_manifest=None):
    snapshot = EvidenceSnapshot.capture(manifest, evidence)
    adapter = FakeAdapter(outcomes)
    value = DispatchSession(snapshot, preflight(snapshot), OfflineAuthorization(
        snapshot.fingerprint, budget, time.monotonic() + 60), adapter,
        current_manifest=current_manifest)
    return value, adapter


def prove():
    manifest, evidence = make_smoke_fixture()
    snapshot = EvidenceSnapshot.capture(manifest, evidence)
    fixture = {'scope': 'synthetic_offline_fixture', 'manifest': manifest,
               'evidence': {k: {'base64': base64.b64encode(v).decode(),
                                'bytes': len(v), 'sha256': sha(v)} for k, v in evidence.items()}}
    fixture_path = ROOT / 'eval/qualification/execution-gate/smoke-offline.json'
    fixture_path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + '\n')
    smoke, smoke_adapter = session(manifest, evidence)
    smoke_result = smoke.dispatch('smoke-1', 'call-1', fake_request(), 500)
    assert smoke_adapter.calls == 1 and smoke_result['status'] == 'completed'
    replay_agent(smoke.record())
    retry, retry_adapter = session(manifest, evidence, budget=500, outcomes=[FakeOutcome('timeout')])
    retry.dispatch('first', 'same-call', fake_request(), 500)
    retry_result = retry.dispatch('second', 'same-call', fake_request(), 500, retry_of='first')
    assert retry_adapter.calls == 1 and retry_result['status'] == 'rejected_before_send'
    assert retry.record()['accounting']['retained_reservation_micro_usd'] == 500
    changed, changed_adapter = session(manifest, evidence, current_manifest=lambda: manifest)
    manifest['configuration']['input_tokens'] = 101
    try:
        changed.dispatch('changed', 'changed-call', fake_request(), 600)
    except ValueError as error:
        changed_reason = str(error)
    else:
        raise AssertionError('configuration mutation passed dispatch')
    assert changed_adapter.calls == 0
    manifest, evidence = make_smoke_fixture()
    manifest['intent'] = 'campaign_d1'
    manifest['dataset'] = {'name': 'D1', 'origin': 'qualified_corpus', 'purpose': 'competitive_campaign'}
    campaign_snapshot = EvidenceSnapshot.capture(manifest, evidence)
    campaign = preflight(campaign_snapshot)
    campaign_adapter = FakeAdapter()
    try:
        DispatchSession(campaign_snapshot, campaign, OfflineAuthorization(campaign_snapshot.fingerprint,
            1000, time.monotonic() + 60), campaign_adapter)
    except ValueError:
        pass
    else:
        raise AssertionError('incomplete campaign reached session')
    assert not campaign.accepted and campaign_adapter.calls == 0
    manifest, _ = make_smoke_fixture()
    original = fake_session()
    manifest['intent'] = 'replay_offline'
    manifest['dataset']['purpose'] = 'offline_replay'
    evidence = {'replay': canonical(original)}
    manifest['evidence_sha256'] = {k: sha(v) for k, v in evidence.items()}
    replay, replay_adapter = session(manifest, evidence)
    replay_result = replay.replay(original)
    assert replay_adapter.calls == 0
    sources = ['crates/xrai-eval/harness/execution_gate.py',
               'crates/xrai-eval/harness/tests/test_execution_gate.py',
               'crates/xrai-eval/harness/agent_ledger.py',
               'docs/relatorios/logs/L5-C03/gate/prove_gate.py']
    result = {'schema_version': 'xrai.eval.execution-gate.proof.v1',
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'command': 'python docs/relatorios/logs/L5-C03/gate/prove_gate.py',
        'sources_sha256': {p: sha((ROOT / p).read_bytes()) for p in sources},
        'fixture_sha256': sha(fixture_path.read_bytes()),
        'snapshot_sha256': snapshot.fingerprint,
        'smoke': {'decision': preflight(snapshot).as_dict(), 'result': smoke_result,
                  'adapter_calls': smoke_adapter.calls, 'ledger': smoke.record()},
        'retry': {'result': retry_result, 'adapter_calls': retry_adapter.calls,
                  'ledger': retry.record()},
        'configuration_mutation': {'refusal': changed_reason, 'adapter_calls': changed_adapter.calls},
        'campaign': {'decision': campaign.as_dict(), 'adapter_calls': campaign_adapter.calls},
        'replay': {'result': replay_result, 'adapter_calls': replay_adapter.calls},
        'network_calls': 0, 'paid_provider_called': False, 'real_containment_proved': False,
        'campaign_scoring_enabled': False}
    (Path(__file__).with_name('proof.json')).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'verified': True, 'smoke_adapter_calls': 1,
                      'campaign_adapter_calls': 0, 'replay_adapter_calls': 0,
                      'proof': str(Path(__file__).with_name('proof.json'))}, sort_keys=True))


if __name__ == '__main__':
    prove()
