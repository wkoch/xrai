#!/usr/bin/env python3
"""Independent documentary checks for experimental P3 v3; no public capability."""

import json
import argparse
import sys
import re
from functools import lru_cache
from pathlib import Path

from blake3 import blake3
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / 'examples'


class Violation(Exception):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


def require(condition, code, detail):
    if not condition:
        raise Violation(code, detail)


def compact_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


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
    q, r, state = case['request'], case['response'], case['fixture_state']
    comparison, params = r['comparison'], q['params']
    revision = q['consistency']['revision']
    error = r['error']['code'] if r['error'] else None
    has_data = any(r[k] for k in ['items', 'assertions', 'candidates', 'unknowns'])
    require(q['operation'] in ['context', 'expand'], 'comparison_operation', 'P3 profile only')
    require(('base' in params) == ('head' in params), 'comparison', 'incomplete pair')
    manifest = case['fixture_manifest']
    expected = ([params['base'], params['head']] if 'base' in params else
                [s['snapshot_id'] for s in manifest['snapshots']] if q['operation'] == 'expand' and manifest else
                [revision['snapshot_id']] if revision['kind'] == 'fixed' else
                [state['published_snapshot_id']] if state['published_snapshot_id'] is not None else [])
    comparison_requested = len(expected) == 2
    if comparison_requested:
        require(revision['kind'] == 'fixed' and revision['snapshot_id'] == expected[-1],
                'comparison', 'comparison must fix head')
        require(q['consistency']['mode'] == 'snapshot' or error == 'unsupported_capability',
                'comparison_mode', 'pair validation unsupported')
    missing = [s for s in expected if s not in state['retained_snapshot_ids']]
    expired = q['operation'] == 'expand' and (not manifest or manifest['retention']['expired'] or missing or
              any(s not in manifest['retention']['retained_snapshot_ids'] for s in expected))
    if expired or missing:
        require(error == ('context_expired' if q['operation'] == 'expand' else 'snapshot_expired')
                and r['snapshot'] is None and comparison is None and not has_data,
                'retention', 'unretained pair must fail without fallback')
        return
    if r['snapshot']:
        actual = [comparison[k]['snapshot_id'] for k in ['base', 'head']] if comparison else [r['snapshot']['snapshot_id']]
        require(actual == expected, 'comparison', 'undeclared or reordered revision')
        require(len(set(actual)) == len(actual), 'comparison', 'identical comparison snapshots')
        if comparison:
            require(r['snapshot'] == comparison['head'], 'comparison_head', 'principal must equal complete head')
            require(all(s[k] == q[k] for s in comparison.values() for k in ['workspace_id', 'worktree_id']),
                    'snapshot_identity', 'cross-checkout pair')
        require(all(s in state['retained_snapshot_ids'] for s in actual), 'retention', 'snapshot not retained')
    require(q['consistency']['mode'] == 'snapshot' or error == 'unsupported_capability',
            'comparison_mode', 'initial P3 mode unsupported')
    require(r['freshness']['validated_at'] is None and not r['freshness']['validation_complete'],
            'freshness', 'snapshot must not claim validation')
    bindings = {b['id']: b for b in state['bindings']}
    for anchor in params.get('anchors', []):
        require(anchor in bindings, 'anchor_revision', 'unknown anchor binding')
        if bindings[anchor]['snapshot_id'] not in expected:
            require(error == 'anchor_revision_mismatch' and not has_data,
                    'anchor_revision', 'third revision anchor')
    if q['operation'] == 'expand' and error != 'context_expired':
        require(manifest and params['context_id'] == manifest['context_id'], 'manifest', 'foreign context')
        require(revision['kind'] == 'fixed' and revision['snapshot_id'] == expected[-1],
                'manifest', 'expansion must fix original head')
        requested = params['item_ids']
        known = {x['id'] for x in manifest['items']}
        invalid = len(set(requested)) != len(requested) or not set(requested) <= known
        require(not invalid or error == 'invalid_request' and not has_data,
                'manifest', 'unknown or duplicate object')


def snapshots(response):
    return ({response['comparison'][k]['snapshot_id']: response['comparison'][k] for k in ['base', 'head']} if response['comparison'] else
            {response['snapshot']['snapshot_id']: response['snapshot']} if response['snapshot'] else {})


