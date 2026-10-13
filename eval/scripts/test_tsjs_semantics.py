"""Frozen-data negatives locally; actual native-receipt mutations only with CI outputs."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import verify_tsjs_semantics as v


class FrozenLabels(unittest.TestCase):
    def test_freeze_case_denominator(self):
        data = v.labels()
        self.assertEqual(len(data['cases']), 45)
        self.assertEqual(sum(c['resolvable_labeled_before_implementation'] for c in data['cases']), 13)

    def test_two_dialects_are_explicit(self):
        data = v.labels()
        for case in data['cases']:
            self.assertEqual(case['input']['profile'], 'captured-relative-exact-v1')
            self.assertEqual(case['input']['configuration'], {'module': 'esm'})
            for source in case['input']['files'].values():
                self.assertIn(source['dialect'], ['javascript', 'typescript'])

    def test_no_callable_label_promotion(self):
        for case in v.labels()['cases']:
            self.assertTrue(all(q['callable'] == 'unknown' for q in case['queries']))

    def test_real_sources_are_whole_unit_bytes(self):
        case = next(c for c in v.labels()['cases'] if c.get('real_source'))
        for path, source in case['input']['files'].items():
            self.assertEqual(source['source'].encode(), (v.LABELS.parent / 'real' / path).read_bytes())

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            v.strict_json('{"state":"unknown","state":"resolved"}')

    def test_later_label_edit_rejected(self):
        original = Path.read_bytes
        def changed(path):
            raw = original(path)
            return raw + b' ' if path == v.LABELS else raw
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(ValueError, 'freeze'):
                v.labels()

    def test_later_real_source_edit_rejected(self):
        original = Path.read_bytes
        target = v.LABELS.parent / 'real/src/v4.js'
        def changed(path):
            raw = original(path)
            return raw + b' ' if path == target else raw
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(ValueError, 'real source'):
                v.labels()


@unittest.skipUnless(os.environ.get('XRAI_TSJS_OUTPUTS'), 'native outputs only from disposable CI')
class ActualSnapshots(unittest.TestCase):
    def setUp(self):
        self.directory = Path(os.environ['XRAI_TSJS_OUTPUTS'])
        self.case = next(c for c in v.labels()['cases'] if c['id'] == 'javascript-alias')
        self.output = v.strict_json((self.directory / (self.case['id'] + '.json')).read_bytes())

    def rejects(self, mutation):
        out = copy.deepcopy(self.output); mutation(out)
        with self.assertRaises(ValueError):
            v.snapshot(out, self.case['input'])

    def test_complete_labeled_outputs(self):
        result = v.verify_outputs(self.directory)
        self.assertTrue(result['real_relation_verified']); self.assertEqual(result['false_promotions'], 0)

    def test_source_swap(self):
        self.rejects(lambda s: s['input']['files']['lib.js'].__setitem__('source', 'export function wrong() {}'))

    def test_config_swap(self):
        self.rejects(lambda s: s['input']['configuration'].__setitem__('module', 'cjs'))

    def test_dialect_swap(self):
        self.rejects(lambda s: s['input']['files']['lib.js'].__setitem__('dialect', 'typescript'))

    def test_producer_swap(self):
        self.rejects(lambda s: s.__setitem__('producer_fingerprint', '0' * 64))

    def test_grammar_swap(self):
        self.rejects(lambda s: s['producer_components'].__setitem__('javascript', '0' * 64))

    def test_gap_erasure_field(self):
        self.rejects(lambda s: s.pop('gaps'))

    def test_coverage_erasure(self):
        self.rejects(lambda s: s['coverage'].pop('lib.js'))

    def test_span_out_of_bounds(self):
        self.rejects(lambda s: s['references'][0]['evidence'].__setitem__('end', 1000000))

    def test_snapshot_evidence_swapped(self):
        self.rejects(lambda s: s['references'][0]['evidence'].__setitem__('snapshot_id', '0' * 64))

    def test_unknown_to_callable_promotion(self):
        self.rejects(lambda s: s['references'][0]['callable'].__setitem__('state', 'resolved'))

    def test_missing_reference_evidence(self):
        self.rejects(lambda s: s['references'][0]['resolution'].__setitem__('evidence', []))

    def test_chain_export_omitted(self):
        q = self.case['queries'][0]
        def change(s):
            r = next(r for r in s['references'] if r['evidence']['start'] == q['offset'] and r['evidence']['path'] == q['path'])
            r['resolution']['evidence'].pop(2)
        self.rejects(change)

    def test_target_not_declared(self):
        q = self.case['queries'][0]
        def change(s):
            r = next(r for r in s['references'] if r['evidence']['start'] == q['offset'] and r['evidence']['path'] == q['path'])
            r['resolution']['target'] = 'other.js:run'
        self.rejects(change)

    def test_dependency_erasure(self):
        self.rejects(lambda s: s['references'][0]['resolution'].__setitem__('dependencies', []))


if __name__ == '__main__':
    unittest.main()
