"""Owned offline collector: fake dispatch + own lexical Python; no network/native/model."""
from pathlib import Path
import json
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[5]
HARNESS=ROOT/'crates/xrai-eval/harness'
sys.path.insert(0,str(HARNESS));sys.path.insert(0,str(HARNESS/'tests'))
from agent_adapter_protocol import comparator_preflight,COMPARATORS,replay_adapter,canonical,sha,TOOL_SCHEMA,VERSION
from test_agent_adapter_protocol import AdapterTests
from execution_dispatch_v2 import FakeResultV2
from agent_ledger import fake_receipt

OUT=ROOT/'eval/adapters/experimental-v1'
LOG=Path(__file__).resolve().parent
source=(ROOT/'docs/PROVA-DE-DIFERENCIACAO.md').read_bytes()
manifest={'schema':'xrai.eval.comparator-plan.v1','mode':'planning_only',
 'source':{'path':'docs/PROVA-DE-DIFERENCIACAO.md','sha256':sha(source)},
 'configurations':[]}
manifest['configurations']=[{'id':name,'regimes':['common_local','best_documented_enriched'],
 'version_pin':None,'installation_receipt':None,'strong_configuration_receipt':None,'exclusion':None} for name in COMPARATORS]
(OUT/'comparator-plan.json').write_bytes(canonical(manifest)+b'\n')
(LOG/'comparator-preflight.json').write_bytes(canonical(comparator_preflight(manifest,current_source=source))+b'\n')
protocol={'schema':VERSION,'execution_kind':'scripted_retrieval','transport':'D01-offline-fake-only',
 'tools':TOOL_SCHEMA,'limits':{'frame_bytes':1048576,'transcript_bytes':8388608,'events':256,
 'query_utf8_bytes':4096,'top_k':[1,20],'expansion_ids':[1,20],'response_wire_bytes':[256,524288]},
 'measurements':{'exact_json_bytes':True,'provider_wire':'unknown','tokenizer_execution':'not_measured',
 'model_tokens':None,'provider_usage':None,'provider_charge':None,'virtual_accounting':'D01 synthetic only'},
 'agent_run':False,'campaign_scoring_enabled':False,'judgment':'not_judged'}
(OUT/'protocol.json').write_bytes(canonical(protocol)+b'\n')
records={}
for name in ['completed-bm25','completed-tfidf','timeout-unknown','error-before-transport',
 'partial-unanswered','cancelled-revoked','late-usage-idempotent']:
 test=AdapterTests();test.setUp()
 if name.startswith('completed'):
  raw=test.complete('tfidf_cosine' if name.endswith('tfidf') else 'bm25')
 else:
  if name in ['timeout-unknown','late-usage-idempotent']:
   test.fake._outcomes=[FakeResultV2(state='sent_no_response',response=None)]
  if name=='error-before-transport':test.fake._outcomes=[FakeResultV2(failure='before_transport')]
  test.dispatch()
  if name=='partial-unanswered':
   test.spy.transform=lambda value:(_ for _ in ()).throw(ValueError('own deterministic error'))
   try:test.adapter.recover('tool-unanswered','recover')
   except ValueError:pass
  if name=='cancelled-revoked':test.session.revoke()
  if name=='late-usage-idempotent':
   receipt=fake_receipt('late-fake-fixture')
   assert test.adapter.reconcile_fake('attempt-1',state='completed',response=b'late scripted response',receipt=receipt)
   assert not test.adapter.reconcile_fake('attempt-1',state='completed',response=b'late scripted response',receipt=receipt)
  state={'timeout-unknown':'timeout','error-before-transport':'error','partial-unanswered':'partial',
   'cancelled-revoked':'cancelled','late-usage-idempotent':'completed'}[name]
  raw=test.adapter.finish(state,b'explicit scripted terminal; not agent judgment')
 (OUT/(name+'.jsonl')).write_bytes(raw)
 result=replay_adapter(raw)
 assert result['external_calls']==0 and not result['agent_run'] and result['provider_charge'] is None
 records[name]={'sha256':sha(raw),'bytes':len(raw),'replay':result,'fake_invocations':test.fake.calls,
 'owned_handler_calls':len(test.spy.calls)}
(LOG/'fixtures-replay.json').write_bytes(canonical(records)+b'\n')
command=[sys.executable,'-m','unittest','discover','-s','crates/xrai-eval/harness/tests','-p','test_agent_adapter_protocol.py']
tests=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=120)
(LOG/'tests.stdout').write_bytes(tests.stdout);(LOG/'tests.stderr').write_bytes(tests.stderr)
owned=['crates/xrai-eval/harness/agent_adapter_protocol.py','crates/xrai-eval/harness/tests/test_agent_adapter_protocol.py',
 'crates/xrai-eval/harness/lexical_retrieval.py','crates/xrai-eval/harness/execution_dispatch_v2.py',
 'docs/PROVA-DE-DIFERENCIACAO.md','docs/PLANO-DE-IMPLEMENTACAO.md','docs/relatorios/REVISAO-L4.md',
 'eval/adapters/experimental-v1/verify.py','docs/relatorios/logs/L5-C04/adapter/prove.py']
receipt={'schema':'xrai.eval.adapter-proof.v1','command':command,'exit_code':tests.returncode,
 'interpreter':{'implementation':platform.python_implementation(),'version':list(sys.version_info[:3]),'executable':sys.executable},
 'execution_scope':'owned Python / lexical sources / D01 fake only','network_calls':0,'native_builds':0,
 'provider_calls':0,'tokens_measured':False,'pricing_claimed':False,'agent_runs':0,'source_hashes':
 {path:sha((ROOT/path).read_bytes()) for path in owned},'fixtures':{name:value['sha256'] for name,value in records.items()}}
(LOG/'receipt.json').write_bytes(canonical(receipt)+b'\n')
print(json.dumps({'exit_code':tests.returncode,'fixtures':len(records),'external_calls':0}))
raise SystemExit(tests.returncode)
