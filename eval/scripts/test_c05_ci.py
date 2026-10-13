"""Synthetic API/ZIP counterproofs; original authenticated bundle tests are opt-in."""
import copy
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import reconcile_c05_ci as c

HEAD='f' * 40
RUN=1
ARTIFACT=2


def synthetic_metadata(profile):
    p=c.config(profile)
    run={'id':RUN,'head_sha':HEAD,'head_branch':'main','run_attempt':1,'path':p['workflow'],
         'event':'workflow_dispatch','status':'completed','conclusion':'success',
         'repository':{'full_name':c.REPOSITORY},'html_url':f'https://github.com/{c.REPOSITORY}/actions/runs/{RUN}'}
    job={'name':p['job'],'run_id':RUN,'head_sha':HEAD,'run_attempt':1,'status':'completed','conclusion':'success',
         'labels':['ubuntu-24.04'],'id':3,'html_url':f'https://github.com/{c.REPOSITORY}/actions/runs/{RUN}/job/3',
         'started_at':'2026-10-13T15:00:00Z','completed_at':'2026-10-13T15:03:00Z',
         'steps':[{'name':name,'number':i+1,'status':'completed','conclusion':'success',
                   'started_at':'2026-10-13T15:01:00Z','completed_at':'2026-10-13T15:02:00Z'} for i,name in enumerate(p['steps'])]}
    artifact={'id':ARTIFACT,'name':p['artifact'],'expired':False,'size_in_bytes':1,'digest':'sha256:'+'0'*64,
              'archive_download_url':f'https://api.github.com/repos/{c.REPOSITORY}/actions/artifacts/{ARTIFACT}/zip',
              'workflow_run':{'id':RUN,'head_sha':HEAD,'head_branch':'main'},'created_at':'2026-10-13T15:01:30Z'}
    return run,{'total_count':1,'jobs':[job]},{'total_count':1,'artifacts':[artifact]}


def make_zip(members,extras=None):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,raw in members.items():archive.writestr(name,raw)
        for name,raw in extras or []:archive.writestr(name,raw)
    return out.getvalue()


def structural_members(profile):
    return {name:b'{}' for name in c.expected_files(profile)}


