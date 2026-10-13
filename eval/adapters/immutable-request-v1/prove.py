"""Owned diagnostic collector; the transport spy is test-only, not a runtime seam."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
LOG=ROOT/'docs/relatorios/logs/L5-C06/D01-request'
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness/tests'))
from test_immutable_request_dispatch import ImmutableTests,mutate
from immutable_request_dispatch import replay_immutable
from agent_ledger import canonical,sha
from execution_dispatch_v2 import DispatchBarriers,FakeResultV2
import threading


def collect():
    output={}
    for point in ('before_commit','after_commit'):
        case=ImmutableTests();case.setUp();observations=case.barred(point)
        output['caller-'+point]={'immutable_request':case.wrapper.request_record(),'dispatch_v2':case.session.record(),
            'observed_payload_sha256':[sha(raw) for raw in observations['observed']],
            'observed_payloads':[raw.decode() for raw in observations['observed']], 'replay':case.replay(),
            'fake_invocations':case.fake.calls,'caller_payload_sha256_after':sha(canonical(case.request))}
    case=ImmutableTests();case.setUp();case.make()
    thread,observed,results,errors=case.started(case.dispatch,mutate_adapter=True);case.joined(thread)
    if errors:raise errors[0]
    output['transport-disposable']={'immutable_request':case.wrapper.request_record(),'dispatch_v2':case.session.record(),
        'observed_payload_sha256':[sha(raw) for raw in observed],'observed_payloads':[raw.decode() for raw in observed],
        'replay':case.replay(),'fake_invocations':case.fake.calls,'caller_payload_sha256_after':sha(canonical(case.request))}
    for point in ('before_commit','after_commit'):
        case=ImmutableTests();case.setUp();reached,release=threading.Event(),threading.Event()
        case.make(DispatchBarriers(**{point+'_reached':reached,point+'_release':release}),[FakeResultV2(response=None)])
        cancel=threading.Event();thread,observed,results,errors=case.started(lambda:case.dispatch(cancel=cancel))
        if not reached.wait(5):raise ValueError('own proof barrier timeout')
        cancel.set();mutate(case.request);release.set();case.joined(thread)
        if errors:raise errors[0]
        output['cancel-'+point]={'immutable_request':case.wrapper.request_record(),'dispatch_v2':case.session.record(),
            'observed_payload_sha256':[sha(raw) for raw in observed],'observed_payloads':[raw.decode() for raw in observed],
            'replay':case.replay(),'fake_invocations':case.fake.calls,'caller_payload_sha256_after':sha(canonical(case.request))}
    case=ImmutableTests();case.setUp();case.test_retry_late_idempotence_preserved()
    output['retry-late']={'immutable_request':case.wrapper.request_record(),'dispatch_v2':case.session.record(),
        'replay':case.replay(),'fake_invocations':case.fake.calls,'observed_payloads':None,'observed_payload_sha256':None,
        'caller_payload_sha256_after':sha(canonical(case.request))}
    return output


if __name__=='__main__':
    proof={'schema_version':'xrai.eval.immutable-request-diagnostic-proof.v1','cases':collect(),
        'source_hashes':{name:sha((ROOT/name).read_bytes()) for name in (
            'crates/xrai-eval/harness/immutable_request_dispatch.py',
            'crates/xrai-eval/harness/tests/test_immutable_request_dispatch.py',
            'eval/adapters/immutable-request-v1/prove.py','eval/adapters/immutable-request-v1/verify.py',
            'eval/adapters/immutable-request-v1/freeze.json')},'scope':'owned offline fake diagnostic; test-only Python profiler spy',
        'provider_calls':0,'agent_runs':0,'campaign_scoring_enabled':False,'provider_charge':None,'model_tokens':None}
    (LOG/'proof.json').write_bytes(canonical(proof))
    print(canonical({'verified':True,'cases':len(proof['cases']),'proof_sha256':sha(canonical(proof))}).decode())
