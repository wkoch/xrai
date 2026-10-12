"""Contraprovas on the retained real S01 inventory; no upstream execution."""
import json
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest
import verify_gitea_exposure as exposure


class ExposureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'gitea'
        shutil.copytree(exposure.DIRECTORY, self.directory)
        self.path = self.directory / 'decisions.json'
        self.inventory = json.loads(self.path.read_text())

    def mutate(self, change):
        change(self.inventory)
        self.path.write_text(json.dumps(self.inventory))

    def refused(self, change):
        self.mutate(change)
        with self.assertRaises((ValueError, KeyError)):
            exposure.check_data(self.directory)

    def test_actual_all_55_decisions_with_23_priority(self):
        result = exposure.check_data(self.directory)
        self.assertTrue(result['data_acceptance'])
        self.assertFalse(result['execution_allowed'])
        self.assertEqual((result['alerts'], result['prioritized_critical_high']), (55, 23))
        self.assertEqual(result['blocking_alerts'], list(range(1, 56)))

    def test_all_three_effective_phases_blocked(self):
        for phase in exposure.PHASES:
            with self.subTest(phase=phase), self.assertRaises(PermissionError):
                exposure.require_execution(phase, self.directory)

    def test_unknown_phase_never_bypasses(self):
        with self.assertRaises(ValueError):
            exposure.require_execution('data-only', self.directory)

    def test_forged_global_permission(self):
        self.refused(lambda v: v.update(execution_allowed=True))

    def test_forged_individual_allowance(self):
        self.refused(lambda v: v['alerts'][0].update(decision='allow'))

    def test_missing_alert(self):
        self.refused(lambda v: v['alerts'].pop())

    def test_duplicate_alert(self):
        self.refused(lambda v: v['alerts'].__setitem__(0, v['alerts'][1]))

    def test_boolean_flag_cannot_replace_alert_id(self):
        self.refused(lambda v: next(r for r in v['alerts'] if r['number'] == 1).update(number=True))

    def test_unknown_alert(self):
        self.refused(lambda v: v['alerts'][0].update(number=999))

    def test_setup_binding_rehash_cannot_switch_setup(self):
        self.refused(lambda v: v['setup_bindings'].update({exposure.SETUP + 'go.mod': '0' * 64}))

    def test_forged_not_applicable(self):
        self.refused(lambda v: v['alerts'][0].update(assessment='not_applicable'))

    def test_phase_permission(self):
        self.refused(lambda v: v['alerts'][0]['phases']['probe'].update(decision='allowed'))

    def test_network_off_is_not_sufficient_control(self):
        self.refused(lambda v: v['controls']['build_probe']['limits'].clear())

    def test_advisory_status_forged(self):
        self.refused(lambda v: v['alerts'][0]['official_source'].update(fetch_status='not_affected'))

    def test_advisory_changed_and_rehashed(self):
        row = self.inventory['alerts'][0]
        path = self.directory / 'advisories' / (row['ghsa_id'] + '.json')
        advisory = json.loads(path.read_text()); advisory['description'] = 'safe now'
        path.write_text(json.dumps(advisory))
        self.refused(lambda v: v['alerts'][0]['official_source'].update(raw_sha256=exposure.sha(path.read_bytes())))

    def test_missing_advisory(self):
        row = self.inventory['alerts'][0]
        (self.directory / 'advisories' / (row['ghsa_id'] + '.json')).unlink()
        with self.assertRaises(OSError):
            exposure.check_data(self.directory)

    def test_pin_changed(self):
        self.refused(lambda v: v['alerts'][0]['resolved_pin'].update(version='v99.0.0'))

    def test_invented_compiled_chain(self):
        self.refused(lambda v: v['alerts'][0]['dependency_chain'].update(compiled_probe_chain='not compiled'))

    def test_import_witness_tampered_and_rehashed(self):
        path = self.directory / 'source-import-evidence.json'
        data = json.loads(path.read_text()); next(iter(data['packages'].values()))['import_witness_count'] = 999
        path.write_text(json.dumps(data))
        self.refused(lambda v: v.update(import_evidence_sha256=exposure.sha(path.read_bytes())))

    def test_blanket_waiver_rejected(self):
        self.refused(lambda v: v.update(waiver='test corpus'))

    def test_missing_pending(self):
        self.refused(lambda v: v['alerts'][0].update(pending=[]))

    def test_remote_closure_rejected(self):
        self.refused(lambda v: v.update(remote_actions='close all'))

    def test_cwe_claim_forged(self):
        self.refused(lambda v: v['alerts'][0]['advisory_evidence'].update(cwe_ids=[]))


class ConsumerWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (exposure.ROOT / '.github/workflows/l5-corpus-next.yml').read_text()

    def refused(self, text):
        with self.assertRaises(ValueError):
            exposure.check_consumer_workflow(text)

    def test_actual_go_workflow_guards_before_fetch_and_conditional_reference(self):
        result = exposure.check_consumer_workflow(self.workflow)
        self.assertTrue(result['verified'])
        self.assertFalse(result['execution_observed'])
        self.assertEqual(len(result['probe_step_indices']), 2)

    def test_reference_shell_stops_before_safe_execution_spy(self):
        # Only the own guard and a shell printf spy; never the Go executor.
        own_guard = shlex.quote(sys.executable) + ' ' + shlex.quote(str(exposure.ROOT / 'eval/scripts/verify_gitea_exposure.py')) + ' --require-execution --phase probe'
        command = own_guard + "\nprintf 'XRAI_SAFE_SPY_WAS_CALLED'\n"
        result = subprocess.run([shutil.which('bash'), '-e', '-c', command], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'S01 blocks probe', result.stdout)
        self.assertNotIn(b'XRAI_SAFE_SPY_WAS_CALLED', result.stdout)

    def test_missing_download_guard(self):
        self.refused(self.workflow.replace('--require-execution --phase download', '--check-data'))

    def test_guard_after_setup_go(self):
        self.refused(self.workflow.replace('      - name: Require advisory-specific admission before affected Go execution', '      - uses: actions/setup-go@v6\n      - name: Require advisory-specific admission before affected Go execution', 1))

    def test_conditional_reference_guard_missing(self):
        self.refused(self.workflow.replace('          python eval/scripts/verify_gitea_exposure.py --require-execution --phase probe\n', ''))

    def test_conditional_download_guard(self):
        self.refused(self.workflow.replace('        run: python eval/scripts/verify_gitea_exposure.py --require-execution --phase download', '        if: always()\n        run: python eval/scripts/verify_gitea_exposure.py --require-execution --phase download', 1))

    def test_continue_on_error_does_not_bypass_guard(self):
        self.refused(self.workflow.replace('        run: python eval/scripts/verify_gitea_exposure.py --require-execution --phase download', '        continue-on-error: true\n        run: python eval/scripts/verify_gitea_exposure.py --require-execution --phase download', 1))

    def test_shell_override_refused(self):
        self.refused(self.workflow.replace('        shell: bash', '        shell: sh', 1))

    def test_probe_guard_with_suppressed_exit_refused(self):
        self.refused(self.workflow.replace('--require-execution --phase probe\n', '--require-execution --phase probe || true\n', 1))


if __name__ == '__main__':
    unittest.main()
