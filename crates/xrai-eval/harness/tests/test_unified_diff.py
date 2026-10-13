"""Frozen labels and independent typed consumer counterproofs, entirely data-only."""
import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS))
import unified_diff as u
ROOT = HARNESS.parents[2]
DIRECTORY = ROOT / 'eval/context/diff-v1'


def decode_capture(case, key):
    return {path: bytes.fromhex(source) for path, source in case[key].items()}


def load_cases():
    frozen = json.loads((DIRECTORY / 'freeze.json').read_text())
    raw = (DIRECTORY / 'cases.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == frozen['cases_sha256']
    assert frozen['algorithm_files_present'] is False
    assert frozen['labels_after_results_changed'] is False
    return json.loads(raw)['cases']


class FrozenDiffTests(unittest.TestCase):
    def test_freeze_and_real_source(self):
        cases = load_cases()
        freeze = json.loads((DIRECTORY / 'freeze.json').read_text())
        self.assertEqual(sum(c['expected'] == 'accepted' for c in cases), freeze['positive_cases'])
        self.assertEqual(sum(c['expected'] == 'rejected' for c in cases), freeze['negative_cases'])
        capture = json.loads((DIRECTORY / 'cases.json').read_text())['real_capture']
        raw = (ROOT / capture['input_path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), capture['input_sha256'])
        source = json.loads(raw)['files'][capture['path']].encode()
        self.assertEqual(hashlib.sha256(source).hexdigest(), capture['source_sha256'])

    def test_source_boundaries(self):
        old = 'á\n猫'.encode()
        patch = b'--- a/a.txt\n+++ b/a.txt\n@@ -2 +2 @@\n-' + '猫'.encode() + b'\n\\ No newline at end of file\n+' + '犬'.encode() + b'\n\\ No newline at end of file\n'
        receipt = u.decode_unified(patch, {'a.txt': old}, {'a.txt': 'á\n犬'.encode()})
        h = receipt.changes[0].hunks[0]
        self.assertEqual((h.base_start, h.base_end), (3, 6))
        self.assertEqual((h.head_start, h.head_end), (3, 6))
        self.assertEqual(receipt.receipt()['native_p3_support'], False)

    def test_header_like_source_records(self):
        old = b'-- old\n++ old\n@@ old\n'
        new = b'-- new\n++ new\n@@ new\n'
        patch = b'--- a/a.txt\n+++ b/a.txt\n@@ -1,3 +1,3 @@\n--- old\n-++ old\n-@@ old\n+-- new\n+++ new\n+@@ new\n'
        result = u.decode_unified(patch, {'a.txt': old}, {'a.txt': new})
        self.assertEqual(u.apply_typed({'a.txt': old}, result.changes), {'a.txt': new})

    def test_empty_diff_identical_snapshots(self):
        files = {'zero': b'', 'real': b'x\r\n'}
        result = u.decode_unified(b'', files, files)
        self.assertEqual(result.changes, ())
        self.assertEqual(result.base_snapshot_id, result.head_snapshot_id)

    def test_typed_hash_presence_and_spans(self):
        result = u.decode_unified(b'--- a/a\n+++ b/a\n@@ -1 +1 @@\n-x\n+y\n', {'a': b'x\n'}, {'a': b'y\n'})
        change = result.changes[0]
        hunk = change.hunks[0]
        forged = [dataclasses.replace(change, base_sha256='0' * 64),
                  dataclasses.replace(change, head_sha256='0' * 64),
                  dataclasses.replace(change, base_present=False),
                  dataclasses.replace(change, hunks=(dataclasses.replace(hunk, base_start=True),)),
                  dataclasses.replace(change, hunks=(dataclasses.replace(hunk, removed=b'X\n'),)),
                  dataclasses.replace(change, hunks=(dataclasses.replace(hunk, head_end=3),)),
                  dataclasses.replace(change, hunks=())]
        for item in forged:
            with self.subTest(item=item), self.assertRaises(u.DiffError):
                u.apply_typed({'a': b'x\n'}, (item,))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            change.path = 'other'

    def test_typed_missing_and_duplicated_handles(self):
        result = u.decode_unified(b'--- /dev/null\n+++ b/zero\n@@ -0,0 +0,0 @@\n', {}, {'zero': b''})
        with self.assertRaises(u.DiffError):
            u.apply_typed({'zero': b''}, result.changes)
        with self.assertRaises(u.DiffError):
            u.apply_typed({}, result.changes + result.changes)
        self.assertNotEqual(u.snapshot_id({}), u.snapshot_id({'zero': b''}))

    def test_bounds_fail_before_parsing(self):
        for source in [bytearray(), '', None]:
            with self.subTest(source=source), self.assertRaises(u.DiffError):
                u.decode_unified(source, {}, {})
        with self.assertRaises(u.DiffError) as error:
            u.decode_unified(b'x' * (u.MAX_DIFF_BYTES + 1), {}, {})
        self.assertEqual(error.exception.code, 'diff_limit')
        with self.assertRaises(u.DiffError):
            u.decode_unified(b'', {str(n): b'' for n in range(u.MAX_FILES + 1)}, {})
        with self.assertRaises(u.DiffError):
            u.decode_unified(b'', {'large': b'a' * (u.MAX_FILE_BYTES + 1)}, {})
        with self.assertRaises(u.DiffError):
            u.decode_unified(b'', {'lines': b'\n' * (u.MAX_LINES + 1)}, {})
        with self.assertRaises(u.DiffError):
            u.decode_unified(b'', {'bad': bytearray()}, {})

    def test_sparse_preserves_every_unchanged_byte(self):
        c = next(c for c in load_cases() if c['id'] == 'sparse-two-hunks')
        base, head = decode_capture(c, 'base'), decode_capture(c, 'head')
        result = u.decode_unified(bytes.fromhex(c['diff_hex']), base, head)
        self.assertEqual(u.apply_typed(base, result.changes), head)
        self.assertEqual(base['untouched.txt'], head['untouched.txt'])
        changed = {**head, 'src/unit.txt': b'a\nB\nC\nD\ne\n'}
        with self.assertRaises(u.DiffError) as error:
            u.decode_unified(bytes.fromhex(c['diff_hex']), base, changed)
        self.assertEqual(error.exception.code, 'head_mismatch')


def frozen_test(case):
    def check(self):
        base, head = decode_capture(case, 'base'), decode_capture(case, 'head')
        diff = bytes.fromhex(case['diff_hex'])
        if case['expected'] == 'rejected':
            with self.assertRaises(u.DiffError) as error:
                u.decode_unified(diff, base, head)
            self.assertEqual(error.exception.code, case['reason'])
        else:
            result = u.decode_unified(diff, base, head)
            self.assertEqual(u.apply_typed(base, result.changes), head)
            actual = [{'path': c.path, 'kind': c.kind, 'base_present': c.base_present,
                       'head_present': c.head_present, 'hunks': [
                           {'base_span': [h.base_start, h.base_end],
                            'head_span': [h.head_start, h.head_end],
                            'replacement_hex': h.replacement.hex()} for h in c.hunks]}
                      for c in result.changes]
            self.assertEqual(actual, case['expected_changes'])
    return check


for _case in load_cases():
    setattr(FrozenDiffTests, 'test_frozen_' + _case['id'].replace('-', '_'), frozen_test(_case))

if __name__ == '__main__':
    unittest.main()
