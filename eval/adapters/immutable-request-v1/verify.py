"""Read-only current-source reconciliation of retained immutable request diagnostic data."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
LOG=ROOT/'docs/relatorios/logs/L5-C06/D01-request'
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
from guarded_smoke import owned,decode,MAX_RECORD_BYTES,canonical,sha,require,exact
from immutable_request_dispatch import replay_immutable,restore


def verify():
    proof=decode(owned(LOG/'proof.json',MAX_RECORD_BYTES),MAX_RECORD_BYTES)
    require(type(proof) is dict and set(proof)=={'schema_version','cases','source_hashes','scope','provider_calls','agent_runs','campaign_scoring_enabled','provider_charge','model_tokens'} and proof['schema_version']=='xrai.eval.immutable-request-diagnostic-proof.v1','exact diagnostic proof')
    expected={'caller-before_commit','caller-after_commit','transport-disposable','cancel-before_commit','cancel-after_commit','retry-late'}
    require(type(proof['cases']) is dict and set(proof['cases'])==expected,'exact six diagnostic scenarios')
    source_names={'crates/xrai-eval/harness/immutable_request_dispatch.py','crates/xrai-eval/harness/tests/test_immutable_request_dispatch.py','eval/adapters/immutable-request-v1/prove.py','eval/adapters/immutable-request-v1/verify.py','eval/adapters/immutable-request-v1/freeze.json'}
    require(set(proof['source_hashes'])==source_names and all(sha(owned(ROOT/name,MAX_RECORD_BYTES))==digest for name,digest in proof['source_hashes'].items()),'diagnostic method closure')
    freeze=decode(owned(ROOT/'eval/adapters/immutable-request-v1/freeze.json',MAX_RECORD_BYTES),MAX_RECORD_BYTES)
    require(freeze['wrapper_absent'] is True and len(freeze['scenarios'])==12 and all(sha(owned(ROOT/path,MAX_RECORD_BYTES))==digest for path,digest in freeze['source_hashes'].items()),'pre-wrapper freeze and unchanged historical modules')
    result={}
    for name,case in proof['cases'].items():
        require(set(case)=={'immutable_request','dispatch_v2','observed_payload_sha256','observed_payloads','replay','fake_invocations','caller_payload_sha256_after'},'typed actual diagnostic case')
        replay=replay_immutable(case['immutable_request'],case['dispatch_v2'],target_kind='dispatch_v2')
        require(exact(replay,case['replay']),'complete prospective replay')
        ledger=case['dispatch_v2'];invocations=sum(row['committed'] and not row['transport_proven_absent'] for row in ledger['attempts'].values())
        require(type(case['fake_invocations']) is int and case['fake_invocations']==invocations,'actual fake invocation evidence')
        if name!='retry-late':
            expected_count=0 if name=='cancel-before_commit' else 1
            require(type(case['observed_payloads']) is list and len(case['observed_payloads'])==expected_count and type(case['observed_payload_sha256']) is list and len(case['observed_payload_sha256'])==expected_count,'actual test-spy invocation cardinality')
            for raw,digest in zip(case['observed_payloads'],case['observed_payload_sha256']):
                require(type(raw) is str and sha(raw.encode())==digest==case['immutable_request']['requests'][0]['payload']['sha256'] and raw.encode()==restore(case['immutable_request']['requests'][0]['payload']),'test-spy payload exactly equals reserved/authoritative bytes')
            if name.startswith('caller-') or name.startswith('cancel-'):
                require(case['caller_payload_sha256_after']!=case['immutable_request']['requests'][0]['payload']['sha256'],'actual caller mutation after capture')
            else:require(case['caller_payload_sha256_after']==case['immutable_request']['requests'][0]['payload']['sha256'],'adapter discard mutation did not modify caller authority')
        else:require(case['observed_payloads'] is None and case['observed_payload_sha256'] is None,'no independent spy claimed for retry')
        require(ledger['accounting']['retained_reservation_micro_usd']==(500 if name in ('cancel-after_commit','retry-late') else 0),'virtual retained uncertainty preserved')
        result[name]={'verified':True,'fake_invocations':invocations,'test_spy_equals_reserved':None if name=='retry-late' else True,'runtime_transport_independent_observation':False,'accounting':ledger['accounting']}
    require(proof['scope']=='owned offline fake diagnostic; test-only Python profiler spy' and all(type(proof[k]) is int and proof[k]==0 for k in ('provider_calls','agent_runs')) and proof['campaign_scoring_enabled'] is False and proof['provider_charge'] is None and proof['model_tokens'] is None,'fake diagnostic boundary')
    return {'verified':True,'cases':result,'provider_calls':0,'agent_runs':0,'model_tokens':None,'provider_charge':None}


if __name__=='__main__':
    try:print(canonical(verify()).decode())
    except (ValueError,KeyError,TypeError,OSError) as error:
        print(str(error),file=sys.stderr);raise SystemExit(1)
