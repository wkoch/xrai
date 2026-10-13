"""Read-only current-source and guarded transcript proof consumer."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
LOG=ROOT/'docs/relatorios/logs/L5-C05/D01-tools'
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
from session_tool_guard import load_guard,replay_guard,SOURCE_PATHS,MAX_RECORD_BYTES
from agent_ledger import canonical,sha
from agent_adapter_protocol import require,exact
NAMES=('accepted-search-expand','manifest-before-tool','evidence-after-delegate','evidence-during-handler',
    'allowance-revoked-handler','expiry-handler','fake-revoked-blocked','allowance-before-commit',
    'budget-incident','retry-late-usage','two-tools-simultaneous')
SOURCES=SOURCE_PATHS+('crates/xrai-eval/harness/tests/test_session_tool_guard.py',
    'docs/relatorios/logs/L5-C05/D01-tools/prove.py','eval/adapters/guarded-v1/verify.py')


def owned(path):
    require(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=MAX_RECORD_BYTES,'ordinary bounded owned proof file')
    raw=path.read_bytes();require(len(raw)<=MAX_RECORD_BYTES,'actual proof byte bound');return raw


def verify():
    receipt=load_guard(owned(LOG/'receipt.json'));expected=load_guard(owned(LOG/'fixtures-replay.json'))
    fields={'schema_version','command','exit_code','interpreter','source_hashes','historical_receipt_sha256',
        'historical_sources_unchanged','historical_fixtures_unchanged','fixtures','scope','native_execution',
        'upstream_execution','network_calls','provider_calls','agent_runs','campaign_scoring_enabled','model_tokens','provider_charge'}
    require(type(receipt) is dict and set(receipt)==fields and receipt['schema_version']=='xrai.eval.session-tool-guard-proof.v1','typed guard receipt')
    require(receipt['scope']=='owned Python/fake only' and receipt['native_execution'] is False and receipt['upstream_execution'] is False and receipt['campaign_scoring_enabled'] is False and receipt['model_tokens'] is None and receipt['provider_charge'] is None,'fake/unknown proof boundary')
    require(all(type(receipt[k]) is int and receipt[k]==0 for k in ('exit_code','network_calls','provider_calls','agent_runs')),'actual zero external/agent observations')
    command=receipt['command'];require(type(command) is list and len(command)==8 and type(command[0]) is str and command[0] and command[1:]==['-m','unittest','discover','-s','crates/xrai-eval/harness/tests','-p','test_session_tool_guard.py'],'recorded own historical command, never executed here')
    interpreter=receipt['interpreter'];require(type(interpreter) is dict and set(interpreter)=={'implementation','version','executable'} and interpreter['implementation']=='CPython' and interpreter['executable']==command[0] and type(interpreter['version']) is list and len(interpreter['version'])==3 and all(type(v) is int and v>=0 for v in interpreter['version']) and interpreter['version'][0]==3 and interpreter['version'][1]>=10,'recorded positive compatible interpreter')
    require(type(receipt['source_hashes']) is dict and set(receipt['source_hashes'])==set(SOURCES),'complete current-source closure')
    source_bytes={path:owned(ROOT/path) for path in SOURCES}
    require(all(sha(raw)==receipt['source_hashes'][path] for path,raw in source_bytes.items()),'current guard/legacy/test/collector/verifier method binding')
    old_raw=owned(ROOT/'docs/relatorios/logs/L5-C04/adapter/receipt.json');old=load_guard(old_raw)
    require(sha(old_raw)==receipt['historical_receipt_sha256'],'historical proof receipt intact')
    require(type(receipt['historical_sources_unchanged']) is dict and set(receipt['historical_sources_unchanged'])=={
        'crates/xrai-eval/harness/agent_adapter_protocol.py','crates/xrai-eval/harness/tests/test_agent_adapter_protocol.py',
        'crates/xrai-eval/harness/lexical_retrieval.py','crates/xrai-eval/harness/execution_dispatch_v2.py'},'historical method subset')
    require(all(sha(owned(ROOT/path))==digest==old['source_hashes'][path] for path,digest in receipt['historical_sources_unchanged'].items()),'historical code unchanged against original receipt')
    require(exact(receipt['historical_fixtures_unchanged'],old['fixtures']) and all(sha(owned(ROOT/'eval/adapters/experimental-v1'/(name+'.jsonl')))==digest for name,digest in old['fixtures'].items()),'all seven historical fixture bytes intact')
    files=sorted(HERE.glob('*.json'));require({p.stem for p in files}==set(NAMES) and len(files)==len(NAMES),'exact eleven new guarded fixtures')
    require(type(expected) is dict and set(expected)==set(NAMES) and type(receipt['fixtures']) is dict and set(receipt['fixtures'])==set(NAMES),'fixture evidence bijection')
    result={}
    for path in files:
        raw=owned(path);entry=expected[path.stem];record=load_guard(raw)
        require(type(entry) is dict and set(entry)=={'sha256','bytes','state','replay','fake_invocations','owned_handler_invocations'} and type(entry['bytes']) is int and entry['bytes']==len(raw) and entry['sha256']==sha(raw)==receipt['fixtures'][path.stem],'actual guarded fixture SHA/bytes')
        replay=replay_guard(record);require(exact(replay,entry['replay']) and record['events'][-1]['details']['state']==entry['state'],'complete typed guarded replay/terminal recomposition')
        ledger=record['session'];fake_calls=sum(row['committed'] and not row['transport_proven_absent'] for row in ledger['attempts'].values())
        require(type(entry['fake_invocations']) is int and entry['fake_invocations']==fake_calls and type(entry['owned_handler_invocations']) is int and entry['owned_handler_invocations']==replay['delegate_tool_calls'],'actual fake/own handler invocation evidence')
        result[path.stem]={'sha256':sha(raw),'accepted_tool_results':replay['accepted_tool_results'],
            'refused_operations':replay['refused_operations'],'retained_but_not_returned_tool_results':replay['retained_but_not_returned_tool_results']}
    require(all(owned(ROOT/path)==raw for path,raw in source_bytes.items()),'source closure changed during read-only verification')
    return {'schema_version':'xrai.eval.session-tool-guard-evidence-verification.v1','verified':True,
        'fixtures':result,'historical_fixtures_unchanged':7,'provider_calls':0,'agent_runs':0,
        'campaign_scoring_enabled':False,'model_tokens':None,'provider_charge':None}


if __name__=='__main__':
    try:print(canonical(verify()).decode())
    except (ValueError,KeyError,TypeError,OSError) as error:
        print(str(error),file=sys.stderr);raise SystemExit(1)
