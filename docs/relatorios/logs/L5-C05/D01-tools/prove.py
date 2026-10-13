"""Own offline capture of the composed guard; no native/upstream/model/network."""
from pathlib import Path
import base64
import json
import platform
import subprocess
import sys
import threading
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[5]
HARNESS=ROOT/'crates/xrai-eval/harness';sys.path.insert(0,str(HARNESS));sys.path.insert(0,str(HARNESS/'tests'))
from session_tool_guard import replay_guard,load_guard,ToolGuardBarriers,SOURCE_PATHS,GuardRefused
from test_session_tool_guard import GuardTests
from execution_dispatch_v2 import FakeResultV2,DispatchBarriers
from agent_ledger import canonical,sha,fake_receipt,fake_request
from agent_adapter_protocol import require
OUT=ROOT/'eval/adapters/guarded-v1';LOG=Path(__file__).resolve().parent
NAMES=('accepted-search-expand','manifest-before-tool','evidence-after-delegate','evidence-during-handler',
    'allowance-revoked-handler','expiry-handler','fake-revoked-blocked','allowance-before-commit',
    'budget-incident','retry-late-usage','two-tools-simultaneous')
old_receipt_path=ROOT/'docs/relatorios/logs/L5-C04/adapter/receipt.json'
old_receipt=json.loads(old_receipt_path.read_bytes())
legacy_paths=('crates/xrai-eval/harness/agent_adapter_protocol.py','crates/xrai-eval/harness/tests/test_agent_adapter_protocol.py',
 'crates/xrai-eval/harness/lexical_retrieval.py','crates/xrai-eval/harness/execution_dispatch_v2.py')
legacy_current={path:sha((ROOT/path).read_bytes()) for path in legacy_paths}
require(all(old_receipt['source_hashes'][path]==digest for path,digest in legacy_current.items()),'historically proven source hashes unchanged')
old_fixtures={name:sha((ROOT/'eval/adapters/experimental-v1'/(name+'.jsonl')).read_bytes()) for name in old_receipt['fixtures']}
require(old_fixtures==old_receipt['fixtures'],'all historical fixture bytes unchanged')
results={}
for name in NAMES:
 test=GuardTests();test.setUp();state='completed'
 if name=='accepted-search-expand':
  record=test.complete()
 else:
  options={}
  reached=threading.Event();release=threading.Event()
  if name=='evidence-after-delegate':options['guard_barriers']=ToolGuardBarriers(reached,release);release.set()
  if name=='allowance-before-commit':options['dispatch_barriers']=DispatchBarriers(before_commit_reached=reached,before_commit_release=release)
  if name=='fake-revoked-blocked':options.update(outcomes=[FakeResultV2(response=None)],dispatch_barriers=DispatchBarriers(transport_reached=reached,transport_release=release))
  if name=='budget-incident':
   receipt=fake_receipt('incident-fixture');receipt['observed_charge_micro_usd']=501;options['outcomes']=[FakeResultV2(receipt=receipt)]
  if name=='retry-late-usage':options['outcomes']=[FakeResultV2(response=None),FakeResultV2(response=None)]
  test.make(**options)
  if name in ('allowance-before-commit','fake-revoked-blocked'):
   thread,values,errors=test.threaded(test.dispatch);require(reached.wait(5),'own fake barrier reached')
   if name=='allowance-before-commit':test.authorization.revoked=True
   else:test.guard.revoke()
   release.set();test.joined(thread);require(not values and len(errors)==1 and isinstance(errors[0],GuardRefused),'fake boundary refusal observed');state='cancelled'
  else:
   try:test.dispatch()
   except GuardRefused:require(name=='budget-incident','expected fake dispatch refusal')
   if name=='manifest-before-tool':
    test.manifest['configuration']['input_tokens']=99
    try:test.guard.recover('r','recover')
    except GuardRefused:pass
    else:raise AssertionError('mutated manifest accepted')
    state='partial'
   elif name=='evidence-after-delegate':
    release.clear();reached.clear();thread,values,errors=test.threaded(lambda:test.guard.recover('r','recover'))
    require(reached.wait(5),'delegated result barrier reached');test.evidence['controls']+=b'changed';release.set();test.joined(thread)
    require(not values and len(errors)==1 and isinstance(errors[0],GuardRefused),'recorded tool result refused');state='partial'
   elif name in ('evidence-during-handler','allowance-revoked-handler','expiry-handler'):
    test.handler.enter=threading.Event();test.handler.release=threading.Event()
    thread,values,errors=test.threaded(lambda:test.guard.recover('r','recover'));require(test.handler.enter.wait(5),'handler barrier reached')
    if name=='evidence-during-handler':test.evidence['configuration']+=b'changed';state='partial'
    elif name=='allowance-revoked-handler':test.authorization.revoked=True;state='cancelled'
    else:test.now=100;state='timeout'
    test.handler.release.set();test.joined(thread);require(not values and len(errors)==1 and isinstance(errors[0],GuardRefused),'handler output not returned')
   elif name=='budget-incident':
    try:test.guard.recover('r','recover')
    except GuardRefused:pass
    else:raise AssertionError('incident admitted tool')
    state='error'
   elif name=='retry-late-usage':
    test.guard.dispatch_fake('attempt-2','call-1',fake_request(),500,retry_of='attempt-1')
    receipt=fake_receipt('late-fixture');require(test.guard.reconcile_fake('attempt-2',state='completed',response=b'late fake',receipt=receipt),'first late receipt applied')
    require(not test.guard.reconcile_fake('attempt-2',state='completed',response=b'late fake',receipt=receipt),'repeated late receipt idempotent')
   elif name=='two-tools-simultaneous':
    test.handler.enter=threading.Event();test.handler.release=threading.Event()
    a,av,ae=test.threaded(lambda:test.guard.recover('a','recover'));require(test.handler.enter.wait(5),'first handler');test.handler.enter.clear()
    b,bv,be=test.threaded(lambda:test.guard.recover('b','query'));require(test.handler.enter.wait(5),'second handler');test.handler.release.set();test.joined(a);test.joined(b)
    require(not ae and not be and len(av)==len(bv)==1,'two correlated returned results')
  record=test.guard.finish(state,b'explicit guarded scripted terminal; not judged')
 raw=canonical(record)+b'\n';(OUT/(name+'.json')).write_bytes(raw);verified=replay_guard(load_guard(raw))
 results[name]={'sha256':sha(raw),'bytes':len(raw),'state':state,'replay':verified,
  'fake_invocations':test.fake.calls,'owned_handler_invocations':len(test.handler.calls)}
