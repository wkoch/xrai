import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from execution_gate import (EvidenceSnapshot, Decision, preflight, verify_decision,
                            DispatchSession, OfflineAuthorization, FakeAdapter,
                            FakeOutcome, make_smoke_fixture, VERSION)
from agent_ledger import canonical, sha, fake_request, fake_receipt, fake_session, replay_agent


class GateTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.evidence = make_smoke_fixture()

    def snapshot(self):
        return EvidenceSnapshot.capture(self.manifest, self.evidence)

    def bind(self):
        self.manifest['evidence_sha256'] = {key: sha(value) for key, value in self.evidence.items()}

    def session(self, *, budget=1000, outcomes=None, current=False):
        snapshot = self.snapshot()
        adapter = FakeAdapter(outcomes)
        auth = OfflineAuthorization(snapshot.fingerprint, budget, time.monotonic() + 60)
        session = DispatchSession(snapshot, preflight(snapshot), auth, adapter,
            current_manifest=(lambda: self.manifest) if current else None,
            current_evidence=(lambda: self.evidence) if current else None)
        return session, adapter

    def refused_consumer(self):
        snapshot = self.snapshot()
        decision = preflight(snapshot)
        adapter = FakeAdapter()
        with self.assertRaises(ValueError):
            DispatchSession(snapshot, decision, OfflineAuthorization(snapshot.fingerprint, 1000,
                time.monotonic() + 60), adapter)
        self.assertEqual(adapter.calls, 0)
        self.assertFalse(decision.accepted)
        self.assertTrue(decision.dimensions)

    def test_smoke_without_d1_calls_fake_and_replays_ledger(self):
        session, adapter = self.session()
        self.assertEqual(session.dispatch('a', 'call', fake_request(), 500)['status'], 'completed')
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(replay_agent(session.record())['accounting']['observed_cost_micro_usd'], 35)
        self.assertFalse(preflight(self.snapshot()).as_dict()['campaign_scoring_enabled'])

    def test_flags_not_authority(self):
        for key, value in [('ready', True), ('admitted', 32), ('model_available', True)]:
            with self.subTest(key=key):
                original = copy.deepcopy(self.manifest)
                self.manifest[key] = value
                self.refused_consumer()
                self.manifest = original

    def test_unknown_dataset_and_d1_relabel_refused(self):
        for name, origin in [('bogus', 'development_seed'), ('D1', 'qualified_corpus'),
                             ('D0', 'qualified_corpus')]:
            with self.subTest(name=name):
                self.manifest['dataset'].update(name=name, origin=origin)
                self.refused_consumer()

    def test_missing_swapped_extra_and_rehashed_evidence(self):
        for mode in ['missing', 'swapped', 'extra', 'rehashed']:
            with self.subTest(mode=mode):
                self.setUp()
                if mode == 'missing':
                    del self.evidence['controls']
                elif mode == 'extra':
                    self.evidence['admitted'] = b'32'
                    self.bind()
                else:
                    self.evidence['model'] = self.evidence['controls']
                    if mode == 'rehashed':
                        self.bind()
                self.refused_consumer()

    def test_rehashed_task_oracle_replacement_fails_review(self):
        self.evidence['task/D0-RS-01/oracle'] = b'changed oracle'
        self.bind()
        self.refused_consumer()

    def test_rehashed_smoke_protocol_not_campaign(self):
        self.manifest['protocol']['result_destination'] = 'D1'
        self.evidence['protocol'] = canonical(self.manifest['protocol'])
        self.bind()
        self.refused_consumer()

    def test_protocol_scalar_types_not_python_equal_flags(self):
        self.manifest['protocol']['paired_resources'] = 1
        self.evidence['protocol'] = canonical(self.manifest['protocol'])
        self.bind()
        self.refused_consumer()
        self.setUp()
        self.manifest['configuration']['input_tokens'] = 100.0
        self.evidence['configuration'] = canonical(self.manifest['configuration'])
        self.bind()
        self.refused_consumer()

    def test_campaign_forged_rows_and_event_flags_zero_calls(self):
        self.manifest['intent'] = 'campaign_d1'
        self.manifest['dataset'] = {'name': 'D1', 'origin': 'qualified_corpus',
                                    'purpose': 'competitive_campaign'}
        self.evidence['corpus'] = canonical({'admitted': 32, 'tasks': list(range(32))})
        self.evidence['events'] = canonical({'Rust': True, 'TSJS': True, 'Python': True, 'Go': True})
        self.bind()
        self.refused_consumer()
        self.assertIn('events', dict(preflight(self.snapshot()).dimensions))

    def test_decision_intent_snapshot_and_acceptance_forgery(self):
        snapshot = self.snapshot()
        decision = preflight(snapshot)
        for forged in [replace(decision, intent='campaign_d1'),
                       replace(decision, snapshot_sha256='0' * 64),
                       replace(decision, scope='paid')]:
            with self.assertRaises(ValueError):
                verify_decision(snapshot, forged)
        self.manifest['intent'] = 'campaign_d1'
        with self.assertRaises(ValueError):
            verify_decision(self.snapshot(), decision)

    def test_snapshot_owns_bytes_and_original_mutation_cannot_change_dispatch(self):
        session, adapter = self.session()
        self.manifest['intent'] = 'campaign_d1'
        self.evidence['model'] = b'changed'
        session.dispatch('a', 'call', fake_request(), 500)
        self.assertEqual(adapter.calls, 1)
        with self.assertRaises(ValueError):
            EvidenceSnapshot(b'{}', [('model', b'mutable container')])

    def test_current_config_and_evidence_change_invalidates(self):
        for mode in ['config', 'evidence', 'intent']:
            with self.subTest(mode=mode):
                self.setUp()
                session, adapter = self.session(current=True)
                if mode == 'config':
                    self.manifest['configuration']['input_tokens'] = 101
                elif mode == 'intent':
                    self.manifest['intent'] = 'campaign_d1'
                else:
                    self.evidence['controls'] += b' '
                with self.assertRaises(ValueError):
                    session.dispatch('a', 'call', fake_request(), 500)
                self.assertEqual(adapter.calls, 0)
                self.setUp()
                with self.assertRaises(ValueError):
                    session.dispatch('b', 'other', fake_request(), 500)

    def test_changed_request_zero_calls(self):
        session, adapter = self.session()
        request = fake_request()
        request['limits']['output_tokens'] = 101
        with self.assertRaises(ValueError):
            session.dispatch('a', 'call', request, 600)
        self.assertEqual(adapter.calls, 0)

    def test_expired_revoked_wrong_auth_and_nonfake_adapter(self):
        snapshot = self.snapshot()
        for auth in [OfflineAuthorization('0' * 64, 1000, time.monotonic() + 60),
                     OfflineAuthorization(snapshot.fingerprint, 1000, 0),
                     OfflineAuthorization(snapshot.fingerprint, 1000, time.monotonic() + 60, True)]:
            adapter = FakeAdapter()
            with self.assertRaises(ValueError):
                DispatchSession(snapshot, preflight(snapshot), auth, adapter)
            self.assertEqual(adapter.calls, 0)
        session, adapter = self.session()
        session.revoke()
        with self.assertRaises(ValueError):
            session.dispatch('a', 'call', fake_request(), 500)
        self.assertEqual(adapter.calls, 0)
        with self.assertRaises(ValueError):
            DispatchSession(snapshot, preflight(snapshot), OfflineAuthorization(snapshot.fingerprint,
                1000, time.monotonic() + 60), object())

    def test_retry_without_balance_unknown_charge_retained(self):
        session, adapter = self.session(budget=500, outcomes=[FakeOutcome('timeout')])
        session.dispatch('a', 'call', fake_request(), 500)
        result = session.dispatch('retry', 'call', fake_request(), 500, retry_of='a')
        self.assertEqual(result['status'], 'rejected_before_send')
        self.assertEqual(adapter.calls, 1)
        account = replay_agent(session.record())['accounting']
        self.assertEqual(account['retained_reservation_micro_usd'], 500)
        self.assertEqual(account['unknown_charge_attempts'], ['a'])

    def test_retry_rechecks_current_plan_before_adapter(self):
        session, adapter = self.session(current=True)
        session.dispatch('a', 'call', fake_request(), 500)
        self.manifest['configuration']['profile'] = 'changed'
        with self.assertRaises(ValueError):
            session.dispatch('retry', 'call', fake_request(), 500, retry_of='a')
        self.assertEqual(adapter.calls, 1)

    def test_retry_link_and_duplicate_attempt_rejected(self):
        session, adapter = self.session()
        session.dispatch('a', 'call', fake_request(), 500)
        for attempt, call, retry in [('a', 'new', None), ('retry', 'call', None),
                                     ('retry', 'other', 'a')]:
            with self.assertRaises(ValueError):
                session.dispatch(attempt, call, fake_request(), 500, retry_of=retry)
        self.assertEqual(adapter.calls, 1)

    def test_racing_reservations_only_one_call(self):
        session, adapter = self.session(budget=500, outcomes=[FakeOutcome('timeout')])
        barrier = threading.Barrier(3)
        results, errors = [], []
        def dispatch(name):
            barrier.wait()
            try:
                results.append(session.dispatch(name, name, fake_request(), 500)['status'])
            except Exception as error:
                errors.append(str(error))
        threads = [threading.Thread(target=dispatch, args=(str(i),)) for i in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(5)
        self.assertFalse(errors)
        self.assertCountEqual(results, ['timeout', 'rejected_before_send'])
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(session.record()['accounting']['retained_reservation_micro_usd'], 500)

    def test_cancel_before_send_and_after_send_unknown(self):
        event = threading.Event()
        event.set()
        session, adapter = self.session()
        self.assertEqual(session.dispatch('a', 'call', fake_request(), 500, cancel=event)['status'],
                         'cancelled_before_send')
        self.assertEqual(adapter.calls, 0)
        event.clear()
        session, adapter = self.session(outcomes=[FakeOutcome('cancelled')])
        session.dispatch('a', 'call', fake_request(), 500, cancel=event)
        self.assertEqual(adapter.calls, 1)
        self.assertFalse(session.record()['accounting']['observed_cost_complete'])

    def test_transport_response_or_usage_absent_preserves_possible_charge(self):
        for outcome in [FakeOutcome('sent_no_response', None),
                        FakeOutcome('completed', b'response', None),
                        FakeOutcome(raises_after_send=True),
                        FakeOutcome(receipt={'provider': 'fake', 'provider_receipt_id': 'no-usage'})]:
            with self.subTest(outcome=outcome):
                session, adapter = self.session(outcomes=[outcome])
                try:
                    session.dispatch('a', 'call', fake_request(), 500)
                except (ValueError, KeyError, RuntimeError):
                    pass
                self.assertEqual(adapter.calls, 1)
                account = replay_agent(session.record())['accounting']
                self.assertFalse(account['observed_cost_complete'])
                self.assertEqual(account['retained_reservation_micro_usd'], 500)

    def test_substituted_receipt_closes_session_without_releasing_charge(self):
        receipt = fake_receipt('same-receipt')
        session, adapter = self.session(outcomes=[FakeOutcome(receipt=receipt),
            FakeOutcome(receipt={**receipt, 'observed_charge_micro_usd': 36})])
        session.dispatch('a', 'call', fake_request(), 500)
        with self.assertRaises(ValueError):
            session.dispatch('retry', 'call', fake_request(), 500, retry_of='a')
        self.assertEqual(adapter.calls, 2)
        account = replay_agent(session.record())['accounting']
        self.assertEqual(account['retained_reservation_micro_usd'], 500)
        with self.assertRaises(ValueError):
            session.dispatch('third', 'third', fake_request(), 500)
        self.assertEqual(adapter.calls, 2)

    def test_budget_incident_refuses_next_call(self):
        session, adapter = self.session(outcomes=[FakeOutcome(receipt={**fake_receipt(),
            'observed_charge_micro_usd': 501})])
        session.dispatch('a', 'call', fake_request(), 500)
        with self.assertRaises(ValueError):
            session.dispatch('b', 'other', fake_request(), 500)
        self.assertEqual(adapter.calls, 1)
        self.assertTrue(session.record()['budget_incidents'])

    def test_adapter_direct_route_refused(self):
        adapter = FakeAdapter()
        with self.assertRaises(ValueError):
            adapter._invoke(object(), fake_request())
        self.assertEqual(adapter.calls, 0)

    def test_replay_zero_adapter_calls_and_no_dispatch_route(self):
        record = fake_session()
        self.manifest['intent'] = 'replay_offline'
        self.manifest['dataset']['purpose'] = 'offline_replay'
        self.evidence = {'replay': canonical(record)}
        self.bind()
        session, adapter = self.session()
        self.assertEqual(session.replay(record)['status'], 'verified_fake_session')
        with self.assertRaises(ValueError):
            session.dispatch('a', 'call', fake_request(), 500)
        changed = copy.deepcopy(record)
        changed['accounting']['observed_cost_micro_usd'] = 0
        with self.assertRaises(ValueError):
            session.replay(changed)
        self.assertEqual(adapter.calls, 0)


if __name__ == '__main__':
    unittest.main()
