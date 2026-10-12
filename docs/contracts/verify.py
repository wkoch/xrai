#!/usr/bin/env python3
"""Documentary checks for M0-01 examples; not a product/domain implementation."""

import json
import sys
from pathlib import Path

from blake3 import blake3
from jsonschema import Draft202012Validator, FormatChecker


EXAMPLES = Path(__file__).resolve().parent / 'examples'


class Violation(Exception):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


def require(condition, code, detail):
    if not condition:
        raise Violation(code, detail)


def compact_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def check_case(case, validator):
    errors = list(validator.iter_errors(case))
    require(not errors, 'schema', str(errors[0]) if errors else '')
    q, r, admission = case['request'], case['response'], case['admission_error']
    require((q['limits']['max_tokens'] is None) == (q['limits']['tokenizer'] is None),
            'tokenizer', 'tokenizer and max_tokens must be supplied together')
    if admission:
        require(r is None and not case['fixture_files'], 'admission', 'admission must recover no payload')
        require(q['limits']['max_bytes'] < admission['minimum_bytes'], 'admission', 'budget meets minimum')
        require(len(compact_bytes(admission)) <= admission['diagnostic_hard_cap_bytes'],
                'admission', 'diagnostic exceeds hard cap')
        return
    require(r is not None, 'response', 'normal response absent')
    for field in ['schema_version', 'request_id', 'workspace_id', 'worktree_id']:
        require(r[field] == q[field], 'request_identity', field)
    require(r['freshness']['mode'] == q['consistency']['mode'], 'freshness', 'mode changed')
    require(r['budget']['used_bytes'] == len(compact_bytes(r)), 'budget_count', 'serialized size mismatch')
    require(r['budget']['requested_bytes'] == q['limits']['max_bytes'], 'budget_limit', 'request differs')
    require(r['budget']['used_bytes'] <= r['budget']['requested_bytes'], 'budget_limit', 'payload exceeds limit')
    if r['budget']['counting'] == 'not_requested':
        require(r['budget']['used_tokens'] is None and r['budget']['requested_tokens'] is None
                and r['budget']['tokenizer'] is None, 'tokenizer', 'fictitious token count')
    facts = r['assertions'] + r['candidates'] + r['unknowns']
    if r['snapshot'] is None:
        require(not r['items'] and not facts, 'snapshot_identity', 'data without snapshot')
        require(r['coverage']['query']['completeness'] != 'complete', 'snapshot_identity', 'false completeness')
        require(r['status'] == 'error' or (q['operation'] == 'status' and r['index']['availability'] == 'not_indexed'),
                'snapshot_identity', 'missing snapshot outside error/status not_indexed')
    else:
        snap = r['snapshot']
        for field in ['workspace_id', 'worktree_id']:
            require(snap[field] == q[field], 'snapshot_identity', field)
        require(snap['snapshot_id'] == q['consistency']['snapshot_id'], 'snapshot_identity', 'silent rebind')
    files = {}
    for f in case['fixture_files']:
        raw = bytes.fromhex(f['source_hex'])
        require(f['byte_length'] == len(raw), 'source_length', f['file_id'])
        require(f['source_hash']['hex'] == blake3(raw).hexdigest(), 'source_hash', f['file_id'])
        files[(f['snapshot_id'], f['file_id'])] = f
        path = f['path']
        if path['encoding'] == 'unix_bytes':
            native = bytes.fromhex(path['units_hex'])
            require(b'\0' not in native and not native.startswith(b'/')
                    and b'..' not in native.split(b'/'), 'native_path', 'nonrelative Unix path')
        else:
            units = [int(path['units_hex'][i:i + 4], 16) for i in range(0, len(path['units_hex']), 4)]
            require(0 not in units and units[0] not in [47, 92], 'native_path', 'nonrelative Windows path')
    def source_check(item):
        require(r['snapshot'] is not None and item['snapshot_id'] == r['snapshot']['snapshot_id'],
                'snapshot_identity', 'mixed snapshot')
        key = (item['snapshot_id'], item['file_id'])
        require(key in files, 'snapshot_identity', 'unknown file version')
        f = files[key]
        raw = bytes.fromhex(f['source_hex'])
        require(item['source_hash'] == f['source_hash'], 'source_hash', 'mixed hash')
        start, end = item['span']['start'], item['span']['end']
        require(0 <= start <= end <= len(raw), 'source_span', 'span outside blob')
        try:
            raw[:start].decode('utf-8')
            raw[start:end].decode('utf-8')
        except UnicodeDecodeError as error:
            raise Violation('source_boundary', str(error)) from error
        if 'content' in item:
            require(item['content'].encode('utf-8') == raw[start:end], 'source_content', 'wrong source')
            require(item['byte_length'] == len(raw), 'source_length', 'wrong blob length')
    for item in r['items']:
        source_check(item)
        require(item['configuration_id'] == r['snapshot']['configuration_id'], 'derivation', 'mixed configuration')
        require(item['producer_id'] in [p['producer_id'] for p in r['support']['producers']],
                'derivation', 'unknown producer')
    for fact in facts:
        require(fact['snapshot_id'] == r['snapshot']['snapshot_id'], 'snapshot_identity', 'mixed fact revision')
        require(fact['configuration_id'] == r['snapshot']['configuration_id'], 'derivation', 'mixed fact config')
        for evidence in fact.get('evidence', [fact] if fact['state'] == 'unknown' else []):
            source_check(evidence)
        if q['operation'] == 'relations' and fact['state'] != 'unknown':
            target = q['params']['symbol_id']
            relevant = fact['origin_id'] == target if q['params']['direction'] == 'out' else (
                fact.get('target_id') == target or target in fact.get('candidate_ids', []))
            require(relevant, 'relation_endpoint', 'relation unrelated to requested endpoint/direction')
    inv = r['coverage']['inventory']
    require(inv['eligible'] == sum(inv[k] for k in ['processed', 'partial', 'failed', 'stale', 'capability_absent']),
            'coverage', 'eligible denominator inconsistent')
    require(inv['discovered'] == inv['eligible'] + inv['excluded'], 'coverage', 'discovered denominator inconsistent')
    for f in r['coverage']['files']:
        if f['state'] == 'processed':
            require(f['tree_valid'] is True, 'coverage', 'processed without valid tree')
            require(f['symbol_count'] is not None, 'coverage', 'processed without observed count')
        else:
            require(f['reason'] is not None, 'coverage', 'missing reason')
        if f['state'] in ['excluded', 'capability_absent']:
            require(f['symbol_count'] is None, 'coverage', 'unobserved extraction reported as zero')
        if (f['snapshot_id'], f['file_id']) in files:
            for span in f['gaps']:
                require(span['start'] <= span['end'] <= files[(f['snapshot_id'], f['file_id'])]['byte_length'],
                        'source_span', 'gap outside source')
    rel = r['coverage']['relations']
    if rel['denominator'] == 'not_available':
        require(all(rel[k] is None for k in ['recognized', 'resolved', 'external', 'candidates', 'unknown']),
                'coverage', 'unavailable relations reported as complete zero')
    else:
        require(rel['recognized'] == rel['resolved'] + rel['external'] + rel['candidates'] + rel['unknown'], 'coverage', 'relation counts')
    required_budget = any(o['required'] and o['reason'] == 'budget' for o in r['omissions'])
    if r['status'] != 'error':
        require((r['status'] == 'insufficient_budget') == required_budget, 'budget_status', 'budget mislabeled')
        require((r['sufficiency']['state'] == 'insufficient_budget') == required_budget, 'budget_status', 'sufficiency mismatch')
    require(r['sufficiency']['included'] <= r['sufficiency']['identified'], 'sufficiency', 'too many included')
    require((r['status'] == 'error') == (r['error'] is not None), 'error_status', 'error/status mismatch')
    if r['support']['status'] == 'unsupported':
        require(r['status'] == 'error' and r['error']['code'] == 'unsupported_capability', 'support', 'silent unsupported')
    if q['consistency']['mode'] == 'strict' and not r['freshness']['validation_complete']:
        require(r['coverage']['query']['completeness'] != 'complete', 'freshness', 'strict false completeness')
    if r['status'] == 'ok' and q['operation'] != 'status':
        require(r['coverage']['query']['completeness'] == 'complete', 'coverage', 'ok with gaps')


def main():
    schema = json.loads((EXAMPLES / 'schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    valid = invalid = failed = 0
    for path in sorted(EXAMPLES.glob('*.json')):
        if path.name == 'schema.json':
            continue
        case = json.loads(path.read_text())
        caught = None
        try:
            check_case(case, validator)
        except Violation as error:
            caught = error
        expected = None if case['valid'] else case['expected_violation']
        if (caught.code if caught else None) != expected:
            failed += 1
            print(f'FAIL {path.name}: expected={expected}; actual={caught.code if caught else None}; {caught or ""}')
        else:
            valid += case['valid']
            invalid += not case['valid']
            print(f'PASS {path.name}: {expected or "valid"}')
    print(f'{valid} valid accepted; {invalid} invalid rejected; {failed} failures; schema valid')
    return int(failed != 0)


if __name__ == '__main__':
    sys.exit(main())
