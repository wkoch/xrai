"""Read-only complete public fake transport proof verification."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
from agent_ledger import canonical,sha
from execution_gate import require
from transport_receipt_session import sources,replay_public_transport
DEFAULT=ROOT/'docs/relatorios/logs/L5-C07/Transport/public-consumer.json'
NAMES={'response','pre-entry','exception','timeout','no-return','retry-late','inflight','mutated-caller'}


def verify(path):
    require(path.stat().st_size <= 16*1024*1024,'bounded own proof file')
    raw=path.read_bytes();value=json.loads(raw)
    require(canonical(value)+b'\n'==raw and set(value)=={'schema_version','source_bindings','runtime','records','results','external_calls','provider_called','native_called','upstream_imported'} and value['schema_version']=='xrai.eval.public-transport-consumer-proof.v1','exact canonical proof')
    require(canonical(value['source_bindings'])==canonical(sources()) and set(value['records'])==NAMES and set(value['results'])==NAMES,'source closure and complete concrete fake cases')
    require(value['external_calls']==0 and type(value['external_calls']) is int and all(value[k] is False for k in ('provider_called','native_called','upstream_imported')) and type(value['runtime']) is str,'owned Python-only scope')
    results={name:replay_public_transport(record,require_closed=name!='inflight') for name,record in value['records'].items()}
    require(canonical(results)==canonical(value['results']),'full public transport replay recomputation')
    for name in ('exception','timeout','no-return'):
        require(results[name]['entries']==1 and results[name]['uncertain_outcomes']==1 and results[name]['accounting']['retained_reservation_micro_usd']==500,'uncertain reserve retained')
    require(results['pre-entry']['entries']==0 and results['pre-entry']['commitments']==0 and results['inflight']['closed'] is False and results['retry-late']['entries']==2,'absence/inflight/retry controls')
    return {'verified':True,'records':len(NAMES),'proof_sha256':sha(raw),'public_entries':sum(r['entries'] for r in results.values()),'results':results,'provider_called':False,'native_called':False,'upstream_imported':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--receipt',type=Path,default=DEFAULT);args=parser.parse_args();print(json.dumps(verify(args.receipt),sort_keys=True))
