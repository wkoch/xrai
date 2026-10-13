import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from execution_gate import EvidenceSnapshot, OfflineAuthorization, make_smoke_fixture, preflight
from execution_dispatch_v2 import (DispatchSessionV2, DispatchBarriers, FakeTransportV2,
    FakeResultV2, make_bindings, replay_dispatch_v2)
from agent_ledger import fake_request, fake_receipt, canonical, sha


class DispatchV2Tests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.evidence = make_smoke_fixture()
        self.now = 1

    def session(self, *, budget=1000, results=None, barriers=None, current=False):
        snapshot = EvidenceSnapshot.capture(self.manifest, self.evidence)
        adapter = FakeTransportV2(results)
        session = DispatchSessionV2(snapshot, preflight(snapshot), OfflineAuthorization(snapshot.fingerprint, budget, 100), adapter,
            bindings=make_bindings(snapshot, task_id='D0-RS-01', arm='direct', run_id='test-v2'),
            clock=lambda: self.now, barriers=barriers,
            current_manifest=(lambda: self.manifest) if current else None,
            current_evidence=(lambda: self.evidence) if current else None)
        return session, adapter

    def threaded(self, session, **kwargs):
        result, error = [], []
        def run():
            try:
                result.append(session.dispatch('a', 'c', fake_request(), 500, **kwargs))
            except Exception as exc:
                error.append(exc)
        thread = threading.Thread(target=run)
        thread.start()
        return thread, result, error

    def finish(self, thread, errors):
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors, errors)

    def checked(self, session):
        record = session.record()
        self.assertEqual(replay_dispatch_v2(record)['accounting'], record['accounting'])
        return record

    def test_explicit_bindings_replayed(self):
        session, adapter = self.session()
        session.dispatch('a', 'c', fake_request(), 500)
        record = self.checked(session)
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(record['attempts']['a']['task_id'], 'D0-RS-01')
        self.assertEqual(record['attempts']['a']['arm'], 'direct')
        self.assertEqual(record['accounting']['observed_cost_micro_usd'], 35)
        self.assertEqual([e['kind'] for e in record['events']], ['reserve', 'commit', 'outcome', 'receipt'])

    def test_cancel_before_commit_zero_calls_releases_reservation(self):
        reached, release = threading.Event(), threading.Event()
        session, adapter = self.session(barriers=DispatchBarriers(before_commit_reached=reached, before_commit_release=release))
        thread, result, errors = self.threaded(session)
        self.assertTrue(reached.wait(5))
        self.assertEqual(session.record()['accounting']['retained_reservation_micro_usd'], 500)
        session.cancel('a')
        release.set()
        self.finish(thread, errors)
        self.assertEqual(adapter.calls, 0)
        self.assertFalse(result[0]['committed'])
        self.assertEqual(self.checked(session)['accounting']['retained_reservation_micro_usd'], 0)

    def test_revoke_expire_invalidate_after_reserve_before_commit(self):
        for action in ['revoke', 'expiry', 'invalidate', 'mutation', 'event_cancel']:
            with self.subTest(action=action):
                self.setUp()
                reached, release, cancel = threading.Event(), threading.Event(), threading.Event()
                session, adapter = self.session(current=True, barriers=DispatchBarriers(before_commit_reached=reached, before_commit_release=release))
                thread, result, errors = self.threaded(session, cancel=cancel)
                self.assertTrue(reached.wait(5))
                if action == 'expiry':
                    self.now = 100
                elif action == 'mutation':
                    self.evidence['controls'] += b'changed'
                elif action == 'event_cancel':
                    cancel.set()
                elif action == 'revoke':
                    session.revoke()
                else:
                    session.invalidate('config change')
                release.set()
                self.finish(thread, errors)
                self.assertEqual(adapter.calls, 0)
                self.assertEqual(self.checked(session)['accounting']['retained_reservation_micro_usd'], 0)

    def test_cancel_after_commit_is_abort_not_zero_call_promise(self):
        reached, release = threading.Event(), threading.Event()
        session, adapter = self.session(results=[FakeResultV2(response=None)], barriers=DispatchBarriers(after_commit_reached=reached, after_commit_release=release))
        thread, result, errors = self.threaded(session)
        self.assertTrue(reached.wait(5))
        self.assertTrue(session.record()['attempts']['a']['committed'])
        session.cancel('a')
        release.set()
        self.finish(thread, errors)
        record = self.checked(session)
        self.assertEqual(result[0]['status'], 'cancelled')
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(record['accounting']['unknown_charge_attempts'], ['a'])
        self.assertEqual(record['accounting']['retained_reservation_micro_usd'], 500)

    def test_io_lock_released_revoke_and_invalidation_record_abort(self):
        for operation in ['revoke', 'invalidate']:
            with self.subTest(operation=operation):
                reached, release = threading.Event(), threading.Event()
                session, adapter = self.session(results=[FakeResultV2(response=None)], barriers=DispatchBarriers(transport_reached=reached, transport_release=release))
                thread, result, errors = self.threaded(session)
                self.assertTrue(reached.wait(5))
                done = threading.Event()
                def control():
                    session.revoke() if operation == 'revoke' else session.invalidate('during I/O')
                    done.set()
                control_thread = threading.Thread(target=control)
                control_thread.start()
                self.assertTrue(done.wait(5), 'control lock held during I/O')
                self.assertTrue(session.record()['attempts']['a']['abort_requests'])
                release.set()
                self.finish(thread, errors)
                control_thread.join(5)
                self.assertEqual(adapter.calls, 1)
                self.assertEqual(result[0]['status'], 'cancelled')
                self.assertEqual(self.checked(session)['accounting']['retained_reservation_micro_usd'], 500)

    def test_late_response_and_usage_idempotent_after_cancel(self):
        reached, release = threading.Event(), threading.Event()
        session, adapter = self.session(results=[FakeResultV2(response=None)], barriers=DispatchBarriers(after_commit_reached=reached, after_commit_release=release))
        thread, result, errors = self.threaded(session)
        self.assertTrue(reached.wait(5))
        session.cancel('a')
        release.set()
        self.finish(thread, errors)
        receipt = fake_receipt('late')
        self.assertTrue(session.reconcile('a', state='completed', response=b'late bytes', receipt=receipt))
        record = self.checked(session)
        self.assertFalse(session.reconcile('a', state='completed', response=b'late bytes', receipt=receipt))
        self.assertEqual(record, session.record())
        self.assertEqual(record['attempts']['a']['state'], 'cancelled')
        self.assertEqual(record['accounting']['observed_cost_micro_usd'], 35)
        self.assertEqual(record['accounting']['retained_reservation_micro_usd'], 0)
        with self.assertRaises(ValueError):
            session.reconcile('a', state='completed', response=b'changed')
        altered = copy.deepcopy(receipt)
        altered['observed_charge_micro_usd'] += 1
        with self.assertRaises(ValueError):
            session.reconcile('a', receipt=altered)

    def test_uncertain_failure_retains_and_proven_before_transport_releases(self):
        for failure, calls, retained in [('before_transport', 0, 0), ('uncertain', 1, 500)]:
            with self.subTest(failure=failure):
                session, adapter = self.session(results=[FakeResultV2(response=None, failure=failure)])
                session.dispatch('a', 'c', fake_request(), 500)
                record = self.checked(session)
                self.assertEqual(adapter.calls, calls)
                self.assertEqual(record['accounting']['retained_reservation_micro_usd'], retained)
                self.assertEqual(record['accounting']['unknown_charge_attempts'], ['a'] if retained else [])

    def test_retry_rechecks_auth_and_unknown_budget(self):
        session, adapter = self.session(budget=500, results=[FakeResultV2('timeout', response=None)])
        session.dispatch('a', 'c', fake_request(), 500)
        self.assertEqual(session.dispatch('b', 'c', fake_request(), 500, retry_of='a')['status'], 'rejected_before_commit')
        self.assertEqual(adapter.calls, 1)
        self.checked(session)
        session.revoke()
        with self.assertRaises(ValueError):
            session.dispatch('d', 'c', fake_request(), 500, retry_of='a')
        self.assertEqual(adapter.calls, 1)

    def test_retry_identifies_same_call_and_unique_attempt(self):
        session, adapter = self.session()
        session.dispatch('a', 'c', fake_request(), 500)
        for attempt, call, previous in [('a', 'new', None), ('b', 'c', None), ('b', 'other', 'a'), ('b', 'c', 'missing')]:
            with self.assertRaises(ValueError):
                session.dispatch(attempt, call, fake_request(), 500, retry_of=previous)
        session.dispatch('b', 'c', fake_request(), 500, retry_of='a')
        self.assertEqual(adapter.calls, 2)
        self.checked(session)

    def test_racing_reservations_atomic(self):
        session, adapter = self.session(budget=500, results=[FakeResultV2('timeout', response=None)])
        barrier, results, errors = threading.Barrier(3), [], []
        def run(name):
            barrier.wait()
            try:
                results.append(session.dispatch(name, name, fake_request(), 500)['status'])
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=run, args=(str(i),)) for i in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            self.finish(thread, errors)
        self.assertCountEqual(results, ['timeout', 'rejected_before_commit'])
        self.assertEqual(adapter.calls, 1)
        self.checked(session)

    def test_incident_during_reserved_window_rejects_second_commit(self):
        reached, release = threading.Event(), threading.Event()
        session, adapter = self.session(budget=1500, results=[FakeResultV2('timeout', response=None)])
        session.dispatch('old', 'old-call', fake_request(), 500)
        session._barriers = DispatchBarriers(before_commit_reached=reached, before_commit_release=release)
        thread, result, errors = self.threaded(session)
        self.assertTrue(reached.wait(5))
        receipt = fake_receipt('incident')
        receipt['observed_charge_micro_usd'] = 501
        session.reconcile('old', receipt=receipt)
        release.set()
        self.finish(thread, errors)
        self.assertFalse(result[0]['committed'])
        self.assertEqual(adapter.calls, 1)
        self.assertTrue(self.checked(session)['budget_incidents'])

    def test_receipt_identity_not_shared_between_attempts(self):
        receipt = fake_receipt('same')
        session, adapter = self.session(results=[FakeResultV2(receipt=receipt), FakeResultV2(receipt=receipt)])
        session.dispatch('a', 'c', fake_request(), 500)
        with self.assertRaises(ValueError):
            session.dispatch('b', 'other', fake_request(), 500)
        record = self.checked(session)
        self.assertEqual(record['accounting']['known_observed_charge_micro_usd'], 35)
        self.assertEqual(record['accounting']['retained_reservation_micro_usd'], 500)

    def test_changed_request_is_zero_calls(self):
        session, adapter = self.session()
        request = fake_request()
        request['messages'][0]['content'] = 'changed'
        with self.assertRaises(ValueError):
            session.dispatch('a', 'c', request, 500)
        self.assertEqual(adapter.calls, 0)

    def test_bindings_wrong_task_arm_tokenizer_serializer_model_refused(self):
        snapshot = EvidenceSnapshot.capture(self.manifest, self.evidence)
        original = make_bindings(snapshot, task_id='D0-RS-01', arm='direct', run_id='test')
        for key, value in [('task_id', 'missing'), ('arm', 'campaign'), ('model', {}), ('tokenizer', {}), ('serializer_sha256', '0' * 64), ('configuration_sha256', '0' * 64)]:
            binding = copy.deepcopy(original)
            binding[key] = value
            with self.assertRaises((ValueError, KeyError)):
                DispatchSessionV2(snapshot, preflight(snapshot), OfflineAuthorization(snapshot.fingerprint, 1000, 100), FakeTransportV2(), bindings=binding, clock=lambda: 1)

    def test_malformed_authorization_and_nonfake_transport(self):
        snapshot = EvidenceSnapshot.capture(self.manifest, self.evidence)
        binding = make_bindings(snapshot, task_id='D0-RS-01', arm='direct', run_id='test')
        for auth in [OfflineAuthorization('0' * 64, 1000, 100), OfflineAuthorization(snapshot.fingerprint, True, 100), OfflineAuthorization(snapshot.fingerprint, 1000, float('nan')), OfflineAuthorization(snapshot.fingerprint, 1000, 100, True), OfflineAuthorization(snapshot.fingerprint, 1000, 100, 0), OfflineAuthorization(snapshot.fingerprint, 1000, 1)]:
            with self.assertRaises(ValueError):
                DispatchSessionV2(snapshot, preflight(snapshot), auth, FakeTransportV2(), bindings=binding, clock=lambda: 1)
        with self.assertRaises(ValueError):
            DispatchSessionV2(snapshot, preflight(snapshot), OfflineAuthorization(snapshot.fingerprint, 1000, 100), object(), bindings=binding, clock=lambda: 1)

    def test_replay_tampering_rehash_does_not_hide_illegal_transition(self):
        session, adapter = self.session()
        session.dispatch('a', 'c', fake_request(), 500)
        original = session.record()
        for change in ['delete_commit', 'wrong_task', 'scalar_budget', 'lost_response', 'no_snapshot', 'extra_flag', 'commit_expired', 'removed_tokenizer']:
            with self.subTest(change=change):
                record = copy.deepcopy(original)
                if change == 'delete_commit':
                    del record['events'][1]
                elif change == 'wrong_task':
                    record['bindings']['task_id'] = 'missing'
                elif change == 'scalar_budget':
                    record['authorization']['budget_micro_usd'] = True
                elif change == 'lost_response':
                    record['attempts']['a']['response'] = None
                elif change == 'no_snapshot':
                    record['snapshot']['evidence'] = {}
                elif change == 'extra_flag':
                    record['ready'] = True
                elif change == 'commit_expired':
                    record['authorization']['expires_monotonic'] = 1
                else:
                    record['bindings']['tokenizer'] = {}
                record['events_sha256'] = sha(canonical(record['events']))
                with self.assertRaises((ValueError, KeyError)):
                    replay_dispatch_v2(record)

    def test_fixture_replays_from_frozen_file(self):
        root = Path(__file__).resolve().parents[4]
        fixture = root / 'eval/qualification/execution-gate/v2/completed.json'
        self.assertTrue(fixture.is_file())
        self.assertEqual(replay_dispatch_v2(json.loads(fixture.read_text()))['accounting']['observed_cost_micro_usd'], 35)
        fixtures = list(fixture.parent.glob('*.json'))
        self.assertEqual(len(fixtures), 6)
        for case in fixtures:
            with self.subTest(fixture=case.name):
                self.assertEqual(replay_dispatch_v2(json.loads(case.read_text()))['status'], 'verified_offline_dispatch_v2')


if __name__ == '__main__':
    unittest.main()