class MetadataAndZipTests(unittest.TestCase):
    def test_actual_statuses_not_words_in_test_names(self):
        good = b'test_chunk_skipped (Suite.test_chunk_skipped) ... ok\ntest_expected_failure_words (Suite.test_expected_failure_words) ... ok\n\n----------------------------------------------------------------------\nRan 2 tests in 0.001s\n\nOK\n'
        self.assertTrue(c.successful_tests(good,2))
        for bad in [good.replace(b'... ok',b"... skipped 'not supplied'",1),
                    good.replace(b'... ok',b'... expected failure',1),
                    good.replace(b'... ok',b'... ERROR',1),
                    good.replace(b'OK\n',b'OK (skipped=1)\n'),good+b'OK\n',
                    good.replace(b'test_chunk_skipped (Suite.test_chunk_skipped) ... ok\n',b'')]:
            with self.subTest(raw=bad):self.assertFalse(c.successful_tests(bad,2))
        self.assertFalse(c.successful_tests(good,1))

    def test_both_exact_metadata_profiles(self):
        for profile in c.PROFILES:
            with self.subTest(profile=profile):
                c.metadata(profile,*synthetic_metadata(profile),RUN,HEAD,ARTIFACT)

    def test_both_exact_zip_profiles(self):
        for profile in c.PROFILES:
            with self.subTest(profile=profile):
                members=structural_members(profile)
                self.assertEqual(c.zip_members(make_zip(members),profile),members)
                self.assertEqual(len(members),361 if profile=='tokens' else 24)

    def test_profile_is_explicit(self):
        for profile in ['unknown','',True,None]:
            with self.subTest(profile=profile),self.assertRaises(ValueError):c.config(profile)

    def test_profile_cannot_relabel_other_workflow(self):
        with self.assertRaises(ValueError):c.metadata('tokens',*synthetic_metadata('tsjs'),RUN,HEAD,ARTIFACT)

    def test_original_zip_profile_cannot_relabel(self):
        with self.assertRaises(ValueError):c.zip_members(make_zip(structural_members('tokens')),'tsjs')

    def test_typed_identifiers(self):
        for values in [(True,HEAD,ARTIFACT,1),(RUN,HEAD,True,1),(RUN,HEAD,ARTIFACT,True),(RUN,'F'*40,ARTIFACT,1)]:
            with self.subTest(values=values),self.assertRaises(ValueError):
                c.metadata('tsjs',*synthetic_metadata('tsjs'),*values)

    def test_duplicate_and_nonfinite_json(self):
        for raw in [b'{"id":1,"id":2}',b'{"id":NaN}']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):c.decode(raw)

    def test_zip_missing_file(self):
        for profile in c.PROFILES:
            members=structural_members(profile);members.pop('design.json')
            with self.subTest(profile=profile),self.assertRaises(ValueError):c.zip_members(make_zip(members),profile)

    def test_zip_extra_file(self):
        with self.assertRaises(ValueError):c.zip_members(make_zip(structural_members('tsjs'),[('extra.txt',b'')]),'tsjs')

    def test_zip_duplicate(self):
        with self.assertRaises(ValueError):c.zip_members(make_zip(structural_members('tsjs'),[('design.json',b'')]),'tsjs')

    def test_zip_alias_and_absolute(self):
        for name in ['../outside','event/../outside','/outside','event//outside','event/./outside','event\\outside','C:/outside','event/tab\tname']:
            with self.subTest(name=name),self.assertRaises(ValueError):c.zip_members(make_zip(structural_members('tsjs'),[(name,b'')]),'tsjs')

    def test_zip_symlink_special(self):
        for kind in [stat.S_IFLNK,stat.S_IFIFO,stat.S_IFCHR]:
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w') as archive:
                for name,raw in structural_members('tsjs').items():archive.writestr(name,raw)
                info=zipfile.ZipInfo('event/foreign');info.create_system=3;info.external_attr=(kind | 0o600)<<16
                archive.writestr(info,b'outside')
            with self.subTest(kind=kind),self.assertRaises(ValueError):c.zip_members(out.getvalue(),'tsjs')

    def test_zip_extra_empty_directory(self):
        with self.assertRaises(ValueError):c.zip_members(make_zip(structural_members('tsjs'),[('unowned/',b'')]),'tsjs')

    def test_zip_file_directory_collision(self):
        with self.assertRaises(ValueError):c.zip_members(make_zip(structural_members('tsjs'),[('event',b'')]),'tsjs')

    def test_profile_member_limit(self):
        members=structural_members('tokens');members['event/records/000.json']=b'x' * (512*1024+1)
        with self.assertRaises(ValueError):c.zip_members(make_zip(members),'tokens')

    def test_profile_member_total_count_limit(self):
        members=structural_members('tsjs')
        extras=[(f'event/extra{i}',b'') for i in range(65)]
        with self.assertRaises(ValueError):c.zip_members(make_zip(members,extras),'tsjs')

    def test_safe_export_requires_fresh_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'export'
            c.safe_export(structural_members('tsjs'),path)
            self.assertEqual(c.export_members(path,'tsjs'),structural_members('tsjs'))
            with self.assertRaises(ValueError):c.safe_export(structural_members('tsjs'),path)

    def test_export_symlink_and_extra_directory_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'export'; c.safe_export(structural_members('tsjs'),path)
            (path/'empty').mkdir()
            with self.assertRaises(ValueError):c.export_members(path,'tsjs')
            (path/'empty').rmdir();(path/'linked').symlink_to(path/'design.json')
            with self.assertRaises(ValueError):c.export_members(path,'tsjs')

    def test_token_measurement_cannot_use_wrong_python_or_counter(self):
        with patch.object(c.sys,'version_info',(3,15,0)),patch.object(c.subprocess,'run',side_effect=AssertionError('no actual interpreter')):
            with self.assertRaisesRegex(ValueError,'3.13.13'):c._recompute('tokens',Path('/none'))

    def test_verifier_launcher_is_owned_isolated_not_artifact(self):
        result=type('Result',(),{'returncode':0,'stderr':b'','stdout':b'{"verified":true}'})()
        with patch.object(c.subprocess,'run',return_value=result) as run:
            c._recompute('tsjs',Path('/untrusted/event'))
        args=run.call_args.args[0]
        self.assertEqual(args[:3],[sys.executable,'-I','-c'])
        self.assertEqual(args[4],str(c.ROOT/'eval/scripts'))
        self.assertEqual(args[5],str(c.ROOT/c.config('tsjs')['verifier']))
        self.assertEqual(args[-2:],['--output','/untrusted/event'])

    def test_verifier_failure_never_uses_cached_success(self):
        result=type('Result',(),{'returncode':1,'stderr':b'fixed runtime absent','stdout':b'{"verified":true}'})()
        with patch.object(c.subprocess,'run',return_value=result),self.assertRaises(ValueError):c._recompute('tsjs',Path('/none'))

    def test_actual_own_design_ignores_parent_module_spy(self):
        fake=type('Fake',(),{'__file__':'/untrusted/verifier.py','assets':lambda:(_ for _ in ()).throw(AssertionError('parent cache leaked'))})()
        with patch.dict(sys.modules,{'verify_tsjs_semantic_session':fake}):
            result=c._recompute('tsjs',Path('/none'),design=True)
        self.assertTrue(result['verified']);self.assertFalse(result['native_executed'])

    def test_original_zip_digest_enforced_before_recompute(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory); run,jobs,artifacts=synthetic_metadata('tsjs')
            for name,value in [('run.json',run),('jobs.json',jobs),('artifacts.json',artifacts)]:
                (path/name).write_text(json.dumps(value))
            (path/'original.zip').write_bytes(make_zip(structural_members('tsjs')))
            with patch.object(c,'_recompute',side_effect=AssertionError('not before ZIP check')):
                with self.assertRaisesRegex(ValueError,'API digest'):c.reconcile(path,'tsjs',RUN,HEAD,ARTIFACT)

    def test_supplied_tainted_export_rejected_before_recompute(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory); run,jobs,artifacts=synthetic_metadata('tsjs')
            members=structural_members('tsjs'); raw=make_zip(members)
            a=artifacts['artifacts'][0];a['digest']='sha256:'+c.sha(raw);a['size_in_bytes']=len(raw)
            for name,value in [('run.json',run),('jobs.json',jobs),('artifacts.json',artifacts)]:
                (path/name).write_text(json.dumps(value))
            (path/'original.zip').write_bytes(raw);c.safe_export(members,path/'export')
            (path/'export/design.json').write_text('{"tainted":true}')
            with patch.object(c,'_recompute',side_effect=AssertionError('not before exact export check')):
                with self.assertRaisesRegex(ValueError,'export equals'):c.reconcile(path,'tsjs',RUN,HEAD,ARTIFACT)


