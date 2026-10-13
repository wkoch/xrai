"""Replay fixed data-only diff labels and demonstrate separate typed reconstruction."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'crates/xrai-eval/harness'))
from unified_diff import DiffError, decode_unified, apply_typed


def replay():
    raw = (HERE / 'cases.json').read_bytes()
    frozen = json.loads((HERE / 'freeze.json').read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen['cases_sha256'], 'frozen_cases_changed'
    assert frozen['algorithm_files_present'] is False, 'not_frozen_before_algorithm'
    corpus = json.loads(raw)
    source = corpus['real_capture']
    capture = (ROOT / source['input_path']).read_bytes()
    assert hashlib.sha256(capture).hexdigest() == source['input_sha256'], 'real_capture_changed'
    reports = []
    for case in corpus['cases']:
        base = {p: bytes.fromhex(b) for p, b in case['base'].items()}
        head = {p: bytes.fromhex(b) for p, b in case['head'].items()}
        diff = bytes.fromhex(case['diff_hex'])
        try:
            validated = decode_unified(diff, base, head)
        except DiffError as error:
            assert case['expected'] == 'rejected' and error.code == case['reason'], case['id']
            reports.append({'case_id': case['id'], 'status': 'rejected', 'reason': error.code,
                            'diff_sha256': hashlib.sha256(diff).hexdigest()})
            continue
        assert case['expected'] == 'accepted', case['id']
        rebuilt = apply_typed(base, validated.changes)
        assert rebuilt == head, 'typed_consumer_head_mismatch'
        receipt = validated.receipt()
        actual = [{key: c[key] for key in ('path', 'kind', 'base_present', 'head_present')}
                  | {'hunks': [{key: h[key] for key in ('base_span', 'head_span', 'replacement_hex')}
                               for h in c['hunks']]} for c in receipt['changes']]
        assert actual == case['expected_changes'], 'frozen_typed_span_mismatch'
        reports.append({'case_id': case['id'], 'status': 'accepted',
                        'typed_consumer_integral_head_equal': True, 'receipt': receipt})
    positive = sum(r['status'] == 'accepted' for r in reports)
    negative = len(reports) - positive
    assert positive == frozen['positive_cases'] and negative == frozen['negative_cases']
    module = ROOT / 'crates/xrai-eval/harness/unified_diff.py'
    return {'schema': 'unified-diff-proof-v1', 'profile': corpus['schema'],
            'cases_sha256': frozen['cases_sha256'], 'decoder_sha256': hashlib.sha256(module.read_bytes()).hexdigest(),
            'replay_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'positive_cases': positive, 'negative_cases': negative,
            'accepted_typed_consumers': positive, 'native_execution': False,
            'native_p3_support': False, 'new_acquisitions': 0, 'provider_calls': 0,
            'real_capture': source, 'cases': reports}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    proof = replay()
    data = json.dumps(proof, sort_keys=True, ensure_ascii=False, indent=2) + '\n'
    if arguments.output:
        arguments.output.write_text(data)
    else:
        sys.stdout.write(data)
