"""Owned Python/data-only counterproofs; captured Django is never imported."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from django_router_physical import CASE, FREEZE_SHA, ROOT, command, lock, prepared, validate_result, validate_visibility, wheel_tree
from django_router_verify import archive_tree, sha


class PhysicalPreparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.freeze, cls.data, cls.files = prepared()
        cls.oracle = json.loads((CASE / 'evaluator/oracle.json').read_text())
        cls.origins = {name: {'path': '/checkout/' + name.replace('.', '/') + '.py',
                             'sha256': sha(cls.files[name.replace('.', '/') + '.py'])}
                       for name in ['django.db.migrations.operations.models', 'django.db.migrations.operations.base',
                                    'django.db.utils', 'django.db.models.options']}
        cls.origins['policy'] = {'path': '/public/policy.py', 'sha256': sha((CASE / 'agent/policy.py').read_bytes())}

    def fixture(self, phase='b'):
        # Synthetic JSON tests verifier rejection only, never physical evidence.
        expected = self.oracle['physical_controls'] if phase == 'controls' else [r for r in self.oracle['main_cells'] if r['state'] == phase]
        rows = []
        for row in expected:
            row = copy.deepcopy(row)
            if phase == 'controls':
                row.update({'app': 'xrai', 'model': 'allnone' if row['control'] == 'all-none' else 'absentfalse',
                            'table': 'xrai_' + ('allnone' if row['control'] == 'all-none' else 'absentfalse'),
                            'isolated_router_allows': row['creates_table'], 'router_consulted': True})
            row.update({'historical_model': True, 'real_database_forwards': True, 'real_schema_editor': True,
                        'model_can_migrate': row.get('model') != 'legacyentry',
                        'sentinel': [[phase + ':' + row['alias']]],
                        'router_events_during_operation': []})
            if row['router_consulted']:
                row['router_events_during_operation'] = [{'alias': row['alias'], 'app': row['app'],
                                                         'model_name': row['model'], 'answer': row['creates_table']}]
            rows.append(row)
        return {'phase': phase, 'oracle_executed': True, 'cells': rows, 'python_version': lock()['python'],
                'provider_used': False, 'qualified': False, 'admitted': False,
                'database_files': [{'alias': 'default', 'inode': 1}, {'alias': 'reporting', 'inode': 2}],
                'module_origins': self.origins,
                'configuration_sha256': sha((CASE / ('agent/deployment.json' if phase == 'a' else 'evaluator/reference.json')).read_bytes()),
                'policy_sha256': sha((CASE / 'agent/policy.py').read_bytes())}

    def rejects(self, edit, phase='b'):
        record = self.fixture(phase)
        edit(record)
        with self.assertRaises((ValueError, KeyError, TypeError)):
            validate_result(record, phase, self.oracle, self.origins)

    def test_full_captured_checkout(self):
        self.assertEqual(len(self.files), 7084)
        self.assertIn('LICENSE', self.files)
        self.assertIn('LICENSE.python', self.files)

    def test_frozen_hash(self):
        self.assertEqual(sha((CASE / 'freeze.json').read_bytes()), FREEZE_SHA)
        self.assertTrue(self.freeze['before_framework_execution'])

    def test_policy_exact_previous_bytes(self):
        self.assertEqual((CASE / 'agent/policy.py').read_bytes(), (ROOT / 'eval/qualification/django-router-v1/agent/policy.py').read_bytes())

    def test_only_order_changed(self):
        a = json.loads((CASE / 'agent/deployment.json').read_text())
        b = json.loads((CASE / 'evaluator/reference.json').read_text())
        self.assertNotEqual(a.pop('router_order'), b.pop('router_order'))
        self.assertEqual(a, b)

    def test_public_unmanaged_requirement(self):
        self.assertIn('managed=False', (CASE / 'agent/input.md').read_text())

    def test_baseline_executes_and_fails_public_requirement(self):
        result = validate_result(self.fixture('a'), 'a', self.oracle, self.origins)
        self.assertTrue(result['oracle_executed'])
        self.assertFalse(result['requirement_satisfied'])

    def test_reference_matches_public_requirement(self):
        self.assertTrue(validate_result(self.fixture(), 'b', self.oracle, self.origins)['requirement_satisfied'])

    def test_four_physical_controls(self):
        self.assertEqual(validate_result(self.fixture('controls'), 'controls', self.oracle, self.origins)['cells_verified'], 4)

    def test_control_wrong_table_cannot_pass_internal_truth(self):
        self.rejects(lambda r: r['cells'][0].__setitem__('table', 'unused'), 'controls')

    def test_control_wrong_app_resealed_event_refused(self):
        def edit(r):
            r['cells'][0]['app'] = 'other'
            r['cells'][0]['router_events_during_operation'][0]['app'] = 'other'
        self.rejects(edit, 'controls')

    def test_control_model_gate_and_isolated_router_refused(self):
        for field in ('model_can_migrate', 'isolated_router_allows'):
            self.rejects(lambda r: r['cells'][0].__setitem__(field, False), 'controls')

    def test_visibility_missing_public_and_replaced_private_target(self):
        # Execute only the own verifier over synthetic JSON; no visibility claim.
        names = ['/private/oracle.json', '/private/reference.json', '/private/physical_oracle.py',
                 '/checkout/../private/oracle.json', '/public/../private/oracle.json',
                 '/workspace/private/oracle.json', '/proc/1/root/workspace/private/oracle.json',
                 '/public/private-link', '/checkout/graft/INDEX.md', '/checkout/.git/config',
                 '/checkout/eval/qualification/django-router-v2/evaluator/oracle.json']
        r = {'schema': 'xrai.eval.django-router.agent-view.v2', 'framework_imported': False, 'model_called': False,
             'private_reads_denied': True, 'checkout_readonly': True,
             'attacks': [{'path': name, 'readable': False} for name in names],
             'public_readable': {name: True for name in ['/checkout/django/db/utils.py', '/public/input.md', '/public/policy.py', '/public/deployment.json']}}
        self.assertTrue(validate_visibility(r)['visibility_verified'])
        changed = copy.deepcopy(r); changed['attacks'][0]['path'] = '/not-private'
        with self.assertRaises(ValueError): validate_visibility(changed)
        changed = copy.deepcopy(r); changed['public_readable'] = {}
        with self.assertRaises(ValueError): validate_visibility(changed)

    def test_missing_cell(self):
        self.rejects(lambda r: r['cells'].pop())

    def test_duplicate_cell(self):
        self.rejects(lambda r: r['cells'].__setitem__(1, copy.deepcopy(r['cells'][0])))

    def test_wrong_database_truth(self):
        self.rejects(lambda r: r['cells'][0].__setitem__('creates_table', True))

    def test_truth_integer_not_boolean(self):
        self.rejects(lambda r: r['cells'][0].__setitem__('creates_table', 0))

    def test_unmanaged_table_creation(self):
        self.rejects(lambda r: next(x for x in r['cells'] if x['model'] == 'legacyentry').__setitem__('creates_table', True))

    def test_unmanaged_router_consultation(self):
        self.rejects(lambda r: next(x for x in r['cells'] if x['model'] == 'legacyentry').__setitem__('router_consulted', True))

    def test_isolated_router_veto_erased(self):
        self.rejects(lambda r: next(x for x in r['cells'] if x['model'] == 'legacyentry' and x['alias'] == 'reporting').__setitem__('isolated_router_allows', False))

    def test_historical_model_erased(self):
        self.rejects(lambda r: r['cells'][0].__setitem__('historical_model', False))

    def test_schema_editor_erased(self):
        self.rejects(lambda r: r['cells'][0].__setitem__('real_schema_editor', False))

    def test_sentinel_changed(self):
        self.rejects(lambda r: r['cells'][0].__setitem__('sentinel', [['changed']]))

    def test_aliases_same_inode(self):
        self.rejects(lambda r: r['database_files'][1].__setitem__('inode', 1))

    def test_alias_inode_bool(self):
        self.rejects(lambda r: r['database_files'][0].__setitem__('inode', True))

    def test_module_origin_host(self):
        self.rejects(lambda r: r.__setitem__('module_origins', {}))

    def test_order_binding_changed(self):
        self.rejects(lambda r: r.__setitem__('configuration_sha256', '0' * 64))

    def test_policy_binding_changed(self):
        self.rejects(lambda r: r.__setitem__('policy_sha256', '0' * 64))

    def test_router_result_fabricated(self):
        self.rejects(lambda r: r['cells'][0]['router_events_during_operation'][0].__setitem__('answer', True))

    def test_no_qualification_promotion(self):
        self.rejects(lambda r: r.__setitem__('qualified', True))

    def test_no_provider(self):
        self.rejects(lambda r: r.__setitem__('provider_used', True))

    def test_agent_mount_excludes_private(self):
        args = command('agent')
        self.assertNotIn('/private', args)
        self.assertNotIn('/workspace/private', args)
        self.assertIn('--ro-bind', args)
        self.assertIn('--unshare-all', args)

    def test_evaluator_mount_has_private(self):
        self.assertIn('/workspace/private', command('a'))

    def test_process_resource_policy_real_arguments(self):
        launch = command('b')[-1]
        self.assertIn('RLIMIT_AS', launch)
        self.assertIn('RLIMIT_NPROC', launch)
        self.assertIn('RLIMIT_FSIZE', launch)
        self.assertIn('67108864', command('b'))

    def test_unknown_phase(self):
        with self.assertRaises(ValueError):
            command('paid')

    def wheel(self, names):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as z:
            for name in names:
                z.writestr(name, 'data')
        return raw.getvalue()

    def test_wheel_traversal(self):
        with self.assertRaises(ValueError):
            wheel_tree(self.wheel(['../escape', 'LICENSE']))

    def test_wheel_absolute(self):
        with self.assertRaises(ValueError):
            wheel_tree(self.wheel(['/escape', 'LICENSE']))

    def test_wheel_missing_license(self):
        with self.assertRaises(ValueError):
            wheel_tree(self.wheel(['package.py']))

    def test_wheel_safe_license(self):
        self.assertEqual(len(wheel_tree(self.wheel(['pkg/LICENSE', 'pkg/module.py']))), 2)


if __name__ == '__main__':
    unittest.main()
