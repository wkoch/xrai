#!/usr/bin/env python3
"""Own artifact/executor counterchecks; no upstream compilation or tests."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import prepare_l5_go as prepare
import run_l5_go as run

class DataContract(unittest.TestCase):
    def test_frozen_capture_verifies(self):self.assertTrue(prepare.verify()['verified'])
    def test_reference_contains_only_expected_delta(self):
        tree=prepare.source_tree(prepare.CASE/'sources/base.tar.gz')
        original=tree['modules/util/url.go'][0]
        reference=prepare.reference(original)
        self.assertEqual(reference.count(b'url.ParseQuery'),1)
        self.assertTrue(reference.startswith(original[:original.index(b'func SanitizeURL')]))
        self.assertIn(b'case "token", "access_token", "password":',reference)
    def test_case_counter_digest_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            case=Path(d);(case/'sources').mkdir();(case/'oracles').mkdir();(case/'setup').mkdir()
            import shutil
            shutil.copytree(prepare.CASE,case,dirs_exist_ok=True)
            p=case/'agent/input.md';p.write_bytes(p.read_bytes()+b'changed')
            with patch.object(prepare,'CASE',case):
                with self.assertRaisesRegex(ValueError,'frozen artifact mismatch'):prepare.verify()
    def test_reference_counter_delta_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            case=Path(d)
            import shutil
            shutil.copytree(prepare.CASE,case,dirs_exist_ok=True)
            p=case/'oracles/reference-url.go';p.write_bytes(p.read_bytes()+b'changed')
            with patch.object(prepare,'CASE',case):
                with self.assertRaisesRegex(ValueError,'reference delta mismatch'):prepare.verify()
    def test_materialization_fresh_and_evaluator_only(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'base';receipt=run.materialize(path,'base')
            self.assertFalse(receipt['agent_workspace'])
            self.assertEqual((path/run.HIDDEN).read_bytes(),(prepare.CASE/'oracles/xrai_url_contract_test.go').read_bytes())
            with self.assertRaisesRegex(ValueError,'fresh workspace'):run.materialize(path,'base')
    def test_probe_macos_denied_before_upstream_import(self):
        with patch.object(run.platform,'system',return_value='Darwin'):
            with self.assertRaisesRegex(ValueError,'macOS denied'):run.probe(Path('/none'),'base',Path('/none'),Path('/none'),Path('/none'),1)

    def test_timeout_out_of_bounds_denied(self):
        for timeout in [0,-1,901,float('inf'),float('nan')]:
            with self.assertRaisesRegex(ValueError,'timeout'):run.probe(Path('/none'),'base',Path('/none'),Path('/none'),Path('/none'),timeout)
    def test_materialized_production_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'base';run.materialize(path,'base')
            p=path/'modules/util/url.go';p.write_bytes(p.read_bytes()+b'changed')
            with self.assertRaisesRegex(ValueError,'source mismatch'):run.validate_workspace(path,'base')
    def test_materialized_extra_go_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'base';run.materialize(path,'base')
            (path/'xrai_extra.go').write_text('package main')
            with self.assertRaisesRegex(ValueError,'extra or missing'):run.validate_workspace(path,'base')
    def test_materialized_reference_verified(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'reference';run.materialize(path,'reference')
            self.assertEqual(run.validate_workspace(path,'reference')['reference_changed_paths'],['modules/util/url.go'])

class ReceiptClassification(unittest.TestCase):
    def events(self,name,failed=False):
        events=[]
        for test in run.EXPECTED[name]:
            events.extend([{'Action':'output','Test':test,'Output':'XRAI_CONTRACT_SECRET_QUERY\n' if failed else 'ok\n'}, {'Action':'fail' if failed else 'pass','Test':test}])
        return events
    def test_three_baseline_assertions(self):self.assertTrue(run.classify(self.events('requirement',True),'base','requirement'))
    def test_reference_passes(self):self.assertTrue(run.classify(self.events('requirement'),'reference','requirement'))
    def test_regressions_pass_both(self):
        for side in ['base','reference']:self.assertTrue(run.classify(self.events('regression'),side,'regression'))
    def test_compile_fail_no_named_results_rejected(self):self.assertFalse(run.classify([{'Action':'fail','Output':'compile error'}],'base','requirement'))
    def test_panic_without_contract_assertion_rejected(self):
        e=self.events('requirement',True)
        for row in e:
            if row.get('Action')=='output':row['Output']='panic: setup failed\n'
        self.assertFalse(run.classify(e,'base','requirement'))
    def test_missing_name_rejected(self):self.assertFalse(run.classify(self.events('requirement',True)[:-2],'base','requirement'))
    def test_skip_rejected(self):
        e=self.events('regression');e[-1]['Action']='skip';self.assertFalse(run.classify(e,'reference','regression'))
    def test_extra_test_rejected(self):
        e=self.events('regression')+[{'Action':'pass','Test':'TestOther'}];self.assertFalse(run.classify(e,'reference','regression'))
    def test_named_api_infrastructure_failure_rejected(self):
        e=self.events('requirement',True);e[4]['Output']+='XRAI_CONTRACT_INFRASTRUCTURE\n';self.assertFalse(run.classify(e,'base','requirement'))
    def test_private_tool_copy_bytes_no_links(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);source=d/'source';source.mkdir();(source/'tool').write_bytes(b'own fixture')
            receipt=run.copy_tree(source,d/'dest');self.assertEqual(receipt['file_count'],1)
            self.assertNotEqual((source/'tool').stat().st_ino,(d/'dest/tool').stat().st_ino)
    def test_tool_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);source=d/'source';source.mkdir();(source/'tool').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError,'link'):run.copy_tree(source,d/'dest')

if __name__=='__main__':unittest.main()
