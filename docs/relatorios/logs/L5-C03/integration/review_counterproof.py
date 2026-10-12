#!/usr/bin/env python3
"""Narrow data-only review counterproofs. Does not run a native binary."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'eval/scripts'))
import verify_state_event as v
import execution_preflight as cli


def raw(value):
    return json.dumps(value, separators=(',', ':')).encode() + b'\n'


def transport_fixture(directory, kind):
    session, identity = 'a' * 64, 'snap_actual'
    requests = [{'operation': 'open', 'input': {}}, {'operation': 'snapshot'}]
    responses = []
    for request in requests:
        result = {'snapshot_id': identity} if request['operation'] == 'snapshot' else {}
        responses.append({'status': 'ok', 'response': {
            'schema': 'xrai.eval.c03.rust-session.v1', 'operation': request['operation'],
            'pid': 200, 'generation': 1, 'snapshot_id': identity,
            'session_id': session, 'result': result}})
    if kind == 'stale_error_fields':
        requests.append({'operation': 'update', 'expected_snapshot': 'intentionally-stale-revision', 'input': {}})
        responses.append({'status': 'error',
            'diagnostic': 'expected snapshot mismatch; previous snapshot preserved',
            'session_id': session, 'snapshot_id': 'snap_substituted', 'generation': 999})
    elif kind == 'envelope_snapshot':
        responses[1]['response']['snapshot_id'] = 'snap_substituted'
    requests.append({'operation': 'close'})
    responses.append({'status': 'ok', 'response': {
        'schema': 'xrai.eval.c03.rust-session.v1', 'operation': 'close',
        'pid': 200, 'generation': 1, 'snapshot_id': identity,
        'session_id': session, 'result': {'closed': True}}})
    frames = []
    stdout = b''
    for sequence, (request, response) in enumerate(zip(requests, responses)):
        rq, rs = raw(request), raw(response)
        stdout += rs
        frames.append({'sequence': sequence, 'request_base64': base64.b64encode(rq).decode(),
            'response_base64': base64.b64encode(rs).decode(), 'request_sha256': v.sha(rq),
            'response_sha256': v.sha(rs)})
    (directory / 'transcript.jsonl').write_bytes(b''.join(raw(x) for x in frames))
    (directory / 'stdout.jsonl').write_bytes(stdout)
    (directory / 'stderr.bin').write_bytes(b'')
    (directory / 'process.json').write_bytes(raw({'pid': 200, 'exit_code': 0,
        'explicit_close': True, 'wrapper_reaped': True, 'unread_output_bytes': 0,
        'command_count': len(requests), 'transport': 'bounded newline JSON', 'elapsed_seconds': 0.5,
        'closed_response': responses[-1]}))
    return requests


def run():
    checks = {}
    for kind in ['unchanged', 'envelope_snapshot', 'stale_error_fields']:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            requests = transport_fixture(directory, kind)
            try:
                v.load_process(directory, requests)
                checks[kind] = {'accepted': True}
            except Exception as error:
                checks[kind] = {'accepted': False, 'error': str(error)}
    fixture = ROOT / 'eval/qualification/execution-gate/smoke-offline.json'
    smoke = cli.run(fixture, True)
    assert smoke['adapter_calls'] == 1 and smoke['external_calls'] == 0
    value = json.loads(fixture.read_bytes())
    value['manifest']['intent'] = 'campaign_d1'
    value['manifest']['dataset'] = {'name': 'D1', 'origin': 'qualified_corpus', 'purpose': 'competitive_campaign'}
    with tempfile.TemporaryDirectory() as name:
        changed = Path(name) / 'campaign.json'
        changed.write_bytes(raw(value))
        campaign = cli.run(changed, True)
    assert campaign['adapter_calls'] == 0 and campaign['decision']['accepted'] is False
    return {'data_only': True, 'native_code_executed': False,
        'source_sha256': {str(p.relative_to(ROOT)): v.sha(p.read_bytes()) for p in
            [ROOT / 'eval/scripts/verify_state_event.py', ROOT / 'eval/scripts/execution_preflight.py', Path(__file__)]},
        'narrow_transport_checks': checks,
        'cli': {'smoke_adapter_calls': smoke['adapter_calls'], 'campaign_adapter_calls': campaign['adapter_calls'],
                'campaign_refusals': campaign['decision']['dimensions']},
        'scope': 'load_process envelope linkage only; this synthetic fixture is not a valid full native event proof'}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, sort_keys=True))
