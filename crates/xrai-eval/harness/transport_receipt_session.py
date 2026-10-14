"""Prospective public fake transport; one inherited D01 financial authority.

The new owner reuses DispatchSessionV2's actual _State, authorization, lock,
reconciliation and accounting. Historical owners and their receipts are intact.
Entry receipts attest local fake consumption only, never remote delivery/usage.
"""
import base64
import copy
import json
from pathlib import Path

from agent_ledger import canonical, sha, fake_request, fake_receipt
from execution_gate import require, EvidenceSnapshot, OfflineAuthorization, make_smoke_fixture, preflight
from execution_dispatch_v2 import (DispatchSessionV2, FakeTransportV2, DispatchBarriers,
                                   make_bindings, replay_dispatch_v2)
from immutable_request_dispatch import capture_request

VERSION = 'xrai.eval.public-transport-session.v1'
WIRE_VERSION = 'xrai.eval.fake-transport-wire.v1'
MAX_BYTES = 128 * 1024
MAX_REQUESTS = 16
ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATHS = tuple('crates/xrai-eval/harness/' + name for name in (
    'transport_receipt_session.py', 'execution_dispatch_v2.py', 'execution_gate.py',
    'agent_ledger.py', 'offline_measurement.py', 'immutable_request_dispatch.py',
    'agent_adapter_protocol.py', 'session_tool_guard.py'))


def sources():
    return {path: sha((ROOT / path).read_bytes()) for path in SOURCE_PATHS}


def packed(raw):
    require(type(raw) is bytes and len(raw) <= MAX_BYTES, 'bounded immutable bytes')
    return {'base64': base64.b64encode(raw).decode(), 'bytes': len(raw), 'sha256': sha(raw)}


def unpack(value):
    require(type(value) is dict and set(value) == {'base64', 'bytes', 'sha256'} and
            type(value['base64']) is str and len(value['base64']) <= (MAX_BYTES + 2) // 3 * 4,
            'exact bounded payload evidence')
    raw = base64.b64decode(value['base64'], validate=True)
    require(type(value['bytes']) is int and value['bytes'] == len(raw) <= MAX_BYTES and
            value['sha256'] == sha(raw), 'full actual payload hash/size')
    return raw


def serialize(logical):
    """Wire is a distinct, deterministic full envelope prepared before reserve."""
    raw = canonical({'wire_version': WIRE_VERSION, 'request': json.loads(logical)}) + b'\n'
    packed(raw)
    return raw


def validate_wire(raw, logical_sha256):
    packed(raw)
    value = json.loads(raw)
    require(type(value) is dict and set(value) == {'wire_version', 'request'} and
            value['wire_version'] == WIRE_VERSION and canonical(value) + b'\n' == raw,
            'complete exact canonical wire envelope')
    logical = capture_request(canonical(value['request']))
    require(sha(logical) == logical_sha256 and raw == serialize(logical), 'wire binds logical request')
    return logical


class PublicFakeTransport:
    """This public entry observes its input bytes directly; no runtime profiler."""
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [])
        self._claimed = False

    def send(self, wire, identity, emit, barriers, outcome):
        require(type(wire) is bytes, 'public transport receives immutable final bytes')
        validate_wire(wire, identity['logical_sha256'])
        emit('entry', {'identity': copy.deepcopy(identity), 'consumed': packed(wire)})
        barriers.pause('transport')  # I/O boundary outside the session lock.
        if outcome == 'exception':
            raise RuntimeError('fake exception after entry')
        if outcome == 'timeout':
            raise TimeoutError('fake timeout after entry')
        if outcome == 'no_return':
            return None
        require(outcome == 'response', 'fixed fake outcome')
        response = b'public fake response'
        emit('response', {'identity': copy.deepcopy(identity), 'received': packed(response)})
        return response


