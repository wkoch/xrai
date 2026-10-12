import copy
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_ledger import Ledger, fake_metadata, fake_receipt, fake_request, fake_session, readiness, replay_agent, replay_versioned


class LedgerTests(unittest.TestCase):
    def ledger(self, budget=1000):
        return Ledger(fake_metadata(), budget)

    def sent(self, ledger, name='a1', call='c1', start=0):
        self.assertTrue(ledger.reserve(name, call, fake_request(), 500, timestamp=start))
        ledger.send(name, timestamp=start+1)

    def test_complete_fake_and_subset_not_double_counted(self):
        value = fake_session()
        result = replay_versioned(value)
        self.assertTrue(result['accounting']['observed_cost_complete'])
        self.assertEqual(result['accounting']['observed_cost_micro_usd'], 35)
        self.assertEqual(value['attempts']['a1']['receipt']['usage']['cached_input_tokens'], 4)
        self.assertFalse(value['paid_provider_called'])
        self.assertEqual(value['outcome'], 'not_judged')

    def test_partial_timeout_unknown_charge_retains_reservation(self):
        value = fake_session(unknown=True)
        result = replay_agent(value)
        self.assertEqual(value['attempts']['a1']['state'], 'timeout')
        self.assertEqual(value['attempts']['a1']['response_chunks'][0]['captured_bytes'], 7)
        self.assertIsNone(result['accounting']['observed_cost_micro_usd'])
        self.assertEqual(result['accounting']['retained_reservation_micro_usd'], 500)
        self.assertEqual(result['accounting']['supported_cost_interval_micro_usd'], [0, 500])

    def test_all_sent_terminal_failures_and_missing_completion_charge_remain_unknown(self):
        for state in ['partial', 'sent_no_response', 'completed', 'timeout', 'cancelled']:
            ledger = self.ledger(); self.sent(ledger)
            if state == 'partial': ledger.chunk('a1', b'partial', timestamp=2)
            ledger.finish('a1', state, timestamp=3)
            result = replay_agent(ledger.record())
            self.assertFalse(result['accounting']['observed_cost_complete'])
            self.assertIsNone(result['accounting']['observed_cost_micro_usd'])
            self.assertEqual(result['accounting']['retained_reservation_micro_usd'], 500)

    def test_retry_does_not_erase_unknown_prior_attempt(self):
        ledger = self.ledger()
        self.sent(ledger)
        ledger.finish('a1', 'sent_no_response', timestamp=2)
        self.assertTrue(ledger.reserve('a2', 'c1', fake_request(), 500, timestamp=3, retry_of='a1'))
        ledger.send('a2', timestamp=4)
        ledger.finish('a2', 'completed', timestamp=5)
        ledger.receipt('a2', fake_receipt(), timestamp=6)
        value = ledger.record(); replay_agent(value)
        self.assertEqual(value['accounting']['known_observed_charge_micro_usd'], 35)
        self.assertEqual(value['accounting']['unknown_charge_attempts'], ['a1'])
        self.assertEqual(value['accounting']['retained_reservation_micro_usd'], 500)
        self.assertIsNone(value['accounting']['observed_cost_micro_usd'])

    def test_receipt_exact_duplicate_idempotent_and_cross_attempt_rejected(self):
        ledger = self.ledger(); self.sent(ledger)
        ledger.finish('a1', 'completed', timestamp=2)
        self.assertTrue(ledger.receipt('a1', fake_receipt(), timestamp=3))
        count = len(ledger.events)
        self.assertFalse(ledger.receipt('a1', fake_receipt(), timestamp=4))
        self.assertEqual(len(ledger.events), count)
        self.sent(ledger, 'a2', 'c2', start=5)
        ledger.finish('a2', 'completed', timestamp=6.5)
        with self.assertRaisesRegex(ValueError, 'duplicated'):
            ledger.receipt('a2', fake_receipt(), timestamp=7)
        self.assertEqual(ledger.record()['accounting']['known_observed_charge_micro_usd'], 35)
        replay_agent(ledger.record())

    def test_streaming_receipt_cannot_release_maximum_reservation(self):
        ledger = self.ledger(500)
        self.sent(ledger)
        ledger.chunk('a1', b'partial', timestamp=2)
        before = ledger.record()
        with self.assertRaisesRegex(ValueError, 'terminal attempt'):
            ledger.receipt('a1', fake_receipt(), timestamp=3)
        self.assertEqual(ledger.record(), before)
        self.assertFalse(ledger.reserve('a2', 'c2', fake_request(), 500, timestamp=4))
        self.assertEqual(ledger.record()['accounting']['retained_reservation_micro_usd'], 500)
        self.assertIsNone(ledger.record()['accounting']['observed_cost_micro_usd'])
        replay_agent(ledger.record())

    def test_cancel_possible_charge_and_rejected_before_send(self):
        ledger = self.ledger(500); self.sent(ledger)
        ledger.finish('a1', 'cancelled', timestamp=2)
        self.assertFalse(ledger.reserve('a2', 'c2', fake_request(), 500, timestamp=3))
        value = ledger.record(); replay_agent(value)
        self.assertEqual(value['attempts']['a2']['state'], 'rejected_before_send')
        self.assertFalse(value['attempts']['a2']['sent'])
        self.assertEqual(value['accounting']['retained_reservation_micro_usd'], 500)
        self.assertIsNone(value['accounting']['observed_cost_micro_usd'])

    def test_unsent_rejection_frees_reservation(self):
        ledger = self.ledger(500)
        ledger.reserve('a1', 'c1', fake_request(), 500, timestamp=0)
        ledger.finish('a1', 'rejected_before_send', timestamp=1)
        self.assertTrue(ledger.reserve('a2', 'c2', fake_request(), 500, timestamp=2))
        replay_agent(ledger.record())

    def test_concurrent_reservation_never_overcommits(self):
        ledger = self.ledger(1000)
        barrier = threading.Barrier(8)
        allowed = []
        def submit(i):
            barrier.wait()
            allowed.append(ledger.reserve('a'+str(i), 'c'+str(i), fake_request(), 500, timestamp=0))
        threads = [threading.Thread(target=submit, args=(i,)) for i in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sum(allowed), 2)
        value = ledger.record(); replay_agent(value)
        self.assertEqual(value['accounting']['retained_reservation_micro_usd'], 1000)
        self.assertTrue(value['accounting']['budget_limit_respected'])
        self.assertEqual(len(value['attempts']), 8)

    def test_underreservation_and_invalid_subset_rejected(self):
        ledger = self.ledger()
        with self.assertRaisesRegex(ValueError, 'maximum'):
            ledger.reserve('a1', 'c1', fake_request(), 499, timestamp=0)
        self.sent(ledger)
        receipt = fake_receipt(); receipt['usage']['cached_input_tokens'] = 11
        ledger.finish('a1', 'completed', timestamp=1.5)
        with self.assertRaisesRegex(ValueError, 'subset'):
            ledger.receipt('a1', receipt, timestamp=2)
        self.assertIsNone(ledger.record()['accounting']['observed_cost_micro_usd'])

    def test_excess_observed_charge_is_recorded_and_stops_admissions(self):
        ledger = self.ledger(); self.sent(ledger)
        ledger.finish('a1', 'completed', timestamp=2)
        receipt = fake_receipt(); receipt['observed_charge_micro_usd'] = 600
        self.assertTrue(ledger.receipt('a1', receipt, timestamp=3))
        self.assertFalse(ledger.reserve('a2', 'c2', fake_request(), 500, timestamp=4))
        value = ledger.record(); replay_agent(value)
        self.assertEqual(value['accounting']['known_observed_charge_micro_usd'], 600)
        self.assertFalse(value['accounting']['budget_limit_respected'])
        self.assertEqual(len(value['budget_incidents']), 1)
        self.assertEqual(value['budget_incidents'][0]['observed_charge_micro_usd'], 600)

    def test_tampered_events_response_metadata_and_summary_rejected(self):
        value = fake_session()
        mutations = [lambda x: x['accounting'].__setitem__('known_observed_charge_micro_usd', 0),
                     lambda x: x['events'][2]['details'].__setitem__('base64', 'ZmFrZQ=='),
                     lambda x: x['events'][1].__setitem__('sequence', 9),
                     lambda x: x['metadata']['price'].__setitem__('input', 99),
                     lambda x: x['attempts']['a1'].__setitem__('state', 'timeout')]
        for mutate in mutations:
            changed = copy.deepcopy(value); mutate(changed)
            with self.assertRaises(ValueError): replay_agent(changed)

    def test_readiness_d0_smoke_d1_campaign_and_no_adapter_authorization(self):
        d0, d1 = readiness(), readiness(dataset='D1')
        self.assertEqual(d0['run_kind'], 'paired_smoke')
        self.assertEqual(d1['run_kind'], 'campaign')
        self.assertNotIn('D1 corpus not admitted: 0/32', d0['reasons'])
        self.assertIn('D1 corpus not admitted: 0/32', d1['reasons'])
        ready = readiness(model_available=True, credentials_available=True, monetary_budget=1000,
                          arbitrary_containment=True, real_adapter_available=True)
        self.assertTrue(ready['real_run_ready'])
        self.assertFalse(ready['paid_adapter_enabled'])
        self.assertTrue(ready['readiness_does_not_authorize_provider_call'])


if __name__ == '__main__': unittest.main()
