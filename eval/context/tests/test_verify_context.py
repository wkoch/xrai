"""Adversarial verification using receipts produced by the current native binary.

Run after the context drivers: XRAI_CONTEXT_RECEIPT_DIR defaults native-evidence.
Kept outside global documentary tests, which use a different Python runtime.
"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'eval/scripts'))
from verify_context import verify

class Verification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        receipts=Path(os.environ.get('XRAI_CONTEXT_RECEIPT_DIR','native-evidence'))
        cls.receipts={name:json.loads((receipts / ('context-'+name+'.json')).read_text())
                      for name in ['removed-consumer','central-hunk']}

    def run_receipt(self,name,mutate=None):
        output=copy.deepcopy(self.receipts[name])
        if mutate: mutate(output)
        with tempfile.TemporaryDirectory(prefix='xrai-context-verification-') as directory:
            path=Path(directory)/'output.json';path.write_text(json.dumps(output,ensure_ascii=False))
            return verify(ROOT/'eval/context'/f'{name}-input.json',path)

    def test_two_current_native_receipts(self):
        for name in self.receipts:
            with self.subTest(name=name):self.assertTrue(self.run_receipt(name)['verified'])

    def test_false_exact_token_count(self):
        with self.assertRaises(AssertionError):
            self.run_receipt('removed-consumer',lambda o:o['initial']['response']['budget'].update(used_tokens=1))

    def test_wire_hash_corruption(self):
        with self.assertRaises(AssertionError):
            self.run_receipt('removed-consumer',lambda o:o['expanded'].update(wire_blake3='0'*64))

    def test_span_not_matching_captured_utf8_source(self):
        with self.assertRaises((AssertionError,UnicodeError)):
            self.run_receipt('central-hunk',lambda o:o['initial']['manifest']['candidates'][0].update(minimum=[1,99999999]))

    def test_fictitious_resolved_consumer(self):
        def corrupt(o):
            reference=next(r for r in o['initial']['snapshots'][0]['references'] if r['resolution']['state']=='resolved')
            reference['resolution']['target_id']='sym_unavailable'
        with self.assertRaises(AssertionError):self.run_receipt('removed-consumer',corrupt)

    def test_expansion_mutating_immutable_manifest(self):
        with self.assertRaises(AssertionError):
            self.run_receipt('removed-consumer',lambda o:o['after_new']['manifest'].update(created_ms=15,expires_ms=60015))

    def test_changed_capture_identity(self):
        with self.assertRaises(AssertionError):
            self.run_receipt('removed-consumer',lambda o:o['initial']['snapshots'][0]['input']['files'].update({'src/lib.rs':'pub fn fake() {}\n'}))

    def test_controls_cannot_change_token_budget(self):
        with self.assertRaises(AssertionError):
            self.run_receipt('removed-consumer',lambda o:o['controls'][0]['input']['request']['limits'].update(max_tokens=99999))

    def test_recreation_cannot_rebind_previous_incarnation(self):
        def corrupt(o):
            o['retention_recreated']['manifest']['context_id']=o['initial']['manifest']['context_id']
        with self.assertRaises(AssertionError):self.run_receipt('removed-consumer',corrupt)

if __name__=='__main__':unittest.main()
