"""C03 offline dispatch boundary: content-bound intent before ledger reservation.

This entry point supports only the built-in fake adapter. It neither authorizes
paid resources nor asserts that simulated controls prove OS containment. D1
stays closed until a complete immutable corpus/event reconciler is connected.
"""
from dataclasses import dataclass, field
import copy
import json
import threading
import time

from agent_ledger import (Ledger, canonical, sha, money, fake_metadata,
                          fake_request, fake_receipt, replay_agent)

VERSION = 'xrai.eval.execution-gate.v1'
INTENTS = {'replay_offline', 'smoke_seed', 'campaign_d1'}
MANIFEST_KEYS = {'schema_version', 'intent', 'dataset', 'task_ids', 'configuration',
                 'model', 'tools', 'measurement', 'controls', 'protocol',
                 'request_sha256', 'evidence_sha256'}


def require(value, message):
    if not value:
        raise ValueError(message)


def exact_json(actual, expected):
    # Python equality conflates 1/True and 100/100.0; protocol types do not.
    return canonical(actual) == canonical(expected)


@dataclass(frozen=True)
class EvidenceSnapshot:
    """Owned immutable bytes, not a digest pointing at a mutable directory."""
    manifest_bytes: bytes
    evidence: tuple
    _fingerprint: str = field(init=False, repr=False)

    def __post_init__(self):
        require(type(self.manifest_bytes) is bytes and type(self.evidence) is tuple,
                'snapshot must own immutable bytes/tuple')
        require(all(type(pair) is tuple and len(pair) == 2 and type(pair[0]) is str
                    and type(pair[1]) is bytes for pair in self.evidence), 'immutable evidence entries')
        require(self.evidence == tuple(sorted(self.evidence)) and
                len({k for k, _ in self.evidence}) == len(self.evidence), 'unique sorted evidence entries')
        require(type(json.loads(self.manifest_bytes)) is dict, 'manifest must be an object')
        object.__setattr__(self, '_fingerprint', sha(canonical({
            'manifest': sha(self.manifest_bytes), 'evidence': {k: sha(v) for k, v in self.evidence}})))

    @classmethod
    def capture(cls, manifest, evidence):
        require(type(manifest) is dict and type(evidence) is dict, 'snapshot inputs')
        require(all(type(k) is str and type(v) is bytes for k, v in evidence.items()),
                'evidence must be named bytes')
        return cls(canonical(manifest), tuple(sorted(evidence.items())))

    @property
    def manifest(self):
        return json.loads(self.manifest_bytes)

    @property
    def fingerprint(self):
        return self._fingerprint

    def assert_current(self, manifest=None, evidence=None):
        if manifest is not None:
            require(canonical(manifest) == self.manifest_bytes, 'manifest/configuration changed')
        if evidence is not None:
            require(tuple(sorted(evidence.items())) == self.evidence, 'evidence changed')


@dataclass(frozen=True)
class Decision:
    schema_version: str
    snapshot_sha256: str
    intent: str
    accepted: bool
    dimensions: tuple
    scope: str = 'offline-fake-only'

    def as_dict(self):
        return {'schema_version': self.schema_version, 'snapshot_sha256': self.snapshot_sha256,
                'intent': self.intent, 'accepted': self.accepted,
                'dimensions': dict(self.dimensions), 'scope': self.scope,
                'campaign_scoring_enabled': False, 'paid_provider_enabled': False}


