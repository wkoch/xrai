#!/usr/bin/env python3
"""Counterproofs for prepared source capture and owned policy replay only."""
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('django_router_verify', Path(__file__).with_name('django_router_verify.py'))
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class DjangoRouterPreparedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = v.verify()
        cls.freeze, cls.data = v.frozen_inputs()
        cls.state = v.decode(cls.data[v.BASE + 'evaluator/state-b.json'])

    def model(self, values, gate=True, alias='default'):
        return v.reduce_policy(alias, gate, values)

    def changed_record(self, mutate):
        record = deepcopy(self.record)
        mutate(record)
        with self.assertRaises(ValueError):
            v.verify(record)

    def test_recompute_actual_prepared_receipt(self):
        self.assertEqual(v.verify(self.record), self.record)

    def test_both_aliases_and_states(self):
        rows = self.record['declarative_replay']['main']
        self.assertEqual(len(rows), 8)
        result = {r['id']: r['owned_declarative_result']['creates_table'] for r in rows}
        self.assertTrue(result['a-ledger-default'])
        self.assertFalse(result['a-ledger-reporting'])
        self.assertFalse(result['b-ledger-default'])
        self.assertTrue(result['b-ledger-reporting'])
        self.assertTrue(result['b-catalog-default'])
        self.assertFalse(result['b-catalog-reporting'])

    def test_none_abstains(self):
        self.assertTrue(self.model([None, None])['creates_table'])
        self.assertEqual(self.model([None, False])['decisive_router_index'], 1)

    def test_false_is_decisive(self):
        self.assertFalse(self.model([False, True])['creates_table'])
        self.assertEqual(self.model([False, True])['consulted_router_count'], 1)

    def test_true_is_decisive(self):
        self.assertTrue(self.model([True, False])['creates_table'])
        self.assertEqual(self.model([True, False])['consulted_router_count'], 1)

    def test_order_changes_outcome(self):
        self.assertNotEqual(self.model([False, True]), self.model([True, False]))

    def test_veto_before_router(self):
        self.assertEqual(self.model([True], gate=False),
                         {'creates_table': False, 'decisive_router_index': None, 'consulted_router_count': 0})

    def test_missing_method_does_not_invoke(self):
        actual = self.model(['method_absent', False])
        self.assertEqual(actual['decisive_router_index'], 1)
        self.assertEqual(actual['consulted_router_count'], 1)
        self.assertFalse(actual['creates_table'])

    def test_no_router_fallback(self):
        self.assertTrue(self.model([])['creates_table'])

    def test_nonboolean_is_outside_owned_profile(self):
        for value in (0, 1, '', 'allowed', {}, []):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'outside owned profile'):
                self.model([value])

    def test_alias_case_not_normalized(self):
        with self.assertRaisesRegex(ValueError, 'alias outside'):
            self.model([True], alias='Default')

    def test_unknown_alias(self):
        with self.assertRaisesRegex(ValueError, 'alias outside'):
            self.model([True], alias='other')

    def test_model_gate_requires_boolean(self):
        with self.assertRaises(ValueError):
            self.model([True], gate=1)

    def test_router_count_bound(self):
        with self.assertRaises(ValueError):
            self.model([None] * 17)

    def test_immutable_policy_predicate_for_other_app(self):
        for app in ('catalog', 'audit', 'unseen_app'):
            for alias in ('default', 'reporting'):
                returns = v.configured_returns(self.state, app, alias)
                self.assertIsNone(returns[0])
                self.assertEqual(returns[1], alias == 'default')

    def test_policy_cannot_replace_existing_components(self):
        state = deepcopy(self.state)
        state['router_components']['scoped'] = 'invented.Policy'
        with self.assertRaisesRegex(ValueError, 'immutable policy'):
            v.configured_returns(state, 'ledger', 'reporting')

    def test_duplicate_component(self):
        state = deepcopy(self.state)
        state['router_order'] = ['scoped', 'scoped']
        with self.assertRaisesRegex(ValueError, 'exactly once'):
            v.configured_returns(state, 'ledger', 'reporting')

    def test_omitted_component(self):
        state = deepcopy(self.state)
        state['router_order'] = ['scoped']
        with self.assertRaises(ValueError):
            v.configured_returns(state, 'ledger', 'reporting')

    def test_wrong_database_pair(self):
        state = deepcopy(self.state)
        state['databases']['other'] = state['databases'].pop('reporting')
        with self.assertRaisesRegex(ValueError, 'exact two'):
            v.configured_returns(state, 'ledger', 'default')

    def test_empty_app_label(self):
        with self.assertRaises(ValueError):
            v.configured_returns(self.state, '', 'default')

    def test_hypothetical_aba_restores_bytes_not_live_claim(self):
        sequence = self.record['declarative_replay']['aba']
        self.assertEqual(sequence['configuration_sha256'][0], sequence['configuration_sha256'][2])
        self.assertNotEqual(sequence['configuration_sha256'][0], sequence['configuration_sha256'][1])
        self.assertFalse(sequence['live_session_executed'])

    def test_wrong_aba_revision_receipt(self):
        self.changed_record(lambda r: r['declarative_replay']['aba']['configuration_sha256'].__setitem__(2, '0' * 64))

    def test_byte_ranges_are_exact(self):
        files = v.archive_tree(self.data[v.ARCHIVE])
        for row in self.record['source_anchors']:
            self.assertEqual(files[row['path']][row['byte_start']:row['byte_end']], row['needle'].encode())

    def test_three_necessary_units_and_inheritance(self):
        anchors = self.record['source_anchors']
        self.assertEqual(len(anchors), 7)
        self.assertTrue(any('class CreateModel(ModelOperation)' in r['needle'] for r in anchors))
        self.assertTrue(any('class ModelOperation(Operation)' in r['needle'] for r in anchors))
        self.assertTrue(any('import Operation, OperationCategory' in r['needle'] for r in anchors))

    def test_one_module_evidence_incomplete(self):
        self.changed_record(lambda r: r.update(source_anchors=[r['source_anchors'][0]]))

    def test_altered_anchor_offset(self):
        self.changed_record(lambda r: r['source_anchors'][0].update(byte_start=0))

    def test_search_universe_not_anchor_only(self):
        self.assertEqual(self.record['capture']['regular_files'], 7084)
        self.assertEqual(self.record['capture']['production_files'], 929)
        self.changed_record(lambda r: r['capture'].update(production_files=4))

    def test_native_claim_rejected(self):
        self.changed_record(lambda r: r.update(native_behavior_verified=True))

    def test_actual_database_claim_rejected(self):
        self.changed_record(lambda r: r['declarative_replay'].update(actual_database_operations=1, framework_executed=True))

    def test_quota_admission_claim_rejected(self):
        self.changed_record(lambda r: r.update(multimodule_projection=20, multimodule_projection_credit=1, admitted=True))

    def test_eligibility_claim_rejected(self):
        self.changed_record(lambda r: r.update(individual_eligible=True))

    def test_python_resolution_claim_rejected(self):
        self.changed_record(lambda r: r.update(python_semantic_resolution='resolved'))

    def clone_inputs(self, root):
        for name, raw in self.data.items():
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        (root / v.BASE / 'freeze.json').write_bytes((v.ROOT / v.BASE / 'freeze.json').read_bytes())

    def test_frozen_label_change_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.clone_inputs(root)
            p = root / v.BASE / 'evaluator/oracle.json'
            x = v.decode(p.read_bytes())
            x['controls'][2]['expected']['creates_table'] = True
            p.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError, 'frozen input changed'):
                v.verify(root=root)

    def test_frozen_source_change_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.clone_inputs(root)
            p = root / v.BASE / 'sources/django/db/utils.py'
            p.write_bytes(p.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'frozen input changed'):
                v.verify(root=root)

    def test_reanchoring_freeze_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.clone_inputs(root)
            p = root / v.BASE / 'freeze.json'
            x = v.decode(p.read_bytes())
            x['inputs'][0]['sha256'] = '0' * 64
            p.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError, 'freeze fingerprint'):
                v.verify(root=root)

    def test_symlink_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.clone_inputs(root)
            p = root / v.BASE / 'agent/policy.py'
            backup = root / 'policy-backup.py'
            shutil.move(p, backup)
            p.symlink_to(backup)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                v.verify(root=root)

    def make_tar(self, entries):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            for name, raw, link in entries:
                member = tarfile.TarInfo(name)
                if link:
                    member.type = tarfile.SYMTYPE
                    member.linkname = link
                    archive.addfile(member)
                else:
                    member.size = len(raw)
                    archive.addfile(member, io.BytesIO(raw))
        return buffer.getvalue()

    def test_archive_member_escape_rejected(self):
        with self.assertRaises(ValueError):
            v.archive_tree(self.make_tar([('../escape.py', b'', None)]))

    def test_archive_alias_rejected(self):
        with self.assertRaises(ValueError):
            v.archive_tree(self.make_tar([('django/./db/a.py', b'', None)]))

    def test_duplicate_archive_member_rejected(self):
        with self.assertRaises(ValueError):
            v.archive_tree(self.make_tar([('a.py', b'a', None), ('a.py', b'b', None)]))

    def test_archive_symlink_rejected(self):
        with self.assertRaises(ValueError):
            v.archive_tree(self.make_tar([('a.py', b'', '../elsewhere')]))

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(ValueError):
            v.decode(b'{"allow":true,"allow":false}')

    def test_nonfinite_json_rejected(self):
        with self.assertRaises(ValueError):
            v.decode(b'{"result":NaN}')


if __name__ == '__main__':
    unittest.main()
