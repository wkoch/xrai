"""Scripted offline adapter boundary; no provider/model transport is added.

D01 v2 owns virtual dispatch accounting. This protocol adds bounded tool wires,
source-bound recovery/expansion and replay; all model observations remain null.
"""
import base64
import copy
from dataclasses import dataclass
import json
from pathlib import Path
import re
import math
import threading
import time

from agent_ledger import canonical, sha
from execution_dispatch_v2 import DispatchSessionV2, replay_dispatch_v2
from offline_measurement import SERIALIZER

VERSION = 'xrai.eval.adapter-scripted.v1'
MAX_FRAME_BYTES = 1024 * 1024
MAX_TRANSCRIPT_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 256
HEX = re.compile('[0-9a-f]{64}')
COMPARATORS = ('graft', 'trace-mcp', 'codebase-memory-mcp', 'code-review-graph',
               'jCodeMunch', 'tokensave', 'ProjectAtlas', 'codegraph-mcp')
TOOL_SCHEMA = {
    'schema': 'xrai.eval.adapter-tools.v1',
    'tools': {'recover': {'required': ['query', 'method', 'top_k', 'max_wire_bytes'],
                         'methods': ['bm25', 'tfidf_cosine'], 'output': 'captured lexical JSON bytes'},
              'expand': {'required': ['snippet_ids', 'max_wire_bytes'],
                         'output': 'full captured source files or explicit refusals'}},
    'source_scope': 'captured_sources_only', 'parsing': 'unknown', 'semantics': 'unknown',
    'token_measurement': 'not_measured', 'model_usage': None, 'model_charge': None}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact(left, right):
    return canonical(left) == canonical(right)


def decode(raw):
    require(type(raw) is bytes and len(raw) <= MAX_FRAME_BYTES, 'bounded owned JSON frame')
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + value)))


def path_name(name):
    require(type(name) is str and name and not name.startswith('/') and '\\' not in name and ':' not in name and
            all(part not in ('', '.', '..') for part in name.split('/')), 'captured source path')


@dataclass(frozen=True)
class ToolSnapshot:
    """Actual producer/source bytes bound to the handler's observed IDs."""
    snapshot_id: str
    configuration_id: str
    producer_bytes: bytes
    configuration_bytes: bytes
    files: tuple

    def __post_init__(self):
        require(type(self.snapshot_id) is str and bool(self.snapshot_id) and type(self.configuration_id) is str and bool(self.configuration_id), 'tool snapshot/config IDs')
        require(type(self.producer_bytes) is bytes and bool(self.producer_bytes), 'actual owned producer bytes')
        configuration = decode(self.configuration_bytes)
        require(canonical(configuration) == self.configuration_bytes and sha(self.configuration_bytes) == self.configuration_id and configuration['producer_sha256'] == sha(self.producer_bytes), 'actual configuration/producer byte binding')
        require(type(self.files) is tuple and self.files == tuple(sorted(self.files)) and
                len({name for name, _ in self.files}) == len(self.files), 'unique immutable source capture')
        require(all(type(raw) is bytes for _, raw in self.files), 'owned source bytes')
        for name, raw in self.files:
            path_name(name)
            raw.decode('utf-8', errors='strict')
        require(sum(len(raw) for _, raw in self.files) <= 16 * 1024 * 1024, 'tool source memory bound')
        require(self.snapshot_id == sha(canonical([{'path':name,'sha256':sha(raw),'bytes':len(raw)} for name,raw in self.files])), 'actual source snapshot byte identity')

    @property
    def producer_sha256(self):
        return sha(self.producer_bytes)

    @property
    def fingerprint(self):
        return sha(canonical(self.as_dict()))

    def as_dict(self):
        return {'snapshot_id': self.snapshot_id, 'configuration_id': self.configuration_id,
                'producer_base64': base64.b64encode(self.producer_bytes).decode(),
                'producer_sha256': self.producer_sha256,
                'configuration_base64':base64.b64encode(self.configuration_bytes).decode(),
                'sources': {name: {'base64': base64.b64encode(raw).decode(), 'sha256': sha(raw), 'bytes': len(raw)} for name, raw in self.files}}

    @classmethod
    def capture(cls, handler, files, producer_bytes):
        require(type(files) is dict, 'named source bytes')
        result = cls(handler.snapshot_id, handler.configuration_id, producer_bytes, canonical(dict(handler.configuration)), tuple(sorted(files.items())))
        require(handler.producer_sha256 == result.producer_sha256, 'actual handler producer byte fingerprint')
        return result

    @classmethod
    def restore(cls, value):
        require(set(value) == {'snapshot_id', 'configuration_id', 'producer_base64', 'producer_sha256', 'configuration_base64', 'sources'}, 'tool capture fields')
        files = {}
        for name, item in value['sources'].items():
            require(set(item) == {'base64', 'sha256', 'bytes'}, 'source byte fields')
            raw = base64.b64decode(item['base64'], validate=True)
            require(type(item['bytes']) is int and len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'source hash/bytes')
            files[name] = raw
        result = cls(value['snapshot_id'], value['configuration_id'], base64.b64decode(value['producer_base64'], validate=True), base64.b64decode(value['configuration_base64'], validate=True), tuple(sorted(files.items())))
        require(result.producer_sha256 == value['producer_sha256'] and exact(result.as_dict(), value), 'producer/capture substitution')
        return result


