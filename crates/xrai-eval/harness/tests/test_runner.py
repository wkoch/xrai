import copy
import json
import os
import socket
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import execute, payload, record, replay


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xrai-isolation-test-')
        self.root = Path(self.temp.name)
        self.workspace = self.root / 'arm-A'
        self.workspace.mkdir()
        self.other = self.root / 'arm-B'
        self.other.mkdir()
        (self.other / 'secret.txt').write_text('evaluator-only-secret')
        (self.workspace / 'public.txt').write_text('public-source')

    def tearDown(self):
        self.temp.cleanup()

    def run_cmd(self, command, **kwargs):
        return execute(command, self.workspace, **kwargs)

    def test_allowed_workspace_read_and_edit(self):
        result = self.run_cmd(['/bin/cat', 'public.txt'])
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual(result['stdout'], payload(b'public-source', 13))
        result = self.run_cmd(['/bin/sh', '-c', 'printf edited > edit.txt'])
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual((self.workspace / 'edit.txt').read_text(), 'edited')

    def test_cross_arm_and_evaluator_absolute_read_denied(self):
        for path in [self.other / 'secret.txt', Path(__file__).resolve()]:
            result = self.run_cmd(['/bin/cat', str(path)])
            self.assertEqual(result['status'], 'error', result)
            self.assertEqual(result['stdout']['captured_bytes'], 0)

    def test_symlink_escape_and_cross_arm_write_denied(self):
        (self.workspace / 'escape').symlink_to(self.other / 'secret.txt')
        result = self.run_cmd(['/bin/cat', 'escape'])
        self.assertEqual(result['status'], 'error', result)
        result = self.run_cmd(['/bin/sh', '-c', 'printf leaked > "$1"', 'sh', str(self.other / 'write.txt')])
        self.assertEqual(result['status'], 'error', result)
        self.assertFalse((self.other / 'write.txt').exists())

    def test_network_denied(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            listener.settimeout(.1)
            port = listener.getsockname()[1]
            result = self.run_cmd(['/usr/bin/curl', '--noproxy', '*', '--max-time', '.5', f'http://127.0.0.1:{port}'])
            self.assertEqual(result['status'], 'error', result)
            with self.assertRaises(TimeoutError):
                listener.accept()

    def test_host_environment_not_inherited(self):
        os.environ['XRAI_TEST_SECRET'] = 'not-for-agent'
        try:
            result = self.run_cmd(['/bin/sh', '-c', 'printf "%s" "${XRAI_TEST_SECRET-unset}"'])
        finally:
            del os.environ['XRAI_TEST_SECRET']
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual(result['stdout'], payload(b'unset', 5))

    def test_error_keeps_partial_output(self):
        result = self.run_cmd(['/bin/sh', '-c', 'printf partial; printf diagnosis >&2; exit 7'])
        self.assertEqual(result['status'], 'error', result)
        self.assertEqual(result['exit_code'], 7)
        self.assertEqual(result['stdout'], payload(b'partial', 7))
        self.assertEqual(result['stderr'], payload(b'diagnosis', 9))

    def test_timeout_kills_descendants_keeps_partial(self):
        result = self.run_cmd(['/bin/sh', '-c', 'printf partial; sleep 10 & wait'], timeout=.25)
        self.assertEqual(result['status'], 'timeout', result)
        self.assertLess(result['elapsed_seconds'], 3)
        self.assertEqual(result['stdout'], payload(b'partial', 7))

    def test_output_limit_is_bounded(self):
        result = self.run_cmd(['/bin/sh', '-c', 'while :; do printf 0123456789; done'], output_limit=100)
        self.assertEqual(result['status'], 'output_limit', result)
        self.assertEqual(result['stdout']['captured_bytes'], 100)
        self.assertTrue(result['stdout']['truncated'])

    def test_closed_pipes_do_not_disable_timeout(self):
        result = self.run_cmd(['/bin/sh', '-c', 'exec 1>&- 2>&-; sleep 2'], timeout=.15)
        self.assertEqual(result['status'], 'timeout', result)
        self.assertLess(result['elapsed_seconds'], 1)

    def test_detached_descendant_cannot_block_evaluator(self):
        # Finite descendant so even an escaping session consumes only two seconds.
        code = 'if (fork() == 0) { POSIX::setsid(); sleep 2; exit 0; } print "partial"; sleep 2;'
        result = self.run_cmd(['/usr/bin/perl', '-MPOSIX', '-e', code], timeout=.15)
        self.assertEqual(result['status'], 'timeout', result)
        self.assertLess(result['elapsed_seconds'], 1.2)

    def test_replay_preserves_binary_and_rejects_tampering(self):
        result = self.run_cmd(['/bin/sh', '-c', 'printf "\\377\\000CR\\r\\n"'])
        public = {'id': 'diagnostic', 'family': 'Rust', 'prompt': 'diagnostic'}
        value = record(public, 'test', [result], 0.1, self.workspace)
        self.assertIsNone(value['usage'])
        self.assertIsNone(value['measurement']['model_tokens'])
        self.assertEqual(replay(value), replay(json.loads(json.dumps(value))))
        broken = copy.deepcopy(value)
        broken['rounds'][0]['stdout']['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            replay(broken)
        for field in ['model','tokenizer','financial_cost']:
            broken=copy.deepcopy(value)
            broken[field]=0
            with self.assertRaises(ValueError):
                replay(broken)

    def test_evaluator_hash_does_not_follow_agent_symlink(self):
        (self.workspace/'escape').symlink_to(self.other/'secret.txt')
        value=record({'id':'diagnostic','family':'Rust','prompt':'diagnostic'},'test',[],0,self.workspace)
        # Changing the hidden target cannot change the public source inventory hash.
        (self.other/'secret.txt').write_text('changed-hidden-target')
        again=record({'id':'diagnostic','family':'Rust','prompt':'diagnostic'},'test',[],0,self.workspace)
        self.assertEqual(value['workspace_sha256'],again['workspace_sha256'])
        broken = copy.deepcopy(value)
        broken['measurement']['captured_bytes'] += 1
        with self.assertRaises(ValueError):
            replay(broken)

    def test_invalid_adapter_does_not_fall_back_to_unsandboxed(self):
        with self.assertRaises(ValueError):
            self.run_cmd(['cat', 'public.txt'])


if __name__ == '__main__':
    unittest.main()
