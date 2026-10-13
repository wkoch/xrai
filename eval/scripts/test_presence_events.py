"""Presence framing/data contraproofs. Never starts a native executable.

Without XRAI_PRESENCE_PROOF the records are explicitly synthetic contract data.
With that variable, the same negatives run on copies of all three CI exports.
"""
import base64
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from verify_presence_event import (PROFILE, SCHEMA, SOURCES, ROOT, expected_snapshot,
                                   expected_query, same, verify, sha)


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def replace_response(directory, side, position, change):
    """Rehash transport evidence too: test semantics rather than stale SHA only."""
    folder = directory / side
    rows = [json.loads(line) for line in (folder / 'transcript.jsonl').read_bytes().splitlines()]
    row = rows[position]
    response = json.loads(base64.b64decode(row['response_base64']))
    change(response)
    raw = wire(response)
    row['response_base64'], row['response_sha256'] = base64.b64encode(raw).decode(), sha(raw)
    (folder / 'transcript.jsonl').write_bytes(b''.join(wire(item) for item in rows))
    (folder / 'stdout.jsonl').write_bytes(b''.join(base64.b64decode(item['response_base64']) for item in rows))
    if position in {-1, len(rows) - 1}:
        process = read(folder / 'process.json')
        process['closed_response'] = response
        write(folder / 'process.json', process)


def replace_process(directory, side, key, value):
    path = directory / side / 'process.json'
    process = read(path)
    process[key] = value
    write(path, process)


def replace_receipt(directory, change):
    path = directory / 'receipt.json'
    value = read(path)
    change(value)
    write(path, value)


def synthetic_contract(directory, folder='js'):
    """Build fake transport data, not evidence of native execution or admission."""
    assets = ROOT / 'eval/qualification/state-events' / folder
    (directory / 'inputs').mkdir(parents=True)
    for name in ['descriptor.json', 'a.json', 'b.json', 'queries.json', 'oracle.json']:
        shutil.copyfile(assets / name, directory / 'inputs' / name)
    (directory / 'native-bin').mkdir()
    binary = directory / 'native-bin/source-presence-session'
    binary.write_bytes(b'SYNTHETIC CONTRACT DATA: NEVER EXECUTED')
    descriptor = read(directory / 'inputs/descriptor.json')
    a, b, queries = [read(directory / 'inputs' / name) for name in ['a.json', 'b.json', 'queries.json']]
    before, after = expected_snapshot(a), expected_snapshot(b)
    qr = [{'operation': 'query', 'kind': q['kind'], 'path': q['path']} for q in queries]
    requests = [{'operation': 'open', 'input': a}, {'operation': 'snapshot'}] + qr + [
        {'operation': 'update', 'expected_snapshot': 'intentionally-stale-revision', 'input': b},
        {'operation': 'snapshot'}, {'operation': 'update', 'expected_snapshot': before['snapshot_id'], 'input': b},
        {'operation': 'snapshot'}] + qr + [{'operation': 'close'}]
    fresh = [{'operation': 'open', 'input': b}, {'operation': 'snapshot'}] + qr + [{'operation': 'close'}]
    for side, reqs, initial, pid, session in [('incremental', requests, before, 1001, 'a' * 64),
                                            ('rebuild', fresh, after, 1002, 'b' * 64)]:
        target = directory / side
        target.mkdir()
        current, generation, rows, responses = initial, 0, [], []
        for sequence, request in enumerate(reqs):
            operation = request['operation']
            if operation == 'update' and request['expected_snapshot'] == 'intentionally-stale-revision':
                response = {'status': 'error', 'diagnostic': 'expected snapshot mismatch; previous snapshot preserved',
                            'session_id': session, 'snapshot_id': current['snapshot_id'], 'generation': generation}
            else:
                if operation in {'open', 'update'}:
                    generation += 1
                    if operation == 'update':
                        current = after
                    result = {'strategy': 'conservative_full_rebuild'}
                elif operation == 'snapshot':
                    result = current
                elif operation == 'query':
                    result = expected_query(current, request)
                else:
                    result = {'closed': True}
                response = {'status': 'ok', 'response': {'schema': SCHEMA, 'session_id': session, 'pid': pid,
                    'generation': generation, 'snapshot_id': current['snapshot_id'], 'operation': operation,
                    'result': copy.deepcopy(result)}}
            rq, rs = wire(request), wire(response)
            rows.append({'sequence': sequence, 'request_base64': base64.b64encode(rq).decode(),
                         'request_sha256': sha(rq), 'response_base64': base64.b64encode(rs).decode(),
                         'response_sha256': sha(rs)})
            responses.append(rs)
        (target / 'transcript.jsonl').write_bytes(b''.join(wire(item) for item in rows))
        (target / 'stdout.jsonl').write_bytes(b''.join(responses))
        (target / 'stderr.bin').write_bytes(b'')
        write(target / 'process.json', {'pid': pid, 'exit_code': 0, 'explicit_close': True,
            'wrapper_reaped': True, 'unread_output_bytes': 0, 'command_count': len(reqs),
            'transport': 'bounded newline JSON', 'elapsed_seconds': 0.1,
            'closed_response': json.loads(responses[-1])})
    write(directory / 'receipt.json', {'schema': 'xrai.eval.c04.source-presence.receipt.v1',
        'family': descriptor['family'], 'task_id': descriptor['task_id'], 'slot_id': descriptor['slot_id'],
        'descriptor_sha256': sha((directory / 'inputs/descriptor.json').read_bytes()),
        'input_sha256': {name: sha((directory / 'inputs' / name).read_bytes()) for name in ['a.json', 'b.json', 'queries.json', 'oracle.json']},
        'source_sha256': {name: sha((ROOT / name).read_bytes()) for name in SOURCES},
        'binary': {'path': 'native-bin/source-presence-session', 'sha256': sha(binary.read_bytes()), 'bytes': binary.stat().st_size},
        'environment': {'platform': 'synthetic contract data', 'machine': 'not executed',
                        'github_sha': '0' * 40, 'github_run_id': 'synthetic-no-run'},
        'scope': PROFILE, 'strategy': 'conservative_full_rebuild', 'normalization': [],
        'admitted': False, 'competitive_runs_allowed': False})


