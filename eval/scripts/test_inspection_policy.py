"""S02 offline inspection contract counterproofs; zero acquisitions/execution."""
from copy import deepcopy
import gzip
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

import inventory_gitea_availability as v


class InspectionPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.availability = v.decode((v.DEST / 'availability.json').read_bytes())
        cls.contract = v.decode((v.DEST / 'inspection-policy.json').read_bytes())
        cls.example = v.decode((v.DEST / 'sample-request.json').read_bytes())

    def setUp(self):
        self.policy = deepcopy(self.contract)
        self.requests = deepcopy(self.example)
        self.inventory = self.availability

    def reject(self):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            v.validate_requests(self.policy, self.requests, self.inventory)

    def request_for(self, artifact):
        request = deepcopy(self.example[0]); suffix = artifact['path'][len('cache/download/'):]
        request.update(artifact=artifact, url='https://proxy.golang.org/' + suffix,
                       destination='inspection-data/' + artifact['sha256'] + '/raw/' + suffix)
        return request

    def test_valid_metadata_request_is_only_shape_validation(self):
        result = v.validate_requests(self.policy, self.requests, self.inventory)
        self.assertTrue(result['prospective_shape_valid'])
        self.assertFalse(result['acquisition_performed'])
        self.assertFalse(result['execution_allowed'])
        self.assertEqual(result['remote_actions'], 'none')

    def test_valid_request_never_calls_network_or_subprocess(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('network spy')), \
             patch('subprocess.Popen', side_effect=AssertionError('execution spy')):
            self.assertTrue(v.validate_requests(self.policy, self.requests, self.inventory)['prospective_shape_valid'])

    def test_waiver_does_not_unlock_s01(self):
        self.policy['S01_execution_allowed'] = True
        self.reject()

    def test_acquisition_flag_does_not_implement_downloader(self):
        self.policy['acquisition_implemented'] = True
        self.reject()

    def test_alternate_inspection_profile_rejected(self):
        self.policy['profile'] = 'allow-inspection'
        self.reject()

    def test_project_credentials_rejected(self):
        self.requests[0]['credentials'] = True
        self.reject()

    def test_authorization_header_rejected(self):
        self.requests[0]['headers'] = {'Authorization': 'dummy-never-a-secret'}
        self.reject()

    def test_cookie_header_rejected(self):
        self.requests[0]['headers'] = {'Cookie': 'dummy'}
        self.reject()

    def test_redirect_rejected(self):
        self.requests[0]['redirects'] = True
        self.reject()

    def test_http_rejected(self):
        self.requests[0]['url'] = self.requests[0]['url'].replace('https:', 'http:')
        self.reject()

    def test_other_host_rejected(self):
        self.requests[0]['url'] = self.requests[0]['url'].replace('proxy.golang.org', 'example.invalid')
        self.reject()

    def test_host_suffix_rejected(self):
        self.requests[0]['url'] = self.requests[0]['url'].replace('proxy.golang.org', 'proxy.golang.org.example.invalid')
        self.reject()

    def test_url_userinfo_rejected(self):
        self.requests[0]['url'] = self.requests[0]['url'].replace('proxy.golang.org', 'user@proxy.golang.org')
        self.reject()

    def test_explicit_port_rejected(self):
        self.requests[0]['url'] = self.requests[0]['url'].replace('proxy.golang.org', 'proxy.golang.org:443')
        self.reject()

    def test_url_query_and_fragment_rejected(self):
        for suffix in ['?token=dummy', '#redirect']:
            with self.subTest(suffix=suffix):
                self.requests[0]['url'] = self.example[0]['url'] + suffix
                self.reject()

    def test_url_path_alias_rejected(self):
        self.requests[0]['url'] = self.requests[0]['url'].replace('/github.com/', '/./github.com/')
        self.reject()

    def test_latest_is_not_a_frozen_version(self):
        self.requests[0]['url'] = self.requests[0]['url'].rsplit('/', 1)[0] + '/latest'
        self.reject()

    def test_post_rejected(self):
        self.requests[0]['method'] = 'POST'
        self.reject()

    def test_hash_required(self):
        del self.requests[0]['artifact']['sha256']
        self.reject()

    def test_hash_repinning_not_authority(self):
        self.requests[0]['artifact']['sha256'] = '0' * 64
        self.reject()

    def test_wrong_byte_length_rejected(self):
        self.requests[0]['artifact']['bytes'] += 1
        self.reject()

    def test_reader_not_pinned_rejected(self):
        self.requests[0]['reader_sha256'] = '0' * 64
        self.reject()

    def test_hook_and_upstream_import_rejected(self):
        for operator in ['hook', 'upstream_import', 'go_list', 'build', 'probe']:
            with self.subTest(operator=operator):
                self.requests[0]['operators'] = [operator]
                self.reject()

    def test_go_mod_download_operation_rejected(self):
        self.requests[0]['operation'] = 'go_mod_download'
        self.reject()

    def test_shell_flag_rejected(self):
        self.requests[0]['shell'] = 'sh'
        self.reject()

    def test_project_destination_rejected(self):
        self.requests[0]['destination'] = 'eval/qualification/l5-real/go/setup/go.mod'
        self.reject()

    def test_traversal_destination_rejected(self):
        self.requests[0]['destination'] = '../inspection-data/out'
        self.reject()

    def test_alias_destination_rejected(self):
        self.requests[0]['destination'] = './' + self.requests[0]['destination']
        self.reject()

    def test_duplicate_request_rejected(self):
        self.requests.append(deepcopy(self.requests[0]))
        self.reject()

    def test_request_count_limit(self):
        self.requests = self.requests * 129
        self.reject()

    def test_large_recorded_zip_does_not_expand_inspection_limit(self):
        artifact = next(r for module in self.availability['requirements']
                        for version in module['historical_cache_versions_declared'] for r in version['archive_metadata']
                        if r['path'].endswith('.zip') and r['bytes'] > v.MAX_OBJECT_BYTES)
        self.requests = [self.request_for(artifact)]
        self.reject()

    def test_limits_cannot_be_increased_by_policy_flag(self):
        self.policy['limits']['total_bytes'] = 10 ** 12
        self.reject()

    def test_unbounded_timeout_rejected(self):
        self.requests[0]['timeout_seconds'] = 900
        self.reject()

    def test_boolean_timeout_not_integer(self):
        self.requests[0]['timeout_seconds'] = True
        self.reject()

    def test_integer_credentials_not_false(self):
        self.requests[0]['credentials'] = 0
        self.reject()

    def test_forged_inventory_does_not_create_trusted_artifact(self):
        self.inventory = deepcopy(self.availability)
        artifact = self.inventory['requirements'][0]['historical_cache_versions_declared'][0]['archive_metadata'][0]
        artifact['sha256'] = '0' * 64
        self.requests = [self.request_for(artifact)]
        self.reject()

    def test_selected_or_compiled_flags_not_evidence(self):
        self.inventory = deepcopy(self.availability)
        self.inventory['requirements'][0]['compiled_version']['status'] = 'verified'
        self.reject()

    def test_remote_dismiss_rejected(self):
        self.policy['remote_actions'] = 'dismiss'
        self.reject()


class AvailabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.availability = v.decode((v.DEST / 'availability.json').read_bytes())

    def test_distinct_requirement_presence_selection_compilation(self):
        summary = self.availability['summary']
        self.assertEqual((summary['root_requirements'], summary['direct_requirements'], summary['indirect_requirements']), (291, 117, 174))
        self.assertEqual(summary['root_requirements_with_matching_declared_cache_version'], 287)
        self.assertEqual(summary['replacement_requirements'], 4)
        self.assertTrue(self.availability['source_setup_locks_identical'])
        for row in self.availability['requirements']:
            self.assertEqual(row['present_now']['verified_bytes'], 0)
            self.assertEqual(row['selected_version']['status'], 'unknown')
            self.assertEqual(row['compiled_version']['status'], 'unknown')
        self.assertFalse(summary['execution_allowed'])
        self.assertEqual(summary['new_acquisitions'], 0)

    def test_replacements_are_declarations_not_selected_versions(self):
        replacements = [r for r in self.availability['requirements'] if r['replacement_declared']]
        self.assertEqual(len(replacements), 4)
        for row in replacements:
            self.assertTrue(row['replacement_cache_versions_declared'])
            self.assertEqual(row['selected_version']['status'], 'unknown')
        self.assertEqual(len(self.availability['excludes']), 4)

    def test_all_missing_files_enumerated_not_only_a_count(self):
        raw = (v.ROOT / v.MISSING_PATH).read_bytes()
        missing = v.decode(gzip.decompress(raw))
        manifest = v.decode(v.read_pinned(v.CACHE))
        self.assertEqual(missing['files'], manifest['files'])
        self.assertEqual(missing['file_count'], 36892)
        self.assertEqual(missing['declared_bytes'], 1076105923)
        self.assertEqual(self.availability['summary']['retained_ci_zip_files'], 14)
        self.assertEqual(self.availability['summary']['retained_module_cache_bytes'], 0)

    def test_fifty_five_individual_decisions_remain_blocking(self):
        alerts = self.availability['alerts']
        self.assertEqual(len({a['number'] for a in alerts}), 55)
        self.assertEqual(sum(a['priority'] == 1 for a in alerts), 23)
        for alert in alerts:
            self.assertEqual(alert['decision'], 'pending_blocks_execution')
            self.assertEqual(alert['selected_version'], 'unknown')
            self.assertEqual(alert['compiled_version'], 'unknown')
            self.assertEqual(set(alert['phase_decisions'].values()), {'blocked'})
            self.assertTrue(alert['absence_of_import_is_not_exclusion'])

    def test_s01_guard_still_blocks_every_phase(self):
        import verify_gitea_exposure
        for phase in ['download', 'build', 'probe']:
            with self.subTest(phase=phase):
                with self.assertRaisesRegex(PermissionError, 'S01 blocks ' + phase):
                    verify_gitea_exposure.require_execution(phase)

    def test_go_mod_unsupported_directive_cannot_be_ignored(self):
        with self.assertRaisesRegex(ValueError, 'unsupported go.mod'):
            v.parse_go_mod(b'module m\ngo 1.22\ntoolchain go1.22.12\n')

    def test_cache_duplicate_path_rejected(self):
        rows = [{'path': 'example.org/m@v1/source.go', 'bytes': 1, 'sha256': '0' * 64}] * 2
        with self.assertRaisesRegex(ValueError, 'duplicate cache'):
            v.validate_cache({'file_count': 2, 'bytes': 2, 'files': rows})

    def test_cache_sum_cannot_replace_missing_bytes(self):
        rows = [{'path': 'example.org/m@v1/source.go', 'bytes': 1, 'sha256': '0' * 64}]
        with self.assertRaisesRegex(ValueError, 'declared byte total'):
            v.validate_cache({'file_count': 1, 'bytes': 2, 'files': rows})

    def test_zip_archive_symlink_member_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for index, name in enumerate(v.ZIP_NAMES):
                entry = zipfile.ZipInfo(name); entry.external_attr = ((0o120777 if index == 0 else 0o100644) << 16)
                archive.writestr(entry, 'never executed')
        with self.assertRaisesRegex(ValueError, 'ordinary bounded ZIP'):
            v.retained_zip(stream.getvalue())

    def test_json_duplicate_and_nonfinite_rejected(self):
        for raw in [b'{"a":1,"a":2}', b'{"a":NaN}']:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    v.decode(raw)


if __name__ == '__main__':
    unittest.main()