def anchor(item):
    return {key:item[key] for key in ['id','path','start','end','source_sha256','snippet_sha256','text']}


def verify_snippet(item, snapshot):
    require(type(item) is dict and {'id', 'path', 'start', 'end', 'source_sha256', 'snippet_sha256', 'text'} <= set(item), 'source snippet evidence fields')
    require(type(item['id']) is str and bool(item['id']), 'snippet handle')
    files = dict(snapshot.files)
    require(item['path'] in files, 'snippet outside captured sources')
    source, start, end = files[item['path']], item['start'], item['end']
    require(type(start) is int and type(end) is int and 0 <= start <= end <= len(source), 'typed source span')
    source[:start].decode('utf-8'); source[start:end].decode('utf-8'); source[end:].decode('utf-8')
    require(item['source_sha256'] == sha(source) and item['snippet_sha256'] == sha(source[start:end]) and item['text'] == source[start:end].decode(), 'exact captured snippet/hash/text')


def verify_delivery(value, snapshot, maximum, *, query=None, handles=None, known=None, method=None, top_k=None):
    fields = {'schema', 'snapshot_id', 'configuration_id', 'producer_sha256', 'mode', 'method',
        'query_sha256', 'status', 'snippets', 'refusals', 'requested_ids', 'coverage',
        'model_tokens', 'financial_cost', 'wire_bytes'}
    require(type(value) is dict and set(value) == fields and value['schema'] == 'lexical-delivery.v1', 'exact lexical delivery profile')
    raw = canonical(value)
    require(len(raw) <= maximum and type(value['wire_bytes']) is int and value['wire_bytes'] == len(raw), 'complete JSON wire budget/accounting')
    decode(raw)
    require(value['snapshot_id'] == snapshot.snapshot_id and value['configuration_id'] == snapshot.configuration_id and value['producer_sha256'] == snapshot.producer_sha256, 'tool wire snapshot/config/producer binding')
    require(value['model_tokens'] is None and value['financial_cost'] is None, 'tokens/financial cost remain unavailable')
    coverage = value['coverage']; files = dict(snapshot.files)
    require(type(coverage) is dict and set(coverage) == {'captured_scope_only','whole_repository','captured_files','source_bytes','indexed_chunks','empty_files','complete_captured_index','parse_status','semantic_status'}, 'exact captured coverage profile')
    for key, expected in {'captured_scope_only':True, 'whole_repository':False, 'captured_files':len(files),
        'source_bytes':sum(map(len,files.values())), 'empty_files':sum(not raw for raw in files.values()),
        'complete_captured_index':True, 'parse_status':'unknown', 'semantic_status':'unknown'}.items():
        require(exact(coverage[key], expected), 'captured coverage/types/unknown')
    configuration = decode(snapshot.configuration_bytes)
    lines, overlap = configuration['chunk_lines'], configuration['overlap_lines']
    require(type(lines) is int and type(overlap) is int and 1 <= lines <= 200 and 0 <= overlap < lines, 'owned chunk configuration')
    count = sum(0 if not raw else 1 + max(0, (len(raw.splitlines(keepends=True))-lines+lines-overlap-1)//(lines-overlap)) for raw in files.values())
    require(type(coverage['indexed_chunks']) is int and coverage['indexed_chunks'] == count <= 4096, 'actual captured chunk coverage')
    items = value['snippets']
    require(type(items) is list and all(type(item) is dict and type(item.get('id')) is str for item in items) and len({item['id'] for item in items}) == len(items) and type(value['refusals']) is list, 'unique snippets/explicit refusals')
    for item in items:
        verify_snippet(item, snapshot)
        expected_id = sha(canonical({'snapshot_id':snapshot.snapshot_id, 'configuration_id':snapshot.configuration_id,
            'path':item['path'], 'start':item['start'], 'end':item['end']}))
        require(item['id'] == expected_id, 'content/config/span handle binding')
    if query is not None:
        require(value['mode'] == 'search' and value['method'] == method and value['query_sha256'] == sha(query.encode()) and value['requested_ids'] == [] and value['refusals'] == [], 'search request binding')
        require(value['status'] in {'lexical_matches','no_lexical_match_captured_scope','insufficient_byte_budget'} and (value['status'] == 'lexical_matches') == bool(items) and len(items) <= top_k, 'search status/top-k')
        for rank, item in enumerate(items, 1):
            require(set(item) == {'id','path','start','end','source_sha256','snippet_sha256','text','score','rank'} and type(item['rank']) is int and item['rank'] == rank and type(item['score']) in (int,float) and math.isfinite(item['score']) and item['score'] > 0, 'lexical score/rank remain producer observations')
    else:
        require(handles is not None and known is not None and value['mode'] == 'full_captured_file' and value['method'] is None and value['query_sha256'] is None and exact(value['requested_ids'],handles), 'expansion request binding')
        paths = sorted({known[handle]['path'] for handle in handles})
        if value['status'] == 'expanded_full_captured_files':
            require(value['refusals'] == [] and [item['path'] for item in items] == paths, 'deduplicated requested full files')
            for item in items:
                require(set(item) == {'id','path','start','end','source_sha256','snippet_sha256','text'} and item['start'] == 0 and item['end'] == len(files[item['path']]), 'complete source expansion; no truncation')
        else:
            require(value['status'] == 'insufficient_byte_budget' and items == [] and exact(value['refusals'],[{'reason':'full_files_exceed_budget','paths':paths}]), 'explicit expansion budget refusal')
    return raw


class ScriptedAdapterProtocol:
    """Own tool handler seam plus verified D01 fake session, never agent_run."""
    def __init__(self, session, handler, snapshot, *, current_sources, current_producer,
                 clock=time.monotonic):
        require(type(session) is DispatchSessionV2 and type(snapshot) is ToolSnapshot, 'verified D01/session and owned tool snapshot required')
        require(callable(current_sources) and callable(current_producer), 'current actual byte callbacks required')
        self.session, self.handler, self.snapshot = session, handler, snapshot
        self.current_sources, self.current_producer, self.clock = current_sources, current_producer, clock
        self._lock, self.events, self.handles, self.pending = threading.RLock(), [], {}, {}
        self.identity, self.terminal, self.dispatching = None, False, False
        self._check_tool()

    def _check_tool(self):
        observed = self.current_sources()
        require(type(observed) is dict and tuple(sorted(observed.items())) == self.snapshot.files, 'current source bytes changed')
        producer = self.current_producer()
        require(type(producer) is bytes and producer == self.snapshot.producer_bytes, 'current producer bytes changed')
        require((self.handler.snapshot_id, self.handler.configuration_id, self.handler.producer_sha256) ==
                (self.snapshot.snapshot_id, self.snapshot.configuration_id, self.snapshot.producer_sha256), 'current handler snapshot/config/producer changed')
        require(canonical(dict(self.handler.configuration)) == self.snapshot.configuration_bytes, 'current actual configuration changed')
        record = self.session.record()
        require(not record['revoked'] and record['invalidated'] is None and self.clock() < record['authorization']['expires_monotonic'], 'D01 session authorization revoked/expired/invalidated')
        require(not self.terminal, 'adapter already terminal')

    def _append(self, kind, details):
        event = {'schema_version': VERSION, 'sequence': len(self.events), 'kind': kind,
                 'identity': copy.deepcopy(self.identity), 'details': copy.deepcopy(details),
                 'previous_event_sha256': sha(canonical(self.events[-1])) if self.events else None}
        require(len(canonical(event)) + 1 <= MAX_FRAME_BYTES and len(self.events) < MAX_EVENTS, 'adapter event/frame bound')
        require(sum(len(canonical(item)) + 1 for item in self.events) + len(canonical(event)) + 1 <= MAX_TRANSCRIPT_BYTES, 'adapter transcript bound')
        self.events.append(event)

    def dispatch_fake(self, attempt_id, call_id, request, maximum_micro_usd, *, retry_of=None):
        with self._lock:
            self._check_tool()
            require(not self.dispatching and all(row['answered'] for row in self.pending.values()), 'one active dispatch; no unresolved tool identity')
            self.dispatching = True
            binding = self.session.record()['bindings']
            self.identity = {name: binding[name] for name in ['task_id', 'arm', 'run_id']}
            self.identity.update(call_id=call_id, attempt_id=attempt_id)
            if not self.events:
                self._append('start', {'execution_kind': 'scripted_retrieval', 'transport': 'D01-offline-fake-only',
                    'tool_schema': TOOL_SCHEMA, 'tool_snapshot': self.snapshot.as_dict(),
                    'tool_snapshot_sha256': self.snapshot.fingerprint, 'serializer': SERIALIZER,
                    'provider_usage': None, 'provider_charge': None})
        try:
            outcome = self.session.dispatch(attempt_id, call_id, request, maximum_micro_usd, retry_of=retry_of)
            with self._lock:
                self._append('dispatch', {'outcome': outcome, 'd01_record': self.session.record()})
        finally:
            with self._lock:
                self.dispatching = False
        return outcome

    def recover(self, tool_call_id, query, *, method='bm25', top_k=5, max_wire_bytes=65536):
        require(type(query) is str and bool(query) and len(query.encode()) <= 4096, 'bounded query')
        require(method in TOOL_SCHEMA['tools']['recover']['methods'] and type(top_k) is int and 1 <= top_k <= 20, 'supported search method/top-k')
        require(type(max_wire_bytes) is int and 256 <= max_wire_bytes <= MAX_FRAME_BYTES // 2, 'tool wire ceiling')
        with self._lock:
            self._check_tool(); self._request(tool_call_id, 'recover', {'query': query, 'method': method, 'top_k': top_k, 'max_wire_bytes': max_wire_bytes})
        value = self.handler.search(query, method=method, top_k=top_k, max_wire_bytes=max_wire_bytes)
        raw = verify_delivery(value, self.snapshot, max_wire_bytes, query=query, method=method, top_k=top_k)
        with self._lock:
            self._check_tool()
            for item in value['snippets']:
                previous = self.handles.get(item['id'])
                require(previous is None or exact(previous, anchor(item)), 'snippet handle changed source identity')
                self.handles[item['id']] = copy.deepcopy(anchor(item))
            self._result(tool_call_id, raw)
        return copy.deepcopy(value)

    def expand(self, tool_call_id, snippet_ids, *, max_wire_bytes=65536):
        require(type(snippet_ids) is list and 1 <= len(snippet_ids) <= 20 and all(type(item) is str for item in snippet_ids) and len(snippet_ids) == len(set(snippet_ids)), 'unique expansion handles')
        require(type(max_wire_bytes) is int and 256 <= max_wire_bytes <= MAX_FRAME_BYTES // 2, 'expansion wire ceiling')
        with self._lock:
            self._check_tool()
            require(all(item in self.handles for item in snippet_ids), 'handle belongs to current recorded context')
            self._request(tool_call_id, 'expand', {'snippet_ids': snippet_ids, 'max_wire_bytes': max_wire_bytes})
        value = self.handler.expand(snippet_ids, max_wire_bytes=max_wire_bytes)
        raw = verify_delivery(value, self.snapshot, max_wire_bytes, handles=snippet_ids, known=self.handles)
        with self._lock:
            self._check_tool()
            for item in value['snippets']:
                self.handles[item['id']] = copy.deepcopy(anchor(item))
            self._result(tool_call_id, raw)
        return copy.deepcopy(value)

    def _request(self, tool_call_id, tool, arguments):
        require(not self.dispatching and self.identity is not None and type(tool_call_id) is str and bool(tool_call_id) and tool_call_id not in self.pending, 'unique explicit tool call after fake dispatch')
        row = self.session.record()['attempts'][self.identity['attempt_id']]
        require(row['committed'] and not row['transport_proven_absent'], 'refused/absent D01 fake invocation cannot invoke tools')
        self.pending[tool_call_id] = {'tool': tool, 'arguments': copy.deepcopy(arguments), 'answered': False}
        self._append('tool_request', {'tool_call_id': tool_call_id, 'tool': tool, 'arguments': arguments})

    def _result(self, tool_call_id, raw):
        self._append('tool_result', {'tool_call_id': tool_call_id, 'wire_base64': base64.b64encode(raw).decode(),
                                   'wire_sha256': sha(raw), 'wire_bytes': len(raw)})
        self.pending[tool_call_id]['answered'] = True

    def reconcile_fake(self, attempt_id, **kwargs):
        """Late D01 fake receipt/response remains virtual; repeated input is idempotent."""
        with self._lock:
            require(not self.terminal and not self.dispatching and self.identity is not None and attempt_id == self.identity['attempt_id'], 'reconcile current fake attempt before terminal')
            changed = self.session.reconcile(attempt_id, **kwargs)
            if changed:
                self._append('ledger_snapshot', {'d01_record': self.session.record()})
            return changed

    def finish(self, state, answer=b''):
        require(state in {'completed', 'timeout', 'error', 'partial', 'cancelled'} and type(answer) is bytes and len(answer) <= 65536, 'bounded terminal result')
        with self._lock:
            require(not self.terminal and not self.dispatching and self.identity is not None and any(event['kind'] == 'dispatch' for event in self.events), 'terminal once after dispatch')
            require(state != 'completed' or all(row['answered'] for row in self.pending.values()), 'completed transcript needs all tool responses')
            self._append('ledger_snapshot', {'d01_record':self.session.record()})
            self._append('usage', {'provider_usage': None, 'provider_charge': None,
                'model_tokens': None, 'serializer': SERIALIZER,
                'wire_bytes_before_usage': sum(len(canonical(event)) + 1 for event in self.events),
                'measurement_semantics': 'exact JSON bytes; tokenizer/provider-wire/billing not measured'})
            self._append('final', {'state': state, 'answer_base64': base64.b64encode(answer).decode(),
                'answer_sha256': sha(answer), 'execution_kind': 'scripted_retrieval', 'judgment': 'not_judged'})
            self.terminal = True
        return self.transcript()

    def transcript(self):
        with self._lock:
            return b''.join(canonical(event) + b'\n' for event in self.events)


def replay_adapter(raw):
    require(type(raw) is bytes and len(raw) <= MAX_TRANSCRIPT_BYTES and raw.endswith(b'\n'), 'bounded complete adapter transcript')
    frames = raw.splitlines(keepends=True)
    require(1 <= len(frames) <= MAX_EVENTS and all(frame.endswith(b'\n') and len(frame) <= MAX_FRAME_BYTES for frame in frames), 'complete newline frames')
    events = [decode(frame) for frame in frames]
    require(all(frame == canonical(event) + b'\n' for frame,event in zip(frames,events)), 'canonical serializer frames')
    snapshot, binding, pending, handles, prior_ledger, terminal = None, None, {}, {}, None, False
    current_identity = None
    for sequence, event in enumerate(events):
        require(type(event) is dict and set(event) == {'schema_version', 'sequence', 'kind', 'identity', 'details', 'previous_event_sha256'} and
                event['schema_version'] == VERSION and type(event['sequence']) is int and event['sequence'] == sequence and
                event['previous_event_sha256'] == (sha(canonical(events[sequence - 1])) if sequence else None), 'adapter frame/order/hash-chain')
        identity, detail = event['identity'], event['details']
        detail_fields = {'start':{'execution_kind','transport','tool_schema','tool_snapshot','tool_snapshot_sha256','serializer','provider_usage','provider_charge'},
            'dispatch':{'outcome','d01_record'}, 'ledger_snapshot':{'d01_record'}, 'tool_request':{'tool_call_id','tool','arguments'},
            'tool_result':{'tool_call_id','wire_base64','wire_sha256','wire_bytes'},
            'usage':{'provider_usage','provider_charge','model_tokens','serializer','wire_bytes_before_usage','measurement_semantics'},
            'final':{'state','answer_base64','answer_sha256','execution_kind','judgment'}}
        require(event['kind'] in detail_fields and type(detail) is dict and set(detail) == detail_fields[event['kind']], 'exact typed event details')
        require(not any(old['kind'] == 'usage' for old in events[:sequence]) or event['kind'] == 'final', 'usage occurs once immediately before final')
        require(type(identity) is dict and set(identity) == {'task_id', 'arm', 'run_id', 'call_id', 'attempt_id'} and all(type(item) is str and bool(item) for item in identity.values()), 'explicit task/arm/run/call/attempt')
        require(not terminal, 'event after terminal')
        if sequence == 0:
            require(event['kind'] == 'start' and detail['execution_kind'] == 'scripted_retrieval' and detail['transport'] == 'D01-offline-fake-only' and exact(detail['tool_schema'], TOOL_SCHEMA) and exact(detail['serializer'], SERIALIZER) and detail['provider_usage'] is None and detail['provider_charge'] is None, 'scripted offline start profile')
            snapshot = ToolSnapshot.restore(detail['tool_snapshot'])
            require(detail['tool_snapshot_sha256'] == snapshot.fingerprint, 'tool capture fingerprint')
            binding = {key: identity[key] for key in ['task_id', 'arm', 'run_id']}
            continue
        require({key: identity[key] for key in binding} == binding, 'task/arm/run changed')
        require(event['kind'] == 'dispatch' or (current_identity is not None and exact(identity,current_identity)), 'current dispatch call/attempt identity')
        if event['kind'] in {'dispatch','ledger_snapshot'}:
            require(event['kind'] != 'ledger_snapshot' or prior_ledger is not None, 'ledger snapshot follows explicit dispatch')
            ledger = detail['d01_record']; replay_dispatch_v2(ledger)
            if prior_ledger is not None:
                require(all(exact(ledger[key],prior_ledger[key]) for key in ['snapshot','decision','bindings','authorization']), 'D01 immutable metadata replaced')
            require(all(ledger['bindings'][key] == binding[key] for key in binding), 'adapter/D01 metadata substitution')
            row = ledger['attempts'][identity['attempt_id']]
            if event['kind'] == 'dispatch':
                current_identity = copy.deepcopy(identity)
                require(set(detail['outcome']) == {'status','committed','adapter_called'} and row['call_id'] == identity['call_id'] and detail['outcome']['status'] == row['state'] and detail['outcome']['committed'] is row['committed'] and detail['outcome']['adapter_called'] is (row['committed'] and not row['transport_proven_absent']), 'dispatch outcome/identity')
            require(prior_ledger is None or exact(ledger['events'][:len(prior_ledger['events'])], prior_ledger['events']), 'D01 history replaced between retries')
            prior_ledger = ledger
        elif event['kind'] == 'tool_request':
            require(prior_ledger is not None and prior_ledger['attempts'][identity['attempt_id']]['committed'] and not prior_ledger['attempts'][identity['attempt_id']]['transport_proven_absent'] and prior_ledger['attempts'][identity['attempt_id']]['call_id'] == identity['call_id'], 'tools require committed D01 attempt')
            name, tool, arguments = detail['tool_call_id'], detail['tool'], detail['arguments']
            require(type(name) is str and bool(name) and name not in pending and tool in TOOL_SCHEMA['tools'], 'unique supported tool call')
            require(set(arguments) == set(TOOL_SCHEMA['tools'][tool]['required']), 'tool argument fields')
            require(type(arguments['max_wire_bytes']) is int and 256 <= arguments['max_wire_bytes'] <= MAX_FRAME_BYTES // 2, 'tool budget types')
            if tool == 'recover':
                require(type(arguments['query']) is str and bool(arguments['query']) and len(arguments['query'].encode()) <= 4096 and arguments['method'] in TOOL_SCHEMA['tools'][tool]['methods'] and type(arguments['top_k']) is int and 1 <= arguments['top_k'] <= 20, 'recover request bounds')
            else:
                require(type(arguments['snippet_ids']) is list and 1 <= len(arguments['snippet_ids']) <= 20 and len(arguments['snippet_ids']) == len(set(arguments['snippet_ids'])) and all(item in handles for item in arguments['snippet_ids']), 'known same-context expansion handles')
            pending[name] = {'tool': tool, 'arguments': arguments, 'identity': identity, 'answered': False}
        elif event['kind'] == 'tool_result':
            name = detail['tool_call_id']; require(name in pending and not pending[name]['answered'] and exact(identity, pending[name]['identity']), 'one paired tool result')
            data = base64.b64decode(detail['wire_base64'], validate=True)
            require(type(detail['wire_bytes']) is int and len(data) == detail['wire_bytes'] and sha(data) == detail['wire_sha256'], 'tool wire bytes/hash')
            value = decode(data); request = pending[name]; arguments = request['arguments']
            expected = verify_delivery(value, snapshot, arguments['max_wire_bytes'], query=arguments.get('query'), handles=arguments.get('snippet_ids'), known=handles, method=arguments.get('method'), top_k=arguments.get('top_k'))
            require(expected == data, 'captured canonical tool JSON')
            if request['tool'] == 'recover':
                for item in value['snippets']:
                    require(item['id'] not in handles or exact(anchor(item), handles[item['id']]), 'handle changed source')
                    handles[item['id']] = anchor(item)
            if request['tool'] == 'expand':
                for item in value['snippets']:
                    handles[item['id']] = anchor(item)
            pending[name]['answered'] = True
        elif event['kind'] == 'usage':
            require(detail['provider_usage'] is None and detail['provider_charge'] is None and detail['model_tokens'] is None and exact(detail['serializer'], SERIALIZER) and type(detail['wire_bytes_before_usage']) is int and detail['wire_bytes_before_usage'] == sum(len(frame) for frame in frames[:sequence]) and detail['measurement_semantics'] == 'exact JSON bytes; tokenizer/provider-wire/billing not measured', 'observed/unavailable measurement distinction')
        elif event['kind'] == 'final':
            require(events[sequence - 1]['kind'] == 'usage' and detail['state'] in {'completed', 'timeout', 'error', 'partial', 'cancelled'} and detail['execution_kind'] == 'scripted_retrieval' and detail['judgment'] == 'not_judged', 'explicit scripted terminal')
            answer = base64.b64decode(detail['answer_base64'], validate=True)
            require(len(answer) <= 65536 and sha(answer) == detail['answer_sha256'], 'terminal answer bytes')
            require(detail['state'] != 'completed' or all(row['answered'] for row in pending.values()), 'completed transcript loses tool response')
            terminal = True
        else:
            raise ValueError('unsupported adapter event')
    require(terminal and prior_ledger is not None, 'complete dispatch/usage/final required')
    return {'schema': 'xrai.eval.adapter-replay.v1', 'verified': True, 'execution_kind': 'scripted_retrieval',
            'events': len(events), 'wire_bytes': len(raw), 'snapshot_id': snapshot.snapshot_id,
            'provider_usage': None, 'provider_charge': None, 'model_tokens': None,
            'virtual_accounting':copy.deepcopy(prior_ledger['accounting']),
            'tool_calls': len(pending), 'external_calls': 0, 'agent_run': False,
            'paid_provider_enabled': False, 'competitive_runs_allowed': False}


def comparator_preflight(manifest, *, current_source):
    """Offline plan-only roster, never an installation/strong-mode claim."""
    require(type(manifest) is dict and set(manifest) == {'schema', 'mode', 'source', 'configurations'} and
            manifest['schema'] == 'xrai.eval.comparator-plan.v1' and manifest['mode'] == 'planning_only', 'comparator manifest shape')
    require(type(current_source) is bytes and type(manifest['source']) is dict and exact(manifest['source'], {'path':'docs/PROVA-DE-DIFERENCIACAO.md','sha256':sha(current_source)}), 'actual current comparator plan source bytes')
    configurations = manifest['configurations']
    require(type(configurations) is list and len(configurations) == len(COMPARATORS) and
            tuple(item['id'] for item in configurations) == COMPARATORS, 'eight planned comparator identities/order')
    reasons = {}
    for item in configurations:
        require(set(item) == {'id', 'regimes', 'version_pin', 'installation_receipt', 'strong_configuration_receipt', 'exclusion'} and
                item['regimes'] == ['common_local', 'best_documented_enriched'] and item['exclusion'] is None, 'strong regimes are not silently excluded/replaced')
        require(item['version_pin'] is None and item['installation_receipt'] is None and item['strong_configuration_receipt'] is None, 'offline placeholders cannot impersonate verified comparator pins/setup')
        reasons[item['id']] = ['available version/pin not demonstrated', 'installation/setup not observed',
                              'strong/enriched configuration not independently documented',
                              'model/resource authorization and concrete ceiling absent']
    return {'schema': 'xrai.eval.comparator-preflight.v1', 'accepted': False,
            'manifest_sha256': sha(canonical(manifest)), 'configurations': reasons,
            'campaign_scoring_enabled': False, 'external_calls': 0,
            'limits': ['Eight candidates retained; no ranking, installation, pricing or version claim.',
                       'A future verified configuration needs its own receipt/profile, not caller flags.']}
