"""Public-API composition counterproofs. Sources are owned inert bytes."""
import base64
import copy
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lexical_retrieval
from lexical_retrieval import LexicalIndex
from agent_adapter_protocol import ToolSnapshot,canonical,sha,decode
from execution_gate import EvidenceSnapshot,OfflineAuthorization,make_smoke_fixture
from execution_dispatch_v2 import FakeTransportV2,FakeResultV2,DispatchBarriers,make_bindings
from agent_ledger import fake_request,fake_receipt
from session_tool_guard import (make_guarded_fake_session,ToolGuardBarriers,GuardRefused,
    replay_guard,load_guard,MAX_FRAME_BYTES,MAX_RECORD_BYTES,MAX_EVENTS)


class Spy:
    def __init__(self,index):
        self.index=index;self.calls=[];self.enter=None;self.release=None
        for name in ('snapshot_id','configuration_id','producer_sha256','configuration'):setattr(self,name,getattr(index,name))
    def search(self,*args,**kwargs):
        self.calls.append(('recover',args[0]))
        if self.enter:
            self.enter.set()
            if not self.release.wait(5):raise ValueError('own test barrier timeout')
        return self.index.search(*args,**kwargs)
    def expand(self,*args,**kwargs):
        self.calls.append(('expand',args[0]));return self.index.expand(*args,**kwargs)


