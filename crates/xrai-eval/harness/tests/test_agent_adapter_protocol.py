"""Owned stdlib lexical seam, offline fake D01, no language/model/network execution."""
import base64
import copy
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent_adapter_protocol import (ScriptedAdapterProtocol, ToolSnapshot, replay_adapter,
    comparator_preflight, COMPARATORS, canonical, sha, decode, MAX_FRAME_BYTES)
from lexical_retrieval import LexicalIndex
import lexical_retrieval
from execution_gate import EvidenceSnapshot, OfflineAuthorization, make_smoke_fixture, preflight
from execution_dispatch_v2 import DispatchSessionV2, FakeTransportV2, FakeResultV2
from execution_dispatch_v2 import make_bindings
from agent_ledger import fake_request, fake_receipt

ROOT=Path(__file__).resolve().parents[4]
PRODUCER=Path(lexical_retrieval.__file__)


class Spy:
    def __init__(self,index):
        self.index=index; self.calls=[]; self.transform=lambda value:value
        self.enter=None; self.release=None
        for attr in ['snapshot_id','configuration_id','producer_sha256','configuration']:
            setattr(self,attr,getattr(index,attr))
    def search(self,*args,**kwargs):
        self.calls.append(('recover',args,kwargs))
        if self.enter:
            self.enter.set()
            if not self.release.wait(5): raise ValueError('own test barrier timeout')
        return self.transform(self.index.search(*args,**kwargs))
    def expand(self,*args,**kwargs):
        self.calls.append(('expand',args,kwargs))
        return self.transform(self.index.expand(*args,**kwargs))


def reseal(events):
    for i,event in enumerate(events):
        event['sequence']=i
        event['previous_event_sha256']=sha(canonical(events[i-1])) if i else None
        if event['kind']=='usage':
            event['details']['wire_bytes_before_usage']=sum(len(canonical(old))+1 for old in events[:i])
    return b''.join(canonical(event)+b'\n' for event in events)


