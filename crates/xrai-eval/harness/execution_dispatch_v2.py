"""D01 commitment protocol, exclusively synthetic and offline.

Reservation, commitment and transport observation are separate facts. The lock
protects commitment/accounting; it is never held during fake blocking I/O.
No paid transport is implemented or authorized by this protocol.
"""
import base64
import copy
from dataclasses import dataclass
import json
import math
from pathlib import Path
import threading
import time

from agent_ledger import canonical, sha, money, fake_metadata, fake_receipt, receipt_usage
from execution_gate import (EvidenceSnapshot, OfflineAuthorization, preflight,
                            verify_decision, require, exact_json)
from offline_measurement import ASSETS, SERIALIZER

VERSION = 'xrai.eval.execution-dispatch.v2'
TERMINAL = {'completed', 'timeout', 'cancelled', 'partial', 'sent_no_response',
            'rejected_before_commit', 'failed_before_transport'}


def make_bindings(snapshot, *, task_id, arm, run_id):
    """Bind actual vendored measurement bytes; does not claim token execution."""
    require(type(task_id) is str and task_id in snapshot.manifest['task_ids'], 'explicit task binding')
    require(type(arm) is str and arm in snapshot.manifest['protocol']['arms'], 'explicit arm binding')
    require(type(run_id) is str and bool(run_id), 'explicit run ID')
    config_bytes = (ASSETS / 'cl100k-config.json').read_bytes()
    config = json.loads(config_bytes)
    vocab_sha = sha((ASSETS / 'cl100k_base.tiktoken').read_bytes())
    require(config['vocab_merges_sha256'] == vocab_sha, 'vendored tokenizer vocabulary changed')
    return {'task_id': task_id, 'arm': arm, 'run_id': run_id,
            'snapshot_sha256': snapshot.fingerprint, 'model': snapshot.manifest['model'],
            'configuration_sha256': sha(canonical(snapshot.manifest['configuration'])),
            'tools_sha256': sha(canonical(snapshot.manifest['tools'])),
            'tokenizer': {'config_sha256': sha(config_bytes), 'vocab_sha256': vocab_sha,
                          'measurement': 'bound-profile-not-tokenized-by-dispatch'},
            'serializer': copy.deepcopy(SERIALIZER),
            'serializer_sha256': sha(canonical(SERIALIZER))}


@dataclass
class DispatchBarriers:
    """Optional deterministic test barriers. Events, never sleeps, order actions."""
    before_commit_reached: threading.Event | None = None
    before_commit_release: threading.Event | None = None
    after_commit_reached: threading.Event | None = None
    after_commit_release: threading.Event | None = None
    transport_reached: threading.Event | None = None
    transport_release: threading.Event | None = None

    def pause(self, point):
        reached, release = getattr(self, point + '_reached'), getattr(self, point + '_release')
        if reached is not None:
            reached.set()
        if release is not None:
            require(release.wait(10), 'offline barrier timed out: ' + point)


@dataclass(frozen=True)
class FakeResultV2:
    state: str = 'completed'
    response: bytes | None = b'offline response'
    receipt: dict | None = None
    failure: str | None = None  # before_transport or uncertain


class FakeTransportV2:
    """Built-in fake only; before_transport fails before invocation is counted."""
    def __init__(self, outcomes=None):
        self._outcomes = list(outcomes or [])
        self._lock = threading.Lock()
        self._capability = None
        self.calls = 0

    def invoke(self, capability, request, barriers):
        require(capability is self._capability and capability is not None, 'verified capability required')
        with self._lock:
            result = self._outcomes.pop(0) if self._outcomes else FakeResultV2(
                receipt=fake_receipt('fake-v2-' + str(self.calls + 1)))
            require(type(result) is FakeResultV2, 'typed fake outcome')
            if result.failure == 'before_transport':
                return result
            self.calls += 1
        barriers.pause('transport')
        return result