META_COUNTERPROOFS={
    'run_failure':lambda r,j,a:r.update(conclusion='failure'),
    'run_attempt':lambda r,j,a:r.update(run_attempt=2),
    'wrong_head':lambda r,j,a:r.update(head_sha='0'*40),
    'wrong_repository':lambda r,j,a:r['repository'].update(full_name='other/repo'),
    'wrong_url':lambda r,j,a:r.update(html_url='https://example.com'),
    'job_wrong_run':lambda r,j,a:j['jobs'][0].update(run_id=2),
    'job_name':lambda r,j,a:j['jobs'][0].update(name='other'),
    'job_attempt':lambda r,j,a:j['jobs'][0].update(run_attempt=2),
    'job_bool_id':lambda r,j,a:j['jobs'][0].update(id=True),
    'job_failure':lambda r,j,a:j['jobs'][0].update(conclusion='failure'),
    'job_skip':lambda r,j,a:j['jobs'][0]['steps'][0].update(conclusion='skipped'),
    'missing_step':lambda r,j,a:j['jobs'][0]['steps'].pop(),
    'duplicate_step':lambda r,j,a:j['jobs'][0]['steps'].append(copy.deepcopy(j['jobs'][0]['steps'][0])),
    'step_order':lambda r,j,a:j['jobs'][0]['steps'].reverse(),
    'bool_step':lambda r,j,a:j['jobs'][0]['steps'][0].update(number=True),
    'unavailable_job_page':lambda r,j,a:j.update(total_count=2),
    'artifact_expired':lambda r,j,a:a['artifacts'][0].update(expired=True),
    'artifact_name':lambda r,j,a:a['artifacts'][0].update(name='wrong'),
    'artifact_other_attempt_time':lambda r,j,a:a['artifacts'][0].update(created_at='2026-10-13T15:10:00Z'),
    'artifact_bad_timezone':lambda r,j,a:a['artifacts'][0].update(created_at='2026-10-13T15:01:30'),
    'artifact_wrong_run':lambda r,j,a:a['artifacts'][0]['workflow_run'].update(id=2),
    'artifact_wrong_head':lambda r,j,a:a['artifacts'][0]['workflow_run'].update(head_sha='0'*40),
    'artifact_missing_page':lambda r,j,a:a.update(total_count=2),
    'artifact_bool_size':lambda r,j,a:a['artifacts'][0].update(size_in_bytes=True),
    'artifact_download_url':lambda r,j,a:a['artifacts'][0].update(archive_download_url='https://example.com'),
    'artifact_digest':lambda r,j,a:a['artifacts'][0].update(digest='md5:'+'0'*32),
}


def metadata_test(change):
    def run(self):
        for profile in c.PROFILES:
            r,j,a=synthetic_metadata(profile);change(r,j,a)
            with self.subTest(profile=profile),self.assertRaises((ValueError,KeyError,TypeError)):
                c.metadata(profile,r,j,a,RUN,HEAD,ARTIFACT)
    return run

for name,change in META_COUNTERPROOFS.items():
    setattr(MetadataAndZipTests,'test_metadata_counterproof_'+name,metadata_test(change))


@unittest.skipUnless(os.environ.get('XRAI_C05_CI_PROOF'),'actual original authenticated C05 proof not supplied')
class ActualBundleTests(unittest.TestCase):
    def test_actual_original_bundle_recomposed(self):
        directory=Path(os.environ['XRAI_C05_CI_PROOF']); profile=os.environ['XRAI_C05_CI_PROFILE']
        run=c.decode((directory/'run.json').read_bytes()); artifacts=c.decode((directory/'artifacts.json').read_bytes())
        selected=next(a for a in artifacts['artifacts'] if a['name']==c.config(profile)['artifact'])
        result=c.reconcile(directory,profile,run['id'],run['head_sha'],selected['id'],run['run_attempt'])
        self.assertTrue(result['verified']);self.assertFalse(result['global_admission'])
        self.assertEqual(result['exact_zip_export_files'],361 if profile=='tokens' else 24)


if __name__=='__main__':unittest.main()