def rewired(events, mutate):
    result=next(event for event in events if event['kind']=='tool_result')
    detail=result['details']; value=decode(base64.b64decode(detail['wire_base64']))
    mutate(value)
    for _ in range(16):
        size=len(canonical(value))
        if value['wire_bytes']==size:break
        value['wire_bytes']=size
    raw=canonical(value)
    detail.update(wire_base64=base64.b64encode(raw).decode(),wire_sha256=sha(raw),wire_bytes=len(raw))
    return reseal(events)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.files={'src/query.py':'# café\ndef recover_sources():\n    return "query recovery"\n'.encode(),
            'src/other.go':b'package example\n// unrelated content\n', 'src/empty.rs':b''}
        self.now=1; self.producer=PRODUCER.read_bytes()
        index=LexicalIndex(self.files,chunk_lines=2,overlap_lines=0)
        self.spy=Spy(index)
        manifest,evidence=make_smoke_fixture(); snapshot=EvidenceSnapshot.capture(manifest,evidence)
        self.fake=FakeTransportV2()
        self.session=DispatchSessionV2(snapshot,preflight(snapshot),OfflineAuthorization(snapshot.fingerprint,5000,100),self.fake,
            bindings=make_bindings(snapshot,task_id='D0-RS-01',arm='direct',run_id='adapter-structural'),clock=lambda:self.now)
        self.capture=ToolSnapshot.capture(self.spy,self.files,self.producer)
        self.adapter=ScriptedAdapterProtocol(self.session,self.spy,self.capture,current_sources=lambda:self.files,
            current_producer=lambda:self.producer,clock=lambda:self.now)
    def dispatch(self):
        return self.adapter.dispatch_fake('attempt-1','call-1',fake_request(),500)
    def complete(self,method='bm25'):
        self.dispatch()
        search=self.adapter.recover('recover-1','recover query',method=method)
        self.adapter.expand('expand-1',[item['id'] for item in search['snippets']])
        return self.adapter.finish('completed',b'Explicit scripted answer; not an agent judgment.')
    def events(self):return [decode(frame) for frame in self.complete().splitlines()]
    def test_search_expand_exact_source_and_replay(self):
        record=replay_adapter(self.complete())
        self.assertEqual(record['tool_calls'],2);self.assertEqual(self.fake.calls,1)
        self.assertFalse(record['agent_run']); self.assertFalse(record['competitive_runs_allowed'])
        self.assertIsNone(record['provider_usage']); self.assertIsNone(record['model_tokens'])
        self.assertEqual([call[0] for call in self.spy.calls],['recover','expand'])
    def test_tfidf_same_contract(self):
        self.assertTrue(replay_adapter(self.complete('tfidf_cosine'))['verified'])
    def test_capture_owns_bytes(self):
        saved=self.capture.fingerprint;self.files['src/query.py']+=b'changed'
        self.assertEqual(saved,self.capture.fingerprint)
        with self.assertRaises(ValueError):self.dispatch()
        self.assertEqual(self.fake.calls,0)
    def test_producer_mutation_zero_dispatch(self):
        self.producer+=b'changed'
        with self.assertRaises(ValueError):self.dispatch()
        self.assertEqual(self.fake.calls,0)
    def test_stale_sources_zero_tool_invocations(self):
        self.dispatch();self.files['src/query.py']+=b'changed'
        with self.assertRaises(ValueError):self.adapter.recover('t','recover')
        self.assertEqual(self.spy.calls,[])
    def test_changed_configuration_zero_tool_invocations(self):
        self.dispatch();self.spy.configuration=dict(self.spy.configuration);self.spy.configuration['path_term_weight']=1
        with self.assertRaises(ValueError):self.adapter.recover('t','recover')
        self.assertEqual(self.spy.calls,[])
    def test_revoke_zero_tool_invocations(self):
        self.dispatch();self.session.revoke()
        with self.assertRaises(ValueError):self.adapter.recover('t','recover')
        self.assertEqual(self.spy.calls,[])
    def test_expiry_zero_tool_invocations(self):
        self.dispatch();self.now=100
        with self.assertRaises(ValueError):self.adapter.recover('t','recover')
        self.assertEqual(self.spy.calls,[])
    def test_unknown_expansion_handle_zero_tool_invocations(self):
        self.dispatch()
        with self.assertRaises(ValueError):self.adapter.expand('t',['invented'])
        self.assertEqual(self.spy.calls,[])
    def test_tool_before_dispatch_refused(self):
        with self.assertRaises(ValueError):self.adapter.recover('t','recover')
        self.assertEqual(self.spy.calls,[])
    def test_duplicate_tool_id_refused(self):
        self.dispatch();self.adapter.recover('t','recover')
        with self.assertRaises(ValueError):self.adapter.recover('t','recover')
        self.assertEqual(len(self.spy.calls),1)
    def test_source_mutation_during_handler_has_no_accepted_result(self):
        self.dispatch();self.spy.enter=threading.Event();self.spy.release=threading.Event();errors=[]
        def work():
            try:self.adapter.recover('t','recover')
            except ValueError as exc:errors.append(str(exc))
        thread=threading.Thread(target=work);thread.start()
        self.assertTrue(self.spy.enter.wait(5));self.files['src/query.py']+=b'changed';self.spy.release.set();thread.join(5)
        self.assertFalse(thread.is_alive());self.assertTrue(errors)
        with self.assertRaises(ValueError):self.adapter.finish('completed')
        replay=replay_adapter(self.adapter.finish('partial',b'source invalidation while handler active'))
        self.assertEqual(replay['tool_calls'],1)
    def test_revocation_during_handler_has_no_accepted_result(self):
        self.dispatch();self.spy.enter=threading.Event();self.spy.release=threading.Event();errors=[]
        def work():
            try:self.adapter.recover('t','recover')
            except ValueError as exc:errors.append(str(exc))
        thread=threading.Thread(target=work);thread.start()
        self.assertTrue(self.spy.enter.wait(5));self.session.revoke();self.spy.release.set();thread.join(5)
        self.assertFalse(thread.is_alive());self.assertTrue(errors)
        self.assertTrue(replay_adapter(self.adapter.finish('cancelled'))['verified'])
    def test_unknown_failure_not_silent_zero(self):
        self.fake._outcomes=[FakeResultV2(state='sent_no_response',response=None)]
        self.dispatch();self.assertEqual(self.session.record()['accounting']['retained_reservation_micro_usd'],500)
        record=replay_adapter(self.adapter.finish('timeout'))
        self.assertIsNone(record['provider_charge'])
    def test_error_timeout_partial_cancelled(self):
        for state in ['error','timeout','partial','cancelled']:
            with self.subTest(state=state):
                self.setUp();self.dispatch();self.assertTrue(replay_adapter(self.adapter.finish(state,b'explicit diagnostic'))['verified'])
    def test_retry_retains_all_dispatch_records(self):
        self.dispatch();self.adapter.dispatch_fake('attempt-2','call-1',fake_request(),500,retry_of='attempt-1')
        replay=replay_adapter(self.adapter.finish('completed'))
        self.assertEqual(replay['events'],6);self.assertEqual(self.fake.calls,2)
    def test_invalid_search_method_topk_and_bool(self):
        self.dispatch()
        for kwargs in [{'method':'literal'},{'top_k':True},{'top_k':21},{'max_wire_bytes':True}]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.adapter.recover('t','query',**kwargs)
        self.assertEqual(self.spy.calls,[])
    def test_handler_error_retains_incomplete_request(self):
        self.dispatch();self.spy.transform=lambda value:(_ for _ in ()).throw(ValueError('explicit injected handler error'))
        with self.assertRaises(ValueError):self.adapter.recover('t','recover')
        self.assertTrue(replay_adapter(self.adapter.finish('error',b'injected handler error'))['verified'])
    def test_budget_refusal_no_truncated_expansion(self):
        self.files={'src/long.py':b'query\n'*1200}
        index=LexicalIndex(self.files,chunk_lines=1,overlap_lines=0);self.spy=Spy(index)
        self.capture=ToolSnapshot.capture(self.spy,self.files,self.producer)
        self.adapter=ScriptedAdapterProtocol(self.session,self.spy,self.capture,current_sources=lambda:self.files,current_producer=lambda:self.producer,clock=lambda:self.now)
        self.dispatch(); value=self.adapter.recover('r','query',top_k=1)
        expanded=self.adapter.expand('e',[value['snippets'][0]['id']],max_wire_bytes=1000)
        self.assertEqual(expanded['status'],'insufficient_byte_budget');self.assertEqual(expanded['snippets'],[])
        self.assertTrue(replay_adapter(self.adapter.finish('completed'))['verified'])
    def test_finished_adapter_refuses_more_calls(self):
        self.complete()
        with self.assertRaises(ValueError):self.adapter.recover('t','recover')
    def test_transport_frame_bounds_duplicate_keys_nonfinite(self):
        for raw in [b'{"x":1,"x":2}',b'{"x":NaN}',b' '* (MAX_FRAME_BYTES+1)]:
            with self.subTest(raw=raw[:25]),self.assertRaises(ValueError):decode(raw)
    def test_replay_counterproofs_resealed_events(self):
        original=self.events()
        def wrong(fields,value):
            def change(events):
                item=events
                for key in fields[:-1]:item=item[key]
                item[fields[-1]]=value
            return change
        request=next(i for i,event in enumerate(original) if event['kind']=='tool_request')
        cases=[wrong([0,'details','execution_kind'],'agent_run'),wrong([0,'details','provider_usage'],{'tokens':0}),
            wrong([0,'details','paid_provider_enabled'],True),wrong([request,'identity','call_id'],'different'),
            wrong([request,'details','arguments','top_k'],True),wrong([len(original)-2,'details','model_tokens'],0),
            wrong([len(original)-2,'details','provider_charge'],0),wrong([len(original)-1,'details','judgment'],'success'),
            wrong([0,'identity','run_id'],'substituted')]
        for change in cases:
            events=copy.deepcopy(original);change(events)
            with self.subTest(change=events),self.assertRaises((ValueError,KeyError)):replay_adapter(reseal(events))
    def test_tool_wire_counterproofs_rehashed_content(self):
        original=self.events()
        cases=[lambda value:value.update(schema='invented.v1'),lambda value:value.update(financial_cost=0),
            lambda value:value.update(model_tokens=0),lambda value:value['coverage'].update(parse_status='parsed'),
            lambda value:value['coverage'].update(semantic_status='known'),lambda value:value['coverage'].update(captured_scope_only=1),
            lambda value:value['coverage'].update(indexed_chunks=0),lambda value:value['snippets'][0].update(start=False),
            lambda value:value['snippets'][0].update(end=float(value['snippets'][0]['end'])),
            lambda value:value['snippets'][0].update(text='forged text'),lambda value:value.update(query_sha256='0'*64),
            lambda value:value.update(method='tfidf_cosine'),lambda value:value.update(producer_sha256='0'*64)]
        for change in cases:
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):replay_adapter(rewired(copy.deepcopy(original),change))
    def test_truncated_noncanonical_or_appended_transcript(self):
        raw=self.complete()
        for changed in [raw[:-1],raw+b'{}\n',b' '+raw]:
            with self.subTest(data=changed[:30]),self.assertRaises((ValueError,KeyError)):replay_adapter(changed)
    def test_duplicate_usage_rejected(self):
        events=self.events();events.insert(-1,copy.deepcopy(events[-2]))
        with self.assertRaises(ValueError):replay_adapter(reseal(events))
    def test_missing_response_completed_rejected(self):
        events=self.events();events=[event for event in events if event['kind']!='tool_result']
        with self.assertRaises(ValueError):replay_adapter(reseal(events))
    def test_multiple_queries_reuse_source_handle_despite_score_changes(self):
        self.dispatch(); self.adapter.recover('r1','recover');self.adapter.recover('r2','query recovery');
        self.assertTrue(replay_adapter(self.adapter.finish('completed'))['verified'])
    def test_before_transport_absence_blocks_tool_invocation(self):
        self.fake._outcomes=[FakeResultV2(failure='before_transport')]
        self.dispatch()
        with self.assertRaises(ValueError):self.adapter.recover('t','recover')
        self.assertEqual(self.fake.calls,0);self.assertEqual(self.spy.calls,[])
        self.assertTrue(replay_adapter(self.adapter.finish('error'))['verified'])
    def test_late_virtual_usage_idempotent_and_unknown_cleared_once(self):
        self.fake._outcomes=[FakeResultV2(state='sent_no_response',response=None)]
        self.dispatch();receipt=fake_receipt('late-own-fake')
        self.assertTrue(self.adapter.reconcile_fake('attempt-1',state='completed',response=b'late scripted response',receipt=receipt))
        count=len(self.adapter.events)
        self.assertFalse(self.adapter.reconcile_fake('attempt-1',state='completed',response=b'late scripted response',receipt=receipt))
        self.assertEqual(count,len(self.adapter.events))
        record=replay_adapter(self.adapter.finish('completed'))
        self.assertEqual(record['virtual_accounting']['known_observed_charge_micro_usd'],receipt['observed_charge_micro_usd'])
        self.assertEqual(record['virtual_accounting']['retained_reservation_micro_usd'],0)
        self.assertIsNone(record['provider_usage'])
    def test_expand_full_handle_can_be_reused_in_context(self):
        self.dispatch();search=self.adapter.recover('r','query')
        expanded=self.adapter.expand('e',[search['snippets'][0]['id']])
        self.adapter.expand('e2',[expanded['snippets'][0]['id']])
        self.assertTrue(replay_adapter(self.adapter.finish('completed'))['verified'])
    def test_current_dispatch_identity_final_usage_and_ledger(self):
        original=self.events()
        for kind in ['final','usage','ledger_snapshot']:
            for field in ['call_id','attempt_id']:
                events=copy.deepcopy(original)
                next(event for event in events if event['kind']==kind)['identity'][field]='invented-other'
                with self.subTest(kind=kind,field=field),self.assertRaises(ValueError):replay_adapter(reseal(events))
    def test_individual_frame_bound_even_below_transcript_limit(self):
        events=self.events();events[0]['details']['tool_snapshot']['producer_base64']='A'*(MAX_FRAME_BYTES+1)
        raw=reseal(events);self.assertLess(len(raw),8*MAX_FRAME_BYTES)
        with self.assertRaises(ValueError):replay_adapter(raw)
    def test_frozen_scripted_fixtures(self):
        fixtures=sorted((ROOT/'eval/adapters/experimental-v1').glob('*.jsonl'))
        self.assertEqual(len(fixtures),7)
        for path in fixtures:
            with self.subTest(path=path.name):
                record=replay_adapter(path.read_bytes())
                self.assertFalse(record['agent_run']);self.assertEqual(record['external_calls'],0)
                self.assertIsNone(record['provider_charge'])

    def test_snapshot_restore_bool_and_config_substitution(self):
        value=self.capture.as_dict();first=next(iter(value['sources']));value['sources'][first]['bytes']=False
        with self.assertRaises(ValueError):ToolSnapshot.restore(value)
        value=self.capture.as_dict();value['configuration_id']='0'*64
        with self.assertRaises(ValueError):ToolSnapshot.restore(value)