class _State:
    """Pure transition machine used by live dispatch and offline replay."""
    def __init__(self, snapshot, bindings, authorization):
        self.snapshot, self.bindings = snapshot, copy.deepcopy(bindings)
        self.authorization = copy.deepcopy(authorization)
        self.revoked = False
        self.invalidated = None
        self.attempts, self.receipts, self.events, self.incidents = {}, {}, [], []
        self.price = fake_metadata()['price']

    def accounting(self):
        known = sum(row['receipt']['observed_charge_micro_usd'] for row in self.attempts.values() if row['receipt'])
        retained = sum(row['reservation_micro_usd'] for row in self.attempts.values() if row['receipt'] is None)
        unknown = [key for key, row in self.attempts.items() if row['committed'] and
                   not row['transport_proven_absent'] and row['receipt'] is None]
        return {'budget_micro_usd': self.authorization['budget_micro_usd'],
                'known_observed_charge_micro_usd': known,
                'retained_reservation_micro_usd': retained, 'unknown_charge_attempts': unknown,
                'observed_cost_complete': not unknown,
                'observed_cost_micro_usd': known if not unknown else None,
                'supported_cost_interval_micro_usd': [known, known + retained],
                'budget_limit_respected': not self.incidents and known + retained <= self.authorization['budget_micro_usd'],
                'reservation_is_provider_charge_guarantee': False}

    def refusal(self, timestamp):
        if self.revoked:
            return 'authorization_revoked'
        if timestamp >= self.authorization['expires_monotonic']:
            return 'authorization_expired'
        if self.invalidated is not None:
            return 'snapshot_invalidated'
        if self.incidents:
            return 'budget_incident'
        return None

    def apply(self, kind, attempt, details, timestamp):
        require(type(timestamp) in (int, float) and math.isfinite(timestamp) and timestamp >= 0, 'monotonic timestamp')
        require(not self.events or timestamp >= self.events[-1]['monotonic_seconds'], 'event time moved backwards')
        if kind == 'revoke':
            require(attempt is None and details == {}, 'revoke shape')
            self.revoked = True
            for row in self.attempts.values():
                if row['state'] == 'committed':
                    row['cancel_requested'] = True
                    row['abort_requests'].append('authorization_revoked')
        elif kind == 'invalidate':
            require(attempt is None and set(details) == {'reason'} and type(details['reason']) is str, 'invalidation shape')
            self.invalidated = details['reason']
            for row in self.attempts.values():
                if row['state'] == 'committed':
                    row['cancel_requested'] = True
                    row['abort_requests'].append('snapshot_invalidated')
        elif kind == 'reserve':
            require(type(attempt) is str and bool(attempt) and attempt not in self.attempts, 'unique explicit attempt ID')
            require(set(details) == {'call_id', 'request', 'maximum', 'retry_of'}, 'reserve fields')
            call, request, maximum, previous = details['call_id'], details['request'], money(details['maximum']), details['retry_of']
            require(type(call) is str and bool(call), 'explicit call ID')
            require(self.refusal(timestamp) is None, 'admission refused')
            require(sha(canonical(request)) == self.snapshot.manifest['request_sha256'], 'request binding')
            required = money(request['limits']['input_tokens']) * self.price['input'] + money(request['limits']['output_tokens']) * self.price['output']
            require(maximum >= required and request['maximum_charge_policy'] == 'fake-enforced', 'maximum must cover enforced request')
            if previous is not None:
                require(type(previous) is str and previous in self.attempts, 'retry reference')
                old = self.attempts[previous]
                require(old['call_id'] == call and old['state'] in TERMINAL, 'retry terminal same call')
            else:
                require(not any(row['call_id'] == call for row in self.attempts.values()), 'retry link required')
            account = self.accounting()
            allowed = account['known_observed_charge_micro_usd'] + account['retained_reservation_micro_usd'] + maximum <= account['budget_micro_usd']
            self.attempts[attempt] = {'task_id': self.bindings['task_id'], 'arm': self.bindings['arm'],
                'call_id': call, 'attempt_id': attempt, 'retry_of': previous,
                'request_sha256': sha(canonical(request)), 'maximum_micro_usd': maximum,
                'reservation_micro_usd': maximum if allowed else 0,
                'state': 'reserved' if allowed else 'rejected_before_commit',
                'committed': False, 'cancel_requested': False, 'transport_proven_absent': False,
                'response': None, 'outcome_state': None, 'late_response_state': None,
                'abort_requests': [], 'receipt': None, 'rejection_reason': None if allowed else 'budget'}
        elif kind in {'cancel', 'commit', 'reject_before_commit', 'before_transport_failure', 'outcome', 'late_response', 'receipt'}:
            require(attempt in self.attempts, 'unknown attempt')
            row = self.attempts[attempt]
            if kind == 'cancel':
                require(details == {} and row['state'] not in TERMINAL, 'cancel requires active attempt')
                row['cancel_requested'] = True
                row['abort_requests'].append('cancel_requested')
            elif kind == 'commit':
                require(details == {} and row['state'] == 'reserved' and not row['cancel_requested'] and self.refusal(timestamp) is None, 'commit recheck refused')
                row['committed'], row['state'] = True, 'committed'
            elif kind == 'reject_before_commit':
                reason = 'cancel_requested' if row['cancel_requested'] else self.refusal(timestamp)
                require(row['state'] == 'reserved' and not row['committed'] and details == {'reason': reason} and reason is not None, 'precommit rejection requires actual cause')
                row['state'], row['reservation_micro_usd'], row['rejection_reason'] = 'rejected_before_commit', 0, reason
            elif kind == 'before_transport_failure':
                require(row['state'] == 'committed' and details == {'proof': 'built-in-fake-before-invocation-v2'}, 'before transport proof')
                row['state'], row['transport_proven_absent'], row['reservation_micro_usd'] = 'failed_before_transport', True, 0
            elif kind in {'outcome', 'late_response'}:
                require(row['committed'] and not row['transport_proven_absent'], 'outcome requires possible transport')
                require(set(details) == {'state', 'response'}, 'outcome shape')
                require(details['state'] in TERMINAL - {'rejected_before_commit', 'failed_before_transport'}, 'transport outcome state')
                require(row['response'] is None and (row['state'] == 'committed' if kind == 'outcome' else row['state'] in TERMINAL), 'outcome once')
                response = details['response']
                if response is not None:
                    require(set(response) == {'base64', 'sha256', 'bytes'}, 'response bytes fields')
                    data = base64.b64decode(response['base64'], validate=True)
                    require(type(response['bytes']) is int and response['bytes'] == len(data) and response['sha256'] == sha(data), 'response byte evidence')
                row['response'] = copy.deepcopy(response)
                if kind == 'outcome':
                    row['outcome_state'] = details['state']
                    row['state'] = 'cancelled' if row['cancel_requested'] else details['state']
                else:
                    require(response is not None, 'late response must contain bytes')
                    row['late_response_state'] = details['state']
            else:
                require(row['committed'] and not row['transport_proven_absent'] and row['state'] in TERMINAL, 'receipt requires terminal possibly sent attempt')
                require(set(details) == set(fake_receipt()), 'receipt fields')
                require(details['observed_charge_source'] == 'synthetic-receipt', 'synthetic charge source')
                require(details['provider'] == 'fake' and type(details['provider_receipt_id']) is str and bool(details['provider_receipt_id']), 'fake receipt identity')
                receipt_usage(details)
                charge, estimate = money(details['observed_charge_micro_usd']), money(details['estimated_charge_micro_usd'])
                require(details['price_version'] == self.price['version'] and estimate == details['usage']['input_tokens'] * self.price['input'] + details['usage']['output_tokens'] * self.price['output'], 'receipt prices')
                key = details['provider'] + ':' + details['provider_receipt_id']
                require(key not in self.receipts and row['receipt'] is None, 'duplicate/conflicting receipt')
                self.receipts[key] = (attempt, copy.deepcopy(details))
                row['receipt'], row['reservation_micro_usd'] = copy.deepcopy(details), 0
                if charge > row['maximum_micro_usd'] or details['usage']['input_tokens'] > self.snapshot.manifest['configuration']['input_tokens'] or details['usage']['output_tokens'] > self.snapshot.manifest['configuration']['output_tokens']:
                    self.incidents.append({'attempt_id': attempt, 'reason': 'observed charge/usage exceeded enforced maximum'})
        else:
            raise ValueError('unknown v2 operation')
        event = {'sequence': len(self.events), 'kind': kind, 'attempt_id': attempt,
                 'details': copy.deepcopy(details), 'monotonic_seconds': timestamp,
                 'previous_event_sha256': sha(canonical(self.events[-1])) if self.events else None}
        self.events.append(event)


