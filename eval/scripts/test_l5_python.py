"""Own code/data-only checks. Never import or execute upstream project code."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import prepare_l5_python as prepare
import run_l5_python as run


class Preparation(unittest.TestCase):
    def test_complete_capture_and_floor(self):
        record=prepare.prepare(False)
        self.assertGreaterEqual(record['production_nonempty_lines'],50000)
        self.assertGreater(record['complete_regular_files'],1000)
        self.assertEqual(len(record['required_modules']),3)
        self.assertFalse(record['historical_bug_claim'])
        self.assertFalse(record['admitted'])

    def test_conservative_exclusions(self):
        for path in ['sklearn/tests/test_a.py','sklearn/externals/lib.py','sklearn/datasets/data.py','examples/demo.py','sklearn/generated.py']:
            data=b'# DO NOT EDIT\n' if 'generated' in path else b'hello\n'
            self.assertFalse(prepare.production(path,data))
        self.assertTrue(prepare.production('sklearn/preprocessing/_data.py',b'production\n'))

    def test_reference_preserves_third_needed_module(self):
        files=prepare.read_archive(prepare.CASE/'sources/base.tar.gz')
        reference=prepare.reference(files)
        self.assertEqual(reference['sklearn/pipeline.py'],files['sklearn/pipeline.py'])
        self.assertIn(b'return adapter.hstack(Xs)',files['sklearn/pipeline.py'])
        self.assertIn(b'np.ma.hstack(Xs)',reference['sklearn/utils/_set_output.py'])
        self.assertIn(b'if adapter.container_lib == "masked":',reference['sklearn/compose/_column_transformer.py'])

    def test_tampered_oracle_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            case=Path(tmp)/'case'
            shutil.copytree(prepare.CASE,case)
            (case/'oracles/probe.py').write_text('altered oracle')
            with patch.object(prepare,'CASE',case),self.assertRaisesRegex(ValueError,'capture receipt differs'):
                prepare.prepare(False)

    def test_tampered_reference_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            case=Path(tmp)/'case'
            shutil.copytree(prepare.CASE,case)
            (case/'oracles/reference.patch').write_text('altered patch')
            with patch.object(prepare,'CASE',case),self.assertRaisesRegex(ValueError,'reference differs'):
                prepare.prepare(False)

    def test_safe_archive_rejects_escape_duplicate_and_symlink(self):
        for names in [[('../escape','file')],[('same','file'),('same','file')],[('linked','symlink')]]:
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'archive.tar.gz'
                with tarfile.open(path,'w:gz') as tar:
                    for name,kind in names:
                        member=tarfile.TarInfo('scikit-learn-'+prepare.COMMIT+'/'+name)
                        if kind=='symlink':
                            member.type=tarfile.SYMTYPE;member.linkname='/etc/passwd';tar.addfile(member)
                        else:
                            member.size=1;tar.addfile(member,io.BytesIO(b'x'))
                with self.assertRaises(ValueError):prepare.read_archive(path)

    def test_materialization_only_reference_runtime_and_hidden_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'base'; ref=Path(tmp)/'ref'
            b=run.materialize(base,'base');h=run.materialize(ref,'reference')
            self.assertEqual(b['commit'],h['commit'])
            self.assertEqual(b['dependency_lock_sha256'],h['dependency_lock_sha256'])
            self.assertEqual((base/'pyproject.toml').read_bytes(),(ref/'pyproject.toml').read_bytes())
            self.assertEqual((base/'sklearn/pipeline.py').read_bytes(),(ref/'sklearn/pipeline.py').read_bytes())
            self.assertNotEqual((base/'sklearn/utils/_set_output.py').read_bytes(),(ref/'sklearn/utils/_set_output.py').read_bytes())
            self.assertEqual((base/'.xrai-probe.py').read_bytes(),(ref/'.xrai-probe.py').read_bytes())

    def test_wheel_rejects_escape_duplicate_symlink(self):
        for names in [[('../escape',False)],[('same',False),('same',False)],[('link',True)]]:
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'wheel.zip'
                with zipfile.ZipFile(path,'w') as archive:
                    for name,linked in names:
                        info=zipfile.ZipInfo(name)
                        info.external_attr=(0o120777 if linked else 0o100644)<<16
                        archive.writestr(info,b'x')
                with self.assertRaises(ValueError):run.wheel_files(path)

    def test_pinned_official_wheel_metadata(self):
        lock=json.loads((prepare.CASE/'setup.lock.json').read_text())
        self.assertEqual(lock['python'],'3.11.13')
        for row in lock['packages']:
            metadata=json.loads((prepare.CASE/'provenance'/f"{row['package']}-{row['version']}.pypi.json").read_text())
            matching=[x for x in metadata['urls'] if x['filename']==row['filename']]
            self.assertEqual(len(matching),1)
            self.assertEqual(matching[0]['digests']['sha256'],row['sha256'])
            self.assertEqual(matching[0]['size'],row['bytes'])
            self.assertEqual(matching[0]['url'],row['url'])

    def test_local_upstream_bootstrap_denied(self):
        with patch.object(run.platform,'system',return_value='Darwin'),self.assertRaisesRegex(ValueError,'pinned Linux'):
            run.bootstrap(Path('/not-created'),Path('/not-read'))


class ReceiptChecks(unittest.TestCase):
    def setup_receipts(self):
        raw=b''
        stream={'base64':'','sha256':run.sha(raw),'captured_bytes':0,'observed_bytes':0,'truncated':False}
        receipt={'execution_status':'error','exit_code':1,'stdout':dict(stream),'stderr':dict(stream)}
        report={'phase':'requirement','tests_run':3,'success':False,'module_origins':{'fixed':'source'},
                'tests':[{'id':n,'status':'error','error':"ValueError: output config must be valid, got masked"} for n in sorted(run.TEST_IDS['requirement'])]}
        return report,receipt

    def test_precise_baseline_failures_accept(self):
        report,receipt=self.setup_receipts()
        self.assertTrue(run.verify_behavior(report,receipt,'base','requirement',{'fixed':'source'}))

    def test_duplicate_and_renamed_ids_rejected(self):
        for change in ['duplicate','rename']:
            report,receipt=self.setup_receipts()
            report['tests'][0]['id']=report['tests'][1]['id'] if change=='duplicate' else '__main__.Other.test_wrong'
            self.assertFalse(run.verify_behavior(report,receipt,'base','requirement',{'fixed':'source'}))

    def test_truncation_timeout_stream_tamper_rejected(self):
        for mutation in ['truncation','timeout','digest','observed']:
            report,receipt=self.setup_receipts()
            if mutation=='truncation':receipt['stderr']['truncated']=True
            if mutation=='timeout':receipt['execution_status']='timeout'
            if mutation=='digest':receipt['stderr']['sha256']='0'*64
            if mutation=='observed':receipt['stderr']['observed_bytes']=3
            self.assertFalse(run.verify_behavior(report,receipt,'base','requirement',{'fixed':'source'}))

    def test_infrastructure_error_and_wrong_origin_rejected(self):
        report,receipt=self.setup_receipts()
        report['tests'][0]['error']='ImportError missing compiled extension'
        self.assertFalse(run.verify_behavior(report,receipt,'base','requirement',{'fixed':'source'}))
        report,receipt=self.setup_receipts()
        self.assertFalse(run.verify_behavior(report,receipt,'base','requirement',{'wrong':'wheel'}))


if __name__=='__main__':unittest.main()