def check_diff(case):
    """Verify unified hunks against both captured UTF-8 blobs, without Git."""
    q, r = case['request'], case['response']
    diff = q['params'].get('diff')
    if not diff or r['status'] == 'error':
        return
    require(r['comparison'] is not None, 'diff', 'diff needs explicit pair')
    for f in case['fixture_files']:
        require(f['path']['encoding'] == 'unix_bytes' and bytes.fromhex(f['path']['units_hex']).decode('utf-8') == f['path']['display'],
                'diff', 'display cannot rebind native path')
    require(len({(f['snapshot_id'], f['path']['display']) for f in case['fixture_files']}) == len(case['fixture_files']),
            'diff', 'ambiguous native path')
    files = {(f['snapshot_id'], f['path']['display']): bytes.fromhex(f['source_hex']).decode('utf-8').splitlines(keepends=True)
             for f in case['fixture_files']}
    lines = diff.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        require(lines[i].startswith('--- '), 'diff', 'missing old path')
        old = lines[i][4:].rstrip('\r\n'); i += 1
        require(i < len(lines) and lines[i].startswith('+++ '), 'diff', 'missing new path')
        new = lines[i][4:].rstrip('\r\n'); i += 1
        old = old[2:] if old.startswith('a/') else old
        new = new[2:] if new.startswith('b/') else new
        base, head = (r['comparison'][k]['snapshot_id'] for k in ['base', 'head'])
        require((base, old) in files and (head, new) in files, 'diff', 'path outside pair')
        hunks = 0; previous = (0, 0)
        while i < len(lines) and not lines[i].startswith('--- '):
            match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\r\n]*\r?\n?', lines[i])
            require(match is not None, 'diff', 'invalid hunk header')
            bs, bn, hs, hn = match.groups(); bs, hs = int(bs), int(hs)
            bn, hn = int(bn) if bn is not None else 1, int(hn) if hn is not None else 1
            require((bn == 0 or bs > 0) and (hn == 0 or hs > 0), 'diff', 'invalid line origin')
            bi, hi = bs - 1 if bn else bs, hs - 1 if hn else hs
            require(bi >= previous[0] and hi >= previous[1], 'diff', 'overlapping hunks')
            i += 1; removed, added = [], []
            while i < len(lines) and not lines[i].startswith(('@@ ', '--- ')):
                line = lines[i]; i += 1
                require(line[:1] in [' ', '-', '+'], 'diff', 'unsupported/no-newline marker')
                if line[0] in ' -': removed.append(line[1:])
                if line[0] in ' +': added.append(line[1:])
            require(len(removed) == bn and len(added) == hn, 'diff', 'hunk ranges disagree')
            require(files[(base, old)][bi:bi + bn] == removed and files[(head, new)][hi:hi + hn] == added,
                    'diff', 'hunk bytes disagree')
            previous = (bi + bn, hi + hn); hunks += 1
        require(hunks > 0, 'diff', 'no hunks')


