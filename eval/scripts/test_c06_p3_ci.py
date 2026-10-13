"""Counterproofs for authenticated native diff context archive; no ELF execution."""
import copy
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import reconcile_c06_p3_ci as c

HEAD='f'*40
RUN=1
ARTIFACT=2


def fixture():
    p=c.CONFIG
    run={'id':RUN,'head_sha':HEAD,'head_branch':'main','run_attempt':1,'path':p['workflow'],'event':'workflow_dispatch','status':'completed','conclusion':'success','repository':{'full_name':c.REPOSITORY},'html_url':f'https://github.com/{c.REPOSITORY}/actions/runs/{RUN}'}
    job={'name':p['job'],'run_id':RUN,'head_sha':HEAD,'run_attempt':1,'status':'completed','conclusion':'success','labels':['ubuntu-24.04'],'id':3,'html_url':f'https://github.com/{c.REPOSITORY}/actions/runs/{RUN}/job/3','started_at':'2026-10-13T15:00:00Z','completed_at':'2026-10-13T15:03:00Z','steps':[{'name':name,'number':i+1,'status':'completed','conclusion':'success','started_at':'2026-10-13T15:01:00Z','completed_at':'2026-10-13T15:02:00Z'} for i,name in enumerate(p['steps'])]}
    artifact={'id':ARTIFACT,'name':p['artifact'],'expired':False,'size_in_bytes':1,'digest':'sha256:'+'0'*64,'archive_download_url':f'https://api.github.com/repos/{c.REPOSITORY}/actions/artifacts/{ARTIFACT}/zip','workflow_run':{'id':RUN,'head_sha':HEAD,'head_branch':'main'},'created_at':'2026-10-13T15:01:30Z'}
    return run,{'total_count':1,'jobs':[job]},{'total_count':1,'artifacts':[artifact]}


def members():
    return {name:b'{}' for name in c.TOP|{'event/'+p for p in c.EVENT}}


def archive(files,extras=()):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,raw in [*files.items(),*extras]:z.writestr(name,raw)
    return out.getvalue()


