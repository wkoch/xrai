"""Behavior at the new public byte boundary; original protocols remain unchanged."""
import copy
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import transport_receipt_session as d
from agent_ledger import fake_request, fake_receipt, canonical, sha
from execution_dispatch_v2 import DispatchBarriers


def reseal(record):
    for i, event in enumerate(record['transport_events']):
        event['sequence'] = i
        event['previous_sha256'] = sha(canonical(record['transport_events'][i - 1])) if i else None
    return record


class PublicTransportTests(unittest.TestCase):
    def make(self, **kwargs):
        self.owner = d.make_public_fake_session(**kwargs)
        return self.owner
    def dispatch(self, attempt='a', call='c', **kwargs):
        return self.owner.dispatch(attempt, call, fake_request(), 500, **kwargs)
    def closed(self):
        record = self.owner.record(close=True)
        self.assertTrue(d.replay_public_transport(record)['verified'])
        return record
    def started(self, call):
        results, errors = [], []
        def work():
            try: results.append(call())
            except Exception as e: errors.append(e)
        thread = threading.Thread(target=work); thread.start()
        return thread, results, errors
    def join(self, thread):
        thread.join(5); self.assertFalse(thread.is_alive())
    def mutated(self, change):
        self.make(); self.dispatch(); record = self.closed(); change(record); reseal(record)
        with self.assertRaises((ValueError, KeyError)): d.replay_public_transport(record)
    def test_final_wire_differs_from_logical(self):
        self.make(); self.dispatch(); record = self.closed()
        row = record['requests'][0]
        self.assertNotEqual(d.unpack(row['logical']), d.unpack(row['wire']))
        entry = next(e for e in record['transport_events'] if e['kind'] == 'entry')
        self.assertEqual(d.unpack(entry['details']['consumed']), d.unpack(row['wire']))
        result = d.replay_public_transport(record)
        self.assertEqual((result['recorded_requests'],result['reservations'],result['commitments'],result['entries'],result['responses']), (1,1,1,1,1))
        self.assertEqual(result['accounting']['retained_reservation_micro_usd'],500)
    def mutation_at(self, point):
        reached, release = threading.Event(), threading.Event()
        self.make(barriers=DispatchBarriers(**{point+'_reached':reached,point+'_release':release}))
        request = fake_request(); original = canonical(request)
        thread, results, errors = self.started(lambda:self.owner.dispatch('a','c',request,500))
        self.assertTrue(reached.wait(5)); request['messages'][0]['content']='mutated'; request['limits']['output_tokens']=9000
        snapshot = self.owner.record(); self.assertEqual(snapshot['active'],['a']); self.assertFalse(snapshot['closed'])
        self.assertTrue(d.replay_public_transport(snapshot,require_closed=False)['verified'])
        with self.assertRaises(ValueError):self.owner.record(close=True)
        release.set(); self.join(thread); self.assertEqual(errors,[])
        self.assertEqual(d.unpack(self.closed()['requests'][0]['logical']),original)
    def test_caller_mutation_before_commit(self): self.mutation_at('before_commit')
    def test_caller_mutation_after_commit(self): self.mutation_at('after_commit')
    def test_snapshot_during_actual_entry_io(self): self.mutation_at('transport')
    def test_preentry_refusal_knows_absence(self):
        self.make(outcomes=['pre_entry_refusal']); self.assertFalse(self.dispatch()['committed'])
        result=d.replay_public_transport(self.closed());self.assertEqual(result['entries'],0);self.assertEqual(result['reservations'],0)
    def test_entry_then_exception(self):
        self.make(outcomes=['exception'])
        with self.assertRaises(RuntimeError):self.dispatch()
        result=d.replay_public_transport(self.closed());self.assertEqual(result['entries'],1);self.assertEqual(result['uncertain_outcomes'],1);self.assertEqual(result['accounting']['retained_reservation_micro_usd'],500)
    def test_entry_then_timeout(self):
        self.make(outcomes=['timeout'])
        with self.assertRaises(TimeoutError):self.dispatch()
        record=self.closed();self.assertEqual(record['ledger']['attempts']['a']['state'],'timeout');self.assertEqual(d.replay_public_transport(record)['entries'],1)
    def test_no_return_keeps_uncertainty(self):
        self.make(outcomes=['no_return']);self.dispatch();result=d.replay_public_transport(self.closed());self.assertEqual(result['responses'],0);self.assertEqual(result['accounting']['retained_reservation_micro_usd'],500)
    def test_retry_identity_and_late_idempotence(self):
        self.make(outcomes=['no_return','response']);self.dispatch();self.dispatch('b','c',retry_of='a')
        receipt=fake_receipt('public-late')
        self.assertTrue(self.owner.reconcile('a',state='completed',response=b'late',receipt=receipt))
        self.assertFalse(self.owner.reconcile('a',state='completed',response=b'late',receipt=receipt))
        result=d.replay_public_transport(self.closed());self.assertEqual(result['entries'],2);self.assertEqual(result['responses'],2)
        self.assertEqual(result['accounting']['known_observed_charge_micro_usd'],fake_receipt('public-late')['observed_charge_micro_usd'])
    def test_repeat_response_with_new_receipt_only(self):
        self.make(outcomes=['no_return']);self.dispatch();self.owner.reconcile('a',state='completed',response=b'late')
        self.owner.reconcile('a',state='completed',response=b'late',receipt=fake_receipt('late-charge'))
        self.closed()
    def test_conflicting_late_response_refused(self):
        self.make(outcomes=['no_return']);self.dispatch();self.owner.reconcile('a',state='completed',response=b'late')
        with self.assertRaises(ValueError):self.owner.reconcile('a',state='completed',response=b'changed')
        self.closed()
    def test_closed_session_no_dispatch_or_late(self):
        self.make();self.dispatch();self.closed()
        with self.assertRaises(ValueError):self.dispatch('b','b')
        with self.assertRaises(ValueError):self.owner.reconcile('a',receipt=fake_receipt('x'))
    def test_cancel_before_commit_no_entry(self):
        reached,release=threading.Event(),threading.Event();cancel=threading.Event()
        self.make(barriers=DispatchBarriers(before_commit_reached=reached,before_commit_release=release))
        thread,_,errors=self.started(lambda:self.dispatch(cancel=cancel));self.assertTrue(reached.wait(5));cancel.set();release.set();self.join(thread);self.assertEqual(errors,[])
        result=d.replay_public_transport(self.closed());self.assertEqual(result['entries'],0);self.assertEqual(result['accounting']['retained_reservation_micro_usd'],0)
    def test_revoke_during_io_lock_free(self):
        reached,release=threading.Event(),threading.Event();self.make(barriers=DispatchBarriers(transport_reached=reached,transport_release=release))
        thread,_,errors=self.started(self.dispatch);self.assertTrue(reached.wait(5));self.owner.revoke();self.owner.record();release.set();self.join(thread);self.assertEqual(errors,[]);self.closed()
    def test_budget_refusal_records_no_entry(self):
        self.make(budget=0);self.dispatch();result=d.replay_public_transport(self.closed());self.assertEqual(result['commitments'],0);self.assertEqual(result['entries'],0)
    def test_mutated_caller_before_capture_refused(self):
        self.make();request=fake_request();request['messages'][0]['content']='changed'
        with self.assertRaises(ValueError):self.owner.dispatch('a','c',request,500)
        self.assertEqual(d.replay_public_transport(self.closed())['reservations'],0)
    def test_omitted_entry_receipt(self):
        self.mutated(lambda r:r['transport_events'].__setitem__(slice(None),[e for e in r['transport_events'] if e['kind']!='entry']))
    def test_omitted_entry_after_exception(self):
        self.make(outcomes=['exception'])
        with self.assertRaises(RuntimeError):self.dispatch()
        record=self.closed();record['transport_events']=[e for e in record['transport_events'] if e['kind']!='entry'];reseal(record)
        with self.assertRaises(ValueError):d.replay_public_transport(record)
    def test_duplicated_entry_receipt(self):
        self.mutated(lambda r:r['transport_events'].insert(3,copy.deepcopy(next(e for e in r['transport_events'] if e['kind']=='entry'))))
    def test_omitted_request_row(self): self.mutated(lambda r:r['requests'].clear())
    def test_omitted_public_request_admission(self):
        self.mutated(lambda r:r['transport_events'].__setitem__(slice(None),[e for e in r['transport_events'] if e['kind']!='request']))
    def test_missing_response_receipt(self):
        self.mutated(lambda r:r['transport_events'].__setitem__(slice(None),[e for e in r['transport_events'] if e['kind']!='response']))
    def test_truncated_wire(self):
        def change(r):
            event=next(e for e in r['transport_events'] if e['kind']=='entry');event['details']['consumed']=d.packed(d.unpack(event['details']['consumed'])[:-1])
        self.mutated(change)
    def test_wrong_serializer(self):self.mutated(lambda r:r['requests'][0]['identity'].__setitem__('wire_version','wrong'))
    def test_wrong_attempt(self):
        def change(r): next(e for e in r['transport_events'] if e['kind']=='entry')['details']['identity']['attempt_id']='other'
        self.mutated(change)
    def test_wrong_commit(self):self.mutated(lambda r:r['requests'][0]['identity'].__setitem__('commit_sha256','0'*64))
    def test_wire_identity_bool_bytes_refused(self):self.mutated(lambda r:r['requests'][0]['identity'].__setitem__('wire_bytes',True))
    def test_response_changed_resealed(self):
        def change(r):next(e for e in r['transport_events'] if e['kind']=='response')['details']['received']=d.packed(b'other')
        self.mutated(change)
    def test_missing_finish_refused(self):self.mutated(lambda r:r['transport_events'].pop())
    def test_public_wire_truncated_refuses_before_entry(self):
        raw=d.serialize(canonical(fake_request())); observed=[]
        with self.assertRaises(ValueError):
            d.PublicFakeTransport().send(raw[:-1], {'logical_sha256':sha(canonical(fake_request()))}, lambda *args:observed.append(args), DispatchBarriers(), 'response')
        self.assertEqual(observed,[])
    def test_missing_live_entry_cannot_be_completed(self):
        self.make()
        with mock.patch.object(self.owner.transport,'send',return_value=b'no receipt'):
            with self.assertRaises(ValueError):self.dispatch()
        result=d.replay_public_transport(self.closed());self.assertEqual(result['entries'],0);self.assertEqual(result['accounting']['retained_reservation_micro_usd'],500)
    def test_wrong_live_attempt_receipt_cannot_be_adopted(self):
        self.make()
        def forged(wire,identity,emit,barriers,outcome):
            identity['attempt_id']='other';emit('entry',{'identity':identity,'consumed':d.packed(wire)})
        with mock.patch.object(self.owner.transport,'send',side_effect=forged):
            with self.assertRaises(ValueError):self.dispatch()
        self.assertEqual(d.replay_public_transport(self.closed())['entries'],0)
    def test_duplicate_live_receipt_cannot_be_adopted(self):
        self.make()
        def doubled(wire,identity,emit,barriers,outcome):
            event={'identity':identity,'consumed':d.packed(wire)};emit('entry',event);emit('entry',event)
        with mock.patch.object(self.owner.transport,'send',side_effect=doubled):
            with self.assertRaises(ValueError):self.dispatch()
        result=d.replay_public_transport(self.closed());self.assertEqual(result['entries'],1);self.assertEqual(result['responses'],0)
    def test_wrong_live_serializer_receipt_cannot_be_adopted(self):
        self.make()
        def forged(wire,identity,emit,barriers,outcome):
            identity['wire_version']='wrong';emit('entry',{'identity':identity,'consumed':d.packed(wire)})
        with mock.patch.object(self.owner.transport,'send',side_effect=forged):
            with self.assertRaises(ValueError):self.dispatch()
        self.closed()
    def test_wrong_returned_bytes_keep_uncertainty(self):
        self.make()
        def forged(wire,identity,emit,barriers,outcome):
            emit('entry',{'identity':identity,'consumed':d.packed(wire)})
            emit('response',{'identity':identity,'received':d.packed(b'actual')});return b'other'
        with mock.patch.object(self.owner.transport,'send',side_effect=forged):
            with self.assertRaises(ValueError):self.dispatch()
        result=d.replay_public_transport(self.closed())
        self.assertEqual(result['responses'],1);self.assertEqual(result['uncertain_outcomes'],1)
        self.assertIsNone(self.owner.record()['ledger']['attempts']['a']['response'])
    def test_entry_omission_and_false_metadata_consistently_resealed_refused(self):
        for mode,error in [('exception',RuntimeError),('timeout',TimeoutError)]:
            self.make(outcomes=[mode])
            with self.assertRaises(error):self.dispatch()
            record=self.closed();record['transport_events']=[e for e in record['transport_events'] if e['kind']!='entry']
            next(e for e in record['transport_events'] if e['kind']=='uncertain')['details']['entry_observed']=False
            reseal(record)
            with self.assertRaises(ValueError):d.replay_public_transport(record)
    def test_oversized_late_response_refused_before_financial_mutation(self):
        self.make(outcomes=['no_return']);self.dispatch();before=self.owner.record()
        with self.assertRaises(ValueError):self.owner.reconcile('a',state='completed',response=b'x'*(d.MAX_BYTES+1))
        self.assertEqual(self.owner.record(),before);self.closed()
    def test_no_runtime_profiler(self):
        source=Path(d.__file__).read_text();self.assertNotIn('sys.setprofile',source);self.assertNotIn('sys.settrace',source)

if __name__=='__main__':unittest.main()