def check_manifest(case):
    q, r, m = case['request'], case['response'], case['fixture_manifest']
    if r['status'] == 'error':
        return
    require(m is not None and r.get('context_id') == m['context_id'], 'manifest', 'missing context binding')
    selected = snapshots(r)
    require(m['snapshots'] == [r['comparison'][k] for k in ['base', 'head']] if r['comparison'] else m['snapshots'] == [r['snapshot']],
            'manifest', 'manifest descriptors changed')
    original = m['request']
    original_ids = ([original['params']['base'], original['params']['head']] if 'base' in original['params'] else
                    [original['consistency']['revision']['snapshot_id']] if original['consistency']['revision']['kind'] == 'fixed' else
                    [m['snapshots'][-1]['snapshot_id']])
    require(original_ids == list(selected), 'manifest', 'manifest original pair rebind')
    require(not m['retention']['expired'] and set(selected) <= set(m['retention']['retained_snapshot_ids']),
            'retention', 'manifest resources unavailable')
    require(m['request']['operation'] == 'context', 'manifest', 'manifest original request')
    if q['operation'] == 'context':
        require(m['request'] == q, 'manifest', 'manifest request changed')
    items = {x['id']: x for x in m['items']}
    require(len(items) == len(m['items']), 'manifest', 'duplicate manifest object')
    files = {(f['snapshot_id'], f['file_id']): f for f in case['fixture_files']}
    for x in items.values():
        key = (x['snapshot_id'], x['file_id'])
        require(x['snapshot_id'] in selected and key in files and x['source_hash'] == files[key]['source_hash'],
                'manifest', 'manifest foreign source')
        require(0 <= x['span']['start'] <= x['span']['end'] <= files[key]['byte_length'], 'manifest', 'manifest span')
    for x in r['items']:
        require(x['id'] in items and all(x[k] == items[x['id']][k] for k in ['snapshot_id', 'file_id', 'source_hash']),
                'manifest', 'response object rebind')
        require(items[x['id']]['span']['start'] <= x['span']['start'] <= x['span']['end'] <= items[x['id']]['span']['end'],
                'manifest', 'representation beyond object')
        if q['operation'] == 'expand':
            require(x['id'] in q['params']['item_ids'], 'manifest', 'expansion added unrequested object')
    obligations = m['obligations']
    require(len({o['id'] for o in obligations}) == len(obligations), 'sufficiency', 'duplicate obligation')
    require(all(o['snapshot_id'] in selected and set(o['item_ids']) <= set(items) for o in obligations),
            'sufficiency', 'foreign obligation')
    receipts = {o['id']: o for o in r['obligation_receipts']}
    require(len(receipts) == len(r['obligation_receipts']) and set(receipts) == {o['id'] for o in obligations},
            'sufficiency', 'receipt obligation identities differ')
    if q['operation'] == 'context':
        require(all(all(receipts[o['id']][k] == o[k] for k in ['state', 'reason', 'item_ids']) for o in obligations),
                'manifest', 'initial state differs from immutable manifest')
    for o in obligations:
        receipt = receipts[o['id']]
        require(set(receipt['item_ids']) <= set(o['item_ids']), 'sufficiency', 'receipt rebind obligation')
        if receipt['state'] == 'satisfied':
            require(receipt['item_ids'], 'sufficiency', 'unsatisfied source obligation')
            objects = [items[i] for i in receipt['item_ids']]
            witnesses = [x for x in r['items'] if any(all(x[k] == obj[k] for k in ['snapshot_id', 'file_id', 'source_hash'])
                         for obj in objects)]
            minimum = o['minimum_span']
            if o['minimum_view'] != 'pointer':
                require(minimum is not None and any(x['content'] and
                        x['span']['start'] <= minimum['start'] <= minimum['end'] <= x['span']['end'] and
                        (o['minimum_view'] == 'signature' or x['view'] != 'signature') for x in witnesses),
                        'sufficiency', 'representation below required content')
            else:
                require(witnesses, 'sufficiency', 'pointer identity unavailable')
    require(r['sufficiency']['identified'] == len(obligations) and r['sufficiency']['included'] ==
            sum(o['state'] == 'satisfied' for o in receipts.values()), 'sufficiency', 'obligation counts')
    omitted = {x['id']: x for x in r['omissions']}
    for o in obligations:
        if receipts[o['id']]['state'] == 'omitted_budget':
            require(o['id'] in omitted and omitted[o['id']]['required'] == o['required'] and omitted[o['id']]['reason'] == 'budget',
                    'budget_status', 'budget obligation omitted silently')
    if r['sufficiency']['state'] == 'satisfied':
        require(all(o['state'] == 'satisfied' for o in receipts.values()), 'sufficiency', 'false obligation satisfaction')
    unavailable = any(o['state'] in ['unavailable', 'not_assessed'] for o in receipts.values())
    if unavailable and r['status'] != 'insufficient_budget':
        require(r['status'] == 'partial', 'sufficiency', 'unavailable obligation called complete')


def check_partitions(case):
    r = case['response']; allowed = snapshots(r)
    parts = r['coverage']['by_snapshot']
    require({p['snapshot_id'] for p in parts} == set(allowed) and len(parts) == len(allowed),
            'coverage_partition', 'missing or duplicate side')
    for p in parts:
        inv = p['inventory']
        require(inv['eligible'] == sum(inv[k] for k in ['processed', 'partial', 'failed', 'stale', 'capability_absent'])
                and inv['discovered'] == inv['eligible'] + inv['excluded'], 'coverage_partition', 'side counts')
        side_files = [f for f in r['coverage']['files'] if f['snapshot_id'] == p['snapshot_id']]
        require(len({f['file_id'] for f in side_files}) == len(side_files), 'coverage_partition', 'duplicate file version')
        require(all(inv[k] == sum(f['state'] == k for f in side_files) for k in
                    ['processed', 'partial', 'excluded', 'failed', 'stale', 'capability_absent']),
                'coverage_partition', 'inventory differs from file versions')
        rel = p['relations']
        if rel['denominator'] == 'not_available':
            require(all(rel[k] is None for k in ['recognized', 'resolved', 'external', 'candidates', 'unknown']),
                    'coverage_partition', 'side fictitious counts')
        else:
            require(rel['recognized'] == sum(rel[k] for k in ['resolved', 'external', 'candidates', 'unknown']),
                    'coverage_partition', 'side relations counts')
        if p['query']['completeness'] != 'complete':
            require(r['coverage']['query']['completeness'] != 'complete', 'coverage_partition', 'hidden side gap')
    for k in ['discovered', 'eligible', 'processed', 'partial', 'excluded', 'failed', 'stale', 'capability_absent']:
        require(r['coverage']['inventory'][k] == sum(p['inventory'][k] for p in parts),
                'coverage_partition', 'historical denominator collapsed')