class ComparatorTests(unittest.TestCase):
    def setUp(self):
        self.source=(ROOT/'docs/PROVA-DE-DIFERENCIACAO.md').read_bytes()
        self.manifest={'schema':'xrai.eval.comparator-plan.v1','mode':'planning_only',
            'source':{'path':'docs/PROVA-DE-DIFERENCIACAO.md','sha256':sha(self.source)},
            'configurations':[{'id':name,'regimes':['common_local','best_documented_enriched'],'version_pin':None,
                'installation_receipt':None,'strong_configuration_receipt':None,'exclusion':None} for name in COMPARATORS]}
    def test_eight_strong_candidates_retained_but_refused(self):
        result=comparator_preflight(self.manifest,current_source=self.source)
        self.assertFalse(result['accepted']);self.assertEqual(len(result['configurations']),8)
        self.assertEqual(result['external_calls'],0)
    def test_caller_pin_install_or_weak_mode_cannot_enable(self):
        for key,value in [('version_pin','latest'),('installation_receipt',{'verified':True}),
            ('strong_configuration_receipt',{'ready':True}),('regimes',['weak']),('exclusion','not installed')]:
            with self.subTest(key=key):
                manifest=copy.deepcopy(self.manifest);manifest['configurations'][0][key]=value
                with self.assertRaises(ValueError):comparator_preflight(manifest,current_source=self.source)
    def test_missing_candidate_source_mutation_and_extra_flag(self):
        changes=[lambda m:m['configurations'].pop(),lambda m:m.update(ready=True),lambda m:m['source'].update(sha256='0'*64)]
        for change in changes:
            manifest=copy.deepcopy(self.manifest);change(manifest)
            with self.assertRaises(ValueError):comparator_preflight(manifest,current_source=self.source)


if __name__=='__main__':unittest.main()
