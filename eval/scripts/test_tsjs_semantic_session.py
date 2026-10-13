"""Own data-only framing/self-checks; CI environment also exercises authentic bundle."""
import base64
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import blake3
import verify_tsjs_semantic_session as v
import run_tsjs_semantic_session as collector


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':')) + '\n').encode()


def synthetic_before(a, known):
    """A transport fixture derived as data, never claimed as executed native A."""
    snapshot = copy.deepcopy(known)
    old = snapshot['snapshot_id']
    sid = blake3.blake3(v.semantics.compact([v.semantics.canonical_input(a),snapshot['producer_fingerprint']])).hexdigest()
    snapshot['snapshot_id'] = sid; snapshot['input'] = copy.deepcopy(a)
    for key in ['scopes','bindings','exports','gaps','references']:
        snapshot[key] = [x for x in snapshot[key] if (x.get('path') or x['evidence']['path']) in a['files']]
    mapping = {x['id']:i for i,x in enumerate(snapshot['scopes'])}
    for scope in snapshot['scopes']:
        scope['id'] = mapping[scope['id']]
        scope['parent'] = mapping[scope['parent']] if scope['parent'] is not None else None
    for key in ['bindings','gaps','references']:
        for item in snapshot[key]:
            item['scope'] = mapping[item['scope']]
    snapshot['coverage'] = {p:c for p,c in snapshot['coverage'].items() if p in a['files']}
    def rebind(value):
        if isinstance(value,dict):
            for key, child in list(value.items()):
                if child == old:
                    value[key] = sid
                else:
                    rebind(child)
        elif isinstance(value,list):
            for i, child in enumerate(value):
                if child == old:
                    value[i] = sid
                else:
                    rebind(child)
    rebind(snapshot)
    for ref in snapshot['references']:
        if ref['resolution']['target'] and ref['resolution']['target'].startswith('src/stringify.js:'):
            ref['resolution'] = {'state':'unknown','target':None,'binding_id':None,'evidence':[copy.deepcopy(ref['evidence'])],
                                 'dependencies':[sid,snapshot['producer_fingerprint']],'diagnostic':'captured_source_absent'}
    return snapshot


def write_process(path, requests, a, b, pid, session):
    path.mkdir(); responses = []; rows = []
    current = None; generation = 0
    counts = {'requests':0,'build_attempts':0,'successful_builds':0,'queries':0,'failed_updates':0}
    for i, request in enumerate(requests):
        counts['requests'] += 1; op = request['operation']
        rejected = op == 'update' and (request['expected_snapshot'] != current['snapshot_id'] or request['input']['configuration']['module'] != 'esm')
        if rejected:
            counts['failed_updates'] += 1
            if request['expected_snapshot'] == current['snapshot_id']:
                counts['build_attempts'] += 1
            diagnostic = ('expected snapshot mismatch; previous snapshot preserved' if request['expected_snapshot'] != current['snapshot_id'] else
                          'update build failed; previous snapshot preserved: explicit ESM captured-relative-exact-v1 profile required')
            response = {'status':'error','diagnostic':diagnostic,'schema':v.SCHEMA,'pid':pid,'counters':copy.deepcopy(counts),
                        'session_id':session,'session_producer_fingerprint':v.producer(),'snapshot_id':current['snapshot_id'],'generation':generation}
        else:
            if op in ['open','update']:
                counts['build_attempts'] += 1; counts['successful_builds'] += 1; generation += 1
                current = a if request['input'] == a['input'] else b
                result = {'strategy':v.STRATEGY}
            elif op == 'snapshot':
                result = copy.deepcopy(current)
            elif op == 'query':
                counts['queries'] += 1
                reference = next(r for r in current['references'] if r['evidence']['path'] == request['path'] and r['evidence']['start'] == request['offset'])
                result = {'kind':'lexical_reference','path':request['path'],'offset':request['offset'],'reference':copy.deepcopy(reference)}
            else:
                result = {'closed':True}
            response = {'status':'ok','response':{'schema':v.SCHEMA,'pid':pid,'counters':copy.deepcopy(counts),'session_id':session,
                        'session_producer_fingerprint':v.producer(),'snapshot_id':current['snapshot_id'],'generation':generation,
                        'operation':op,'result':result}}
        rq,rs = encoded(request),encoded(response)
        rows.append({'sequence':i,'request_base64':base64.b64encode(rq).decode(),'response_base64':base64.b64encode(rs).decode(),
                     'request_sha256':v.sha(rq),'response_sha256':v.sha(rs)})
        responses.append(response)
    (path / 'transcript.jsonl').write_bytes(b''.join(encoded(r) for r in rows))
    (path / 'stdout.jsonl').write_bytes(b''.join(encoded(r) for r in responses))
    (path / 'stderr.bin').write_bytes(b'')
    (path / 'process.json').write_bytes(encoded({'pid':pid,'exit_code':0,'closed_response':responses[-1],
        'elapsed_seconds':0.01,'command_count':len(requests),'transport':'bounded newline JSON','unread_output_bytes':0,
        'explicit_close':True,'wrapper_reaped':True}))