def _snapshot_record(snapshot):
    return {'manifest': snapshot.manifest, 'evidence': {key: base64.b64encode(value).decode('ascii') for key, value in snapshot.evidence}}


class DispatchSessionV2:
    def __init__(self, snapshot, decision, authorization, adapter, *, bindings,
                 current_manifest=None, current_evidence=None, clock=time.monotonic,
                 barriers=None):
        verify_decision(snapshot, decision)
        require(decision.intent == 'smoke_seed', 'v2 dispatch supports synthetic smoke only')
        require(type(authorization) is OfflineAuthorization and type(authorization.revoked) is bool and not authorization.revoked, 'explicit unrevoked offline allowance')
        money(authorization.budget_micro_usd)
        require(type(authorization.expires_monotonic) in (int, float) and math.isfinite(authorization.expires_monotonic), 'finite authorization expiry')
        require(authorization.snapshot_sha256 == snapshot.fingerprint, 'authorization snapshot mismatch')
        require(type(bindings) is dict and exact_json(bindings, make_bindings(snapshot, task_id=bindings['task_id'], arm=bindings['arm'], run_id=bindings['run_id'])), 'model/config/task/arm/tokenizer/serializer bindings')
        require(type(adapter) is FakeTransportV2 and adapter._capability is None, 'only unclaimed built-in fake transport')
        self._snapshot, self._decision, self._adapter = snapshot, decision, adapter
        self._clock, self._lock, self._barriers = clock, threading.RLock(), barriers or DispatchBarriers()
        require(type(self._barriers) is DispatchBarriers, 'typed offline barriers')
        self._current_manifest, self._current_evidence = current_manifest, current_evidence
        self._capability = object()
        self._adapter._capability = self._capability
        self._state = _State(snapshot, bindings, {'snapshot_sha256': authorization.snapshot_sha256,
            'budget_micro_usd': authorization.budget_micro_usd, 'expires_monotonic': authorization.expires_monotonic,
            'scope': 'offline-synthetic-only'})
        self._check()

    def _event(self, kind, attempt, details):
        self._state.apply(kind, attempt, details, self._clock())

    def _check(self):
        try:
            self._snapshot.assert_current(self._current_manifest() if self._current_manifest else None,
                                          self._current_evidence() if self._current_evidence else None)
        except ValueError as error:
            if self._state.invalidated is None:
                self._event('invalidate', None, {'reason': str(error)})
        require(self._state.refusal(self._clock()) is None, 'session admission refused: ' + str(self._state.refusal(self._clock())))

    def revoke(self):
        with self._lock:
            self._event('revoke', None, {})

    def invalidate(self, reason):
        with self._lock:
            self._event('invalidate', None, {'reason': str(reason)})

    def cancel(self, attempt_id):
        with self._lock:
            row = self._state.attempts[attempt_id]
            if row['cancel_requested'] or row['state'] in TERMINAL:
                return False
            self._event('cancel', attempt_id, {})
            return True

    def dispatch(self, attempt_id, call_id, request, max_charge_micro_usd, *, retry_of=None, cancel=None):
        with self._lock:
            self._check()
            self._event('reserve', attempt_id, {'call_id': call_id, 'request': copy.deepcopy(request),
                        'maximum': max_charge_micro_usd, 'retry_of': retry_of})
            row = self._state.attempts[attempt_id]
            if row['state'] == 'rejected_before_commit':
                return {'status': row['state'], 'committed': False, 'adapter_called': False}
        try:
            self._barriers.pause('before_commit')
            with self._lock:
                if cancel is not None and cancel.is_set() and not row['cancel_requested']:
                    self._event('cancel', attempt_id, {})
                try:
                    self._check()
                except ValueError:
                    pass  # Rejection is recorded with its recomputable cause.
                reason = 'cancel_requested' if row['cancel_requested'] else self._state.refusal(self._clock())
                if reason is not None:
                    self._event('reject_before_commit', attempt_id, {'reason': reason})
                    return {'status': 'rejected_before_commit', 'committed': False, 'adapter_called': False}
                self._event('commit', attempt_id, {})  # Linearization point.
            self._barriers.pause('after_commit')
            outcome = self._adapter.invoke(self._capability, copy.deepcopy(request), self._barriers)
            with self._lock:
                if cancel is not None and cancel.is_set() and not row['cancel_requested']:
                    self._event('cancel', attempt_id, {})
                if outcome.failure == 'before_transport':
                    self._event('before_transport_failure', attempt_id, {'proof': 'built-in-fake-before-invocation-v2'})
                    return {'status': row['state'], 'committed': True, 'adapter_called': False}
                require(outcome.failure in {None, 'uncertain'}, 'typed failure classification')
                state = 'sent_no_response' if outcome.failure == 'uncertain' else outcome.state
                self.reconcile(attempt_id, state=state, response=outcome.response,
                               receipt=outcome.receipt)
                return {'status': row['state'], 'committed': True, 'adapter_called': True}
        except Exception:
            with self._lock:
                if row['state'] == 'reserved':
                    # A local barrier failure demonstrably precedes commitment.
                    self._event('invalidate', None, {'reason': 'offline precommit error'})
                    self._event('reject_before_commit', attempt_id, {'reason': 'snapshot_invalidated'})
                elif row['state'] == 'committed':
                    self._event('outcome', attempt_id, {'state': 'sent_no_response', 'response': None})
                if row['committed'] and self._state.invalidated is None:
                    self._event('invalidate', None, {'reason': 'offline dispatch/receipt error'})
                raise

    def reconcile(self, attempt_id, *, state=None, response=None, receipt=None):
        """Late exact response/usage replay is idempotent; conflicting bytes fail."""
        with self._lock:
            row = self._state.attempts[attempt_id]
            require(response is None or type(response) is bytes, 'response must own immutable bytes')
            changed = False
            if state is not None:
                encoded = None if response is None else {'base64': base64.b64encode(response).decode('ascii'),
                    'sha256': sha(response), 'bytes': len(response)}
                if row['state'] == 'committed':
                    self._event('outcome', attempt_id, {'state': state, 'response': encoded})
                    changed = True
                elif row['response'] is None and encoded is not None and row['state'] in TERMINAL:
                    self._event('late_response', attempt_id, {'state': state, 'response': encoded})
                    changed = True
                else:
                    require(state == (row['late_response_state'] or row['outcome_state']) and exact_json(row['response'], encoded), 'conflicting repeated response/state')
            if receipt is not None:
                if row['receipt'] is None:
                    self._event('receipt', attempt_id, copy.deepcopy(receipt))
                    changed = True
                else:
                    require(exact_json(row['receipt'], receipt), 'conflicting repeated usage')
            return changed

    def record(self):
        with self._lock:
            state = self._state
            return {'schema_version': VERSION, 'snapshot': _snapshot_record(self._snapshot),
                'decision': self._decision.as_dict(), 'bindings': copy.deepcopy(state.bindings),
                'authorization': copy.deepcopy(state.authorization), 'events': copy.deepcopy(state.events),
                'events_sha256': sha(canonical(state.events)), 'attempts': copy.deepcopy(state.attempts),
                'accounting': state.accounting(), 'budget_incidents': copy.deepcopy(state.incidents),
                'revoked': state.revoked, 'invalidated': state.invalidated,
                'scope': 'offline-synthetic-fake-only', 'paid_provider_called': False,
                'campaign_scoring_enabled': False}


