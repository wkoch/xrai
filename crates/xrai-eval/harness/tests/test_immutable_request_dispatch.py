"""Prospective private capture; public-method spies are test-only, never runtime seams."""
import base64
import copy
from pathlib import Path
import sys
import threading
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent_ledger import canonical,sha,fake_request,fake_receipt
from execution_gate import EvidenceSnapshot,OfflineAuthorization,make_smoke_fixture,preflight
from execution_dispatch_v2 import DispatchSessionV2,FakeTransportV2,FakeResultV2,DispatchBarriers,make_bindings
from immutable_request_dispatch import ImmutableRequestDispatch,capture_request,replay_immutable,restore,payload,make_immutable_guarded_fake_session


def mutate(request):
    request['messages'][0]['content']='caller changed after reservation'
    request['limits']['output_tokens']=99999
    request['tool_definitions'][0]['input']='nested changed'
    request['messages'].append({'role':'assistant','content':'extra nested'})
    request['tool_calls'].append({'arguments':{'path':['mutated']}})


class ImmutableTests(unittest.TestCase):
    def setUp(self):
        self.manifest,self.evidence=make_smoke_fixture();self.snapshot=EvidenceSnapshot.capture(self.manifest,self.evidence)
        self.auth=OfflineAuthorization(self.snapshot.fingerprint,1500,100)
        self.request=fake_request();self.original=canonical(self.request)
    def make(self,barriers=None,outcomes=None):
        self.fake=FakeTransportV2(outcomes)
        self.session=DispatchSessionV2(self.snapshot,preflight(self.snapshot),self.auth,self.fake,
            bindings=make_bindings(self.snapshot,task_id='D0-RS-01',arm='direct',run_id='immutable-test'),
            clock=lambda:1,barriers=barriers)
        self.wrapper=ImmutableRequestDispatch(self.session)
    def replay(self):return replay_immutable(self.wrapper.request_record(),self.session.record(),target_kind='dispatch_v2')
    def started(self,call,*,mutate_adapter=False):
        observed=[];results=[];errors=[]
        def spy(frame,event,arg):
            if event=='call' and frame.f_code is FakeTransportV2.invoke.__code__:
                observed.append(canonical(frame.f_locals['request']))
                if mutate_adapter:mutate(frame.f_locals['request'])
        def work():
            sys.setprofile(spy)
            try:results.append(call())
            except Exception as error:errors.append(error)
            finally:sys.setprofile(None)
        t=threading.Thread(target=work);t.start();return t,observed,results,errors
    def joined(self,t):t.join(5);self.assertFalse(t.is_alive())
    def dispatch(self,request=None,**kwargs):return self.wrapper.dispatch('attempt-1','call-1',self.request if request is None else request,500,**kwargs)
    def barred(self,point):
        reached,release=threading.Event(),threading.Event()
        self.make(DispatchBarriers(**{point+'_reached':reached,point+'_release':release}))
        t,observed,results,errors=self.started(self.dispatch)
        self.assertTrue(reached.wait(5));mutate(self.request);release.set();self.joined(t)
        self.assertEqual(errors,[]);self.assertEqual(observed,[self.original]);self.assertEqual(self.fake.calls,1)
        self.assertEqual(self.session.record()['attempts']['attempt-1']['request_sha256'],sha(observed[0]))
        self.assertTrue(self.replay()['verified'])
        return {'observed':observed,'results':results}
    def test_caller_before_commit_message_limits_nested(self):self.barred('before_commit')
    def test_caller_after_commit_message_limits_nested(self):self.barred('after_commit')
    def test_original_v2_counterproof_still_diverges_historical(self):
        reached,release=threading.Event(),threading.Event();self.make(DispatchBarriers(before_commit_reached=reached,before_commit_release=release))
        t,observed,_,errors=self.started(lambda:self.session.dispatch('old','old',self.request,500))
        self.assertTrue(reached.wait(5));mutate(self.request);release.set();self.joined(t)
        self.assertEqual(errors,[]);self.assertNotEqual(observed[0],self.original)
        self.assertEqual(self.session.record()['attempts']['old']['request_sha256'],sha(self.original))
    def test_caller_mutated_before_capture_refused_zero(self):
        self.make();mutate(self.request)
        with self.assertRaises(ValueError):self.dispatch()
        self.assertEqual(self.fake.calls,0);self.assertEqual(self.wrapper.request_record()['requests'],[])
    def test_immutable_bytes_accepted(self):
        self.make();t,observed,_,errors=self.started(lambda:self.dispatch(self.original));self.joined(t)
        self.assertEqual(errors,[]);self.assertEqual(observed,[self.original]);self.assertTrue(self.replay()['verified'])
    def test_noncanonical_duplicate_nonfinite_bytes_refused(self):
        for raw in (b'{"a": 1}',b'{"a":1,"a":1}',b'{"a":NaN}',b'{"a":1e999}'):
            with self.assertRaises(ValueError):capture_request(raw)
    def test_transport_mutates_only_disposable_decode(self):
        self.make();t,observed,_,errors=self.started(self.dispatch,mutate_adapter=True);self.joined(t)
        self.assertEqual(errors,[]);self.assertEqual(observed,[self.original])
        self.assertEqual(canonical(self.request),self.original)
        self.assertEqual(restore(self.wrapper.request_record()['requests'][0]['payload']),self.original)
        self.assertTrue(self.replay()['verified'])
    def test_cancel_before_commit_zero_invocation(self):
        reached,release=threading.Event(),threading.Event();self.make(DispatchBarriers(before_commit_reached=reached,before_commit_release=release));cancel=threading.Event()
        t,observed,results,errors=self.started(lambda:self.dispatch(cancel=cancel));self.assertTrue(reached.wait(5));cancel.set();release.set();self.joined(t)
        self.assertEqual(errors,[]);self.assertEqual(observed,[]);self.assertEqual(self.fake.calls,0)
        self.assertFalse(results[0]['committed']);self.assertEqual(self.session.record()['accounting']['retained_reservation_micro_usd'],0)
        self.assertTrue(self.replay()['verified'])
    def test_cancel_after_commit_keeps_unknown_reservation(self):
        reached,release=threading.Event(),threading.Event();self.make(DispatchBarriers(after_commit_reached=reached,after_commit_release=release),[FakeResultV2(response=None)]);cancel=threading.Event()
        t,observed,results,errors=self.started(lambda:self.dispatch(cancel=cancel));self.assertTrue(reached.wait(5));cancel.set();mutate(self.request);release.set();self.joined(t)
        self.assertEqual(errors,[]);self.assertEqual(observed,[self.original]);self.assertEqual(self.fake.calls,1)
        self.assertEqual(results[0]['status'],'cancelled');self.assertEqual(self.session.record()['accounting']['retained_reservation_micro_usd'],500)
        self.assertTrue(self.replay()['verified'])
    def test_retry_late_idempotence_preserved(self):
        self.make(outcomes=[FakeResultV2(response=None),FakeResultV2(response=None)])
        self.dispatch();self.wrapper.dispatch('attempt-2','call-1',self.original,500,retry_of='attempt-1')
        receipt=fake_receipt('immutable-late')
        self.assertTrue(self.wrapper.reconcile('attempt-2',state='completed',response=b'late fake',receipt=receipt))
        self.assertFalse(self.wrapper.reconcile('attempt-2',state='completed',response=b'late fake',receipt=receipt))
        self.assertEqual(self.session.record()['accounting']['retained_reservation_micro_usd'],500);self.assertTrue(self.replay()['verified'])
    def test_failed_before_transport_releases_reservation(self):
        self.make(outcomes=[FakeResultV2(failure='before_transport')]);self.dispatch()
        self.assertEqual(self.fake.calls,0);self.assertEqual(self.session.record()['accounting']['retained_reservation_micro_usd'],0)
        self.assertTrue(self.replay()['verified'])
    def test_uncertain_after_commit_retains_reservation(self):
        self.make(outcomes=[FakeResultV2(failure='uncertain')]);self.dispatch()
        self.assertEqual(self.fake.calls,1);self.assertEqual(self.session.record()['accounting']['retained_reservation_micro_usd'],500)
        self.assertTrue(self.replay()['verified'])
    def test_budget_refusal_has_no_transport_projection(self):
        self.make();self.wrapper.dispatch('large','call-1',self.original,2000)
        self.assertEqual(self.fake.calls,0);self.assertIsNone(self.wrapper.request_record()['requests'][0]['transport_projection']);self.assertTrue(self.replay()['verified'])
    def test_replay_payload_hash_or_bytes_adulterated(self):
        self.make();self.dispatch()
        for key,value in [('sha256','0'*64),('base64',base64.b64encode(b'{}').decode()),('bytes',True),('version','wrong')]:
            record=copy.deepcopy(self.wrapper.request_record());record['requests'][0]['payload'][key]=value
            with self.assertRaises(ValueError):replay_immutable(record,self.session.record(),target_kind='dispatch_v2')
    def test_replay_task_arm_run_authorization_binding_adulterated(self):
        self.make();self.dispatch()
        for key,value in [('task_id','wrong'),('arm','indexed'),('run_id','wrong')]:
            record=copy.deepcopy(self.wrapper.request_record());record['header']['bindings'][key]=value
            with self.assertRaises(ValueError):replay_immutable(record,self.session.record(),target_kind='dispatch_v2')
        record=copy.deepcopy(self.wrapper.request_record());record['header']['authorization']['budget_micro_usd']=999999
        with self.assertRaises(ValueError):replay_immutable(record,self.session.record(),target_kind='dispatch_v2')
    def test_replay_attempt_call_limit_retry_adulterated(self):
        self.make();self.dispatch()
        for key,value in [('attempt_id','wrong'),('call_id','wrong'),('maximum_micro_usd',True),('retry_of','wrong')]:
            record=copy.deepcopy(self.wrapper.request_record());record['requests'][0][key]=value
            with self.assertRaises(ValueError):replay_immutable(record,self.session.record(),target_kind='dispatch_v2')
    def test_replay_projection_omitted_or_changed_refused(self):
        self.make();self.dispatch()
        for value in (None,payload(b'{}')):
            record=copy.deepcopy(self.wrapper.request_record());record['requests'][0]['transport_projection']=value
            with self.assertRaises(ValueError):replay_immutable(record,self.session.record(),target_kind='dispatch_v2')
    def test_guarded_factory_second_admission_refused_without_attempt(self):
        import lexical_retrieval
        from lexical_retrieval import LexicalIndex
        from agent_adapter_protocol import ToolSnapshot
        files={'own.py':b'def owned(): pass\n'};producer=Path(lexical_retrieval.__file__).read_bytes();index=LexicalIndex(files)
        guarded=make_immutable_guarded_fake_session(self.snapshot,self.auth,index,ToolSnapshot.capture(index,files,producer),
            bindings=make_bindings(self.snapshot,task_id='D0-RS-01',arm='direct',run_id='guard-immutable-test'),
            current_manifest=lambda:self.manifest,current_evidence=lambda:self.evidence,current_authorization=lambda:self.auth,
            current_sources=lambda:files,current_producer=lambda:producer,clock=lambda:1)
        guarded.dispatch_fake('one','call',self.original,500);guarded.revoke()
        with self.assertRaises(ValueError):guarded.dispatch_fake('two','call',self.original,500,retry_of='one')
        target=guarded.finish('partial');result=replay_immutable(guarded.request_record(),target)
        self.assertTrue(result['verified']);self.assertEqual(result['attempts'],2)
        self.assertEqual(result['committed_private_projections'],1)
        forged=copy.deepcopy(guarded.request_record());forged['requests'][1]['error']=None;forged['requests'][1]['result']={'status':'completed','committed':True,'adapter_called':True}
        with self.assertRaises(ValueError):replay_immutable(forged,target)
        forged=copy.deepcopy(guarded.request_record());changed=fake_request();changed['messages'][0]['content']='different capture';raw=canonical(changed)
        forged['requests'][1]['payload']=payload(raw)
        changed_target=copy.deepcopy(target)
        for event in changed_target['events']:
            if event['kind']=='begin' and event['details']['operation_id']=='dispatch:two':event['details']['arguments']['request']=changed
        for n,event in enumerate(changed_target['events']):
            event['previous_event_sha256']=sha(canonical(changed_target['events'][n-1])) if n else None
        with self.assertRaises(ValueError):replay_immutable(forged,changed_target)
    def test_public_record_copy_does_not_expose_authority(self):
        self.make();self.dispatch();record=self.wrapper.request_record();record['requests'][0]['payload']['sha256']='0'*64
        self.assertEqual(restore(self.wrapper.request_record()['requests'][0]['payload']),self.original)
    def test_direct_success_cannot_become_fabricated_failure(self):
        self.make();self.dispatch()
        for error in ('ValueError: fabricated public failure',{'kind':'dispatch_exception_unobserved'}):
            record=copy.deepcopy(self.wrapper.request_record());record['requests'][0]['result']=None;record['requests'][0]['error']=error
            with self.assertRaises(ValueError):replay_immutable(record,self.session.record(),target_kind='dispatch_v2')
    def test_direct_failure_lifecycle_has_typed_unknown_exception(self):
        self.make(outcomes=[FakeResultV2(state='unsupported')])
        with self.assertRaises(ValueError):self.dispatch()
        record=self.wrapper.request_record()
        self.assertEqual(record['requests'][0]['error'],{'kind':'dispatch_exception_unobserved'})
        self.assertTrue(self.replay()['verified'])
        record['requests'][0]['error']=None;record['requests'][0]['result']={'status':'completed','committed':True,'adapter_called':True}
        with self.assertRaises(ValueError):replay_immutable(record,self.session.record(),target_kind='dispatch_v2')
    def test_other_attempt_error_cannot_forge_budget_refusal_exception(self):
        self.make(outcomes=[FakeResultV2(state='unsupported')]);self.wrapper.dispatch('budget','budget',self.original,2000)
        with self.assertRaises(ValueError):self.wrapper.dispatch('failed','failed',self.original,500)
        record=self.wrapper.request_record();record['requests'][0]['result']=None;record['requests'][0]['error']={'kind':'dispatch_exception_unobserved'}
        with self.assertRaises(ValueError):replay_immutable(record,self.session.record(),target_kind='dispatch_v2')
    def test_guard_success_cannot_become_fabricated_failure(self):
        import guarded_smoke
        result=guarded_smoke.run(guarded_smoke.frozen()[0][0])
        record=copy.deepcopy(result['immutable_request']);record['requests'][0]['result']=None;record['requests'][0]['error']='ValueError: fabricated public failure'
        with self.assertRaises(ValueError):replay_immutable(record,result['guard'])
    def test_no_runtime_profiler_installed(self):
        self.make();before=sys.getprofile();self.dispatch();self.assertIs(sys.getprofile(),before)
    def test_bounds_and_nonjson_request_types_refused(self):
        for value in (b'x'* (128*1024+1),{'x':'a'*(128*1024+1)}, {'x':float('inf')}, {'x':set()}, {'x':[0]*4097}):
            with self.assertRaises(ValueError):capture_request(value)


if __name__=='__main__':unittest.main()