def nested_change(directory, side, position, function):
    replace_response(directory, side, position, lambda response: function(response['response']['result']))


def erase_unknowns(directory):
    nested_change(directory, 'incremental', 8, lambda value: value.update(unknowns=[]))
    nested_change(directory, 'rebuild', 1, lambda value: value.update(unknowns=[]))


def alter_coverage(directory):
    def mutate(value):
        next(iter(value['coverage'].values()))['semantics'] = 'complete'
    nested_change(directory, 'incremental', 8, mutate)
    nested_change(directory, 'rebuild', 1, mutate)


def make_process_not_independent(directory):
    left_pid = read(directory / 'incremental/process.json')['pid']
    replace_process(directory, 'rebuild', 'pid', left_pid)
    count = read(directory / 'rebuild/process.json')['command_count']
    for position in range(count):
        replace_response(directory, 'rebuild', position, lambda response: response['response'].update(pid=left_pid))


def make_session_not_independent(directory):
    rows = [json.loads(line) for line in (directory / 'incremental/transcript.jsonl').read_bytes().splitlines()]
    session = json.loads(base64.b64decode(rows[0]['response_base64']))['response']['session_id']
    count = read(directory / 'rebuild/process.json')['command_count']
    for position in range(count):
        replace_response(directory, 'rebuild', position, lambda response: response['response'].update(session_id=session))


def change_query_count(directory):
    path = directory / 'inputs/queries.json'
    value = read(path)
    value.pop()
    write(path, value)
    replace_receipt(directory, lambda receipt: receipt['input_sha256'].update({'queries.json': sha(path.read_bytes())}))


def corrupt_binary(directory):
    path = directory / 'native-bin/source-presence-session'
    path.chmod(0o600)
    path.write_bytes(path.read_bytes() + b'altered')


