#!/usr/bin/env python3
"""Data-only ZIP closure counterchecks; mutates disposable copies only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
SCRIPT = BASE/'reconcile_corpus.py'
EXPORT = BASE/'ci-fourth'
COMMIT = 'c48b5993550fd258f1efe5677704a59d9eb73de0'
RUN = 38283109016
spec = importlib.util.spec_from_file_location('corpus_reconcile_closure', SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class ZipClosure(unittest.TestCase):
    def copy_export(self, directory):
        copied = Path(directory)/'export'
        shutil.copytree(EXPORT, copied)
        return copied

    def test_original_complete_ci4_pair_passes(self):
        report = check.reconcile(EXPORT, COMMIT, RUN)
        self.assertTrue(report['verified'])
        self.assertFalse(report['admitted'])
        self.assertFalse(report['competitive_runs_allowed'])
        for family, count in [('rust',25),('js',12)]:
            self.assertTrue(report['export_provenance'][family]['complete_file_set_verified'])
            self.assertTrue(report['export_provenance'][family]['zip_bytes_independently_verified'])
            self.assertEqual(report['export_provenance'][family]['file_count'], count)

    def test_extra_export_file_not_in_zip_rejected(self):
        with tempfile.TemporaryDirectory(prefix='extra-',dir=HERE) as temporary:
            export = self.copy_export(temporary)
            (export/'js/base/unbound-extra.json').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'family export file set differs'):
                check.reconcile(export, COMMIT, RUN, 'js')

    def test_required_summary_outside_zip_rejected(self):
        with tempfile.TemporaryDirectory(prefix='missing-',dir=HERE) as temporary:
            export = self.copy_export(temporary)
            archive = export/'l5-real-rust.zip'
            # Keep a required export file outside the ZIP while coherently updating
            # supplied metadata. This countercheck does not claim GitHub authenticates
            # the modified ZIP: it tests the verifier after the digest comparison.
            with zipfile.ZipFile(archive) as tree:
                retained = [(name,tree.read(name)) for name in tree.namelist() if name != 'summary.json']
            with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as tree:
                for name, raw in retained: tree.writestr(name,raw)
            artifacts = json.loads((export/'artifacts.json').read_text())
            record = next(a for a in artifacts['artifacts'] if a['name'] == 'l5-real-rust')
            record['digest'] = 'sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'family export file set differs'):
                check.reconcile(export,COMMIT,RUN,'rust',{'artifacts.json':json.dumps(artifacts).encode()})

    def test_symlink_extra_export_entry_rejected(self):
        with tempfile.TemporaryDirectory(prefix='symlink-',dir=HERE) as temporary:
            export = self.copy_export(temporary)
            (export/'rust/linked-summary.json').symlink_to('summary.json')
            with self.assertRaisesRegex(ValueError, 'symlink or nonregular'):
                check.reconcile(export,COMMIT,RUN,'rust')


if __name__ == '__main__':
    unittest.main()