def preflight(snapshot):
    """Derive refusal per dimension from actual captured bytes, never ready flags."""
    manifest = snapshot.manifest
    reasons = {}
    evidence = dict(snapshot.evidence)
    intent = manifest.get('intent', 'unknown')
    try:
        require(set(manifest) == MANIFEST_KEYS and manifest['schema_version'] == VERSION,
                'manifest shape/version; readiness flags are not evidence')
        require(intent in INTENTS, 'unknown execution intent')
        require(manifest['evidence_sha256'] == {k: sha(v) for k, v in evidence.items()},
                'missing, extra or substituted evidence')
        require(type(manifest['task_ids']) is list and bool(manifest['task_ids']) and
                all(type(x) is str and x for x in manifest['task_ids']) and
                len(set(manifest['task_ids'])) == len(manifest['task_ids']), 'task IDs')
    except (ValueError, KeyError, TypeError) as error:
        reasons['bindings'] = str(error)
    if reasons:
        return Decision(VERSION, snapshot.fingerprint, intent, False, tuple(sorted(reasons.items())))
    dataset = manifest['dataset']
    if type(dataset) is not dict or set(dataset) != {'name', 'origin', 'purpose'}:
        reasons['dataset'] = 'dataset requires name, origin and purpose'
    elif intent == 'smoke_seed' and not (
            dataset['name'] in {'D0', 'seed', 'qualified'} and
            dataset['origin'] in {'development_seed', 'qualified_corpus'} and
            ((dataset['name'] == 'qualified') == (dataset['origin'] == 'qualified_corpus')) and
            dataset['purpose'] == 'development_smoke'):
        reasons['dataset'] = 'unknown or relabelled dataset; smoke requires its own protocol'
    elif intent == 'campaign_d1' and dataset != {
            'name': 'D1', 'origin': 'qualified_corpus', 'purpose': 'competitive_campaign'}:
        reasons['dataset'] = 'D1 origin/purpose mismatch'
    elif intent == 'replay_offline' and dataset['purpose'] != 'offline_replay':
        reasons['dataset'] = 'replay purpose mismatch'
    if intent == 'replay_offline':
        try:
            require(set(evidence) == {'replay'}, 'replay evidence set')
            record = json.loads(evidence['replay'])
            require(record['metadata']['task_id'] in manifest['task_ids'], 'replay task binding')
            require(record['metadata']['model'] == manifest['model'], 'replay model binding')
            replay_agent(record)
        except (ValueError, KeyError, TypeError) as error:
            reasons['replay'] = str(error)
    elif intent == 'campaign_d1':
        # Prepared descriptors/booleans are deliberately insufficient. This
        # increment cannot admit even a rehashed caller-authored 32-row ledger.
        reasons['corpus'] = 'immutable complete qualified-corpus reconciliation not connected'
        reasons['events'] = 'four required real A-to-B execution reconciliations not connected'
        reasons['provider'] = 'paid provider adapter and authorization unavailable'
    else:
        _verify_smoke(manifest, evidence, reasons)
    return Decision(VERSION, snapshot.fingerprint, intent, not reasons,
                    tuple(sorted(reasons.items())))


def _verify_smoke(manifest, evidence, reasons):
    ids = manifest['task_ids']
    for dimension in ['configuration', 'model', 'tools', 'measurement', 'controls', 'protocol']:
        try:
            bound = json.loads(evidence[dimension])
            require(bound == manifest[dimension], dimension + ' bytes/binding mismatch')
        except (ValueError, KeyError, TypeError) as error:
            reasons[dimension] = str(error)
    try:
        require(exact_json(manifest['model'], {'provider': 'fake', 'name': 'fake-stream-v1',
                                     'version': '1', 'effort': 'fixed'}), 'offline model binding')
        require(exact_json(manifest['measurement'], {'profile': 'offline-counted-v1',
                                            'cost_semantics': 'synthetic_micro_usd'}),
                'measurement profile unavailable')
        require(exact_json(manifest['controls'], {'mode': 'offline_fake', 'network': 'never_called',
                                         'containment_evidence': 'not_a_real_probe'}),
                'simulated controls cannot authorize a provider')
        require(exact_json(manifest['configuration'], {'profile': 'offline-paired-smoke-v1',
                                              'input_tokens': 100, 'output_tokens': 100}),
                'configuration profile unavailable')
        require(manifest['tools'] == fake_request()['tool_definitions'], 'tool configuration')
        protocol = manifest['protocol']
        require(exact_json(protocol, {'id': 'offline-paired-smoke-v1', 'task_ids': ids,
                             'arms': ['direct', 'indexed'], 'paired_resources': True,
                             'result_destination': 'development_only'}), 'paired smoke protocol')
        require(manifest['request_sha256'] == sha(canonical(fake_request())), 'request binding')
    except (ValueError, KeyError, TypeError) as error:
        reasons['smoke_protocol'] = str(error)
    expected = {'configuration', 'model', 'tools', 'measurement', 'controls', 'protocol'}
    for task_id in ids:
        expected.update({'task/' + task_id + '/input', 'task/' + task_id + '/oracle',
                         'task/' + task_id + '/review'})
        try:
            prefix = 'task/' + task_id + '/'
            review = json.loads(evidence[prefix + 'review'])
            require(review == {'task_id': task_id, 'origin': manifest['dataset']['origin'],
                               'input_sha256': sha(evidence[prefix + 'input']),
                               'oracle_sha256': sha(evidence[prefix + 'oracle']),
                               'scope': 'offline_fixture_review'}, 'task/oracle/review binding')
            require(bool(evidence[prefix + 'input']) and bool(evidence[prefix + 'oracle']),
                    'empty smoke task/oracle')
        except (ValueError, KeyError, TypeError) as error:
            reasons['task:' + task_id] = str(error)
    if set(evidence) != expected:
        reasons['evidence_set'] = 'smoke evidence closure differs from declared tasks/configuration'


