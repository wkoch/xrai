"""The vertical evidence path must never relax competitive admission."""
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import tarfile
import unittest

from test_qualification import synthetic_rows
from materialize_task import source_files
from prepare_vertical_sources import regular_tree
from verify_qualified import validate
from verify_vertical import validate_vertical


class VerticalTests(unittest.TestCase):
    def cases(self):
        return [r for r in synthetic_rows() if r['kind'] == 'correction'
                and r['id'].endswith('-0')]

    def test_partial_success_cannot_admit_campaign(self):
        rows = self.cases()
        self.assertEqual(validate_vertical(rows, check_artifacts=False)['candidate_tasks'], 4)
        self.assertFalse(validate_vertical(rows, check_artifacts=False)['competitive_runs_allowed'])
        with self.assertRaisesRegex(ValueError, 'exactly 32'):
            validate(rows, check_artifacts=False)

    def test_partial_requires_one_per_family_and_full_evidence(self):
        for mutate in [lambda r: r.pop(), lambda r: r.append(copy.deepcopy(r[0])),
                       lambda r: r[0]['review_receipt'].update(status='pending'),
                       lambda r: r[0]['probe_receipt']['baseline'].update(exit_code=127),
                       lambda r: r[0]['review_receipt'].update(oracle_sha256='b' * 64)]:
            rows = self.cases()
            mutate(rows)
            with self.assertRaises(ValueError):
                validate_vertical(rows, check_artifacts=False)

    def test_compressed_inventory_is_bound_to_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = gzip.compress(json.dumps([{'path': 'a', 'bytes': 2}]).encode(), mtime=0)
            (root / 'files.gz').write_bytes(data)
            snapshot = {'files_artifact': {'path': 'files.gz', 'sha256': hashlib.sha256(data).hexdigest()}}
            self.assertEqual(source_files(snapshot, root=root)[0]['path'], 'a')
            (root / 'files.gz').write_bytes(data + b'x')
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                source_files(snapshot, root=root)

    def tree(self, entries):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode='w:gz') as tree:
            for name, data, target in entries:
                info = tarfile.TarInfo('upstream/' + name)
                info.mode = 0o644
                if target is not None:
                    info.type, info.linkname = tarfile.SYMTYPE, target
                    tree.addfile(info)
                else:
                    info.size = len(data)
                    tree.addfile(info, io.BytesIO(data))
        return out.getvalue()

    def test_internal_link_materialization_has_explicit_receipt(self):
        files, links = regular_tree(self.tree([('a', b'full source', None), ('docs/link', b'', '../a')]))
        self.assertEqual(files['docs/link'][0], b'full source')
        self.assertEqual(links[0]['path'], 'docs/link')
        self.assertEqual(len(files), 2)

    def test_links_cannot_escape_or_cycle_or_target_directories(self):
        for entries in [[('a', b'', '../../outside')], [('a', b'', '/outside')],
                        [('a', b'', 'b'), ('b', b'', 'a')], [('a', b'', 'directory')]]:
            with self.assertRaises(ValueError):
                regular_tree(self.tree(entries))
