"""CI integration uses the actual owned corpus/ZIP snapshot; never a provider."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(os.environ.get('XRAI_ACTUAL_CAMPAIGN') == 'true', 'actual immutable CI checkout required')
class ActualCampaignSnapshot(unittest.TestCase):
    def test_actual_cli_refuses_with_four_reconciled_events(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, str(root/'eval/scripts/campaign_preflight.py'),
                                 '--intent', 'campaign_d1'], cwd=root, capture_output=True, timeout=240)
        self.assertEqual(result.returncode, 1, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stderr, b'')
        self.assertLess(len(result.stdout), 4*1024*1024)
        value = json.loads(result.stdout)
        self.assertIs(value['accepted'], False)
        self.assertIs(value['paid_provider_enabled'], False)
        self.assertEqual(value['external_calls'], 0)
        facts = value['factual_summary']
        self.assertEqual(facts['required_events_operationally_proven'], 4)
        self.assertEqual(facts['required_event_by_family'], {'Rust':1,'TSJS':1,'Python':1,'Go':1})
        self.assertEqual(facts['individual_eligible_tasks'], 8)
        self.assertEqual(facts['new_state_dossiers_individually_eligible'], 0)
        self.assertEqual(facts['admitted_tasks'], 0)
        self.assertEqual(facts['multi_module_planning_projection'], 19)
        self.assertNotIn('events', value['dimensions'])
        for reason in ['corpus','allocation','state_dossiers','provider','authorization','budget','containment']:
            self.assertIn(reason, value['dimensions'])
        manifest = value['snapshot_manifest']['files']
        for name in ['eval/qualification/l5-state-assignment-v2.json',
                     'docs/relatorios/logs/L5-C03/native-proof/original.zip',
                     'docs/relatorios/logs/L5-C04/presence-native-proof/original.zip']:
            self.assertIn(name, manifest)
        self.assertIn('admission_rows_sha256', value)


if __name__ == '__main__':
    unittest.main()
