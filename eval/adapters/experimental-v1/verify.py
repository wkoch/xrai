"""Read-only evidence verification. Executes only owned Python validators, never producers in receipts."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
LOG=ROOT/'docs/relatorios/logs/L5-C04/adapter'
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
from agent_adapter_protocol import (replay_adapter, comparator_preflight, TOOL_SCHEMA, VERSION,
    canonical, sha, decode, require, exact, MAX_FRAME_BYTES, MAX_TRANSCRIPT_BYTES, MAX_EVENTS)

NAMES=('cancelled-revoked','completed-bm25','completed-tfidf','error-before-transport',
       'late-usage-idempotent','partial-unanswered','timeout-unknown')
SOURCE_PATHS=('crates/xrai-eval/harness/agent_adapter_protocol.py',
 'crates/xrai-eval/harness/tests/test_agent_adapter_protocol.py',
 'crates/xrai-eval/harness/lexical_retrieval.py','crates/xrai-eval/harness/execution_dispatch_v2.py',
 'docs/PROVA-DE-DIFERENCIACAO.md','docs/PLANO-DE-IMPLEMENTACAO.md','docs/relatorios/REVISAO-L4.md',
 'eval/adapters/experimental-v1/verify.py','docs/relatorios/logs/L5-C04/adapter/prove.py')


def read_bounded(path, maximum):
    require(path.is_file() and not path.is_symlink(), 'owned regular evidence file: '+str(path))
    require(path.stat().st_size <= maximum, 'evidence byte bound: '+str(path))
    raw=path.read_bytes()
    require(len(raw)<=maximum, 'actual evidence byte bound')
    return raw


def data(path):
    raw=read_bounded(path,MAX_FRAME_BYTES)
    value=decode(raw)
    require(raw==canonical(value)+b'\n', 'canonical evidence JSON: '+str(path))
    return value


def verify():
    receipt=data(LOG/'receipt.json')
    require(set(receipt)=={'schema','command','exit_code','execution_scope','network_calls','native_builds',
        'provider_calls','tokens_measured','pricing_claimed','agent_runs','source_hashes','fixtures','interpreter'}, 'receipt exact fields')
    require(receipt['schema']=='xrai.eval.adapter-proof.v1' and receipt['execution_scope']=='owned Python / lexical sources / D01 fake only', 'offline proof profile')
    for key in ['exit_code','network_calls','native_builds','provider_calls','agent_runs']:
        require(type(receipt[key]) is int and receipt[key]==0, 'exact zero execution observation: '+key)
    require(receipt['tokens_measured'] is False and receipt['pricing_claimed'] is False, 'unavailable model measurements')
    command=receipt['command']
    require(type(command) is list and len(command)==8 and type(command[0]) is str and bool(command[0]) and
        command[1:]==['-m','unittest','discover','-s','crates/xrai-eval/harness/tests','-p','test_agent_adapter_protocol.py'], 'observed own test command')
    interpreter=receipt['interpreter']
    require(type(interpreter) is dict and set(interpreter)=={'implementation','version','executable'} and interpreter['implementation']=='CPython' and interpreter['executable']==command[0], 'recorded owned Python identity')
    version=interpreter['version']
    require(type(version) is list and len(version)==3 and all(type(part) is int and part>=0 for part in version) and version[0]==3 and version[1]>=10, 'positive compatible historical Python version')
    require(type(receipt['source_hashes']) is dict and set(receipt['source_hashes'])==set(SOURCE_PATHS), 'complete current verifier source closure')
    current={path:read_bounded(ROOT/path,16*MAX_FRAME_BYTES) for path in SOURCE_PATHS}
    require(all(sha(raw)==receipt['source_hashes'][path] for path,raw in current.items()), 'current own source bytes changed since receipt')
    expected_protocol={'schema':VERSION,'execution_kind':'scripted_retrieval','transport':'D01-offline-fake-only',
        'tools':TOOL_SCHEMA,'limits':{'frame_bytes':MAX_FRAME_BYTES,'transcript_bytes':MAX_TRANSCRIPT_BYTES,'events':MAX_EVENTS,
            'query_utf8_bytes':4096,'top_k':[1,20],'expansion_ids':[1,20],'response_wire_bytes':[256,524288]},
        'measurements':{'exact_json_bytes':True,'provider_wire':'unknown','tokenizer_execution':'not_measured',
            'model_tokens':None,'provider_usage':None,'provider_charge':None,'virtual_accounting':'D01 synthetic only'},
        'agent_run':False,'campaign_scoring_enabled':False,'judgment':'not_judged'}
    require(exact(data(HERE/'protocol.json'),expected_protocol), 'protocol parameters/unknown/paid flags changed')
    comparison=comparator_preflight(data(HERE/'comparator-plan.json'),current_source=current['docs/PROVA-DE-DIFERENCIACAO.md'])
    require(exact(data(LOG/'comparator-preflight.json'),comparison) and comparison['accepted'] is False and len(comparison['configurations'])==8, 'eight comparator refusal recomposition')
    fixture_files=sorted(HERE.glob('*.jsonl'))
    require([path.stem for path in fixture_files]==list(NAMES), 'exact seven scripted fixtures; no missing/additional run')
    fixtures=data(LOG/'fixtures-replay.json')
    require(type(fixtures) is dict and set(fixtures)==set(NAMES) and type(receipt['fixtures']) is dict and set(receipt['fixtures'])==set(NAMES), 'complete fixture receipt/map')
    results={}
    for path in fixture_files:
        raw=read_bounded(path,MAX_TRANSCRIPT_BYTES); item=fixtures[path.stem]
        require(type(item) is dict and set(item)=={'sha256','bytes','replay','fake_invocations','owned_handler_calls'}, 'typed fixture evidence fields')
        require(type(item['bytes']) is int and item['bytes']==len(raw) and item['sha256']==sha(raw)==receipt['fixtures'][path.stem], 'fixture actual SHA/bytes receipt agreement')
        result=replay_adapter(raw)
        require(exact(item['replay'],result), 'typed whole replay result differs from evidence')
        events=[decode(frame) for frame in raw.splitlines()]
        ledger=next(event['details']['d01_record'] for event in reversed(events) if event['kind']=='ledger_snapshot')
        fake_calls=sum(row['committed'] and not row['transport_proven_absent'] for row in ledger['attempts'].values())
        tool_calls=sum(event['kind']=='tool_request' for event in events)
        require(type(item['fake_invocations']) is int and item['fake_invocations']==fake_calls and type(item['owned_handler_calls']) is int and item['owned_handler_calls']==tool_calls, 'typed scripted invocation accounting')
        require(result['agent_run'] is False and result['competitive_runs_allowed'] is False and type(result['external_calls']) is int and result['external_calls']==0, 'no authority or external execution inferred')
        results[path.stem]={'sha256':sha(raw),'bytes':len(raw),'verified':True}
    require(all(read_bounded(ROOT/path,16*MAX_FRAME_BYTES)==raw for path,raw in current.items()), 'source closure changed during verification')
    return {'schema':'xrai.eval.adapter-evidence-verification.v1','verified':True,'fixtures':results,
        'comparator_refusals':8,'agent_runs':0,'provider_calls':0,'campaign_scoring_enabled':False}


if __name__=='__main__':
    try:
        print(canonical(verify()).decode())
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(1)
