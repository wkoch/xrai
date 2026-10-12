"""Finite lifecycle regression checks for the incremental known-smoke probe."""
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from incremental import Session


class IncrementalLifecycleTests(unittest.TestCase):
    def session(self, code):
        session = Session.__new__(Session)
        session.profiles = tempfile.TemporaryDirectory(prefix='xrai-incremental-close-test-')
        session.process = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           start_new_session=True)
        session.selector = selectors.DefaultSelector()
        session._close_receipt = None
        return session

    def test_exited_child_is_not_signalled_and_original_error_survives(self):
        session = self.session('raise SystemExit(3)')
        session.process.wait(timeout=5)
        with patch('incremental.os.killpg', side_effect=PermissionError('stale group')) as signal_group:
            with self.assertRaisesRegex(RuntimeError, 'original INDEX failure'):
                try:
                    raise RuntimeError('original INDEX failure')
                finally:
                    receipt = session.close()
            signal_group.assert_not_called()
        self.assertEqual(receipt['status'], 'child_reaped')
        self.assertIs(session.close(), receipt)

    def test_live_child_is_killed_reaped_and_close_is_idempotent(self):
        session = self.session('import time; time.sleep(30)')
        receipt = session.close()
        self.assertEqual(receipt['status'], 'child_reaped')
        self.assertIsNotNone(session.process.poll())
        self.assertIs(session.close(), receipt)
        self.assertTrue(all(getattr(session.process, name).closed for name in ['stdin','stdout','stderr']))

    def test_denied_group_signal_falls_back_to_owned_live_child(self):
        session = self.session('import time; time.sleep(30)')
        with patch('incremental.os.killpg', side_effect=PermissionError('group denied')):
            receipt = session.close()
        self.assertEqual(receipt['status'], 'child_reaped')
        self.assertEqual(receipt['errors'], ['group denied'])
        self.assertIsNotNone(session.process.poll())


if __name__ == '__main__':
    unittest.main()
