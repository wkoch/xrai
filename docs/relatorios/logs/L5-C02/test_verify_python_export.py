"""Counterproofs mutate only exported JSON/data, never import captured upstream."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('verify_python_export',Path(__file__).with_name('verify_python_export.py'))
verifier=importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
RETAINED=verifier.ROOT/'docs/relatorios/logs/L5-C02/ci-next-first/python'
SOURCE=RETAINED if RETAINED.exists() else Path('/private/tmp/xrai-c02-ci-first/python')


class ExportCounterproofs(unittest.TestCase):
    def mutate(self,filename,edit):
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp)/'python'
            shutil.copytree(SOURCE,destination)
            path=destination/filename
            record=json.loads(path.read_text())
            edit(record)
            path.write_text(json.dumps(record,indent=2)+'\n')
            with self.assertRaises(ValueError):
                verifier.verify(destination)

    def test_current_export_accepts_deterministically(self):
        a=verifier.verify(SOURCE);b=verifier.verify(SOURCE)
        self.assertEqual(a,b)
        self.assertEqual(a['fresh_confirmed_domains'],4)
        self.assertEqual([(p['passed'],p['expected_contract_errors']) for p in a['phases']],[(0,3),(2,0),(3,0),(2,0)])

    def test_source_inventory_omission_rejected(self):
        self.mutate('base/receipt.json',lambda x:x['source_and_setup_before_sha256'].pop('sklearn/base.py'))

    def test_post_probe_mutation_rejected(self):
        self.mutate('reference/receipt.json',lambda x:x['source_and_setup_after_sha256'].update({'sklearn/pipeline.py':'0'*64}))

    def test_oracle_materialization_pin_rejected(self):
        self.mutate('base/receipt.json',lambda x:x['materialization'].update({'oracle_sha256':'0'*64}))

    def test_unsupported_origin_rejected(self):
        self.mutate('reference/requirement-tests.json',lambda x:x['module_origins']['sklearn.pipeline'].update({'path':'/workspace/.xrai-deps/sklearn/pipeline.py'}))

    def test_duplicate_test_id_rejected(self):
        self.mutate('base/requirement-tests.json',lambda x:x['tests'][0].update({'id':x['tests'][1]['id']}))

    def test_fake_unrelated_failure_rejected(self):
        self.mutate('base/requirement-tests.json',lambda x:x['tests'][0].update({'error':'ImportError extension missing'}))

    def test_faked_verified_summary_rejected(self):
        self.mutate('reference/receipt.json',lambda x:x['phases'][0].update({'report_sha256':'0'*64}))

    def test_stream_truncation_rejected(self):
        self.mutate('base/requirement-harness.json',lambda x:x['stderr'].update({'truncated':True}))

    def test_stream_digest_rejected(self):
        self.mutate('base/requirement-harness.json',lambda x:x['stderr'].update({'sha256':'0'*64}))

    def test_timeout_rejected(self):
        self.mutate('reference/requirement-harness.json',lambda x:x.update({'execution_status':'timeout'}))

    def test_unconfirmed_namespace_teardown_rejected(self):
        self.mutate('base/regression-harness.json',lambda x:x['termination_evidence'].update({'pidfd_exit_observed':False}))

    def test_reused_domain_rejected(self):
        domain=json.loads((SOURCE/'base/requirement-harness.json').read_text())['domain_id']
        self.mutate('base/regression-harness.json',lambda x:x.update({'domain_id':domain}))

    def test_changed_command_network_setup_rejected(self):
        self.mutate('reference/requirement-harness.json',lambda x:x['command'].append('pip install floating'))

    def test_wheel_pin_rejected(self):
        self.mutate('reference/bootstrap.json',lambda x:x['dependency_wheels'][0].update({'sha256':'0'*64}))

    def test_wheel_python_overlay_rejected(self):
        self.mutate('base/bootstrap.json',lambda x:x['compiled_extensions_sha256'].update({'sklearn/pipeline.py':'0'*64}))

    def test_runtime_digest_inconsistent_rejected(self):
        self.mutate('base/bootstrap.json',lambda x:x['runtime_files_sha256'].update({'bin/python3':'0'*64}))

    def test_native_bytes_manifest_different_across_sides_rejected(self):
        def edit(x):
            name=next(iter(x['compiled_extensions_sha256']))
            x['compiled_extensions_sha256'][name]='0'*64
        self.mutate('reference/bootstrap.json',edit)

    def test_duplicate_json_key_extra_export_and_symlink_rejected(self):
        for kind in ['duplicate_json','extra_file','symlink']:
            with tempfile.TemporaryDirectory() as tmp:
                destination=Path(tmp)/'python';shutil.copytree(SOURCE,destination)
                if kind=='duplicate_json':(destination/'pair.json').write_text('{"admitted":false,"admitted":false}')
                if kind=='extra_file':(destination/'unbound.json').write_text('{}')
                if kind=='symlink':(destination/'unbound.json').symlink_to('pair.json')
                with self.assertRaises(ValueError):verifier.verify(destination)


if __name__=='__main__':unittest.main()