def verify_decision(snapshot, decision):
    require(type(decision) is Decision and decision == preflight(snapshot),
            'decision differs from verified content/intent')
    require(decision.accepted, 'preflight refused: ' + str(dict(decision.dimensions)))


@dataclass
class OfflineAuthorization:
    """Explicit fake-resource allowance; this type conveys no paid authorization."""
    snapshot_sha256: str
    budget_micro_usd: int
    expires_monotonic: float
    revoked: bool = False


@dataclass(frozen=True)
class FakeOutcome:
    state: str = 'completed'
    response: bytes | None = b'offline response'
    receipt: dict | None = None
    raises_after_send: bool = False


class FakeAdapter:
    """No credentials, sockets, subprocesses or real model paths in this adapter."""
    def __init__(self, outcomes=None):
        self._outcomes = list(outcomes or [])
        self.calls = 0
        self._lock = threading.Lock()
        self._session = None

    def _invoke(self, capability, request):
        require(capability is self._session and capability is not None,
                'adapter requires verified dispatch capability')
        with self._lock:
            self.calls += 1
            return self._outcomes.pop(0) if self._outcomes else FakeOutcome(
                receipt=fake_receipt('fake-dispatch-' + str(self.calls)))


class DispatchSession:
    """Lock decision/auth/reserve/send; retries share the same admission boundary."""
    def __init__(self, snapshot, decision, authorization, adapter, *,
                 current_manifest=None, current_evidence=None, clock=time.monotonic):
        verify_decision(snapshot, decision)
        require(type(authorization) is OfflineAuthorization, 'explicit offline authorization required')
        require(type(adapter) is FakeAdapter, 'only built-in offline adapter is enabled')
        require(adapter._session is None, 'adapter already belongs to a session')
        self._snapshot, self._decision = snapshot, decision
        self._authorization = copy.deepcopy(authorization)
        self._adapter = adapter
        self._capability = object()
        self._adapter._session = self._capability
        self._lock = threading.RLock()
        self._clock = clock
        self._current_manifest, self._current_evidence = current_manifest, current_evidence
        self._invalidated = None
        metadata = fake_metadata()
        metadata['task_id'] = snapshot.manifest['task_ids'][0]
        metadata['dataset_sha256'] = snapshot.fingerprint
        self._ledger = Ledger(metadata, money(authorization.budget_micro_usd))
        self._check()

    def _check(self):
        require(self._invalidated is None, 'session invalidated: ' + str(self._invalidated))
        auth = self._authorization
        require(not auth.revoked and self._clock() < auth.expires_monotonic,
                'authorization revoked or expired')
        require(auth.snapshot_sha256 == self._snapshot.fingerprint, 'authorization content mismatch')
        try:
            self._snapshot.assert_current(
                self._current_manifest() if self._current_manifest else None,
                self._current_evidence() if self._current_evidence else None)
        except ValueError as error:
            self._invalidated = str(error)
            raise
        require(not self._ledger.budget_incidents, 'budget incident closed admissions')

    def revoke(self):
        with self._lock:
            self._authorization.revoked = True

    def invalidate(self, reason):
        with self._lock:
            self._invalidated = str(reason)

    def replay(self, record):
        with self._lock:
            self._check()
            require(self._decision.intent == 'replay_offline', 'replay requires replay intent')
            require(canonical(record) == dict(self._snapshot.evidence)['replay'], 'replay evidence replaced')
            return replay_agent(record)

    def dispatch(self, attempt_id, call_id, request, max_charge_micro_usd, *, retry_of=None, cancel=None):
        with self._lock:
            self._check()
            require(self._decision.intent == 'smoke_seed', 'intent cannot dispatch provider/adapter')
            request = copy.deepcopy(request)
            require(sha(canonical(request)) == self._snapshot.manifest['request_sha256'], 'request changed')
            if cancel is not None and cancel.is_set():
                return {'status': 'cancelled_before_send', 'adapter_called': False}
            if not self._ledger.reserve(attempt_id, call_id, request, max_charge_micro_usd,
                                        retry_of=retry_of, timestamp=self._clock()):
                return {'status': 'rejected_before_send', 'adapter_called': False}
            self._ledger.send(attempt_id, timestamp=self._clock())
        try:
            with self._lock:
                # Recheck at the effective invocation after reserve/send. Any
                # intervening revocation or mutation closes this attempt too.
                self._check()
                outcome = self._adapter._invoke(self._capability, request)
            require(type(outcome) is FakeOutcome, 'invalid fake adapter outcome')
            if outcome.raises_after_send:
                raise RuntimeError('fake transport failure after send')
            with self._lock:
                state = 'cancelled' if cancel is not None and cancel.is_set() else outcome.state
                if outcome.response is not None:
                    self._ledger.chunk(attempt_id, outcome.response, timestamp=self._clock())
                self._ledger.finish(attempt_id, state, timestamp=self._clock())
                if outcome.receipt is not None:
                    require(outcome.receipt['provider'] == 'fake', 'receipt provider substitution')
                    self._ledger.receipt(attempt_id, outcome.receipt, timestamp=self._clock())
                return {'status': state, 'adapter_called': True}
        except Exception as error:
            with self._lock:
                row = self._ledger.calls[attempt_id]
                if row['state'] in {'sent', 'streaming'}:
                    self._ledger.finish(attempt_id, 'sent_no_response', timestamp=self._clock())
                self._invalidated = 'dispatch/receipt error: ' + str(error)
            raise

    def record(self):
        with self._lock:
            return self._ledger.record()