class PublicTransportSession(DispatchSessionV2):
    """Fused public owner; no wrapped owner or second financial ledger.

    The historical constructor's exact built-in adapter remains an unused private
    construction requirement; all prospective transport I/O goes through send().
    The inherited fake dispatch entry is overridden and never invoked.
    """
    def __init__(self, snapshot, decision, authorization, transport, *, bindings,
                 current_manifest=None, current_evidence=None, clock, barriers=None):
        require(type(transport) is PublicFakeTransport and not transport._claimed,
                'one unclaimed public fake transport')
        super().__init__(snapshot, decision, authorization, FakeTransportV2(), bindings=bindings,
                         current_manifest=current_manifest, current_evidence=current_evidence,
                         clock=clock, barriers=barriers)
        transport._claimed = True
        self.transport = transport
        self._requests, self._transport_events = [], []
        self._active = set()
        self._closed = False
        self._source_bindings = sources()

    def _public_event(self, kind, details):
        with self._lock:
            require(len(self._transport_events) < 128, 'public event bound')
            if kind in ('entry', 'response', 'uncertain', 'reconcile'):
                request = next((r for r in self._requests if r['attempt_id'] == details.get('identity', {}).get('attempt_id')), None)
                require(request is not None and request['identity'] is not None and
                        canonical(details['identity']) == canonical(request['identity']), 'live receipt binds owned attempt/commit/serializer')
                if kind == 'entry':
                    require(not any(e['kind'] == 'entry' and e['details']['identity']['attempt_id'] == request['attempt_id'] for e in self._transport_events) and
                            unpack(details['consumed']) == unpack(request['wire']), 'live full consumed bytes, exactly one entry receipt')
                elif kind == 'response':
                    require(any(e['kind'] == 'entry' and e['details']['identity']['attempt_id'] == request['attempt_id'] for e in self._transport_events) and
                            not any(e['kind'] == 'response' and e['details']['identity']['attempt_id'] == request['attempt_id'] for e in self._transport_events), 'live response requires one actual entry')
                    unpack(details['received'])
            row = {'sequence': len(self._transport_events), 'kind': kind,
                   'details': copy.deepcopy(details),
                   'previous_sha256': sha(canonical(self._transport_events[-1])) if self._transport_events else None,
                   'ledger_events': len(self._state.events)}
            require(len(canonical(row)) <= MAX_BYTES * 4, 'public event byte bound')
            self._transport_events.append(row)

    def dispatch(self, attempt_id, call_id, request, max_charge_micro_usd, *, retry_of=None, cancel=None):
        with self._lock:
            require(not self._closed and len(self._requests) < MAX_REQUESTS and
                    type(attempt_id) is str and 0 < len(attempt_id.encode()) <= 256 and
                    type(call_id) is str and 0 < len(call_id.encode()) <= 256 and
                    type(max_charge_micro_usd) is int and max_charge_micro_usd >= 0 and
                    (retry_of is None or type(retry_of) is str) and
                    all(row['attempt_id'] != attempt_id for row in self._requests), 'unique bounded public request')
            row = {'attempt_id': attempt_id, 'call_id': call_id, 'retry_of': retry_of,
                   'maximum_micro_usd': max_charge_micro_usd, 'logical': None, 'wire': None,
                   'identity': None, 'status': 'capturing', 'error': None, 'transport_plan': None}
            self._requests.append(row)
            self._active.add(attempt_id)
            self._public_event('request', {k: row[k] for k in ('attempt_id', 'call_id', 'retry_of', 'maximum_micro_usd')})
        try:
            logical = capture_request(request)
            require(sha(logical) == self._snapshot.manifest['request_sha256'], 'captured manifest request')
            wire = serialize(logical)
            with self._lock:
                row['logical'], row['wire'] = packed(logical), packed(wire)
                self._public_event('prepared', {'attempt_id': attempt_id, 'logical': row['logical'], 'wire': row['wire']})
                self._check()
                # Outcomes are selected locally before any financial commitment.
                mode = self.transport.outcomes.pop(0) if self.transport.outcomes else 'response'
                require(mode in ('response', 'exception', 'timeout', 'no_return', 'pre_entry_refusal'), 'owned fake mode')
                row['transport_plan'] = mode
                self._public_event('plan', {'attempt_id': attempt_id, 'outcome': mode})
                if mode == 'pre_entry_refusal':
                    row['status'] = 'refused_before_entry'
                    self._public_event('absent', {'attempt_id': attempt_id, 'reason': 'public_fake_preentry_policy'})
                    return {'status': row['status'], 'committed': False, 'entry_observed': False}
                self._event('reserve', attempt_id, {'call_id': call_id, 'request': json.loads(logical),
                            'maximum': max_charge_micro_usd, 'retry_of': retry_of})
                attempt = self._state.attempts[attempt_id]
                if attempt['state'] == 'rejected_before_commit':
                    row['status'] = 'rejected_before_commit'
                    return {'status': row['status'], 'committed': False, 'entry_observed': False}
            self._barriers.pause('before_commit')
            with self._lock:
                if cancel is not None and cancel.is_set() and not attempt['cancel_requested']:
                    self._event('cancel', attempt_id, {})
                try:
                    self._check()
                except ValueError:
                    pass
                reason = 'cancel_requested' if attempt['cancel_requested'] else self._state.refusal(self._clock())
                if reason is not None:
                    self._event('reject_before_commit', attempt_id, {'reason': reason})
                    row['status'] = 'rejected_before_commit'
                    return {'status': row['status'], 'committed': False, 'entry_observed': False}
                self._event('commit', attempt_id, {})
                commit = self._state.events[-1]
                row['identity'] = {**{k: self._state.bindings[k] for k in ('task_id', 'arm', 'run_id')},
                    'call_id': call_id, 'attempt_id': attempt_id, 'commit_sha256': sha(canonical(commit)),
                    'logical_sha256': sha(logical), 'wire_sha256': sha(wire),
                    'wire_bytes': len(wire), 'wire_version': WIRE_VERSION}
                row['status'] = 'committed'
            self._barriers.pause('after_commit')
            response = self.transport.send(wire, copy.deepcopy(row['identity']), self._public_event, self._barriers, mode)
            with self._lock:
                if cancel is not None and cancel.is_set() and not attempt['cancel_requested']:
                    self._event('cancel', attempt_id, {})
                require(sum(e['kind'] == 'entry' and e['details']['identity']['attempt_id'] == attempt_id for e in self._transport_events) == 1, 'public entry receipt missing/duplicated')
                if response is not None:
                    observed = [e for e in self._transport_events if e['kind'] == 'response' and e['details']['identity']['attempt_id'] == attempt_id]
                    require(len(observed) == 1 and unpack(observed[0]['details']['received']) == response, 'returned response matches public full observation')
                if response is None:
                    self._public_event('uncertain', {'identity': row['identity'], 'reason': 'return_absent', 'entry_observed': True, 'response_observed': False})
                super().reconcile(attempt_id, state='completed' if response is not None else 'sent_no_response', response=response)
                row['status'] = attempt['state']
                return {'status': row['status'], 'committed': True, 'entry_observed': True}
        except Exception as error:
            with self._lock:
                attempt = self._state.attempts.get(attempt_id)
                row['error'] = type(error).__name__
                if attempt is not None and attempt['state'] == 'reserved':
                    self._event('invalidate', None, {'reason': 'public precommit error'})
                    self._event('reject_before_commit', attempt_id, {'reason': 'snapshot_invalidated'})
                if attempt is not None and attempt['state'] == 'committed':
                    self._public_event('uncertain', {'identity': row['identity'], 'reason': 'exception_after_commit', 'entry_observed': any(e['kind'] == 'entry' and e['details']['identity']['attempt_id'] == attempt_id for e in self._transport_events), 'response_observed': any(e['kind'] == 'response' and e['details']['identity']['attempt_id'] == attempt_id for e in self._transport_events)})
                    super().reconcile(attempt_id, state='timeout' if type(error) is TimeoutError else 'sent_no_response')
                row['status'] = attempt['state'] if attempt is not None else 'refused_before_reserve'
            raise
        finally:
            with self._lock:
                self._active.remove(attempt_id)
                self._public_event('finish', {'attempt_id': attempt_id, 'status': row['status'], 'error': row['error']})

    def reconcile(self, attempt_id, *, state=None, response=None, receipt=None):
        """Late observation is exact/idempotent; the original authority counts it once."""
        with self._lock:
            require(not self._closed and attempt_id not in self._active, 'late observation after initial I/O')
            if response is not None:
                packed(response)  # Refuse oversized/non-byte observations before touching authority.
            if receipt is not None:
                receipt = json.loads(capture_request(receipt))
            attempt = self._state.attempts[attempt_id]
            row = next(row for row in self._requests if row['attempt_id'] == attempt_id)
            require(row['identity'] is not None, 'late observation requires original commitment')
            before = len(self._state.events)
            try:
                return super().reconcile(attempt_id, state=state, response=response, receipt=receipt)
            finally:
                delta = self._state.events[before:]
                if delta:
                    response_event = next((e for e in delta if e['kind'] == 'late_response'), None)
                    receipt_event = next((e for e in delta if e['kind'] == 'receipt'), None)
                    self._public_event('reconcile', {'identity': row['identity'],
                        'state': response_event['details']['state'] if response_event else None,
                        'response': response_event['details']['response'] if response_event else None,
                        'receipt': receipt_event['details'] if receipt_event else None})

    def record(self, *, close=False):
        with self._lock:
            if close:
                require(not self._active, 'cannot close during actual transport/capture')
                self._closed = True
            return {'schema_version': VERSION, 'source_bindings': copy.deepcopy(self._source_bindings),
                    'requests': copy.deepcopy(self._requests), 'transport_events': copy.deepcopy(self._transport_events),
                    'ledger': super().record(), 'active': sorted(self._active), 'closed': self._closed,
                    'remote_delivery_observed': False, 'model_executed': False, 'model_tokens': None,
                    'provider_charge': None, 'paid_provider_called': False}


