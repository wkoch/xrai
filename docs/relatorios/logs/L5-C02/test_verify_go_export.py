#!/usr/bin/env python3
"""Own data-only adversarial tests over an authenticated CI export fixture."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('go_export_verifier',HERE/'verify_go_export.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
DIRECTORY=Path(sys.argv.pop(1)) if len(sys.argv)>1 and not sys.argv[1].startswith('-') else HERE/'ci-next-first/go'

class ExportProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline=v.verify(DIRECTORY)
        cls.frozen=v.frozen_source()
    def check(self,overrides):
        # The immutable source inventory is verified once for this test suite;
        # export data/corruptions remain parsed anew by every adversarial check.
        from unittest.mock import patch
        with patch.object(v,'frozen_source',return_value=copy.deepcopy(self.frozen)):
            return v._verify(DIRECTORY,overrides)
    def row(self,name):return json.loads((DIRECTORY/name).read_bytes())
    def encode(self,row):return json.dumps(row,indent=2).encode()
    def reject(self,name,mutate):
        row=self.row(name);mutate(row)
        with self.assertRaises((ValueError,KeyError)):self.check({name:self.encode(row)})
    def test_valid_export_and_determinism(self):
        self.assertTrue(self.baseline['verified']);self.assertEqual(self.baseline,self.check({}))
        self.assertEqual(self.baseline['sides']['base']['requirement']['failed'],3)
        self.assertEqual(self.baseline['sides']['reference']['requirement']['passed'],3)
    def test_four_fresh_domains(self):self.assertEqual(len(set(self.baseline['fresh_namespace_domains'])),4)
    def test_verified_flags_not_authority(self):
        overrides={}
        for side in ['base','reference']:
            row=self.row(side+'/probe.json');row['verified']=False
            for p in row['phases']:
                p['verified']=False;p['behavioral_result_verified']=False;p['teardown_verified']=False
            overrides[side+'/probe.json']=self.encode(row)
        self.assertTrue(self.check(overrides)['verified'])
    def test_oracle_digest_corruption(self):self.reject('base/probe.json',lambda r:r.update(oracle_sha256='0'*64))
    def test_source_validation_corruption(self):self.reject('reference/probe.json',lambda r:r['source_validation'].update(full_pinned_source_files_verified=1))
    def test_materialization_reference_corruption(self):self.reject('reference/probe.json',lambda r:r['materialization'].update(reference_changed_paths=[]))
    def test_lock_after_corruption(self):self.reject('base/probe.json',lambda r:r['lock_after'].update({'go.sum':'0'*64}))
    def test_toolchain_manifest_corruption(self):self.reject('base/toolchain-manifest.json',lambda r:r.update(file_count=1))
    def test_module_cache_manifest_corruption(self):self.reject('base/module-cache-manifest.json',lambda r:r.update(manifest_sha256='0'*64))
    def test_go_binary_inventory_corruption(self):self.reject('base/probe.json',lambda r:r.update(go_executable_sha256='0'*64))
    def test_go_version_corruption(self):self.reject('base/probe.json',lambda r:r.update(go_version='go1.23.1'))
    def test_compiler_escape_corruption(self):self.reject('base/probe.json',lambda r:r.update(native_compilers={'/etc/gcc':'0'*64,'/usr/bin/g++':'0'*64}))
    def test_domain_invalid(self):self.reject('base/requirement-harness.json',lambda r:r.update(domain_id='invalid'))
    def test_domain_reuse(self):
        old=self.row('base/requirement-harness.json')['domain_id']
        self.reject('reference/requirement-harness.json',lambda r:r.update(domain_id=old))
    def test_namespace_reuse(self):
        old=self.row('base/requirement-harness.json')['termination_evidence']['pid_namespace']
        self.reject('reference/requirement-harness.json',lambda r:r['termination_evidence'].update(pid_namespace=old))
    def test_teardown_incomplete(self):self.reject('base/regression-harness.json',lambda r:r['termination_evidence'].update(pidfd_exit_observed=False))
    def test_user_mapping_unsafe(self):self.reject('base/regression-harness.json',lambda r:r['termination_evidence']['user_namespace_mapping'].update(count=2))
    def test_stream_hash_corruption(self):self.reject('base/requirement-harness.json',lambda r:r['stdout'].update(sha256='0'*64))
    def test_stream_base64_corruption(self):self.reject('base/requirement-harness.json',lambda r:r['stdout'].update(base64='invalid!'))
    def test_stream_truncation(self):self.reject('base/requirement-harness.json',lambda r:r['stdout'].update(truncated=True))
    def test_jsonl_bytes_corruption(self):
        name='base/requirement-go-test.jsonl'
        with self.assertRaises(ValueError):self.check({name:(DIRECTORY/name).read_bytes()+b'changed'})
    def test_command_filter_corruption(self):self.reject('base/requirement-harness.json',lambda r:r['command'].__setitem__(-2,'-run=Other'))
    def test_operation_timeout(self):self.reject('base/regression-harness.json',lambda r:r.update(elapsed_seconds=901))
    def test_json_duplicate_key(self):
        name='base/probe.json';raw=(DIRECTORY/name).read_bytes();raw=raw.replace(b'{',b'{"side":"reference",',1)
        with self.assertRaisesRegex(ValueError,'duplicate JSON'):self.check({name:raw})
    def test_named_requirement_skip(self):
        raw=(DIRECTORY/'reference/requirement-go-test.jsonl').read_bytes();events=[json.loads(l) for l in raw.splitlines()]
        for e in events:
            if e.get('Test') and e['Action']=='pass':e['Action']='skip';break
        with self.assertRaises(ValueError):v.test_outcomes(b'\n'.join(json.dumps(e).encode() for e in events),'reference','requirement')
    def test_baseline_panic_not_behavior(self):
        raw=(DIRECTORY/'base/requirement-go-test.jsonl').read_bytes().replace(b'XRAI_CONTRACT_SECRET_QUERY',b'panic: setup failure')
        with self.assertRaises(ValueError):v.test_outcomes(raw,'base','requirement')
    def test_baseline_missing_test(self):
        events=[json.loads(l) for l in (DIRECTORY/'base/requirement-go-test.jsonl').read_bytes().splitlines()]
        events=[e for e in events if e.get('Test')!='TestXraiContractModel']
        with self.assertRaises(ValueError):v.test_outcomes(b'\n'.join(json.dumps(e).encode() for e in events),'base','requirement')
    def test_baseline_compile_error_not_behavior(self):
        with self.assertRaises(ValueError):v.test_outcomes(json.dumps({'Action':'fail','Package':v.PACKAGE,'Output':'build failed'}).encode(),'base','requirement')

if __name__=='__main__':unittest.main()