def fake_bundle(directory):
    values,known = v.assets()
    a = synthetic_before(values['input-a.json'],known)
    (directory / 'inputs').mkdir()
    for name in v.INPUTS:
        shutil.copyfile(v.ASSETS / name,directory / 'inputs' / name)
    (directory / 'native-bin').mkdir()
    binary = b'\x7fELF' + b'FAKE_TRANSPORT_FIXTURE_NEVER_EXECUTED' + b'\0' * 4096
    (directory / 'native-bin/tsjs-semantic-session').write_bytes(binary)
    m = {'schema':'xrai.eval.tsjs-semantic-session-receipt.v1','source_sha256':{p:v.sha((v.ROOT / p).read_bytes()) for p in v.SOURCES},
         'input_sha256':{p:v.sha((v.ASSETS / p).read_bytes()) for p in v.INPUTS},
         'binary':{'path':'native-bin/tsjs-semantic-session','sha256':v.sha(binary),'bytes':len(binary)},
         'environment':{'platform':'Linux-synthetic-transport-fixture','machine':'x86_64','github_sha':'f' * 40,'github_run_id':'1'},
         'scope':v.PROFILE,'strategy':v.STRATEGY,'normalization':[],'admitted':False,'competitive_runs_allowed':False,
         'quota_event_credit':False,'new_eligible_dossier':False,'native_process_helper_frame_bytes':v.FRAME}
    (directory / 'receipt.json').write_bytes(encoded(m))
    args = [values[n] for n in ['input-a.json','input-b.json','input-invalid.json']]
    write_process(directory / 'incremental',v.requests(*args,a['snapshot_id'],values['protocol.json']['queries']),a,known,12345,'a' * 64)
    write_process(directory / 'rebuild',v.requests(*args,a['snapshot_id'],values['protocol.json']['queries'],fresh=True),a,known,12346,'b' * 64)