def replay_dispatch_v2(record):
    """Recompute from owned snapshot bytes and ordered transitions, without I/O."""
    require(type(record) is dict and record.get('schema_version') == VERSION, 'v2 record version')
    snapshot_record = record['snapshot']
    require(set(snapshot_record) == {'manifest', 'evidence'}, 'snapshot wrapper fields')
    snapshot = EvidenceSnapshot.capture(snapshot_record['manifest'], {key: base64.b64decode(value, validate=True)
        for key, value in snapshot_record['evidence'].items()})
    decision = preflight(snapshot)
    require(decision.accepted and decision.intent == 'smoke_seed', 'replay preflight refuses')
    bindings, auth = record['bindings'], record['authorization']
    expected_bindings = make_bindings(snapshot, task_id=bindings['task_id'], arm=bindings['arm'], run_id=bindings['run_id'])
    require(exact_json(bindings, expected_bindings), 'replay explicit bindings')
    require(set(auth) == {'snapshot_sha256', 'budget_micro_usd', 'expires_monotonic', 'scope'} and
            auth['snapshot_sha256'] == snapshot.fingerprint and auth['scope'] == 'offline-synthetic-only', 'authorization bindings')
    money(auth['budget_micro_usd'])
    require(type(auth['expires_monotonic']) in (int, float) and math.isfinite(auth['expires_monotonic']), 'authorization expiry')
    session = object.__new__(DispatchSessionV2)
    session._snapshot, session._decision = snapshot, decision
    session._lock = threading.RLock()
    session._state = _State(snapshot, expected_bindings, auth)
    for event in record['events']:
        session._state.apply(event['kind'], event['attempt_id'], event['details'], event['monotonic_seconds'])
    require(exact_json(session.record(), record), 'v2 replay differs from full evidence')
    return {'status': 'verified_offline_dispatch_v2', 'attempts': len(session._state.attempts),
            'accounting': session._state.accounting(), 'external_calls': 0, 'paid_provider_called': False}
