"""Independent occurrence and homonym counterchecks on current native receipts."""
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


class R3Context(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = Path(os.environ.get('XRAI_CONTEXT_RECEIPT_DIR', 'native-evidence'))
        cls.receipt = json.loads((directory / 'context-r3-binding.json').read_text())

    def check(self, mutation=None):
        output = copy.deepcopy(self.receipt)
        if mutation:
            mutation(output)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'receipt.json'
            path.write_text(json.dumps(output))
            return verify(ROOT / 'eval/context/r3-binding-input.json', path)

    def test_current_receipt_selects_position_bound_targets(self):
        self.assertTrue(self.check()['verified'])

    def test_alias_cannot_borrow_import_homonym(self):
        def corrupt(output):
            delivery = output['initial']
            head = delivery['snapshots'][-1]
            old = next(d for d in head['declarations'] if d['module'] == 'old' and d['name'] == 'target')
            delivery['manifest']['resolutions'][1]['result']['target_id'] = old['id']
        with self.assertRaises(AssertionError):
            self.check(corrupt)

    def test_query_position_cannot_move_to_import(self):
        def corrupt(output):
            delivery = output['initial']
            source = delivery['snapshots'][-1]['input']['files']['src/lib.rs']
            delivery['manifest']['resolutions'][1]['occurrence']['start'] = source.index('entry;')
        with self.assertRaises(AssertionError):
            self.check(corrupt)

    def test_parameter_cannot_borrow_resolved_alias(self):
        def corrupt(output):
            rows = output['initial']['manifest']['resolutions']
            rows[2]['result'] = copy.deepcopy(rows[1]['result'])
        with self.assertRaises(AssertionError):
            self.check(corrupt)


if __name__ == '__main__':
    unittest.main()