def mutate_response(directory, side, index, change):
    path = directory / side
    rows = [v.decode(line) for line in (path / 'transcript.jsonl').read_bytes().splitlines()]
    response = v.decode(base64.b64decode(rows[index]['response_base64']))
    change(response)
    raw = encoded(response)
    rows[index]['response_base64'] = base64.b64encode(raw).decode(); rows[index]['response_sha256'] = v.sha(raw)
    (path / 'transcript.jsonl').write_bytes(b''.join(encoded(r) for r in rows))
    (path / 'stdout.jsonl').write_bytes(b''.join(base64.b64decode(r['response_base64']) for r in rows))
    if index == len(rows) - 1:
        meta = v.decode((path / 'process.json').read_bytes()); meta['closed_response'] = response
        (path / 'process.json').write_bytes(encoded(meta))


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='xrai-tsjs-session-test-')
        self.directory = Path(self.temporary.name) / 'event'
        supplied = os.environ.get('XRAI_TSJS_SESSION_OUTPUT')
        if supplied:
            source = Path(supplied)
        else:
            source = Path(self.temporary.name) / 'readonly-fake-source'
            source.mkdir(); fake_bundle(source)
            # Exercise the actual collector's modes with the offline transport fixture.
            for path in (source / 'inputs').iterdir():
                path.chmod(0o400)
            (source / 'native-bin/tsjs-semantic-session').chmod(0o500)
        shutil.copytree(source,self.directory)
        copies = []
        for path in source.rglob('*'):
            if path.is_file():
                copied = self.directory / path.relative_to(source)
                self.assertEqual(copied.read_bytes(),path.read_bytes(), 'private copy changed source bytes')
                copies.append(copied)
        # Only this private adversarial-test copy becomes writable; never the source.
        for copied in copies:
            copied.chmod(copied.stat().st_mode | 0o200)

    def tearDown(self):
        self.temporary.cleanup()

    def reject(self, mutate):
        mutate(self.directory)
        with self.assertRaises((ValueError,KeyError,TypeError,UnicodeError)):
            v.verify(self.directory)

    def test_complete_bundle_consumer(self):
        result = v.verify(self.directory)
        self.assertTrue(result['full_B_snapshot_equal'])
        self.assertTrue(result['failed_updates_preserve_full_A'])
        self.assertFalse(result['quota_event_credit'])
        self.assertFalse(result['admitted'])

    def test_frozen_design(self):
        values,_ = v.assets()
        self.assertEqual(len(values['protocol.json']['queries']),3)

    def test_collector_refuses_local_native(self):
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'false'}):
            with self.assertRaisesRegex(ValueError,'disposable Linux CI'):
                collector.collect('/does/not/exist',self.directory)

    def test_duplicate_keys_nonfinite(self):
        for raw in [b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                v.decode(raw)

    def test_input_rebound(self):
        self.reject(lambda d:(d / 'inputs/input-a.json').write_bytes((d / 'inputs/input-b.json').read_bytes()))

    def test_executable_rebound(self):
        self.reject(lambda d:(d / 'native-bin/tsjs-semantic-session').write_bytes(b'\x7fELF' + b'wrong' * 1024))

    def test_extra_file(self):
        self.reject(lambda d:(d / 'extra.json').write_text('{}'))

    def test_stderr_and_unread_output(self):
        self.reject(lambda d:(d / 'incremental/stderr.bin').write_bytes(b'failure'))

    def test_missing_operations(self):
        self.reject(lambda d:(d / 'incremental/transcript.jsonl').write_bytes(b''))

    def test_forged_scope_admission(self):
        def change(d):
            p=d / 'receipt.json'; m=v.decode(p.read_bytes()); m['admitted']=True; p.write_bytes(encoded(m))
        self.reject(change)

    def test_empty_loss_normalization_not_allowed(self):
        def change(d):
            p=d / 'receipt.json'; m=v.decode(p.read_bytes()); m['normalization']=['remove_dependencies']; p.write_bytes(encoded(m))
        self.reject(change)

    def test_wrong_source_binding(self):
        def change(d):
            p=d / 'receipt.json'; m=v.decode(p.read_bytes()); m['source_sha256'][v.SOURCE_BIN]='0' * 64; p.write_bytes(encoded(m))
        self.reject(change)

    def test_missing_source_binding(self):
        def change(d):
            p=d / 'receipt.json'; m=v.decode(p.read_bytes()); m['source_sha256'].pop('Cargo.lock'); p.write_bytes(encoded(m))
        self.reject(change)

    def test_process_bool_count(self):
        def change(d):
            p=d / 'rebuild/process.json'; m=v.decode(p.read_bytes()); m['command_count']=True; p.write_bytes(encoded(m))
        self.reject(change)

    def test_full_evidence_not_normalized_both_sides(self):
        def change(d):
            for side,index in [('incremental',10),('rebuild',1)]:
                mutate_response(d,side,index,lambda r:r['response']['result']['references'][0]['resolution']['evidence'].clear())
        self.reject(change)

    def test_full_gaps_not_normalized_both_sides(self):
        def change(d):
            for side,index in [('incremental',10),('rebuild',1)]:
                mutate_response(d,side,index,lambda r:r['response']['result']['gaps'].clear())
        # Existing uuid gaps are real. Clearing both must not pass equal-B alone.
        self.reject(change)

    def test_native_grammar_not_normalized_both_sides(self):
        def change(d):
            for side,index in [('incremental',10),('rebuild',1)]:
                mutate_response(d,side,index,lambda r:r['response']['result']['producer_components'].update({'javascript':'0' * 64}))
        self.reject(change)

    def test_unchanged_semantic_snapshot_exact(self):
        self.reject(lambda d:mutate_response(d,'incremental',6,lambda r:r['response']['result']['coverage'].clear()))

    def test_cold_b_request_relabel(self):
        def change(d):
            path = d / 'incremental/transcript.jsonl'
            rows = [v.decode(line) for line in path.read_bytes().splitlines()]
            request = v.decode(base64.b64decode(rows[0]['request_base64']))
            request['input'] = v.decode((d / 'inputs/input-b.json').read_bytes())
            raw = encoded(request)
            rows[0]['request_base64'] = base64.b64encode(raw).decode()
            rows[0]['request_sha256'] = v.sha(raw)
            path.write_bytes(b''.join(encoded(r) for r in rows))
        self.reject(change)

    def test_same_pid_independent_process_rejected(self):
        def change(d):
            left = v.decode((d / 'incremental/process.json').read_bytes())['pid']
            for i in range(6):
                mutate_response(d,'rebuild',i,lambda r:r['response'].update(pid=left))
            p = d / 'rebuild/process.json'
            m = v.decode(p.read_bytes()); m['pid'] = left; p.write_bytes(encoded(m))
        self.reject(change)

    def test_same_session_independent_index_rejected(self):
        def change(d):
            first = v.decode((d / 'incremental/transcript.jsonl').read_bytes().splitlines()[0])
            session = v.decode(base64.b64decode(first['response_base64']))['response']['session_id']
            for i in range(6):
                mutate_response(d,'rebuild',i,lambda r:r['response'].update(session_id=session))
        self.reject(change)

    def test_non_single_frame_rejected(self):
        def change(d):
            path = d / 'incremental/transcript.jsonl'
            rows = [v.decode(line) for line in path.read_bytes().splitlines()]
            raw = base64.b64decode(rows[0]['request_base64']) + b'\n'
            rows[0]['request_base64'] = base64.b64encode(raw).decode()
            rows[0]['request_sha256'] = v.sha(raw)
            path.write_bytes(b''.join(encoded(r) for r in rows))
        self.reject(change)


COUNTERPROOFS = {
    'pid_restart': ('incremental',6,lambda r:r['response'].update(pid=99999)),
    'session_restart': ('incremental',6,lambda r:r['response'].update(session_id='c' * 64)),
    'generation_bool': ('incremental',0,lambda r:r['response'].update(generation=True)),
    'generation_float': ('incremental',0,lambda r:r['response'].update(generation=1.0)),
    'snapshot_stale_at_b': ('incremental',10,lambda r:r['response'].update(snapshot_id='0' * 64)),
    'session_producer': ('incremental',1,lambda r:r['response'].update(session_producer_fingerprint='0' * 64)),
    'counter_forged': ('incremental',10,lambda r:r['response']['counters'].update(successful_builds=1)),
    'counter_bool': ('incremental',0,lambda r:r['response']['counters'].update(requests=True)),
    'stale_accepted': ('incremental',5,lambda r:r.update(status='ok')),
    'stale_changed_generation': ('incremental',5,lambda r:r.update(generation=2)),
    'invalid_configuration_accepted': ('incremental',7,lambda r:r.update(status='ok')),
    'query_missing_reference': ('incremental',11,lambda r:r['response']['result'].update(reference=None)),
    'query_wrong_offset': ('incremental',11,lambda r:r['response']['result'].update(offset=644)),
    'query_bool_offset': ('incremental',11,lambda r:r['response']['result'].update(offset=True)),
    'query_removed_dependencies': ('incremental',11,lambda r:r['response']['result']['reference']['resolution']['dependencies'].clear()),
    'query_callable_promotion': ('incremental',11,lambda r:r['response']['result']['reference']['callable'].update(state='resolved')),
    'query_removed_diagnostic': ('incremental',11,lambda r:r['response']['result']['reference']['resolution'].pop('diagnostic')),
    'snapshot_removed_fields': ('incremental',10,lambda r:r['response']['result'].pop('exports')),
    'scope_boolean': ('incremental',1,lambda r:r['response']['result']['scopes'][0].update(start=True)),
    'foreign_config': ('incremental',10,lambda r:r['response']['result']['input']['configuration'].update(module='commonjs')),
    'scope_extra_key': ('incremental',1,lambda r:r['response']['result']['scopes'][0].update(hidden=True)),
    'evidence_wrong_source': ('incremental',11,lambda r:r['response']['result']['reference']['evidence'].update(source_hash='0' * 64)),
    'fresh_index_generation': ('rebuild',0,lambda r:r['response'].update(generation=2)),
}


def counterfeit_test(side,index,change):
    def run(self):
        self.reject(lambda d:mutate_response(d,side,index,change))
    return run

for name,(side,index,change) in COUNTERPROOFS.items():
    setattr(SessionTests,'test_counterproof_' + name,counterfeit_test(side,index,change))

if __name__ == '__main__':
    unittest.main()
