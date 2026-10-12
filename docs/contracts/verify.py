#!/usr/bin/env python3
"""Documentary checks for M0-01 examples; not a product/domain implementation."""

import json
import argparse
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


def check_admission(case):
    """Measure illustrative application serializations, not a real adapter."""
    q, a = case['request'], case['admission_error']
    d = a['diagnostic']
    require(case['response'] is None and not case['fixture_files'],
            'admission', 'admission must recover no payload')
    require(q['limits']['max_bytes'] < d['minimum_bytes'], 'admission', 'budget meets minimum')
    require((d['minimum_counting'] == 'estimated_admission_bound') ==
            (d['estimation_method'] is not None), 'admission', 'estimate must be labeled')
    require(a['cli_stderr'] == compact_bytes(d).decode('utf-8'),
            'admission', 'stderr differs from bounded diagnostic')
    result = a['mcp_result']
    require(result['content'][0]['text'] == a['cli_stderr'],
            'admission', 'MCP diagnostic differs')
    if 'structuredContent' in result:
        require(result['structuredContent'] == d, 'admission', 'structured diagnostic differs')
    for label, raw in [('cli_stderr', a['cli_stderr'].encode('utf-8')),
                       ('mcp_result', compact_bytes(result))]:
        require(a[label + '_bytes'] == len(raw), 'admission_count', label + ' size differs')
        require(len(raw) <= a['diagnostic_hard_cap_bytes'],
                'admission', label + ' exceeds application cap including metadata')
    wire = a['mcp_wire']
    require(wire['id'] == q['request_id'] and wire['result'] == result,
            'admission', 'wire identity/result differs')
    require(a['mcp_wire_bytes'] == len(compact_bytes(wire)),
            'admission_count', 'JSON-RPC wire including ID must be counted')


def check_selection(case):
    """Check revision policy against a documentary state oracle."""
    q, r, state = case['request'], case['response'], case['fixture_state']
    revision, mode = q['consistency']['revision'], q['consistency']['mode']
    sid = r['snapshot']['snapshot_id'] if r['snapshot'] else None
    error = r['error']['code'] if r['error'] else None
    has_data = any(r[k] for k in ['items', 'assertions', 'candidates', 'unknowns'])
    retained = state['retained_snapshot_ids']
    require(revision['kind'] == 'fixed' or (q['operation'] != 'expand' and 'cursor' not in q['params']),
            'continuation_revision', 'expand/cursor cannot select latest')
    if sid is not None:
        require(sid in retained, 'snapshot_identity', 'returned generation not retained')
    if revision['kind'] == 'fixed':
        fixed = revision['snapshot_id']
        require(sid is None or sid == fixed, 'snapshot_identity', 'silent fixed-ID rebind')
        if fixed not in retained:
            require(error == 'snapshot_expired' and sid is None and not has_data,
                    'revision_policy', 'expired revision must be typed, not rebound')
        elif mode != 'snapshot' and state['required_snapshot_id'] is not None and fixed != state['required_snapshot_id']:
            require(error == 'snapshot_stale' and not has_data,
                    'revision_policy', 'retained but stale fixed ID must be refused')
        else:
            require(error not in ['snapshot_expired', 'snapshot_stale'],
                    'revision_policy', 'false expiration/staleness')
    elif sid is not None:
        expected = state['published_snapshot_id'] if mode == 'snapshot' else state['required_snapshot_id']
        if mode == 'snapshot' or r['freshness']['validation_complete']:
            require(sid == expected, 'revision_policy', 'latest resolved wrong generation')
    if error == 'snapshot_stale':
        require(r['status'] == 'error' and r['next'] and not r['error']['retryable'],
                'revision_policy', 'stale requires a new explicit query')
        require(r['coverage']['query']['completeness'] != 'complete',
                'revision_policy', 'stale must not claim completeness')
    bindings = {b['id']: b for b in state['bindings']}
    params = q['params']
    ids = params.get('anchors', []) + [params[k] for k in ['symbol_id', 'context_id', 'cursor'] if k in params]
    for anchor in ids:
        require(anchor in bindings, 'anchor_revision', 'anchor lacks revision oracle')
        binding = bindings[anchor]
        continuation = binding['kind'] in ['context', 'cursor']
        if continuation:
            require(revision['kind'] == 'fixed' and revision['snapshot_id'] == binding['snapshot_id'],
                    'continuation_revision', 'expand/cursor must fix original manifest revision')
        if sid is not None and binding['snapshot_id'] != sid:
            require(error == 'anchor_revision_mismatch' and not has_data,
                    'anchor_revision', 'incompatible anchor must not migrate')
    if mode == 'snapshot':
        require(r['freshness']['validated_at'] is None and not r['freshness']['validation_complete'],
                'freshness', 'snapshot mode cannot claim filesystem validation')
    elif r['freshness']['validation_complete']:
        require(state['required_snapshot_id'] is not None and sid == state['required_snapshot_id']
                and r['freshness']['validated_at'] is not None
                and r['freshness']['validated_scope'] == q['consistency']['scope'],
                'freshness', 'validation must reconcile the requested scope')
        if q['consistency']['scope']['kind'] == 'workspace':
            expected_files = {f['file_id']: f['source_hash'] for f in state['inventory_at_required']}
            observed_files = {f['file_id'] for f in r['coverage']['files']}
            require(observed_files == set(expected_files),
                    'freshness', 'global reconciliation must include new/removed files')
            for f in case['fixture_files']:
                require(f['snapshot_id'] == sid and expected_files.get(f['file_id']) == f['source_hash'],
                        'freshness', 'reconciled inventory hash differs')
    elif r['status'] != 'error':
        require(r['coverage']['query']['completeness'] != 'complete' and r['freshness']['gaps'],
                'freshness', 'unfinished validation needs gaps and incomplete coverage')


def check_case(case, validator):
    errors = list(validator.iter_errors(case))
    require(not errors, 'schema', str(errors[0]) if errors else '')
    q, r, admission = case['request'], case['response'], case['admission_error']
    require((q['limits']['max_tokens'] is None) == (q['limits']['tokenizer'] is None),
            'tokenizer', 'tokenizer and max_tokens must be supplied together')
    if admission:
        check_admission(case)
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
    check_selection(case)
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
        require(r['snapshot'] is not None and f['snapshot_id'] == r['snapshot']['snapshot_id'],
                'snapshot_identity', 'mixed coverage revision')
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--examples', type=Path, default=EXAMPLES,
                        help='directory with v2 schema and documentary cases')
    examples = parser.parse_args(argv).examples
    schema = json.loads((examples / 'schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    valid = invalid = failed = 0
    for path in sorted(examples.glob('*.json')):
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
