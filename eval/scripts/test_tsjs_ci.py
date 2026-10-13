"""Offline metadata/ZIP attacks; actual CI bundle attacks are explicitly opt-in."""
import copy
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile
import reconcile_tsjs_ci as ci


HEAD = 'a' * 40
RUN = 1001
ARTIFACT = 1002


def fixture():
    run = {'id': RUN, 'head_sha': HEAD, 'head_branch': 'main', 'run_attempt': 1, 'path': ci.WORKFLOW, 'event': 'workflow_dispatch', 'status': 'completed', 'conclusion': 'success', 'repository': {'full_name': ci.REPOSITORY}, 'html_url': f'https://github.com/{ci.REPOSITORY}/actions/runs/{RUN}'}
    steps = [{'name': name, 'number': n + 1, 'status': 'completed', 'conclusion': 'success', 'started_at': '2026-10-12T22:00:00Z', 'completed_at': '2026-10-12T22:02:00Z'} for n, name in enumerate(ci.REQUIRED_STEP_ORDER)]
    job = {'name': ci.JOB, 'id': 1003, 'run_id': RUN, 'head_sha': HEAD, 'run_attempt': 1, 'status': 'completed', 'conclusion': 'success', 'labels': ['ubuntu-24.04'], 'html_url': f'https://github.com/{ci.REPOSITORY}/actions/runs/{RUN}/job/1003', 'steps': steps, 'started_at': '2026-10-12T21:59:00Z', 'completed_at': '2026-10-12T22:03:00Z'}
    artifact = {'id': ARTIFACT, 'name': ci.ARTIFACT, 'expired': False, 'digest': 'sha256:' + 'b' * 64, 'size_in_bytes': 1000, 'workflow_run': {'id': RUN, 'head_sha': HEAD, 'head_branch': 'main'}, 'archive_download_url': f'https://api.github.com/repos/{ci.REPOSITORY}/actions/artifacts/{ARTIFACT}/zip', 'created_at': '2026-10-12T22:01:00Z'}
    return run, {'total_count': 1, 'jobs': [job]}, {'total_count': 1, 'artifacts': [artifact]}


def archive(extra=None):
    target = io.BytesIO()
    with zipfile.ZipFile(target, 'w') as z:
        for name in ci.BUNDLE_FILES:
            z.writestr(name, b'fixture-data-only')
        z.writestr('event/receipt.json', b'{}')
        if extra:
            extra(z)
    return target.getvalue()


class Metadata(unittest.TestCase):
    def accepts(self, data):
        return ci.metadata(*data, RUN, HEAD, ARTIFACT)

    def rejects(self, mutate):
        data = fixture(); mutate(*data)
        with self.assertRaises(ValueError):
            self.accepts(data)

    def test_valid_context_only_fixture(self):
        job, artifact = self.accepts(fixture())
        self.assertEqual(job['id'], 1003); self.assertEqual(artifact['id'], ARTIFACT)

    def test_wrong_head(self):
        self.rejects(lambda r, j, a: r.__setitem__('head_sha', 'c' * 40))

    def test_wrong_repo(self):
        self.rejects(lambda r, j, a: r['repository'].__setitem__('full_name', 'other/repo'))

    def test_wrong_workflow(self):
        self.rejects(lambda r, j, a: r.__setitem__('path', '.github/workflows/ci.yml'))

    def test_failed_job(self):
        self.rejects(lambda r, j, a: j['jobs'][0].__setitem__('conclusion', 'failure'))

    def test_step_skipped(self):
        self.rejects(lambda r, j, a: j['jobs'][0]['steps'][4].__setitem__('conclusion', 'skipped'))

    def test_step_deleted(self):
        self.rejects(lambda r, j, a: j['jobs'][0]['steps'].pop(4))

    def test_step_reordered(self):
        def mutate(r, j, a):
            s = j['jobs'][0]['steps']; s[3], s[4] = s[4], s[3]
        self.rejects(mutate)

    def test_job_envelope_truncated(self):
        self.rejects(lambda r, j, a: j.__setitem__('total_count', 2))

    def test_expired_artifact(self):
        self.rejects(lambda r, j, a: a['artifacts'][0].__setitem__('expired', True))

    def test_artifact_wrong_run(self):
        self.rejects(lambda r, j, a: a['artifacts'][0]['workflow_run'].__setitem__('id', 2000))

    def test_artifact_wrong_attempt_time(self):
        self.rejects(lambda r, j, a: a['artifacts'][0].__setitem__('created_at', '2026-10-12T22:10:00Z'))

    def test_artifact_envelope_truncated(self):
        self.rejects(lambda r, j, a: a.__setitem__('total_count', 2))

    def test_run_flag_not_integer(self):
        r, j, a = fixture(); r['run_attempt'] = True
        with self.assertRaises(ValueError):
            self.accepts((r, j, a))


