"""Own offline extraction tests; no captured JavaScript executes."""
import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'run_l5_js.py'
spec = importlib.util.spec_from_file_location('l5_js_bootstrap', MODULE_PATH)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xrai-js-bootstrap-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir()
        self.original_case = runner.CASE
        self.addCleanup(setattr, runner, 'CASE', self.original_case)
        runner.CASE = self.root / 'case'
        runner.CASE.mkdir()
        shutil.copytree(self.original_case/'setup', runner.CASE/'setup')
        shutil.copyfile(self.original_case/'capture.json', runner.CASE/'capture.json')
        capture = json.loads((runner.CASE/'capture.json').read_text())
        source = capture['snapshots']['base']
        with tarfile.open(runner.ROOT/source['archive']) as tree:
            lock = tree.extractfile('react-'+source['commit']+'/yarn.lock').read()
        (self.workspace/'yarn.lock').write_bytes(lock)
        script = self.workspace/'scripts/yarn/downloadReactIsForPrettyFormat.js'
        script.parent.mkdir(parents=True)
        shutil.copyfile(runner.CASE/'setup/upstream-downloadReactIsForPrettyFormat.js', script)
        self.pretty = self.workspace/'node_modules/pretty-format'
        self.pretty.mkdir(parents=True)
        self.package = self.pretty/'package.json'
        self.package.write_text(json.dumps({'name':'pretty-format','version':'26.6.2','dependencies':{'react-is':'^17.0.1'}}))
        self.sentinel = self.workspace/'packages/production.js'
        self.sentinel.parent.mkdir()
        self.sentinel.write_text('unchanged production\n')

    def test_exact_offline_idempotent_extraction(self):
        first = runner.bootstrap(self.workspace)
        second = runner.bootstrap(self.workspace)
        self.assertEqual(first, second)
        self.assertFalse(first['network_used'])
        self.assertEqual(first['lock_before'], first['lock_after'])
        installed = json.loads((self.pretty/'node_modules/react-is/package.json').read_text())
        self.assertEqual(installed['version'], '17.0.2')
        self.assertEqual(self.sentinel.read_text(), 'unchanged production\n')

    def test_archive_tamper_fails_before_install(self):
        archive = runner.CASE/'setup/react-is-17.0.2.tgz'
        archive.write_bytes(archive.read_bytes()+b'tampered')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            runner.bootstrap(self.workspace)
        self.assertFalse((self.pretty/'node_modules').exists())

    def test_wrong_pretty_format_dependency_fails(self):
        package = json.loads(self.package.read_text())
        package['dependencies']['react-is'] = '^19.0.0'
        self.package.write_text(json.dumps(package))
        with self.assertRaisesRegex(ValueError, 'dependency differs'):
            runner.bootstrap(self.workspace)
        self.assertFalse((self.pretty/'node_modules').exists())

    def test_lock_tamper_fails_before_install(self):
        (self.workspace/'yarn.lock').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'lock differs'):
            runner.bootstrap(self.workspace)
        self.assertFalse((self.pretty/'node_modules').exists())

    def test_symlink_target_escape_fails_without_writing(self):
        target_parent = self.pretty/'node_modules'
        target_parent.mkdir()
        outside = self.root/'outside'
        outside.mkdir()
        (target_parent/'react-is').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'not contained'):
            runner.bootstrap(self.workspace)
        self.assertEqual(list(outside.iterdir()), [])

    def test_installed_tamper_fails_without_repair(self):
        runner.bootstrap(self.workspace)
        entry = self.pretty/'node_modules/react-is/index.js'
        entry.write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'differs from pinned'):
            runner.bootstrap(self.workspace)
        self.assertEqual(entry.read_text(), 'tampered')


if __name__ == '__main__':
    unittest.main()
