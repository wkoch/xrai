"""Counterexamples for the documentary verifier, independent of the Rust engine."""
import copy
import importlib.util
import json
import platform
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('p3_documentary_verify', ROOT / 'verify.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
VALIDATOR = verify.Draft202012Validator(json.loads((ROOT / 'schema.json').read_text()), format_checker=verify.FormatChecker())


def fixture(name='01-comparison'):
    return json.loads((ROOT / 'examples' / (name + '.json')).read_text())


def stabilize(case):
    for _ in range(32):
        size = len(verify.compact_bytes(case['response']))
        if size == case['response']['budget']['used_bytes']:
            return
        case['response']['budget']['used_bytes'] = size
    raise RuntimeError('counter did not stabilize')


class DocumentaryP3Tests(unittest.TestCase):
    def assertViolation(self, case, code):
        stabilize(case)
        with self.assertRaises(verify.Violation) as caught:
            verify.check_case(case, VALIDATOR)
        self.assertEqual(caught.exception.code, code)

    def test_all_versioned_examples(self):
        for path in sorted((ROOT / 'examples').glob('*.json')):
            with self.subTest(path=path.name):
                case = json.loads(path.read_text())
                if case['valid']:
                    verify.check_case(case, VALIDATOR)
                else:
                    self.assertViolation(case, case['expected_violation'])

    def test_object_key_order_is_not_revision_order(self):
        case = fixture()
        comparison = case['response']['comparison']
        case['response']['comparison'] = {'head': comparison['head'], 'base': comparison['base']}
        verify.check_case(case, VALIDATOR)

    def test_versions_are_not_coerced(self):
        case = fixture()
        case['fixture_version'] = 2
        self.assertViolation(case, 'schema')

    def test_only_snapshot_pair_mode(self):
        case = fixture()
        case['request']['consistency']['mode'] = 'validated'
        case['response']['freshness']['mode'] = 'validated'
        self.assertViolation(case, 'comparison_mode')

    def test_missing_other_side(self):
        case = fixture()
        del case['request']['params']['head']
        self.assertViolation(case, 'schema')

    def test_both_producers_have_matching_provenance(self):
        case = fixture()
        case['response']['comparison']['base']['producer_fingerprint']['hex'] = '0' * 64
        case['fixture_manifest']['snapshots'][0]['producer_fingerprint']['hex'] = '0' * 64
        self.assertViolation(case, 'derivation')

    def test_member_producer_cannot_use_other_fingerprint(self):
        case = fixture()
        producer = copy.deepcopy(case['response']['support']['producers'][0])
        producer['producer_id'] = 'prod_wrong'
        producer['fingerprint']['hex'] = '0' * 64
        case['response']['support']['producers'].append(producer)
        case['response']['items'][0]['producer_id'] = 'prod_wrong'
        self.assertViolation(case, 'derivation')

    def test_fact_producer_is_checked(self):
        case = fixture('08-base-relation')
        case['response']['assertions'][0]['producer_id'] = 'prod_absent'
        self.assertViolation(case, 'derivation')

    def test_signature_cannot_satisfy_required_body(self):
        case = fixture()
        item = case['response']['items'][0]
        item['view'] = 'signature'
        item['span']['end'] = 17
        item['content'] = item['content'][:17]
        self.assertViolation(case, 'sufficiency')

    def test_duplicate_expansion_object(self):
        case = fixture('02-expand-original')
        case['request']['params']['item_ids'] = ['item_base', 'item_base']
        self.assertViolation(case, 'schema')

    def test_foreign_context(self):
        case = fixture('02-expand-original')
        case['request']['params']['context_id'] = 'ctx_foreign'
        self.assertViolation(case, 'manifest')

    def test_byte_budget_includes_full_comparison_and_receipts(self):
        case = fixture()
        case['request']['limits']['max_bytes'] = 100
        case['response']['budget']['requested_bytes'] = 100
        self.assertViolation(case, 'budget_limit')

    def test_empty_suite_is_not_a_green_run(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(verify.Violation) as caught:
                verify.main(['--examples', directory])
            self.assertEqual(caught.exception.code, 'empty_suite')

    def test_expansion_receipt_does_not_change_original_manifest(self):
        case = fixture('02-expand-original')
        for obligation in case['fixture_manifest']['obligations']:
            obligation['state'] = 'omitted_budget'
        original = verify.compact_bytes(case['fixture_manifest'])
        verify.check_case(case, VALIDATOR)
        self.assertEqual(original, verify.compact_bytes(case['fixture_manifest']))

    @unittest.skipUnless(platform.python_version() == '3.13.13', 'exact-token profile requires fixed L4 Python')
    def test_exact_tokens_include_unicode_crlf_escapes_and_special_text(self):
        case = fixture()
        encoding, profile = verify.measurement_profile()
        case['request']['limits'].update(max_tokens=8192, tokenizer='l4:' + profile['fingerprint_sha256'])
        case['fixture_manifest']['request'] = copy.deepcopy(case['request'])
        budget = case['response']['budget']
        budget.update(requested_tokens=8192, used_tokens=0, counting='exact', tokenizer=case['request']['limits']['tokenizer'])
        case['response']['next'] = [{'operation': 'expand', 'reason': 'ação\r\n"\\ <|endoftext|> ☃'}]
        for _ in range(32):
            stabilize(case)
            count = len(encoding.encode(verify.compact_bytes(case['response']).decode(), disallowed_special=()))
            if count == budget['used_tokens']:
                break
            budget['used_tokens'] = count
        else:
            self.fail('token counter did not stabilize')
        verify.check_case(case, VALIDATOR)
        budget['used_tokens'] += 1
        self.assertViolation(case, 'budget_count')

    def test_diff_path_display_cannot_override_native_identity(self):
        case = fixture()
        case['fixture_files'][0]['path']['units_hex'] = b'src/other.rs'.hex()
        self.assertViolation(case, 'diff')

    def test_partial_cannot_claim_all_obligations_satisfied(self):
        case = fixture()
        case['fixture_manifest']['obligations'][0]['state'] = 'unavailable'
        case['response']['obligation_receipts'][0]['state'] = 'unavailable'
        case['response']['sufficiency']['included'] = 1
        case['response']['status'] = 'partial'
        self.assertViolation(case, 'sufficiency')

    def test_unavailable_is_not_a_budget_omission(self):
        case = fixture()
        case['fixture_manifest']['obligations'][0]['state'] = 'unavailable'
        case['response']['obligation_receipts'][0]['state'] = 'unavailable'
        case['response']['sufficiency']['included'] = 1
        self.assertViolation(case, 'sufficiency')


if __name__ == '__main__':
    unittest.main()
