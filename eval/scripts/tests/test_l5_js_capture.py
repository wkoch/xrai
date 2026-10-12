"""Archive-bound curation is a receipt, not permission to alter floors or sources."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class JsCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='xrai-l5-js-verifier-')
        cls.root = Path(cls.temp.name)
        cls.case = cls.root / 'eval/qualification/l5-real/js'
        shutil.copytree(ROOT / 'eval/qualification/l5-real/js', cls.case)
        spec = importlib.util.spec_from_file_location('l5_js_capture', ROOT / 'eval/scripts/prepare_l5_js.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.module.ROOT = cls.root
        cls.module.CASE = cls.case

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def assert_mutation_rejected(self, relative, transform):
        path = self.case / relative
        original = path.read_bytes()
        try:
            path.write_bytes(transform(original))
            with self.assertRaises(ValueError):
                self.module.prepare(write=False)
        finally:
            path.write_bytes(original)

    def test_verify_is_read_only(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.case.rglob('*') if p.is_file()}
        receipt = self.module.prepare(write=False)
        self.assertFalse(receipt['admitted'])
        self.assertEqual(receipt['snapshots']['base']['production_nonempty_lines'], 56440)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})

    def test_archive_bytes_are_bound(self):
        self.assert_mutation_rejected('sources/base.tar.gz', lambda b: b + b'unbound')

    def test_inventory_bytes_are_bound(self):
        self.assert_mutation_rejected('sources/base-inventory.json.gz', lambda b: b + b'unbound')

    def test_production_floor_is_recomputed(self):
        def mutate(data):
            value = json.loads(data)
            value['snapshots']['base']['production_nonempty_lines'] += 1
            return json.dumps(value).encode()
        self.assert_mutation_rejected('capture.json', mutate)

    def test_digest_receipt_cannot_be_changed(self):
        def mutate(data):
            value = json.loads(data)
            value['snapshots']['head']['archive_sha256'] = '0' * 64
            return json.dumps(value).encode()
        self.assert_mutation_rejected('capture.json', mutate)

    def test_reference_patch_matches_real_production_delta(self):
        self.assert_mutation_rejected('oracles/reference.patch', lambda b: b + b'not the real patch\n')


if __name__ == '__main__':
    unittest.main()