class ZipSafety(unittest.TestCase):
    def test_valid_data_bundle(self):
        self.assertEqual(len(ci.zip_members(archive())), 5)

    def rejects(self, extra):
        with self.assertRaises(ValueError):
            ci.zip_members(archive(extra))

    def test_traversal(self):
        self.rejects(lambda z: z.writestr('../outside', b'attack'))

    def test_alias(self):
        self.rejects(lambda z: z.writestr('event/./alias', b'attack'))

    def test_drive(self):
        self.rejects(lambda z: z.writestr('C:/outside', b'attack'))

    def test_duplicate(self):
        self.rejects(lambda z: z.writestr('event/receipt.json', b'{}'))

    def test_symlink(self):
        def extra(z):
            info = zipfile.ZipInfo('event/link'); info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, b'/etc/passwd')
        self.rejects(extra)

    def test_empty_directory(self):
        self.rejects(lambda z: z.writestr('event/unused/', b''))

    def test_file_directory_collision(self):
        def extra(z):
            z.writestr('event/collision', b'file'); z.writestr('event/collision/nested', b'other')
        self.rejects(extra)

    def test_safe_export_must_be_fresh(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):
                ci.safe_export({'file': b'data'}, Path(t))

    def test_export_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); (root / 'link').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):
                ci.directory_members(root)


@unittest.skipUnless(os.environ.get('XRAI_TSJS_CI_PROOF'), 'requires authentic original CI bundle')
class ActualBundle(unittest.TestCase):
    def setUp(self):
        self.original = Path(os.environ['XRAI_TSJS_CI_PROOF'])
        run = json.loads((self.original / 'run.json').read_text())
        artifacts = json.loads((self.original / 'artifacts.json').read_text())
        selected = next(a for a in artifacts['artifacts'] if a['name'] == ci.ARTIFACT)
        self.ids = (run['id'], run['head_sha'], selected['id'], run['run_attempt'])

    def test_authentic_bundle(self):
        self.assertTrue(ci.reconcile(self.original, *self.ids)['verified'])

    def rejects(self, mutate):
        import shutil
        with tempfile.TemporaryDirectory() as t:
            destination = Path(t) / 'proof'; shutil.copytree(self.original, destination)
            mutate(destination)
            with self.assertRaises(ValueError):
                ci.reconcile(destination, *self.ids)

    def test_zip_byte_changed(self):
        self.rejects(lambda p: (p / 'original.zip').write_bytes((p / 'original.zip').read_bytes() + b'changed'))

    def test_export_byte_changed(self):
        self.rejects(lambda p: (p / 'export/event/receipt.json').write_bytes(b'{}'))

    def test_export_extra_file(self):
        self.rejects(lambda p: (p / 'export/extra.json').write_bytes(b'{}'))

    def test_export_binary_removed(self):
        self.rejects(lambda p: (p / 'export/event/native-bin/tsjs-semantics').unlink())

    def test_api_hash_changed(self):
        def mutate(p):
            path = p / 'artifacts.json'; data = json.loads(path.read_text()); selected = next(a for a in data['artifacts'] if a['name'] == ci.ARTIFACT); selected['digest'] = 'sha256:' + '0' * 64; path.write_text(json.dumps(data))
        self.rejects(mutate)

    def test_api_step_skipped(self):
        def mutate(p):
            path = p / 'jobs.json'; data = json.loads(path.read_text()); data['jobs'][0]['steps'][4]['conclusion'] = 'skipped'; path.write_text(json.dumps(data))
        self.rejects(mutate)


if __name__ == '__main__':
    unittest.main()
