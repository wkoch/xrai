"""Concrete public fake consumer, no transport projection or runtime profiler."""
import argparse
import json
from pathlib import Path
import sys
import threading
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
from transport_receipt_session import make_public_fake_session, replay_public_transport, sources
from execution_dispatch_v2 import DispatchBarriers
from agent_ledger import fake_request, fake_receipt, canonical, sha


def collect():
    records={}
    for name,mode in [('response','response'),('pre-entry','pre_entry_refusal'),('exception','exception'),('timeout','timeout'),('no-return','no_return')]:
        owner=make_public_fake_session(outcomes=[mode])
        try:owner.dispatch('attempt-'+name,'call-'+name,fake_request(),500)
        except (RuntimeError,TimeoutError):pass
        records[name]=owner.record(close=True)
    owner=make_public_fake_session(outcomes=['no_return','response'])
    owner.dispatch('attempt-1','call-retry',fake_request(),500)
    owner.dispatch('attempt-2','call-retry',fake_request(),500,retry_of='attempt-1')
    receipt=fake_receipt('public-consumer-late')
    assert owner.reconcile('attempt-1',state='completed',response=b'late public bytes',receipt=receipt)
    assert not owner.reconcile('attempt-1',state='completed',response=b'late public bytes',receipt=receipt)
    records['retry-late']=owner.record(close=True)
    reached,release=threading.Event(),threading.Event()
    owner=make_public_fake_session(barriers=DispatchBarriers(transport_reached=reached,transport_release=release))
    request=fake_request();errors=[]
    def work():
        try:owner.dispatch('attempt-inflight','call-inflight',request,500)
        except Exception as error:errors.append(type(error).__name__)
    thread=threading.Thread(target=work);thread.start()
    assert reached.wait(5)
    records['inflight']=owner.record()
    assert replay_public_transport(records['inflight'],require_closed=False)['verified']
    request['messages'][0]['content']='caller changed after public entry'
    release.set();thread.join(5);assert not thread.is_alive() and not errors
    records['mutated-caller']=owner.record(close=True)
    results={name:replay_public_transport(record,require_closed=name!='inflight') for name,record in records.items()}
    return {'schema_version':'xrai.eval.public-transport-consumer-proof.v1', 'source_bindings':sources(),
            'runtime':sys.version,'records':records,'results':results,'external_calls':0,
            'provider_called':False,'native_called':False,'upstream_imported':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    value=collect();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(canonical(value)+b'\n')
    print(json.dumps({'records':len(value['records']),'source_sha256':value['source_bindings']['crates/xrai-eval/harness/transport_receipt_session.py'],'proof_sha256':sha(args.output.read_bytes())},sort_keys=True))
