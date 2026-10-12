"""Regression witnesses for documentary validation, not product API tests."""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

CONTRACTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('contract_verify', CONTRACTS / 'verify.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class DocumentaryVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((verify.EXAMPLES / 'schema.json').read_text())
        cls.validator = verify.Draft202012Validator(cls.schema, format_checker=verify.FormatChecker())

    def case(self, name):
        return json.loads((verify.EXAMPLES / (name + '.json')).read_text())

    def main_for(self, case):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'schema.json').write_text(json.dumps(self.schema), encoding='utf-8')
            (root / 'case.json').write_text(json.dumps(case), encoding='utf-8')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = verify.main(['--examples', folder])
            return code, output.getvalue()

    def test_documentary_suite_has_no_failure(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(verify.main([]), 0)

    def test_fixed_rebind_is_rejected_as_snapshot_identity(self):
        with self.assertRaises(verify.Violation) as caught:
            verify.check_case(self.case('invalid-fixed-response-rebind'), self.validator)
        self.assertEqual(caught.exception.code, 'snapshot_identity')

    def test_invalid_fixture_falsely_labeled_valid_makes_main_nonzero(self):
        case = self.case('invalid-fixed-response-rebind')
        case.update(valid=True, expected_violation=None)
        code, output = self.main_for(case)
        self.assertEqual(code, 1)
        self.assertIn('actual=snapshot_identity', output)

    def test_false_acceptance_of_declared_adverse_case_makes_main_nonzero(self):
        with mock.patch.object(verify, 'check_case', return_value=None):
            code, output = self.main_for(self.case('invalid-fixed-response-rebind'))
        self.assertEqual(code, 1)
        self.assertIn('expected=snapshot_identity; actual=None', output)

    def test_unexpected_rejection_of_positive_case_makes_main_nonzero(self):
        with mock.patch.object(verify, 'check_case', side_effect=verify.Violation('unexpected', 'injected rejection')):
            code, output = self.main_for(self.case('17-latest-published-snapshot'))
        self.assertEqual(code, 1)
        self.assertIn('actual=unexpected', output)

    def test_unexpected_exception_is_not_hidden_as_success(self):
        with mock.patch.object(verify, 'check_case', side_effect=RuntimeError('injected failure')):
            with self.assertRaisesRegex(RuntimeError, 'injected failure'):
                self.main_for(self.case('17-latest-published-snapshot'))

    def test_relabelled_adverse_case_is_nonzero_in_real_process(self):
        case = self.case('invalid-admission-metadata-over-cap')
        case.update(valid=True, expected_violation=None)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'schema.json').write_text(json.dumps(self.schema), encoding='utf-8')
            (root / 'case.json').write_text(json.dumps(case), encoding='utf-8')
            result = subprocess.run([sys.executable, str(CONTRACTS / 'verify.py'), '--examples', folder],
                                    capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('actual=admission', result.stdout)

    def test_global_validation_cannot_ignore_a_new_file(self):
        case = self.case('invalid-global-validation-skips-new-file')
        with self.assertRaises(verify.Violation) as caught:
            verify.check_case(case, self.validator)
        self.assertEqual(caught.exception.code, 'freshness')

    def test_large_jsonrpc_id_is_counted_outside_application_cap(self):
        case = self.case('25-admission-long-input-wire')
        verify.check_case(case, self.validator)
        admission = case['admission_error']
        self.assertGreater(admission['mcp_wire_bytes'], 4096)
        self.assertLessEqual(admission['mcp_result_bytes'], 4096)
        self.assertLessEqual(admission['cli_stderr_bytes'], 4096)
        self.assertNotIn('private_input_', admission['cli_stderr'])
        self.assertNotIn('client_', admission['cli_stderr'])

    def test_legacy_v1_requires_explicit_migration(self):
        case = json.loads((verify.EXAMPLES / 'legacy-v1' / '01-empty-file.json').read_text())
        with self.assertRaises(verify.Violation) as caught:
            verify.check_case(case, self.validator)
        self.assertEqual(caught.exception.code, 'schema')


if __name__ == '__main__':
    unittest.main()