class StructuralTests(unittest.TestCase):
    def test_exact_metadata_and_archive(self):
        c.metadata(*fixture(),RUN,HEAD,ARTIFACT)
        self.assertEqual(c.zip_members(archive(members())),members())
        self.assertEqual(len(members()),22)

    def test_duplicate_and_nonfinite(self):
        for raw in [b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):c.decode(raw)

    def test_identifier_types(self):
        for values in [(True,HEAD,ARTIFACT,1),(RUN,HEAD,True,1),(RUN,HEAD,ARTIFACT,True),(RUN,'F'*40,ARTIFACT,1)]:
            with self.subTest(values=values),self.assertRaises(ValueError):c.metadata(*fixture(),*values)

    def test_missing_extra_and_duplicate_zip(self):
        base=members();base.pop('design.json')
        for raw in [archive(base),archive(members(),[('foreign',b'')]),archive(members(),[('design.json',b'')])]:
            with self.subTest(raw=len(raw)),self.assertRaises(ValueError):c.zip_members(raw)

    def test_alias_absolute_control_and_drive_zip(self):
        for name in ['../outside','event/../outside','/outside','event//outside','event/./outside','event\\outside','C:/outside','event/tab\tname']:
            with self.subTest(name=name),self.assertRaises(ValueError):c.zip_members(archive(members(),[(name,b'')]))

    def test_symlink_fifo_chr_zip(self):
        for kind in [stat.S_IFLNK,stat.S_IFIFO,stat.S_IFCHR]:
            raw=io.BytesIO()
            with zipfile.ZipFile(raw,'w') as z:
                for name,value in members().items():z.writestr(name,value)
                info=zipfile.ZipInfo('event/foreign');info.create_system=3;info.external_attr=(kind|0o600)<<16;z.writestr(info,b'outside')
            with self.subTest(kind=kind),self.assertRaises(ValueError):c.zip_members(raw.getvalue())

    def test_collision_and_empty_directory_zip(self):
        for name in ['event','unowned/']:
            with self.subTest(name=name),self.assertRaises(ValueError):c.zip_members(archive(members(),[(name,b'')]))

    def test_member_and_count_caps(self):
        with patch.dict(c.CONFIG,{'event_member_bytes':1}),self.assertRaises(ValueError):c.zip_members(archive(members()))
        with patch.dict(c.CONFIG,{'total_bytes':1}),self.assertRaises(ValueError):c.zip_members(archive(members()))
        with patch.dict(c.CONFIG,{'max_members':1}),self.assertRaises(ValueError):c.zip_members(archive(members()))

    def test_export_is_fresh_regular_and_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'export';c.safe_export(members(),path)
            self.assertEqual(c.export_members(path),members())
            with self.assertRaises(ValueError):c.safe_export(members(),path)
            (path/'empty').mkdir()
            with self.assertRaises(ValueError):c.export_members(path)
            (path/'empty').rmdir();(path/'alias').symlink_to(path/'design.json')
            with self.assertRaises(ValueError):c.export_members(path)

    def test_original_digest_before_recomputation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            for name,value in zip(['run.json','jobs.json','artifacts.json'],fixture()):(path/name).write_text(json.dumps(value))
            (path/'original.zip').write_bytes(archive(members()))
            with patch.object(c,'_recompute',side_effect=AssertionError('must not execute')):
                with self.assertRaisesRegex(ValueError,'API digest'):c.reconcile(path,RUN,HEAD,ARTIFACT)

    def test_tainted_export_before_recomputation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);run,jobs,artifacts=fixture();raw=archive(members());a=artifacts['artifacts'][0];a['digest']='sha256:'+c.sha(raw);a['size_in_bytes']=len(raw)
            for name,value in [('run.json',run),('jobs.json',jobs),('artifacts.json',artifacts)]:(path/name).write_text(json.dumps(value))
            (path/'original.zip').write_bytes(raw);c.safe_export(members(),path/'export');(path/'export/design.json').write_bytes(b'wrong')
            with patch.object(c,'_recompute',side_effect=AssertionError('must not execute')):
                with self.assertRaisesRegex(ValueError,'export equals'):c.reconcile(path,RUN,HEAD,ARTIFACT)

    def test_owned_isolated_verifier_path(self):
        result=type('Result',(),{'returncode':0,'stderr':b'','stdout':b'{"verified":true}'})()
        with patch.object(c.subprocess,'run',return_value=result) as mock:
            self.assertTrue(c._recompute(Path('/untrusted'))['verified'])
        args=mock.call_args.args[0]
        self.assertEqual(args[1:3],['-I','-c']);self.assertEqual(args[5],str(c.ROOT/c.VERIFIER));self.assertEqual(args[-2:],['--output','/untrusted'])
        self.assertNotIn('/untrusted/native-bin/context-diff-spike',args)

    def test_actual_owned_design_ignores_parent_spy(self):
        with patch.dict('sys.modules',{'p3_diff_native_verify':object()}):result=c._recompute(Path('/untrusted'),True)
        self.assertFalse(result['native_run_performed']);self.assertEqual(result['accepted_cases'],21);self.assertEqual(result['python_decoder_negatives'],34)

    def test_failed_or_stderr_verifier_refused(self):
        for code,err,output in [(1,b'',b'{}'),(0,b'warning',b'{}'),(0,b'',b'')]:
            result=type('Result',(),{'returncode':code,'stderr':err,'stdout':output})()
            with patch.object(c.subprocess,'run',return_value=result),self.assertRaises(ValueError):c._recompute(Path('/none'))

    def test_real_statuses_not_test_name_words(self):
        good=b'test_skipped (Suite.test_skipped) ... ok\n\nRan 1 tests in 0.1s\n\nOK\n'
        self.assertTrue(c.successful_tests(good,1))
        for bad in [good.replace(b'... ok',b"... skipped 'not supplied'"),good.replace(b'... ok',b'... expected failure'),good.replace(b'OK\n',b'OK (skipped=1)\n'),good+b'OK\n']:
            with self.subTest(raw=bad):self.assertFalse(c.successful_tests(bad,1))


