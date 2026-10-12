"""Replayable agent session and fake adapter. No paid provider adapter is enabled.

Money is integral USD micro-units. A dispatched unknown charge retains its entire
reservation. Fake prices demonstrate arithmetic, never assert provider tariffs.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import threading

from runner import canonical, payload, sha
from offline_measurement import VERSION as MEASUREMENT_VERSION, verify_measurement

VERSION = 'xrai.eval.agent.v1'
TERMINAL = {'completed', 'timeout', 'cancelled', 'partial', 'sent_no_response', 'rejected_before_send'}


def money(value):
    if type(value) is not int or value < 0:
        raise ValueError('money must be nonnegative integer USD micro-units')
    return value


def receipt_usage(receipt):
    """Provider totals remain totals; cached/reasoning categories are subsets."""
    usage = receipt['usage']
    for name in ['input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_output_tokens']:
        money(usage[name])
    if usage['cached_input_tokens'] > usage['input_tokens'] or usage['reasoning_output_tokens'] > usage['output_tokens']:
        raise ValueError('usage subset exceeds corresponding total')
    if receipt['category_semantics'] != {'cached_input_tokens': 'subset_of_input_tokens',
                                         'reasoning_output_tokens': 'subset_of_output_tokens'}:
        raise ValueError('unknown receipt category semantics')
    return usage


class Ledger:
    def __init__(self, metadata, budget_micro_usd):
        self.metadata = copy.deepcopy(metadata)
        self.budget = money(budget_micro_usd)
        self.calls = {}
        self.events = []
        self.receipts = {}
        self.budget_incidents = []
        self.lock = threading.RLock()

    def _event(self, kind, attempt_id, details, timestamp):
        if type(timestamp) not in (float, int) or not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError('invalid monotonic timestamp')
        if self.events and timestamp < self.events[-1]['monotonic_seconds']:
            raise ValueError('event time moved backwards')
        event = {'sequence': len(self.events), 'kind': kind, 'attempt_id': attempt_id,
                 'monotonic_seconds': timestamp, 'details': copy.deepcopy(details)}
        # Hash chain detects altered event ordering and payload during replay.
        event['previous_event_sha256'] = sha(canonical(self.events[-1])) if self.events else None
        self.events.append(event)

    def _accounting(self):
        known = sum(row['receipt']['observed_charge_micro_usd'] for row in self.calls.values() if row['receipt'])
        reserved = sum(row['reservation_micro_usd'] for row in self.calls.values()
                       if row['receipt'] is None and row['state'] != 'rejected_before_send')
        unknown = [key for key, row in self.calls.items() if row['sent'] and row['receipt'] is None]
        complete = not unknown
        return {'known_observed_charge_micro_usd': known, 'retained_reservation_micro_usd': reserved,
                'budget_micro_usd': self.budget, 'unknown_charge_attempts': unknown,
                'observed_cost_complete': complete, 'observed_cost_micro_usd': known if complete else None,
                'supported_cost_interval_micro_usd': [known, known + reserved],
                'reservation_is_provider_charge_guarantee': False,
                'budget_limit_respected': not self.budget_incidents and known + reserved <= self.budget}

    def reserve(self, attempt_id, call_id, request, max_charge_micro_usd, *, timestamp, retry_of=None):
        with self.lock:
            maximum = money(max_charge_micro_usd)
            limits = request['limits']
            price = self.metadata['price']
            required = money(limits['input_tokens']) * money(price['input']) + money(limits['output_tokens']) * money(price['output'])
            if maximum < required or request['maximum_charge_policy'] != 'fake-enforced':
                raise ValueError('reservation does not cover enforced maximum and known prices')
            if attempt_id in self.calls:
                raise ValueError('duplicate local attempt')
            if retry_of is not None:
                previous = self.calls.get(retry_of)
                if previous is None or previous['call_id'] != call_id or previous['state'] not in TERMINAL:
                    raise ValueError('retry must identify terminal previous attempt of same call')
            elif any(row['call_id'] == call_id for row in self.calls.values()):
                raise ValueError('existing call requires explicit retry link')
            details = {'call_id': call_id, 'request': copy.deepcopy(request),
                       'max_charge_micro_usd': maximum, 'retry_of': retry_of}
            account = self._accounting()
            allowed = not self.budget_incidents and account['known_observed_charge_micro_usd'] + account['retained_reservation_micro_usd'] + maximum <= self.budget
            state = 'reserved' if allowed else 'rejected_before_send'
            self._event('reserve' if allowed else 'reject', attempt_id, details, timestamp)
            self.calls[attempt_id] = {'call_id': call_id, 'retry_of': retry_of,
                                     'request': payload(canonical(request), len(canonical(request))),
                                     'state': state, 'sent': False, 'response_chunks': [], 'receipt': None,
                                     'reservation_micro_usd': maximum if allowed else 0}
            return allowed

    def send(self, attempt_id, *, timestamp):
        with self.lock:
            row = self.calls[attempt_id]
            if row['state'] != 'reserved':
                raise ValueError('send requires reserved attempt')
            self._event('send', attempt_id, {}, timestamp)
            row['state'], row['sent'] = 'sent', True

    def chunk(self, attempt_id, data, *, timestamp):
        with self.lock:
            row = self.calls[attempt_id]
            if row['state'] not in {'sent', 'streaming'}:
                raise ValueError('chunk requires dispatched active attempt')
            value = payload(data, len(data))
            self._event('chunk', attempt_id, value, timestamp)
            row['response_chunks'].append(value)
            row['state'] = 'streaming'

    def finish(self, attempt_id, state, *, timestamp):
        with self.lock:
            row = self.calls[attempt_id]
            if state not in TERMINAL or row['state'] not in {'reserved', 'sent', 'streaming'}:
                raise ValueError('invalid terminal transition')
            if state == 'rejected_before_send' and row['sent']:
                raise ValueError('sent attempt cannot be rejected before send')
            if state != 'rejected_before_send' and not row['sent']:
                raise ValueError('unsent attempt cannot have dispatched outcome')
            self._event('finish', attempt_id, {'state': state}, timestamp)
            row['state'] = state
            # Timeout/cancel never frees a possible provider charge.
            if not row['sent']:
                row['reservation_micro_usd'] = 0

    def receipt(self, attempt_id, receipt, *, timestamp):
        with self.lock:
            row = self.calls[attempt_id]
            if not row['sent']:
                raise ValueError('receipt for unsent attempt')
            if row['state'] not in TERMINAL:
                raise ValueError('final receipt requires terminal attempt; streaming charge remains reserved')
            receipt_usage(receipt)
            charge = money(receipt['observed_charge_micro_usd'])
            estimate = money(receipt['estimated_charge_micro_usd'])
            price = self.metadata['price']
            if receipt['price_version'] != price['version'] or estimate != receipt['usage']['input_tokens'] * price['input'] + receipt['usage']['output_tokens'] * price['output']:
                raise ValueError('receipt estimate/price version mismatch')
            key = receipt['provider'] + ':' + receipt['provider_receipt_id']
            if key in self.receipts:
                if self.receipts[key] == (attempt_id, receipt):
                    return False  # Idempotent exact duplicate; never double charges.
                raise ValueError('receipt identity duplicated across attempts or changed')
            if row['receipt'] is not None:
                raise ValueError('attempt already has a different receipt')
            self._event('receipt', attempt_id, receipt, timestamp)
            self.receipts[key] = (attempt_id, copy.deepcopy(receipt))
            row['receipt'] = copy.deepcopy(receipt)
            import base64
            limits = json.loads(base64.b64decode(row['request']['base64']))['limits']
            violated = (charge > row['reservation_micro_usd'] or receipt['usage']['input_tokens'] > limits['input_tokens']
                        or receipt['usage']['output_tokens'] > limits['output_tokens'])
            if violated:
                self.budget_incidents.append({'attempt_id': attempt_id,
                                             'reserved_maximum_micro_usd': row['reservation_micro_usd'],
                                             'observed_charge_micro_usd': charge,
                                             'reason': 'observed usage/charge exceeded enforced maximum; admissions closed'})
            return True

    def record(self):
        with self.lock:
            return {'schema_version': VERSION, 'metadata': copy.deepcopy(self.metadata),
                    'budget_micro_usd': self.budget, 'events': copy.deepcopy(self.events),
                    'attempts': copy.deepcopy(self.calls), 'accounting': self._accounting(),
                    'events_sha256': sha(canonical(self.events)), 'budget_incidents': copy.deepcopy(self.budget_incidents),
                    'outcome': 'not_judged', 'adapter': 'fake-offline-v1',
                    'paid_provider_called': False}


def validate_schema(value, filename):
    from jsonschema import Draft202012Validator
    schema = json.loads(Path(__file__).with_name(filename).read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)


def replay_agent(record):
    validate_schema(record, 'agent-v1.schema.json')
    ledger = Ledger(record['metadata'], record['budget_micro_usd'])
    for event in record['events']:
        kind, attempt = event['kind'], event['attempt_id']
        details, timestamp = event['details'], event['monotonic_seconds']
        if kind in {'reserve', 'reject'}:
            ledger.reserve(attempt, details['call_id'], details['request'], details['max_charge_micro_usd'],
                           retry_of=details['retry_of'], timestamp=timestamp)
        elif kind == 'send':
            ledger.send(attempt, timestamp=timestamp)
        elif kind == 'chunk':
            import base64
            data = base64.b64decode(details['base64'], validate=True)
            if payload(data, len(data)) != details:
                raise ValueError('response bytes/accounting mismatch')
            ledger.chunk(attempt, data, timestamp=timestamp)
        elif kind == 'finish':
            ledger.finish(attempt, details['state'], timestamp=timestamp)
        elif kind == 'receipt':
            ledger.receipt(attempt, details, timestamp=timestamp)
        else:
            raise ValueError('unknown ledger event')
    if ledger.record() != record:
        raise ValueError('agent ledger replay differs from event evidence')
    return {'status': 'verified_fake_session', 'attempts': len(ledger.calls), 'accounting': ledger._accounting()}


def replay_versioned(record, *, original=None):
    version = record.get('schema_version')
    if version in {'xrai.eval.local.v1', 'xrai.eval.local.v2'}:
        from runner import replay
        validate_schema(record, 'result.schema.json' if version.endswith('.v1') else 'result-v2.schema.json')
        return replay(record)
    if version == MEASUREMENT_VERSION:
        validate_schema(record, 'measurement-v1.schema.json')
        if original is None:
            raise ValueError('derived measurement requires original local record')
        return verify_measurement(record, original)
    if version == VERSION:
        return replay_agent(record)
    raise ValueError(f'unsupported record version: {version}')


def fake_metadata():
    return {'task_id': 'D0-RS-01', 'dataset_sha256': sha(b'fake-D0-demonstration'),
            'arm': 'fake-ledger-demonstration', 'model': {'provider': 'fake', 'name': 'fake-stream-v1',
            'version': '1', 'effort': 'fixed'}, 'policy': {'id': 'offline-no-provider-v1',
            'config_sha256': sha(b'offline-no-provider-v1')}, 'run_id': 'fake-L4-01',
            'price': {'version': 'fake-usd-v1', 'source': 'synthetic-test-fixture',
            'date': '2026-10-12', 'currency': 'USD', 'unit': 'micro_usd_per_token',
            'input': 2, 'output': 3}, 'setup_amortization': {'regime': 'none', 'uses': 1,
            'gross_micro_usd': 0}, 'credentials': 'never-recorded'}


def fake_request():
    return {'orientation': 'Offline fake session; no source oracle.', 'tool_definitions': [{'name': 'read', 'input': 'path'}],
            'messages': [{'role': 'user', 'content': 'localize função'}],
            'tool_calls': [], 'expansions': [], 'edits': [], 'tests': [],
            'limits': {'input_tokens': 100, 'output_tokens': 100}, 'maximum_charge_policy': 'fake-enforced'}


def fake_receipt(identifier='fake-receipt-1'):
    return {'provider': 'fake', 'provider_receipt_id': identifier,
            'usage': {'input_tokens': 10, 'output_tokens': 5, 'cached_input_tokens': 4, 'reasoning_output_tokens': 2},
            'category_semantics': {'cached_input_tokens': 'subset_of_input_tokens',
                                   'reasoning_output_tokens': 'subset_of_output_tokens'},
            'price_version': 'fake-usd-v1', 'estimated_charge_micro_usd': 35,
            'observed_charge_micro_usd': 35, 'observed_charge_source': 'synthetic-receipt'}


def fake_session(unknown=False):
    ledger = Ledger(fake_metadata(), 1000)
    ledger.reserve('a1', 'c1', fake_request(), 500, timestamp=0)
    ledger.send('a1', timestamp=1)
    ledger.chunk('a1', b'partial' if unknown else 'resposta 🌱'.encode(), timestamp=2)
    ledger.finish('a1', 'timeout' if unknown else 'completed', timestamp=3)
    if not unknown:
        ledger.receipt('a1', fake_receipt(), timestamp=4)
    return ledger.record()


def readiness(*, dataset='D0', admitted=0, model_available=False, credentials_available=False,
              monetary_budget=None, platform='Linux', arbitrary_containment=False, measurement_profile=True, real_adapter_available=False):
    reasons = []
    if not real_adapter_available:
        reasons.append('real provider adapter not implemented/configured; fake only')
    if not model_available:
        reasons.append('model/version/effort adapter not configured')
    if not credentials_available:
        reasons.append('provider credentials/resources not configured')
    if monetary_budget is None:
        reasons.append('authorized monetary ceiling absent; paid adapter disabled')
    elif money(monetary_budget) == 0:
        reasons.append('authorized monetary ceiling cannot fund a dispatch')
    if platform != 'Linux' or not arbitrary_containment:
        reasons.append('arbitrary agent requires disposable containment; macOS smoke is insufficient')
    if not measurement_profile:
        reasons.append('controlled-content tokenizer/serializer profile missing')
    if dataset == 'D1' and admitted != 32:
        reasons.append(f'D1 corpus not admitted: {admitted}/32')
    if dataset not in {'D0', 'seed', 'D1'}:
        reasons.append('unknown dataset')
    return {'offline_fake_ready': True, 'paid_adapter_enabled': False,
            'real_run_ready': not reasons, 'run_kind': 'campaign' if dataset == 'D1' else 'paired_smoke',
            'dataset': dataset, 'reasons': reasons,
            'readiness_does_not_authorize_provider_call': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['fake', 'unknown', 'readiness', 'replay'])
    parser.add_argument('--record')
    parser.add_argument('--original')
    args = parser.parse_args()
    if args.mode == 'replay':
        result = replay_versioned(json.loads(Path(args.record).read_text()),
                                  original=json.loads(Path(args.original).read_text()) if args.original else None)
    elif args.mode == 'readiness':
        result = {'D0': readiness(), 'D1': readiness(dataset='D1')}
    else:
        result = fake_session(unknown=args.mode == 'unknown')
    print(json.dumps(result, indent=2, ensure_ascii=False))
