"""C03 CLI using explicit D01 v2 commitment for captured offline intent; credentials/providers are unavailable."""
import argparse
import base64
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
from execution_gate import EvidenceSnapshot, preflight, DispatchSession, OfflineAuthorization, FakeAdapter
from agent_ledger import fake_request
from execution_dispatch_v2 import DispatchSessionV2, FakeTransportV2, make_bindings, replay_dispatch_v2


def run(path, dispatch_fake=False, *, task_id="D0-RS-01", arm="direct", run_id="cli-offline-seed"):
    # Defaults explicitly designate the existing synthetic seed, never a real campaign.
    fixture = json.loads(Path(path).read_bytes())
    if fixture.get('scope') != 'synthetic_offline_fixture':
        raise ValueError('this entry point accepts only the declared offline fixture profile')
    evidence = {}
    import hashlib
    for key,row in fixture['evidence'].items():
        raw = base64.b64decode(row['base64'],validate=True)
        if type(row['bytes']) is not int or len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('fixture evidence bytes/digest changed')
        evidence[key] = raw
    snapshot = EvidenceSnapshot.capture(fixture['manifest'], evidence)
    decision = preflight(snapshot)
    result = {'decision':decision.as_dict(),'adapter_calls':0,'external_calls':0,'paid_authorization':False}
    if dispatch_fake and decision.accepted:
        authorization = OfflineAuthorization(snapshot.fingerprint,1000,time.monotonic()+30)
        if decision.intent == 'replay_offline':
            adapter = FakeAdapter()
            session = DispatchSession(snapshot,decision,authorization,adapter)
            result['result'] = session.replay(json.loads(evidence['replay']))
        else:
            adapter = FakeTransportV2()
            bindings = make_bindings(snapshot,task_id=task_id,arm=arm,run_id=run_id)
            session = DispatchSessionV2(snapshot,decision,authorization,adapter,bindings=bindings)
            result['result'] = session.dispatch('cli-attempt','cli-call',fake_request(),500)
            result['dispatch_replay'] = replay_dispatch_v2(session.record())
        result['adapter_calls'] = adapter.calls
        result['ledger'] = session.record()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture',type=Path)
    parser.add_argument('--dispatch-fake',action='store_true')
    parser.add_argument('--task-id',default='D0-RS-01')
    parser.add_argument('--arm',default='direct')
    parser.add_argument('--run-id',default='cli-offline-seed')
    args = parser.parse_args()
    result = run(args.fixture,args.dispatch_fake,task_id=args.task_id,arm=args.arm,run_id=args.run_id)
    print(json.dumps(result,indent=2,sort_keys=True))
    raise SystemExit(0 if result['decision']['accepted'] else 1)