(LOG/'fixtures-replay.json').write_bytes(canonical(results)+b'\n')
command=[sys.executable,'-m','unittest','discover','-s','crates/xrai-eval/harness/tests','-p','test_session_tool_guard.py']
result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=120,env={'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'})
(LOG/'tests.stdout').write_bytes(result.stdout);(LOG/'tests.stderr').write_bytes(result.stderr)
sources=SOURCE_PATHS+('crates/xrai-eval/harness/tests/test_session_tool_guard.py',
 'docs/relatorios/logs/L5-C05/D01-tools/prove.py','eval/adapters/guarded-v1/verify.py')
receipt={'schema_version':'xrai.eval.session-tool-guard-proof.v1','command':command,'exit_code':result.returncode,
 'interpreter':{'implementation':platform.python_implementation(),'version':list(sys.version_info[:3]),'executable':sys.executable},
 'source_hashes':{path:sha((ROOT/path).read_bytes()) for path in sources},
 'historical_receipt_sha256':sha(old_receipt_path.read_bytes()),'historical_sources_unchanged':legacy_current,
 'historical_fixtures_unchanged':old_fixtures,'fixtures':{name:row['sha256'] for name,row in results.items()},
 'scope':'owned Python/fake only','native_execution':False,'upstream_execution':False,'network_calls':0,
 'provider_calls':0,'agent_runs':0,'campaign_scoring_enabled':False,'model_tokens':None,'provider_charge':None}
(LOG/'receipt.json').write_bytes(canonical(receipt)+b'\n')
print(json.dumps({'exit_code':result.returncode,'fixtures':len(results),'provider_calls':0,'agent_runs':0}))
raise SystemExit(result.returncode)