def make_smoke_fixture():
    """Synthetic offline demonstration; no corpus eligibility/containment claim."""
    manifest = {'schema_version': VERSION, 'intent': 'smoke_seed',
                'dataset': {'name': 'D0', 'origin': 'development_seed', 'purpose': 'development_smoke'},
                'task_ids': ['D0-RS-01'],
                'configuration': {'profile': 'offline-paired-smoke-v1', 'input_tokens': 100, 'output_tokens': 100},
                'model': fake_metadata()['model'], 'tools': fake_request()['tool_definitions'],
                'measurement': {'profile': 'offline-counted-v1', 'cost_semantics': 'synthetic_micro_usd'},
                'controls': {'mode': 'offline_fake', 'network': 'never_called', 'containment_evidence': 'not_a_real_probe'},
                'protocol': {'id': 'offline-paired-smoke-v1', 'task_ids': ['D0-RS-01'],
                             'arms': ['direct', 'indexed'], 'paired_resources': True,
                             'result_destination': 'development_only'},
                'request_sha256': sha(canonical(fake_request()))}
    evidence = {key: canonical(manifest[key]) for key in ['configuration', 'model', 'tools', 'measurement', 'controls', 'protocol']}
    prefix = 'task/D0-RS-01/'
    evidence[prefix + 'input'] = b'offline fixture task'
    evidence[prefix + 'oracle'] = b'offline fixture expected result'
    evidence[prefix + 'review'] = canonical({'task_id': 'D0-RS-01', 'origin': 'development_seed',
        'input_sha256': sha(evidence[prefix + 'input']), 'oracle_sha256': sha(evidence[prefix + 'oracle']),
        'scope': 'offline_fixture_review'})
    manifest['evidence_sha256'] = {key: sha(value) for key, value in evidence.items()}
    return manifest, evidence