def reseal(record):
    for index,event in enumerate(record['events']):
        event['sequence']=index;event['previous_event_sha256']=sha(canonical(record['events'][index-1])) if index else None
    return record


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.manifest,self.evidence=make_smoke_fixture()
        self.snapshot=EvidenceSnapshot.capture(self.manifest,self.evidence)
        self.authorization=OfflineAuthorization(self.snapshot.fingerprint,2500,100)
        self.now=1;self.producer=Path(lexical_retrieval.__file__).read_bytes()
        self.files={'src/query.py':'# café\ndef recover_source():\n    return "query source"\n'.encode(), 'src/other.rs':b'fn unrelated() {}\n'}
        self.handler=Spy(LexicalIndex(self.files,chunk_lines=2,overlap_lines=0))
        self.tool=ToolSnapshot.capture(self.handler,self.files,self.producer)
    def make(self,*,outcomes=None,dispatch_barriers=None,guard_barriers=None):
        self.fake=FakeTransportV2(outcomes)
        self.guard=make_guarded_fake_session(self.snapshot,self.authorization,self.handler,self.tool,
            bindings=make_bindings(self.snapshot,task_id='D0-RS-01',arm='direct',run_id='guard-test'),
            current_manifest=lambda:self.manifest,current_evidence=lambda:self.evidence,
            current_authorization=lambda:self.authorization,current_sources=lambda:self.files,
            current_producer=lambda:self.producer,clock=lambda:self.now,fake_transport=self.fake,
            dispatch_barriers=dispatch_barriers,guard_barriers=guard_barriers)
        return self.guard
    def dispatch(self):return self.guard.dispatch_fake('attempt-1','call-1',fake_request(),500)
    def checked(self,state='completed'):
        record=self.guard.finish(state,b'explicit guarded scripted output')
        return record,replay_guard(record)
    def complete(self):
        self.make();self.dispatch();search=self.guard.recover('recover-1','recover query')
        self.guard.expand('expand-1',[item['id'] for item in search['snippets']])
        return self.checked()[0]
    def threaded(self,call):
        values=[];errors=[]
        def work():
            try:values.append(call())
            except Exception as error:errors.append(error)
        thread=threading.Thread(target=work);thread.start();return thread,values,errors
    def joined(self,thread):thread.join(5);self.assertFalse(thread.is_alive())
    def test_public_factory_checks_search_expand_replay(self):
        result=replay_guard(self.complete())
        self.assertEqual(result['accepted_tool_results'],2);self.assertFalse(result['agent_run'])
        self.assertFalse(result['campaign_scoring_enabled']);self.assertIsNone(result['provider_charge'])
    def test_manifest_mutation_between_dispatch_and_tool_zero_tool_calls(self):
        self.make();self.dispatch();self.manifest['configuration']['input_tokens']=99
        with self.assertRaises(GuardRefused):self.guard.recover('tool-1','recover')
        self.assertEqual(self.handler.calls,[])
        record,result=self.checked('partial');self.assertEqual(result['accepted_tool_results'],0)
        self.assertIn('gate_snapshot_changed',record['session']['invalidated'])
    def test_evidence_mutation_between_dispatch_and_tool_zero_tool_calls(self):
        self.make();self.dispatch();self.evidence['controls']+=b'changed'
        with self.assertRaises(GuardRefused):self.guard.recover('tool-1','recover')
        self.assertEqual(self.handler.calls,[]);self.assertEqual(self.checked('partial')[1]['accepted_tool_results'],0)
    def test_mutation_during_handler_rejects_without_returning_response(self):
        for kind in ('manifest','evidence'):
            with self.subTest(kind=kind):
                self.setUp();self.make();self.dispatch();self.handler.enter=threading.Event();self.handler.release=threading.Event()
                thread,values,errors=self.threaded(lambda:self.guard.recover('r','recover'))
                self.assertTrue(self.handler.enter.wait(5))
                if kind=='manifest':self.manifest['configuration']['output_tokens']=99
                else:self.evidence['protocol']+=b'changed'
                self.handler.release.set();self.joined(thread)
                self.assertEqual(values,[]);self.assertIsInstance(errors[0],GuardRefused)
                record,result=self.checked('partial')
                self.assertEqual(result['accepted_tool_results'],0)
                self.assertEqual(result['retained_but_not_returned_tool_results'],1)
                self.assertIn('tool_result',base64.b64decode(record['delegate']['base64']).decode())
    def test_delegate_recorded_result_retained_after_postcheck_refusal(self):
        reached,release=threading.Event(),threading.Event()
        self.make(guard_barriers=ToolGuardBarriers(reached,release))
        # Barrier applies to dispatch too; release it for the initial fake operation.
        release.set();self.dispatch();release.clear();reached.clear()
        thread,values,errors=self.threaded(lambda:self.guard.recover('r','recover'))
        self.assertTrue(reached.wait(5));self.evidence['configuration']+=b'changed';release.set();self.joined(thread)
        self.assertEqual(values,[]);self.assertIsInstance(errors[0],GuardRefused)
        record,result=self.checked('partial')
        self.assertEqual(result['retained_but_not_returned_tool_results'],1)
        end=next(e for e in record['events'] if e['kind']=='end' and e['details']['operation_id']=='tool:r')
        self.assertFalse(end['details']['accepted']);self.assertIsNotNone(end['details']['result'])
    def test_revoke_during_blocked_handler_lock_is_free(self):
        self.make();self.dispatch();self.handler.enter=threading.Event();self.handler.release=threading.Event()
        thread,values,errors=self.threaded(lambda:self.guard.recover('r','recover'))
        self.assertTrue(self.handler.enter.wait(5))
        revoke,_,rev_errors=self.threaded(self.guard.revoke);self.joined(revoke)
        self.assertFalse(rev_errors);self.handler.release.set();self.joined(thread)
        self.assertEqual(values,[]);self.assertIsInstance(errors[0],GuardRefused)
        self.assertEqual(self.checked('cancelled')[1]['accepted_tool_results'],0)
    def test_invalidate_during_blocked_handler(self):
        self.make();self.dispatch();self.handler.enter=threading.Event();self.handler.release=threading.Event()
        thread,values,errors=self.threaded(lambda:self.guard.recover('r','recover'))
        self.assertTrue(self.handler.enter.wait(5));self.guard.invalidate('context changed');self.handler.release.set();self.joined(thread)
        self.assertFalse(values);self.assertIsInstance(errors[0],GuardRefused)
        self.assertEqual(self.checked('partial')[1]['accepted_tool_results'],0)
    def test_fake_io_does_not_hold_guard_lock(self):
        reached,release=threading.Event(),threading.Event()
        self.make(outcomes=[FakeResultV2(response=None)],dispatch_barriers=DispatchBarriers(transport_reached=reached,transport_release=release))
        thread,values,errors=self.threaded(self.dispatch)
        self.assertTrue(reached.wait(5));revoke,_,rev_errors=self.threaded(self.guard.revoke);self.joined(revoke)
        self.assertFalse(rev_errors);release.set();self.joined(thread)
        self.assertEqual(values,[]);self.assertIsInstance(errors[0],GuardRefused)
        record,result=self.checked('cancelled');self.assertEqual(self.fake.calls,1)
        self.assertEqual(result['virtual_accounting']['retained_reservation_micro_usd'],500)
        self.assertTrue(record['session']['attempts']['attempt-1']['cancel_requested'])
    def test_current_allowance_revoked_before_fake_commit_zero_calls(self):
        reached,release=threading.Event(),threading.Event()
        self.make(dispatch_barriers=DispatchBarriers(before_commit_reached=reached,before_commit_release=release))
        thread,values,errors=self.threaded(self.dispatch);self.assertTrue(reached.wait(5))
        self.authorization.revoked=True;release.set();self.joined(thread)
        self.assertEqual(self.fake.calls,0);self.assertEqual(values,[]);self.assertIsInstance(errors[0],GuardRefused)
        self.assertEqual(self.checked('cancelled')[1]['virtual_accounting']['retained_reservation_micro_usd'],0)
    def test_expiry_between_dispatch_and_tool(self):
        self.make();self.dispatch();self.now=100
        with self.assertRaises(GuardRefused):self.guard.recover('r','recover')
        self.assertEqual(self.handler.calls,[]);self.assertEqual(self.checked('timeout')[1]['accepted_tool_results'],0)
    def test_allowance_budget_or_expiry_binding_mutation(self):
        for key,value in [('budget_micro_usd',3000),('expires_monotonic',200),('snapshot_sha256','0'*64)]:
            with self.subTest(key=key):
                self.setUp();self.make();self.dispatch();setattr(self.authorization,key,value)
                with self.assertRaises(GuardRefused):self.guard.recover('r','recover')
                self.assertEqual(self.handler.calls,[]);self.assertEqual(self.checked('partial')[1]['accepted_tool_results'],0)
    def test_budget_incident_closes_tool_admission(self):
        receipt=fake_receipt('incident');receipt['observed_charge_micro_usd']=501
        self.make(outcomes=[FakeResultV2(receipt=receipt)])
        with self.assertRaises(GuardRefused):self.dispatch()
        with self.assertRaises(GuardRefused):self.guard.recover('r','recover')
        self.assertEqual(self.fake.calls,1);self.assertEqual(self.handler.calls,[])
        self.assertEqual(self.checked('error')[1]['accepted_tool_results'],0)
    def test_retry_and_late_virtual_usage_idempotent(self):
        self.make(outcomes=[FakeResultV2(response=None),FakeResultV2(response=None)]);self.dispatch()
        self.guard.dispatch_fake('attempt-2','call-1',fake_request(),500,retry_of='attempt-1')
        receipt=fake_receipt('late-own')
        self.assertTrue(self.guard.reconcile_fake('attempt-2',state='completed',response=b'late fake',receipt=receipt))
        self.assertFalse(self.guard.reconcile_fake('attempt-2',state='completed',response=b'late fake',receipt=receipt))
        _,result=self.checked();self.assertEqual(result['virtual_accounting']['retained_reservation_micro_usd'],500)
        self.assertIsNone(result['provider_usage'])
    def test_two_concurrent_tools_correlated_without_sleep(self):
        self.make();self.dispatch();self.handler.enter=threading.Event();self.handler.release=threading.Event()
        a,av,ae=self.threaded(lambda:self.guard.recover('a','recover'))
        self.assertTrue(self.handler.enter.wait(5));self.handler.enter.clear()
        b,bv,be=self.threaded(lambda:self.guard.recover('b','query'))
        self.assertTrue(self.handler.enter.wait(5));self.handler.release.set();self.joined(a);self.joined(b)
        self.assertFalse(ae);self.assertFalse(be);self.assertEqual(len(av),1);self.assertEqual(len(bv),1)
        self.assertEqual(self.checked()[1]['accepted_tool_results'],2)
    def test_no_dispatch_identity_replacement_during_tool(self):
        self.make();self.dispatch();self.handler.enter=threading.Event();self.handler.release=threading.Event()
        thread,_,errors=self.threaded(lambda:self.guard.recover('r','recover'))
        self.assertTrue(self.handler.enter.wait(5))
        with self.assertRaises(ValueError):self.guard.dispatch_fake('attempt-2','call-2',fake_request(),500)
        self.handler.release.set();self.joined(thread);self.assertFalse(errors)
        self.assertEqual(self.fake.calls,1);self.checked()
    def test_completed_cannot_hide_refused_tool_result(self):
        self.make();self.dispatch();self.evidence['controls']+=b'changed'
        with self.assertRaises(GuardRefused):self.guard.recover('r','recover')
        with self.assertRaises(GuardRefused):self.guard.finish('completed')
        self.checked('partial')
    def test_final_completed_rechecks_authority(self):
        self.make();self.dispatch();self.guard.recover('r','recover');self.guard.revoke()
        with self.assertRaises(GuardRefused):self.guard.finish('completed')
        self.checked('cancelled')
    def test_current_callback_bad_types_are_refusal_not_ready_flags(self):
        self.make();self.dispatch();self.evidence={'ready':True}
        with self.assertRaises(GuardRefused):self.guard.recover('r','recover')
        self.assertEqual(self.checked('partial')[1]['accepted_tool_results'],0)
    def test_false_clock_and_mutable_source_refuse(self):
        self.now=True
        with self.assertRaises(ValueError):self.make()
        self.setUp();self.make();self.dispatch();self.files['src/query.py']+=b'changed'
        with self.assertRaises(GuardRefused):self.guard.recover('r','recover')
        self.checked('partial')
    def test_resealed_readiness_type_identity_and_retention_negatives(self):
        original=self.complete()
        checks=[i for i,e in enumerate(original['events']) if e['kind']=='check'];ends=[i for i,e in enumerate(original['events']) if e['kind']=='end']
        mutations=[lambda r:r['events'][checks[0]]['details'].update(accepted=1),
            lambda r:r['events'][checks[0]]['details']['observation'].update(time=True),
            lambda r:r['header'].update(agent_run=True),lambda r:r['header'].update(provider_charge=0),
            lambda r:r['events'][ends[-1]]['details'].update(operation_id='tool:invented'),
            lambda r:r['events'][ends[-1]]['details'].update(result=None),
            lambda r:r['events'][ends[-1]]['details']['delegate_prefix'].update(bytes=True)]
        for change in mutations:
            record=copy.deepcopy(original);change(record)
            with self.subTest(record=record['events'][-1]),self.assertRaises((ValueError,KeyError)):replay_guard(reseal(record))
    def test_forged_snapshot_observation_cannot_authorize(self):
        record=self.complete();event=next(e for e in record['events'] if e['kind']=='check' and e['details']['stage']=='after')
        event['details']['observation']['gate']['manifest']['configuration']['input_tokens']=99
        with self.assertRaises(ValueError):replay_guard(reseal(record))
    def test_individual_frame_and_record_bounds(self):
        record=self.complete();record['events'][0]['details']['observation']['callback_error']='x'*(MAX_FRAME_BYTES+1)
        with self.assertRaises(ValueError):replay_guard(reseal(record))
        record=self.complete();record['unbounded']='x'*MAX_RECORD_BYTES
        with self.assertRaises(ValueError):replay_guard(record)
    def test_decoder_duplicate_nonfinite_and_canonical_bounds(self):
        for raw in [b'{"a":1,"a":2}\n',b'{"a":NaN}\n',b'{"a":1e999}\n',b' {}\n',b'x'*(MAX_RECORD_BYTES+1)]:
            with self.subTest(raw=raw[:30]),self.assertRaises(ValueError):load_guard(raw)
        record=self.complete();self.assertEqual(replay_guard(load_guard(canonical(record)+b'\n'))['accepted_tool_results'],2)
    def test_allowance_revoked_during_handler(self):
        self.make();self.dispatch();self.handler.enter=threading.Event();self.handler.release=threading.Event()
        thread,values,errors=self.threaded(lambda:self.guard.recover('r','recover'))
        self.assertTrue(self.handler.enter.wait(5));self.authorization.revoked=True;self.handler.release.set();self.joined(thread)
        self.assertEqual(values,[]);self.assertIsInstance(errors[0],GuardRefused)
        record,result=self.checked('cancelled');self.assertTrue(record['session']['revoked'])
        self.assertEqual(result['retained_but_not_returned_tool_results'],1)
    def test_expiry_during_handler(self):
        self.make();self.dispatch();self.handler.enter=threading.Event();self.handler.release=threading.Event()
        thread,values,errors=self.threaded(lambda:self.guard.recover('r','recover'))
        self.assertTrue(self.handler.enter.wait(5));self.now=100;self.handler.release.set();self.joined(thread)
        self.assertEqual(values,[]);self.assertIsInstance(errors[0],GuardRefused)
        self.assertEqual(self.checked('timeout')[1]['accepted_tool_results'],0)
    def test_strict_allowance_types_cannot_enable_tools(self):
        self.make();self.dispatch();self.authorization.budget_micro_usd=True
        with self.assertRaises(GuardRefused):self.guard.recover('r','recover')
        self.assertEqual(self.handler.calls,[]);self.checked('partial')
    def test_guard_method_binding_hash_changed_is_refused_by_replay(self):
        record=self.complete();record['header']['source_bindings']['crates/xrai-eval/harness/execution_dispatch_v2.py']='0'*64
        with self.assertRaises(ValueError):replay_guard(record)
    def test_context_expansion_also_checks_manifest_before_handler(self):
        self.make();self.dispatch();search=self.guard.recover('r','recover')
        self.manifest['measurement']['profile']='changed'
        with self.assertRaises(GuardRefused):self.guard.expand('e',[search['snippets'][0]['id']])
        self.assertEqual(len(self.handler.calls),1);self.assertEqual(self.checked('partial')[1]['accepted_tool_results'],1)
    def test_tampered_idempotent_flag_rejected(self):
        self.make(outcomes=[FakeResultV2(response=None)]);self.dispatch();receipt=fake_receipt('late-check')
        self.guard.reconcile_fake('attempt-1',state='completed',response=b'late',receipt=receipt)
        self.guard.reconcile_fake('attempt-1',state='completed',response=b'late',receipt=receipt)
        record=self.checked()[0]
        next(e for e in reversed(record['events']) if e['kind']=='reconcile')['details']['changed']=True
        with self.assertRaises(ValueError):replay_guard(reseal(record))
    def test_allowance_expiry_change_before_commit_is_not_extension(self):
        reached,release=threading.Event(),threading.Event()
        self.make(dispatch_barriers=DispatchBarriers(before_commit_reached=reached,before_commit_release=release))
        thread,values,errors=self.threaded(self.dispatch);self.assertTrue(reached.wait(5));self.authorization.expires_monotonic=200
        release.set();self.joined(thread);self.assertFalse(values);self.assertIsInstance(errors[0],GuardRefused)
        self.assertEqual(self.fake.calls,0);self.assertEqual(self.checked('partial')[1]['virtual_accounting']['retained_reservation_micro_usd'],0)
    def test_pre_refusal_does_not_remove_other_completed_results(self):
        self.make();self.dispatch();self.guard.recover('earlier','query');self.guard.invalidate('later change')
        with self.assertRaises(GuardRefused):self.guard.recover('later','recover')
        record,result=self.checked('partial')
        self.assertEqual(result['accepted_tool_results'],1)
        raw=base64.b64decode(record['delegate']['base64']);self.assertIn(b'earlier',raw)
        self.assertNotIn(b'later"',raw)
    def test_frozen_guarded_fixtures_replay_current_source(self):
        root=Path(__file__).resolve().parents[4]
        paths=list((root/'eval/adapters/guarded-v1').glob('*.json'))
        self.assertEqual(len(paths),11)
        for path in paths:
            with self.subTest(path=path.name):
                result=replay_guard(load_guard(path.read_bytes()))
                self.assertFalse(result['agent_run']);self.assertFalse(result['paid_provider_enabled'])
                self.assertIsNone(result['provider_charge'])
    def test_close_waits_for_active_io_and_terminal_once(self):
        self.make();self.dispatch();self.handler.enter=threading.Event();self.handler.release=threading.Event()
        thread,_,errors=self.threaded(lambda:self.guard.recover('r','recover'))
        self.assertTrue(self.handler.enter.wait(5))
        with self.assertRaises(ValueError):self.guard.finish('partial')
        self.handler.release.set();self.joined(thread);self.assertFalse(errors);self.checked()
        with self.assertRaises(ValueError):self.guard.recover('r2','recover')


if __name__=='__main__':unittest.main()
