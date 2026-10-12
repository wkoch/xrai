#!/usr/bin/env python3
"""Independent replay of P3 development captures, envelope, budgets, retention.

Evaluator labels live in eval/context/development-labels.json, not typed input.
No success claim about full tasks, complete call graph, or production CLI.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from blake3 import blake3
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'crates/xrai-eval/harness'))
from offline_measurement import canonical, tokenizer

def digest(raw):
    return blake3(raw).hexdigest()

def struct_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()

def document_fixture(delivery):
    m, snapshots = delivery['manifest'], delivery['snapshots']
    files = []
    for s in snapshots:
        for path, source in s['input']['files'].items():
            raw = source.encode()
            files.append({'file_id': 'fi_' + digest(path.encode()), 'snapshot_id': s['snapshot_id'],
                'path': {'encoding': 'unix_bytes', 'units_hex': path.encode().hex(), 'display': path},
                'source_hex': raw.hex(), 'source_hash': {'algorithm': 'blake3', 'hex': digest(raw)},
                'byte_length': len(raw), 'language': 'rust'})
    manifest = {k: m[k] for k in ['context_id', 'snapshots', 'request', 'rules_version', 'obligations']}
    manifest['items'] = [{'id': c['id'], 'snapshot_id': c['snapshot_id'], 'file_id': c['file_id'],
        'source_hash': {'algorithm': 'blake3', 'hex': c['source_hash']},
        'span': {'start': c['full'][0], 'end': c['full'][1]}} for c in m['candidates']]
    ids = [s['snapshot_id'] for s in snapshots]
    manifest['retention'] = {'retained_snapshot_ids': ids, 'expired': False}
    return {'fixture_version': 3, 'case_id': 'context-generated', 'valid': True, 'expected_violation': None,
        'fixture_files': files, 'fixture_state': {'published_snapshot_id': ids[-1],
        'required_snapshot_id': ids[-1], 'retained_snapshot_ids': ids, 'bindings': [], 'inventory_at_required': []},
        'fixture_manifest': manifest, 'request': delivery['request'], 'response': delivery['response'], 'admission_error': None}

def verify_delivery(delivery, encoding, profile, contract, validator):
    r, m = delivery['response'], delivery['manifest']
    raw = bytes.fromhex(delivery['wire_hex'])
    assert canonical(r) == raw, 'wire differs from canonical final envelope'
    assert delivery['wire_blake3'] == digest(raw)
    assert r['budget']['used_bytes'] == len(raw) <= r['budget']['requested_bytes']
    count = len(encoding.encode(raw.decode(), disallowed_special=()))
    assert r['budget']['used_tokens'] == count <= r['budget']['requested_tokens']
    assert r['budget']['tokenizer'] == 'l4:' + profile['fingerprint_sha256']
    assert delivery['meter_calls'] > 0 and delivery['meter_elapsed_micros'] >= 0
    assert m['selector_fingerprint'] == digest((ROOT / 'crates/xrai-eval/src/context_spike.rs').read_bytes())
    assert m['expires_ms'] - m['created_ms'] == 60000
    assert len(m['retention_epoch'])==64 and all(c in '0123456789abcdef' for c in m['retention_epoch'])
    assert m['incarnation']>=1
    assert m['retention_policy']=='p3-memory-contexts2-serialized8MiB-ttl60000-attempts4-v1'
    assert m['context_id']=='ctx_'+digest(struct_bytes([m['selection_fingerprint'],m['retention_epoch'],m['incarnation'],m['created_ms'],m['expires_ms'],m['retention_policy']]))
    assert m['retained_bytes'] <= 8 * 1024 * 1024
    actual_sources = {}
    def validate_ir(value, snapshot, declarations):
        if isinstance(value, dict):
            if {'snapshot_id', 'path', 'start', 'end', 'source_hash', 'file_id'} <= value.keys():
                assert value['snapshot_id'] == snapshot['snapshot_id']
                source = actual_sources[(value['snapshot_id'], value['path'])]
                assert value['source_hash'] == digest(source)
                assert value['file_id'] == 'fi_' + digest(value['path'].encode())
                assert 0 <= value['start'] <= value['end'] <= len(source)
                source[:value['start']].decode(); source[value['start']:value['end']].decode()
            if {'state', 'target_id', 'candidate_ids', 'method', 'dependencies'} <= value.keys():
                assert value['method'] == 'semantic_resolution'
                if value['state'] == 'resolved':
                    assert value['target_id'] in declarations and not value['candidate_ids']
                    assert value['evidence'] and value['dependencies']
                elif value['state'] == 'candidate':
                    assert value['target_id'] is None and value['candidate_ids']
                    assert set(value['candidate_ids']) <= declarations
                else:
                    assert value['state'] in ['unknown', 'external']
                    assert value['target_id'] is None and not value['candidate_ids']
                assert all(snapshot['snapshot_id'] in dep for dep in value['dependencies'])
            for child in value.values(): validate_ir(child, snapshot, declarations)
        elif isinstance(value, list):
            for child in value: validate_ir(child, snapshot, declarations)
    for s in delivery['snapshots']:
        inp = s['input']
        # Rust Input field order is part of L4's historical snapshot serializer;
        # output is sorted by Value, so reconstruct that order explicitly.
        typed_input = {k: inp[k] for k in ['files', 'root', 'edition', 'configuration', 'rules']}
        assert s['snapshot_id'] == 'snap_' + digest(struct_bytes([typed_input, s['producer_fingerprint']]))
        assert s['configuration_fingerprint'] == digest(struct_bytes([inp['edition'], inp['configuration']]))
        assert s['configuration_id'] == 'cfg_' + s['configuration_fingerprint']
        for path, source in inp['files'].items():
            actual_sources[(s['snapshot_id'], path)] = source.encode()
        for decl in s['declarations']:
            e = decl['evidence']; source = actual_sources[(e['snapshot_id'], e['path'])]
            assert source[e['start']:e['end']].decode() == decl['name']
            assert e['source_hash'] == digest(source)
        validate_ir(s, s, {d['id'] for d in s['declarations']})
    for resolution in m['resolutions']:
        s = next(s for s in delivery['snapshots'] if s['snapshot_id'] == resolution['snapshot_id'])
        validate_ir(resolution['result'], s, {d['id'] for d in s['declarations']})
    for c in m['candidates']:
        source = actual_sources[(c['snapshot_id'], c['path'])]
        assert c['source_hash'] == digest(source)
        assert c['file_id'] == 'fi_' + digest(c['path'].encode())
        for a, b in [c['minimum'], c['container'], c['full']]:
            assert 0 <= a <= b <= len(source); source[:a].decode(); source[a:b].decode()
        assert c['full'] == [0, len(source)]
        assert c['state'] in ['syntactic', 'resolved']
        if c['reason'] == 'resolved_definition':
            s = next(s for s in delivery['snapshots'] if s['snapshot_id'] == c['snapshot_id'])
            assert any(d['evidence']['path'] == c['path'] and
                       c['minimum'][0] <= d['evidence']['start'] < d['evidence']['end'] <= c['minimum'][1]
                       for d in s['declarations'])
        if c['reason'] == 'demonstrated_consumer':
            s = next(s for s in delivery['snapshots'] if s['snapshot_id'] == c['snapshot_id'])
            assert any(ref['resolution']['state'] == 'resolved' and ref['evidence']['path'] == c['path'] and
                       c['minimum'][0] <= ref['evidence']['start'] < ref['evidence']['end'] <= c['minimum'][1]
                       for ref in s['references'])
    contract.check_case(document_fixture(delivery), validator)
    return {'bytes': len(raw), 'tokens': count, 'status': r['status'], 'items': len(r['items']),
            'identified': r['sufficiency']['identified'], 'included': r['sufficiency']['included']}

def verify(input_path, output_path):
    inp = json.loads(Path(input_path).read_text())
    output = json.loads(Path(output_path).read_text())
    assert output['input'] == inp
    assert output['initial']['manifest']['normalized_request'] == inp['request']
    assert output['initial']['snapshots'][-1]['input'] == inp['head']
    if inp['base'] is not None:
        assert output['initial']['snapshots'][0]['input'] == inp['base']
    spec = importlib.util.spec_from_file_location('experimental_p3_contract', ROOT / 'docs/contracts/experimental-p3/verify.py')
    contract = importlib.util.module_from_spec(spec); spec.loader.exec_module(contract)
    schema = json.loads((ROOT / 'docs/contracts/experimental-p3/schema.json').read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    encoding, profile = tokenizer()
    receipts = {}
    for key in ['initial', 'expanded', 'published', 'after_new']:
        if output[key] is not None:
            receipts[key] = verify_delivery(output[key], encoding, profile, contract, validator)
    if output['insufficient'].get('delivery'):
        receipts['insufficient'] = verify_delivery(output['insufficient']['delivery'], encoding, profile, contract, validator)
    else:
        assert output['insufficient']['error'] in ['budget_below_envelope', 'counter_cycle', 'counter_iterations_exhausted']
    assert output['expired'] == 'context_expired'
    if output.get('retention_recreated'):
        new=output['retention_recreated'];receipts['retention_recreated']=verify_delivery(new,encoding,profile,contract,validator)
        old=output['initial']['manifest']; fresh=new['manifest']
        assert old['selection_fingerprint']==fresh['selection_fingerprint']
        assert old['retention_epoch']==fresh['retention_epoch']
        assert old['context_id']!=fresh['context_id'] and old['incarnation']<fresh['incarnation']
        assert output['old_handle_after_recreation']=='context_expired'
    if output['expanded']:
        assert output['expanded']['response'] == output['after_new']['response']
        assert output['expanded']['manifest'] == output['initial']['manifest'] == output['after_new']['manifest']
        assert output['published']['response']['snapshot']['snapshot_id'] != output['initial']['response']['snapshot']['snapshot_id']
    controls=[]
    assert [(c['pair'], c['p2']) for c in output['controls']] == [(False, False), (False, True), (True, False), (True, True)]
    for control in output['controls']:
        assert control['input']['head'] == inp['head']
        assert control['input']['base'] == (inp['base'] if control['pair'] else None)
        assert control['input']['request']['limits'] == inp['request']['limits']
        if control['outcome'].get('delivery'):
            d=control['outcome']['delivery']
            assert d['manifest']['normalized_request'] == control['input']['request']
            summary=verify_delivery(d, encoding, profile, contract, validator)
            if not control['p2']:
                assert all(c['state'] != 'resolved' for c in d['manifest']['candidates'])
            controls.append({'pair':control['pair'],'p2':control['p2'],**summary})
        else:
            assert control['outcome']['error'] == 'budget_below_envelope'
    assert [c['max_tokens'] for c in output['curves']] == [2000,4000,8000,16000,32000]
    curves=[]
    for point in output['curves']:
        original=json.loads(json.dumps(inp)); original['request']['limits']['max_tokens']=point['max_tokens']
        assert point['input'] == original
        outcome=point['outcome']; summary={'max_tokens':point['max_tokens']}
        if outcome.get('delivery'):
            summary['initial']=verify_delivery(outcome['delivery'],encoding,profile,contract,validator)
            if outcome['expansion'].get('delivery'):
                summary['expansion']=verify_delivery(outcome['expansion']['delivery'],encoding,profile,contract,validator)
                summary['session_tokens']=summary['initial']['tokens']+summary['expansion']['tokens']
            else:
                assert outcome['expansion']['error']=='budget_below_envelope'; summary['expansion_error']=outcome['expansion']['error']
        else:
            assert outcome['error']=='budget_below_envelope';summary['error']=outcome['error']
        curves.append(summary)
    labels = json.loads((ROOT / 'eval/context/development-labels.json').read_text())['cases'].get(Path(input_path).name)
    if labels:
        initial = output['initial']; base_id = initial['snapshots'][0]['snapshot_id']
        if 'required_base_text' in labels:
            assert any(c['reason'] == labels['expected_consumer_reason'] and c['snapshot_id'] == base_id for c in initial['manifest']['candidates'])
            assert any(i['snapshot_id'] == base_id and labels['required_base_text'] in i['content'] for i in initial['response']['items'])
        if 'required_head_text' in labels:
            assert any(i['snapshot_id'] != base_id and labels['required_head_text'] in i['content'] for i in initial['response']['items'])
            assert all(c['minimum'][0] > 1000 for c in initial['manifest']['candidates'])
            assert output['insufficient']['delivery']['response']['status'] == 'insufficient_budget'
    return {'verified': True, 'profile': output['profile'], 'receipts': receipts,'controls':controls,'curves':curves,
            'expired': output['expired'], 'labels_role': 'synthetic_evaluator_only', 'complete_task_success': None}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('input'); parser.add_argument('output'); args = parser.parse_args()
    print(json.dumps(verify(args.input, args.output), indent=2))