@lru_cache(maxsize=1)
def measurement_profile():
    """Lazy: byte-only documentary CI does not require the fixed Python runtime."""
    harness = ROOT.parents[2] / 'crates' / 'xrai-eval' / 'harness'
    sys.path.insert(0, str(harness))
    from offline_measurement import tokenizer
    return tokenizer()


def check_token_budget(case):
    q, r = case['request'], case['response']
    budget = r['budget']
    require(budget['requested_tokens'] == q['limits']['max_tokens'] and
            budget['tokenizer'] == q['limits']['tokenizer'], 'tokenizer', 'requested token profile changed')
    if q['limits']['max_tokens'] is None:
        require(budget['counting'] == 'not_requested' and budget['used_tokens'] is None,
                'tokenizer', 'invented token usage')
        return
    require(budget['counting'] == 'exact', 'tokenizer', 'P3 final envelope requires exact count')
    try:
        encoding, profile = measurement_profile()
        token_count = len(encoding.encode(compact_bytes(r).decode('utf-8'), disallowed_special=()))
    except Exception as error:
        raise Violation('tokenizer', 'pinned L4 tokenizer unavailable: ' + str(error)) from error
    require(budget['tokenizer'] == 'l4:' + profile['fingerprint_sha256'], 'tokenizer', 'profile fingerprint mismatch')
    require(budget['used_tokens'] == token_count, 'budget_count', 'full envelope tokens differ')
    require(token_count <= q['limits']['max_tokens'], 'budget_limit', 'payload token ceiling exceeded')


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
    check_token_budget(case)
    check_selection(case)
    available_producers = {p['producer_id']: p['fingerprint'] for p in r['support']['producers']}
    require(len(available_producers) == len(r['support']['producers']), 'derivation', 'duplicate producer')
    require(all(s['producer_fingerprint'] in available_producers.values() for s in snapshots(r).values()),
            'derivation', 'side producer missing')
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
        require((f['snapshot_id'], f['file_id']) not in files, 'source_hash', 'duplicate file version')
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
        require(r['snapshot'] is not None and item['snapshot_id'] in snapshots(r),
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
        require(item['configuration_id'] == snapshots(r)[item['snapshot_id']]['configuration_id'], 'derivation', 'mixed configuration')
        require(available_producers.get(item['producer_id']) == snapshots(r)[item['snapshot_id']]['producer_fingerprint'],
                'derivation', 'unknown producer')
    for fact in facts:
        require(fact['snapshot_id'] in snapshots(r), 'snapshot_identity', 'mixed fact revision')
        require(fact['configuration_id'] == snapshots(r)[fact['snapshot_id']]['configuration_id'], 'derivation', 'mixed fact config')
        require(available_producers.get(fact['producer_id']) == snapshots(r)[fact['snapshot_id']]['producer_fingerprint'],
                'derivation', 'fact side producer differs')
        bindings = {b['id']: b['snapshot_id'] for b in case['fixture_state']['bindings']}
        for endpoint in [fact.get('origin_id'), fact.get('target_id')] + fact.get('candidate_ids', []):
            if endpoint is not None:
                require(bindings.get(endpoint) == fact['snapshot_id'], 'relation_revision', 'cross-time semantic endpoint')
        for evidence in fact.get('evidence', [fact] if fact['state'] == 'unknown' else []):
            source_check(evidence)
            require(evidence['snapshot_id'] == fact['snapshot_id'], 'relation_revision', 'cross-time evidence')
        if q['operation'] == 'relations' and fact['state'] != 'unknown':
            target = q['params']['symbol_id']
            relevant = fact['origin_id'] == target if q['params']['direction'] == 'out' else (
                fact.get('target_id') == target or target in fact.get('candidate_ids', []))
            require(relevant, 'relation_endpoint', 'relation unrelated to requested endpoint/direction')
    check_diff(case)
    check_manifest(case)
    check_partitions(case)
    inv = r['coverage']['inventory']
    require(inv['eligible'] == sum(inv[k] for k in ['processed', 'partial', 'failed', 'stale', 'capability_absent']),
            'coverage', 'eligible denominator inconsistent')
    require(inv['discovered'] == inv['eligible'] + inv['excluded'], 'coverage', 'discovered denominator inconsistent')
    for f in r['coverage']['files']:
        require(r['snapshot'] is not None and f['snapshot_id'] in snapshots(r),
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
                        help='directory with v3 documentary cases')
    examples = parser.parse_args(argv).examples
    schema = json.loads((ROOT / 'schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    paths = sorted(examples.glob('*.json'))
    require(bool(paths), 'empty_suite', 'no documentary cases')
    valid = invalid = failed = 0
    for path in paths:
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
