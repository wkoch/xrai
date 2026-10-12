"""Mutation counterchecks for our source guard; never execute captured JS."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'verify_l5_js_oracle.py'
spec = importlib.util.spec_from_file_location('l5_js_oracle', path)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class OracleGuardTests(unittest.TestCase):
    def setUp(self):
        self.oracle = (guard.CASE/'oracles/XraiExternalStoreContract-test.js').read_text()
        self.natural = (guard.CASE/'agent/input.md').read_text()

    def test_frozen_checkpoint_and_control(self):
        result = guard.verify_text(self.oracle, self.natural)
        self.assertTrue(result['source_guard_verified'])
        self.assertFalse(result['runtime_behavior_verified'])

    def test_scheduler_drain_rejected(self):
        changed = self.oracle.replace('await Promise.resolve();', 'Scheduler.unstable_flushAllWithoutAsserting();', 1)
        with self.assertRaisesRegex(ValueError, 'drains scheduler'):
            guard.verify_text(changed, self.natural)

    def test_forced_sync_rejected(self):
        changed = self.oracle.replace("React.startTransition(() => source.publish('next'));", "ReactNoop.flushSync(() => source.publish('next'));")
        with self.assertRaisesRegex(ValueError, 'forces'):
            guard.verify_text(changed, self.natural)

    def test_act_wrapped_notification_rejected(self):
        changed = self.oracle.replace("React.startTransition(() => source.publish('next'));", "await act(() => React.startTransition(() => source.publish('next')));")
        with self.assertRaises(ValueError):
            guard.verify_text(changed, self.natural)

    def test_weakened_negative_control_rejected(self):
        changed = self.oracle.replace("expect(root).toMatchRenderedOutput('start');", "expect(root).toMatchRenderedOutput('deferred');")
        with self.assertRaisesRegex(ValueError, 'negative control'):
            guard.verify_text(changed, self.natural)

    def test_same_stack_request_not_reinterpreted(self):
        with self.assertRaisesRegex(ValueError, 'same-stack'):
            guard.verify_text(self.oracle, self.natural+' Complete before publish returns.')

    def test_unrelated_warning_expectation_rejected(self):
        changed = self.oracle.replace('An update to Stateful inside a test was not wrapped in act', 'Any warning')
        with self.assertRaisesRegex(ValueError, 'negative control'):
            guard.verify_text(changed, self.natural)

    def test_global_warning_suppression_rejected(self):
        with self.assertRaisesRegex(ValueError, 'globally suppress'):
            guard.verify_text(self.oracle+'\nconsole.error = () => {};\n', self.natural)


if __name__ == '__main__':
    unittest.main()