COUNTERPROOFS={
 'run_failure':lambda r,j,a:r.update(conclusion='failure'),
 'wrong_head':lambda r,j,a:r.update(head_sha='0'*40),
 'wrong_workflow':lambda r,j,a:r.update(path='.github/workflows/ci.yml'),
 'wrong_event':lambda r,j,a:r.update(event='push'),
 'wrong_attempt':lambda r,j,a:r.update(run_attempt=2),
 'wrong_repository':lambda r,j,a:r['repository'].update(full_name='other/repo'),
 'wrong_url':lambda r,j,a:r.update(html_url='https://example.com'),
 'job_wrong_run':lambda r,j,a:j['jobs'][0].update(run_id=2),
 'job_name':lambda r,j,a:j['jobs'][0].update(name='other'),
 'job_attempt':lambda r,j,a:j['jobs'][0].update(run_attempt=2),
 'job_failure':lambda r,j,a:j['jobs'][0].update(conclusion='failure'),
 'job_skip':lambda r,j,a:j['jobs'][0]['steps'][0].update(conclusion='skipped'),
 'job_host':lambda r,j,a:j['jobs'][0].update(labels=['macos-15']),
 'missing_step':lambda r,j,a:j['jobs'][0]['steps'].pop(),
 'duplicate_step':lambda r,j,a:j['jobs'][0]['steps'].append(copy.deepcopy(j['jobs'][0]['steps'][0])),
 'step_order':lambda r,j,a:j['jobs'][0]['steps'].reverse(),
 'bool_step':lambda r,j,a:j['jobs'][0]['steps'][0].update(number=True),
 'unavailable_job_page':lambda r,j,a:j.update(total_count=2),
 'artifact_expired':lambda r,j,a:a['artifacts'][0].update(expired=True),
 'artifact_name':lambda r,j,a:a['artifacts'][0].update(name='other'),
 'artifact_other_attempt_time':lambda r,j,a:a['artifacts'][0].update(created_at='2026-10-13T15:10:00Z'),
 'artifact_bad_timezone':lambda r,j,a:a['artifacts'][0].update(created_at='2026-10-13T15:01:30'),
 'artifact_wrong_run':lambda r,j,a:a['artifacts'][0]['workflow_run'].update(id=2),
 'artifact_wrong_head':lambda r,j,a:a['artifacts'][0]['workflow_run'].update(head_sha='0'*40),
 'artifact_missing_page':lambda r,j,a:a.update(total_count=2),
 'artifact_bool_size':lambda r,j,a:a['artifacts'][0].update(size_in_bytes=True),
 'artifact_download_url':lambda r,j,a:a['artifacts'][0].update(archive_download_url='https://example.com'),
 'artifact_digest':lambda r,j,a:a['artifacts'][0].update(digest='md5:'+'0'*32),
}


def counterfeit(change):
    def test(self):
        r,j,a=fixture();change(r,j,a)
        with self.assertRaises((ValueError,KeyError,TypeError)):c.metadata(r,j,a,RUN,HEAD,ARTIFACT)
    return test


for name,change in COUNTERPROOFS.items():setattr(StructuralTests,'test_metadata_'+name,counterfeit(change))


@unittest.skipUnless(os.environ.get('XRAI_C06_P3_CI_PROOF'),'actual authenticated original proof not supplied')
class ActualTests(unittest.TestCase):
    def test_original_actual_bundle(self):
        directory=Path(os.environ['XRAI_C06_P3_CI_PROOF']);run=c.decode((directory/'run.json').read_bytes());artifacts=c.decode((directory/'artifacts.json').read_bytes());a=next(a for a in artifacts['artifacts'] if a['name']==c.CONFIG['artifact'])
        result=c.reconcile(directory,run['id'],run['head_sha'],a['id'],run['run_attempt'])
        self.assertTrue(result['verified']);self.assertFalse(result['admitted']);self.assertEqual(result['exact_zip_export_files'],22)


if __name__=='__main__':unittest.main()
