#!/usr/bin/env python3
"""Bounded, read-only counterchecks against preserved CI2 data, never upstream."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'reconcile_corpus.py'
spec = importlib.util.spec_from_file_location('corpus_reconcile_data_only', SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
EXPORT = HERE.parents[1] / 'ci-second'
COMMIT = 'd54520b2d5f7d8fcac1e770ad06d26d1d5333a0d'
RUN = 38280118706


def original(path):
    return json.loads((EXPORT/path).read_bytes())


def encoded(row):
    return json.dumps(row).encode()


class Counterchecks(unittest.TestCase):
    def reject(self, action, fragment):
        with self.assertRaisesRegex(ValueError, fragment):
            action()

    def test_preserved_rust_ci2_passes(self):
        report = check.reconcile(EXPORT, COMMIT, RUN, 'rust')
        self.assertTrue(report['verified'])
        self.assertFalse(report['admitted'])
        self.assertEqual(report['families']['rust']['reference_family_regressions'], 16)

    def test_preserved_full_ci2_rejected(self):
        self.reject(lambda: check.reconcile(EXPORT, COMMIT, RUN), 'js CI job')

    def test_old_js_oracle_rejected_independently_of_job(self):
        self.reject(lambda: check.js(check.Reader(EXPORT)), 'executor/oracle differs')

    def test_metadata_tampering(self):
        mutations = [
            ('run.json', lambda r: r.update(headSha='a'*40), 'commit mismatch'),
            ('run.json', lambda r: r.update(databaseId=RUN+1), 'identity/status'),
            ('run.json', lambda r: r.update(url='https://example.invalid/run'), 'identity/status'),
            ('artifacts.json', lambda r: next(a for a in r['artifacts'] if a['name'] == 'l5-real-rust')['workflow_run'].update(head_sha='b'*40), 'provenance mismatch'),
            ('artifacts.json', lambda r: next(a for a in r['artifacts'] if a['name'] == 'l5-real-rust').update(digest='sha256:bad'), 'provenance mismatch'),
        ]
        for path, mutate, error in mutations:
            with self.subTest(path=path, error=error):
                row = original(path); mutate(row)
                self.reject(lambda: check.reconcile(EXPORT, COMMIT, RUN, 'rust', {path:encoded(row)}), error)

    def test_rust_pins_and_namespace_tampering(self):
        mutations = [
            (lambda r: r.update(runner_sha256='0'*64), 'producer source'),
            (lambda r: r['results']['baseline'].update(source_archive_sha256='0'*64), 'materialization/oracle'),
            (lambda r: r['results']['reference'].update(hidden_test_sha256='0'*64), 'materialization/oracle'),
            (lambda r: r['results']['reference'].update(lock_sha256_after='0'*64), 'Rust lock'),
            (lambda r: r['results']['baseline'].update(namespace_domain_id='00000000-0000-4000-8000-000000000000'), 'contradicts command'),
        ]
        for mutate, error in mutations:
            with self.subTest(error=error):
                row = original('rust/summary.json'); mutate(row)
                self.reject(lambda: check.rust(check.Reader(EXPORT, {'rust/summary.json':encoded(row)})), error)

    def test_containment_and_stream_tampering(self):
        mutations = [
            (lambda r: r.update(exit_code=0), 'behavioral exit'),
            (lambda r: r.update(elapsed_seconds=601), 'deadline'),
            (lambda r: r.update(status='timeout'), 'infrastructure'),
            (lambda r: r.update(cleanup_status='unconfirmed'), 'containment/cleanup'),
            (lambda r: r.update(eligible_for_agent_run=False), 'ineligible'),
            (lambda r: r.update(domain_id='not-a-domain'), 'badly formed'),
            (lambda r: r['termination_evidence'].update(init_pid=1), 'namespace/init'),
            (lambda r: r['termination_evidence'].update(pidfd_exit_observed=False), 'teardown'),
            (lambda r: r['termination_evidence']['user_namespace_mapping'].update(count=2), 'mapping'),
            (lambda r: r['stdout'].update(truncated=True), 'truncated'),
            (lambda r: r['stdout'].update(observed_bytes=1), 'truncated'),
            (lambda r: r['stdout'].update(sha256='0'*64), 'digest mismatch'),
        ]
        for mutate, error in mutations:
            with self.subTest(error=error):
                row = original('rust/baseline/probe.json'); mutate(row)
                self.reject(lambda: check.contained(row, 101, check.Reader(EXPORT), 'rust/baseline/probe'), error)

    def test_exported_log_tampering(self):
        row = original('rust/baseline/probe.json')
        self.reject(lambda: check.contained(row, 101, check.Reader(EXPORT, {'rust/baseline/probe.stdout.log':b'changed'}), 'rust/baseline/probe'), 'differs from captured')

    def test_coherent_wrong_rust_regression_count(self):
        path = 'rust/reference/regressions'
        row = original(path+'.json')
        raw = base64.b64decode(row['stdout']['base64'])
        raw = raw.replace(b'16 passed;', b'15 passed;')
        row['stdout'].update(base64=base64.b64encode(raw).decode(), captured_bytes=len(raw), observed_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        overrides = {path+'.json':encoded(row),path+'.stdout.log':raw}
        self.reject(lambda: check.rust(check.Reader(EXPORT, overrides)), 'regression count/result')

    def test_command_drift(self):
        path = 'rust/reference/probe.json'; row = original(path)
        row['command'][row['command'].index('regression_23336')] = 'irrelevant'
        self.reject(lambda: check.rust(check.Reader(EXPORT, {path:encoded(row)})), 'filter/command drift')

    def test_preparation_tampering(self):
        path = 'rust/baseline/prepare'; row = original(path+'.json')
        row['streams']['stderr']['observed_sha256'] = '0'*64
        self.reject(lambda: check.preparation(check.Reader(EXPORT, {path+'.json':encoded(row)}), path), 'preparation stream digest')

    def test_jest_baseline_and_reference_failure(self):
        oracle = check.source('eval/qualification/l5-real/js/oracles/XraiExternalStoreContract-test.js').decode()
        names = check.re.findall(r"test\('([^']+)'", oracle)
        base = original('js/base/requirement-jest.json')
        self.assertEqual(check.jest_counts(base, names, 'requirement', 'base')['failed'], 3)
        self.reject(lambda: check.jest_counts(original('js/reference/requirement-jest.json'), names, 'requirement', 'reference'), 'behavioral counts')
        corrupt = copy.deepcopy(base); corrupt['wasInterrupted'] = True
        self.reject(lambda: check.jest_counts(corrupt, names, 'requirement', 'base'), 'infrastructure')
        corrupt = copy.deepcopy(base); corrupt['testResults'][0]['assertionResults'][0]['failureMessages'] = ['Different failure']
        self.reject(lambda: check.jest_counts(corrupt, names, 'requirement', 'base'), 'expected missing native hook')

    def test_unsafe_path(self):
        self.reject(lambda: check.Reader(EXPORT).raw('../run.json'), 'unsafe relative')

    def test_imports_are_data_only(self):
        import ast
        parsed = ast.parse(SCRIPT.read_text())
        imported = [name.name.split('.')[0] for node in ast.walk(parsed) if isinstance(node, ast.Import) for name in node.names]
        self.assertFalse({'subprocess','importlib','os','pickle','marshal'} & set(imported))
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'eval','exec','compile','__import__'} for node in ast.walk(parsed)))


if __name__ == '__main__':
    unittest.main()