def make_public_fake_session(*, outcomes=None, barriers=None, budget=1500, clock=lambda: 1):
    manifest, evidence = make_smoke_fixture()
    snapshot = EvidenceSnapshot.capture(manifest, evidence)
    return PublicTransportSession(snapshot, preflight(snapshot), OfflineAuthorization(snapshot.fingerprint, budget, 100),
        PublicFakeTransport(outcomes), bindings=make_bindings(snapshot, task_id='D0-RS-01', arm='direct', run_id='public-transport-smoke'),
        clock=clock, barriers=barriers)


def replay_public_transport(record, *, require_closed=True):
    """Recompute financial authority and full public observations from owned bytes.

    This is local evidence validation, not a cryptographic signature from a
    provider. No transport is called while replaying.
    """
    expected_fields = {'schema_version', 'source_bindings', 'requests', 'transport_events', 'ledger',
                       'active', 'closed', 'remote_delivery_observed', 'model_executed', 'model_tokens',
                       'provider_charge', 'paid_provider_called'}
    require(type(record) is dict and set(record) == expected_fields and record['schema_version'] == VERSION and
            len(canonical(record)) <= 16 * 1024 * 1024, 'bounded public profile')
    require(type(record['closed']) is bool and (not require_closed or record['closed']) and
            record['remote_delivery_observed'] is False and record['model_executed'] is False and
            record['paid_provider_called'] is False and record['model_tokens'] is None and
            record['provider_charge'] is None and canonical(record['source_bindings']) == canonical(sources()), 'actual fake source/method scope')
    ledger = record['ledger']
    replay_dispatch_v2(ledger)
    requests, events = record['requests'], record['transport_events']
    require(type(requests) is list and len(requests) <= MAX_REQUESTS and type(events) is list and len(events) <= 128 and
            type(record['active']) is list and all(type(x) is str for x in record['active']), 'bounded explicit records')
    rows, observation = {}, {}
    request_shape = {'attempt_id', 'call_id', 'retry_of', 'maximum_micro_usd', 'logical', 'wire', 'identity', 'status', 'error', 'transport_plan'}
    for row in requests:
        require(type(row) is dict and set(row) == request_shape and type(row['attempt_id']) is str and
                0 < len(row['attempt_id'].encode()) <= 256 and row['attempt_id'] not in rows,
                'exact unique request rows')
        require(type(row['call_id']) is str and 0 < len(row['call_id'].encode()) <= 256 and
                type(row['maximum_micro_usd']) is int and row['maximum_micro_usd'] >= 0 and
                (row['retry_of'] is None or type(row['retry_of']) is str), 'typed request identities/maximum')
        rows[row['attempt_id']] = row
        observation[row['attempt_id']] = {'requested': False, 'prepared': False, 'finish': False,
                                         'entry': None, 'response': None, 'uncertain': None, 'absent': False,
                                         'reconcile': [], 'plan': False}
        if row['logical'] is not None:
            logical = unpack(row['logical'])
            require(sha(capture_request(logical)) == ledger['snapshot']['manifest']['request_sha256'], 'manifest logical bytes')
            wire = unpack(row['wire'])
            validate_wire(wire, sha(logical))
        else:
            require(row['wire'] is None and row['identity'] is None, 'failed capture has no payload/entry authority')
        attempt = ledger['attempts'].get(row['attempt_id'])
        if attempt is not None:
            reserve = next(e for e in ledger['events'] if e['kind'] == 'reserve' and e['attempt_id'] == row['attempt_id'])
            require(row['logical'] is not None and canonical(reserve['details']) == canonical({
                'call_id': row['call_id'], 'request': json.loads(unpack(row['logical'])),
                'maximum': row['maximum_micro_usd'], 'retry_of': row['retry_of']}), 'reserve binds complete owned request')
            if attempt['committed']:
                commit = next(e for e in ledger['events'] if e['kind'] == 'commit' and e['attempt_id'] == row['attempt_id'])
                expected = {**{k: ledger['bindings'][k] for k in ('task_id', 'arm', 'run_id')},
                    'call_id': row['call_id'], 'attempt_id': row['attempt_id'], 'commit_sha256': sha(canonical(commit)),
                    'logical_sha256': row['logical']['sha256'], 'wire_sha256': row['wire']['sha256'],
                    'wire_bytes': row['wire']['bytes'], 'wire_version': WIRE_VERSION}
                require(canonical(row['identity']) == canonical(expected), 'exact task/arm/run/call/attempt/commit/payload binding')
            else:
                require(row['identity'] is None, 'uncommitted request has no transport identity')
        else:
            require(row['identity'] is None, 'unreserved request has no transport identity')
    require(set(ledger['attempts']) <= set(rows), 'every financial attempt retained publicly')
    last_prefix = 0
    requested_order = []
    for sequence, event in enumerate(events):
        require(type(event) is dict and set(event) == {'sequence', 'kind', 'details', 'previous_sha256', 'ledger_events'} and
                type(event['sequence']) is int and event['sequence'] == sequence and
                event['previous_sha256'] == (sha(canonical(events[sequence - 1])) if sequence else None) and
                type(event['ledger_events']) is int and last_prefix <= event['ledger_events'] <= len(ledger['events']),
                'complete ordered public event/hash/financial prefixes')
        last_prefix = event['ledger_events']
        kind, detail = event['kind'], event['details']
        require(type(detail) is dict, 'typed event details')
        attempt_id = detail.get('attempt_id') if kind in ('request', 'prepared', 'plan', 'absent', 'finish') else detail.get('identity', {}).get('attempt_id')
        require(attempt_id in rows, 'observation belongs to captured request')
        row, obs = rows[attempt_id], observation[attempt_id]
        if kind == 'request':
            require(not obs['requested'] and canonical(detail) == canonical({k: row[k] for k in ('attempt_id', 'call_id', 'retry_of', 'maximum_micro_usd')}), 'request admission bijection')
            obs['requested'] = True
            requested_order.append(attempt_id)
        else:
            require(obs['requested'], 'observation requires public admission')
            if kind == 'prepared':
                require(not obs['prepared'] and not obs['finish'] and canonical(detail) == canonical({'attempt_id': attempt_id, 'logical': row['logical'], 'wire': row['wire']}) and row['logical'] is not None,
                        'one immutable payload prepared before financial reservation')
                require(not any(e['attempt_id'] == attempt_id and e['kind'] == 'reserve' for e in ledger['events'][:last_prefix]), 'payload before reserve')
                obs['prepared'] = True
            elif kind == 'plan':
                require(obs['prepared'] and not obs['plan'] and not obs['finish'] and
                        row['transport_plan'] in ('response', 'exception', 'timeout', 'no_return', 'pre_entry_refusal') and
                        detail == {'attempt_id': attempt_id, 'outcome': row['transport_plan']} and
                        not any(e['attempt_id'] == attempt_id and e['kind'] == 'reserve' for e in ledger['events'][:last_prefix]),
                        'fixed public fake plan before reserve/commit')
                obs['plan'] = True
            elif kind == 'absent':
                require(obs['plan'] and row['transport_plan'] == 'pre_entry_refusal' and not obs['absent'] and not obs['finish'] and attempt_id not in ledger['attempts'] and
                        detail == {'attempt_id': attempt_id, 'reason': 'public_fake_preentry_policy'}, 'actual preentry refusal knows absence')
                obs['absent'] = True
            elif kind == 'finish':
                require(not obs['finish'] and canonical(detail) == canonical({'attempt_id': attempt_id, 'status': row['status'], 'error': row['error']}), 'one exact public terminal outcome')
                obs['finish'] = True
            else:
                require(kind in ('entry', 'response', 'uncertain', 'reconcile') and obs['prepared'] and row['identity'] is not None and
                        canonical(detail['identity']) == canonical(row['identity']), 'actual observed immutable entry identity')
                require(any(e['kind'] == 'commit' and e['attempt_id'] == attempt_id for e in ledger['events'][:last_prefix]), 'observation follows same financial commitment')
                if kind == 'entry':
                    require(not obs['finish'] and obs['entry'] is None and set(detail) == {'identity', 'consumed'} and
                            unpack(detail['consumed']) == unpack(row['wire']), 'one public entry receipt binds bytes actually consumed')
                    obs['entry'] = event
                elif kind == 'response':
                    require(not obs['finish'] and obs['entry'] is not None and obs['response'] is None and obs['uncertain'] is None and set(detail) == {'identity', 'received'}, 'response follows observed entry exactly once')
                    unpack(detail['received'])
                    obs['response'] = event
                elif kind == 'uncertain':
                    require(not obs['finish'] and obs['uncertain'] is None and set(detail) == {'identity', 'reason', 'entry_observed', 'response_observed'} and type(detail['entry_observed']) is bool and type(detail['response_observed']) is bool and detail['response_observed'] is (obs['response'] is not None) and
                            detail['entry_observed'] is (obs['entry'] is not None) and detail['reason'] in ('exception_after_commit', 'return_absent'), 'one explicit uncertainty after commitment')
                    if detail['reason'] == 'return_absent':
                        require(obs['entry'] is not None and obs['response'] is None and row['error'] is None, 'absent return follows actual entry without observed response')
                    else:
                        require(type(row['error']) is str, 'uncertainty exception actually recorded')
                        if ((row['transport_plan'] == 'exception' and row['error'] == 'RuntimeError') or
                                (row['transport_plan'] == 'timeout' and row['error'] == 'TimeoutError')):
                            require(obs['entry'] is not None and detail['entry_observed'], 'fixed fake exception/timeout path enters transport before raising')
                    obs['uncertain'] = event
                else:
                    require(obs['finish'] and set(detail) == {'identity', 'state', 'response', 'receipt'}, 'late observation after initial finish')
                    if detail['response'] is not None:
                        unpack(detail['response'])
                    obs['reconcile'].append(event)
    require(requested_order == [row['attempt_id'] for row in requests], 'all public requests retained once and in admission order')
    active = []
    for attempt_id, row in rows.items():
        obs, attempt = observation[attempt_id], ledger['attempts'].get(attempt_id)
        require(obs['prepared'] is (row['logical'] is not None) and obs['plan'] is (row['transport_plan'] is not None), 'capture/prepared/plan correspondence')
        require(attempt is None or obs['plan'], 'reserved operation must retain prospective fake plan')
        if not obs['finish']:
            active.append(attempt_id)
        elif attempt is None:
            require(row['status'] == ('refused_before_entry' if obs['absent'] else 'refused_before_reserve') and
                    (row['error'] is None if obs['absent'] else type(row['error']) is str), 'exact unreserved refusal outcome')
        else:
            # Late response never changes financial terminal state.
            require(row['status'] == attempt['state'], 'public outcome agrees with original financial authority')
        if attempt is not None and attempt['committed']:
            initial = [e for e in ledger['events'] if e['attempt_id'] == attempt_id and e['kind'] == 'outcome']
            if initial:
                require(len(initial) == 1 and (obs['response'] is not None or obs['uncertain'] is not None), 'all committed initial outcomes publicly observed')
                event = obs['uncertain'] or obs['response']
                require(event['ledger_events'] <= initial[0]['sequence'], 'observation precedes financial outcome')
                require(canonical(initial[0]['details']['response']) == canonical(obs['response']['details']['received'] if obs['response'] and obs['uncertain'] is None else None), 'full response bytes match financial authority')
            else:
                require(not obs['finish'], 'finished commit must have observed outcome')
            late = [e for e in ledger['events'] if e['attempt_id'] == attempt_id and e['kind'] in ('late_response', 'receipt')]
            projected = []
            for event in obs['reconcile']:
                detail = event['details']
                if detail['response'] is not None:
                    projected.append(('late_response', {'state': detail['state'], 'response': detail['response']}))
                if detail['receipt'] is not None:
                    projected.append(('receipt', detail['receipt']))
            require(canonical(projected) == canonical([(e['kind'], e['details']) for e in late]), 'late receipts/response complete bijection, no fabrication/duplication')
        else:
            require(obs['entry'] is None and obs['response'] is None and obs['uncertain'] is None and not obs['reconcile'], 'uncommitted has provable no entry')
    require(sorted(active) == record['active'] and (not record['closed'] or not active), 'snapshot explicitly retains all in-flight operations')
    return {'verified': True, 'profile': VERSION, 'closed': record['closed'], 'recorded_requests': len(rows),
            'reservations': len(ledger['attempts']), 'commitments': sum(a['committed'] for a in ledger['attempts'].values()),
            'entries': sum(o['entry'] is not None for o in observation.values()),
            'responses': sum(o['response'] is not None for o in observation.values()) + sum(
                e['details']['response'] is not None for o in observation.values() for e in o['reconcile']),
            'uncertain_outcomes': sum(o['uncertain'] is not None for o in observation.values()),
            'accounting': ledger['accounting'], 'remote_delivery_observed': False, 'model_tokens': None,
            'provider_charge': None, 'paid_provider_called': False}