NEGATIVES = {
    'unknowns_removed_on_both_sides': erase_unknowns,
    'coverage_forged_on_both_sides': alter_coverage,
    'snapshot_length_float': lambda d: nested_change(d, 'incremental', 8, lambda v: next(iter(v['files'].values())).update(byte_length=float(next(iter(v['files'].values()))['byte_length']))),
    'query_start_boolean': lambda d: nested_change(d, 'incremental', 10, lambda v: v['evidence'].update(start=False)),
    'query_end_float': lambda d: nested_change(d, 'incremental', 10, lambda v: v['evidence'].update(end=float(v['evidence']['end']))),
    'query_evidence_snapshot_changed': lambda d: nested_change(d, 'incremental', 10, lambda v: v['evidence'].update(snapshot_id='wrong')),
    'query_dependency_stripped': lambda d: nested_change(d, 'incremental', 9, lambda v: v.update(dependencies=[])),
    'absence_available_numeric': lambda d: nested_change(d, 'incremental', 11, lambda v: v.update(available=0)),
    'query_diagnostic_stripped': lambda d: nested_change(d, 'incremental', 9, lambda v: v.update(diagnostics=[])),
    'stable_control_answer_changed': lambda d: nested_change(d, 'incremental', 10, lambda v: v.update(available=False)),
    'wrong_revision_accepted': lambda d: replace_response(d, 'incremental', 5, lambda v: v.update(status='ok')),
    'wrong_revision_changed_snapshot': lambda d: replace_response(d, 'incremental', 5, lambda v: v.update(snapshot_id='wrong')),
    'wrong_revision_boolean_generation': lambda d: replace_response(d, 'incremental', 5, lambda v: v.update(generation=True)),
    'a_not_preserved_after_rejected_update': lambda d: nested_change(d, 'incremental', 6, lambda v: v.update(diagnostics=[])),
    'pid_changed_mid_session': lambda d: replace_response(d, 'incremental', 9, lambda v: v['response'].update(pid=987654)),
    'session_reopened_mid_session': lambda d: replace_response(d, 'incremental', 9, lambda v: v['response'].update(session_id='c' * 64)),
    'cold_b_instead_of_same_index': lambda d: replace_response(d, 'incremental', 7, lambda v: v['response'].update(generation=1)),
    'rebuild_same_process': make_process_not_independent,
    'rebuild_same_session': make_session_not_independent,
    'open_strategy_marker_changed': lambda d: nested_change(d, 'incremental', 0, lambda v: v.update(strategy='cache_reuse_claimed')),
    'update_strategy_marker_changed': lambda d: nested_change(d, 'incremental', 7, lambda v: v.update(strategy='cache_reuse_claimed')),
    'nonhex_session_identity': lambda d: replace_response(d, 'incremental', 0, lambda v: v['response'].update(session_id='z' * 64)),
    'extra_envelope_flag': lambda d: replace_response(d, 'incremental', 9, lambda v: v.update(admitted=True)),
    'close_scalar_not_boolean': lambda d: nested_change(d, 'incremental', -1, lambda v: v.update(closed=1)),
    'unread_bytes_boolean': lambda d: replace_process(d, 'incremental', 'unread_output_bytes', False),
    'exit_code_boolean': lambda d: replace_process(d, 'incremental', 'exit_code', False),
    'command_count_float': lambda d: replace_process(d, 'incremental', 'command_count', float(read(d / 'incremental/process.json')['command_count'])),
    'no_explicit_close': lambda d: replace_process(d, 'incremental', 'explicit_close', False),
    'binary_size_float': lambda d: replace_receipt(d, lambda v: v['binary'].update(bytes=float(v['binary']['bytes']))),
    'binary_bytes_changed': corrupt_binary,
    'two_queries_only_rehashed': change_query_count,
    'family_slot_substitution': lambda d: replace_receipt(d, lambda v: v.update(slot_id='L5-SLOT-TSJS-state_config-2')),
    'admission_flag': lambda d: replace_receipt(d, lambda v: v.update(admitted=True)),
    'source_hash_closure_lost': lambda d: replace_receipt(d, lambda v: v['source_sha256'].pop(SOURCES[0])),
    'unexpected_file': lambda d: (d / 'unreviewed.json').write_text('{}'),
    'missing_stdout': lambda d: (d / 'incremental/stdout.jsonl').unlink(),
    'stderr_not_empty': lambda d: (d / 'incremental/stderr.bin').write_bytes(b'unexpected error'),
}


class _CounterBase:
    def sources(self):
        raise NotImplementedError

    def test_valid_full_data_contract(self):
        for name, source in self.sources():
            with self.subTest(family=name):
                result = verify(source)
                self.assertEqual(result['queries'], 3)
                self.assertEqual(result['changed_query_expectations'], 1)
                self.assertTrue(result['full_B_snapshot_equal'])
                self.assertFalse(result['admitted'])
                self.assertNotEqual(result['pid'], result['rebuild_pid'])
                self.assertNotEqual(result['session_id'], result['rebuild_session_id'])


class SyntheticPresenceTests(_CounterBase, unittest.TestCase):
    def sources(self):
        for folder in ['js', 'python', 'go']:
            with tempfile.TemporaryDirectory(prefix='xrai-presence-contract-') as temp:
                directory = Path(temp) / folder
                synthetic_contract(directory, folder)
                yield folder, directory

    def test_utf8_span_is_byte_length_and_semantics_remain_unknown(self):
        snapshot = expected_snapshot({'configuration': {'profile': PROFILE}, 'files': {'a.py': '🍃á\n'}})
        result = expected_query(snapshot, {'path': 'a.py'})
        self.assertEqual(result['evidence']['end'], 7)
        self.assertEqual(result['parse_state'], 'unknown')
        self.assertEqual(result['semantic_state'], 'unknown')
        self.assertEqual(snapshot['coverage']['a.py']['semantics'], 'not_evaluated')
        missing = expected_query(snapshot, {'path': 'absent.py'})
        self.assertFalse(missing['available'])
        self.assertIsNone(missing['evidence'])
        self.assertEqual(missing['semantic_state'], 'unknown')

    def test_collection_rejected_outside_disposable_ci(self):
        from run_presence_events import collect
        with tempfile.TemporaryDirectory(prefix='xrai-presence-no-execution-') as temp:
            with mock.patch('run_presence_events.platform.system', return_value='UntrustedPlatform'), mock.patch('run_presence_events.Process', side_effect=AssertionError('native execution attempted')):
                with self.assertRaisesRegex(ValueError, 'disposable Linux CI'):
                    collect(Path(temp) / 'nonexistent-binary', Path(temp) / 'output', 'js')
            self.assertFalse((Path(temp) / 'output').exists())

    def test_canonical_equality_keeps_boolean_integer_float_distinct(self):
        self.assertFalse(same({'start': 0}, {'start': False}))
        self.assertFalse(same({'end': 10}, {'end': 10.0}))
        self.assertFalse(same({'available': False}, {'available': 0}))


@unittest.skipUnless(os.environ.get('XRAI_PRESENCE_PROOF'), 'real native CI export not provided')
class RealPresenceProofTests(_CounterBase, unittest.TestCase):
    def sources(self):
        root = Path(os.environ['XRAI_PRESENCE_PROOF'])
        self.assertTrue(root.is_dir())
        for folder in ['js', 'python', 'go']:
            source = root / folder
            self.assertTrue((source / 'receipt.json').is_file(), f'missing real {folder} export')
            yield folder, source


def install_negative(name, mutate):
    def test(self):
        for family, source in self.sources():
            with self.subTest(family=family), tempfile.TemporaryDirectory(prefix='xrai-presence-negative-') as temp:
                target = Path(temp) / 'event'
                shutil.copytree(source, target)
                mutate(target)
                with self.assertRaises((ValueError, KeyError, TypeError, FileNotFoundError)):
                    verify(target)
    test.__name__ = 'test_reject_' + name
    for cls in [SyntheticPresenceTests, RealPresenceProofTests]:
        setattr(cls, test.__name__, test)


for name, mutation in NEGATIVES.items():
    install_negative(name, mutation)


if __name__ == '__main__':
    unittest.main()
