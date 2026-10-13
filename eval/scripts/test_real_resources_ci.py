"""Own metadata/container contraproofs. Illustrative binaries never become native proof."""
from copy import deepcopy
import datetime
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

import reconcile_real_resources_ci as c

RUN=101
HEAD='a'*40
IDS={host:202+i for i,host in enumerate(c.HOSTS)}


def utc(seconds):
    return (datetime.datetime(2026,10,13,tzinfo=datetime.timezone.utc)+datetime.timedelta(seconds=seconds)).isoformat().replace('+00:00','Z')


def envelopes():
    run={'id':RUN,'name':c.WORKFLOW_NAME,'head_sha':HEAD,'head_branch':'main','run_attempt':1,
        'path':c.WORKFLOW,'event':'workflow_dispatch','status':'completed','conclusion':'success',
        'repository':{'full_name':c.REPOSITORY},'html_url':f'https://github.com/{c.REPOSITORY}/actions/runs/{RUN}'}
    jobs=[];artifacts=[]
    for i,(host,(runner,_)) in enumerate(c.HOSTS.items()):
        jobid=303+i
        job={'id':jobid,'name':f'C04 real resources {host}','run_id':RUN,'head_sha':HEAD,'run_attempt':1,
            'started_at':utc(0),'completed_at':utc(100),'status':'completed','conclusion':'success','labels':[runner],
            'html_url':f'https://github.com/{c.REPOSITORY}/actions/runs/{RUN}/job/{jobid}',
            'steps':[{'name':name,'number':number+1,'status':'completed','conclusion':'success',
                'started_at':utc(number*2),'completed_at':utc(number*2+1)} for number,name in enumerate(c.REQUIRED_STEP_ORDER)]}
        jobs.append(job)
        artifact={'id':IDS[host],'name':f'c04-real-resources-{host}','expired':False,'digest':'sha256:'+'0'*64,
            'size_in_bytes':100,'created_at':job['steps'][-1]['completed_at'],
            'workflow_run':{'id':RUN,'head_sha':HEAD,'head_branch':'main'},
            'archive_download_url':f'https://api.github.com/repos/{c.REPOSITORY}/actions/artifacts/{IDS[host]}/zip'}
        artifacts.append(artifact)
    return run,{'total_count':2,'jobs':jobs},{'total_count':2,'artifacts':artifacts}


def archive(members=None,extra=()):
    members={name:b'{}' for name in c.BUNDLE_FILES} if members is None else members
    buffer=io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,raw in members.items():z.writestr(name,raw)
            for name,raw in extra:z.writestr(name,raw)
    return buffer.getvalue()


class MetadataTests(unittest.TestCase):
    def setUp(self):self.run,self.jobs,self.artifacts=envelopes()
    def checked(self):return c.metadata(self.run,self.jobs,self.artifacts,RUN,HEAD,IDS)
    def reject(self):
        with self.assertRaises((ValueError,KeyError,TypeError)):self.checked()
    def test_exact_two_host_illustrative_structure(self):self.assertEqual(set(self.checked()),set(c.HOSTS))
    def test_failed_run(self):self.run['conclusion']='failure';self.reject()
    def test_run_boolean_id(self):self.run['id']=True;self.reject()
    def test_run_boolean_attempt(self):self.run['run_attempt']=True;self.reject()
    def test_other_attempt(self):self.run['run_attempt']=2;self.reject()
    def test_wrong_head(self):self.run['head_sha']='b'*40;self.reject()
    def test_wrong_branch(self):self.run['head_branch']='other';self.reject()
    def test_wrong_repository(self):self.run['repository']['full_name']='other/xrai';self.reject()
    def test_wrong_workflow_path(self):self.run['path']='.github/workflows/ci.yml';self.reject()
    def test_wrong_workflow_name(self):self.run['name']='different';self.reject()
    def test_wrong_event(self):self.run['event']='push';self.reject()
    def test_wrong_run_url(self):self.run['html_url']='https://example.test/101';self.reject()
    def test_incomplete_job_page(self):self.jobs['total_count']=3;self.reject()
    def test_boolean_job_count(self):self.jobs['total_count']=True;self.reject()
    def test_missing_host_job(self):self.jobs['jobs'].pop();self.reject()
    def test_duplicate_job_identity(self):self.jobs['jobs'][1]['id']=self.jobs['jobs'][0]['id'];self.reject()
    def test_renamed_job(self):self.jobs['jobs'][0]['name']='new experiment';self.reject()
    def test_failed_other_host(self):self.jobs['jobs'][1]['conclusion']='failure';self.reject()
    def test_missing_job_attempt(self):del self.jobs['jobs'][0]['run_attempt'];self.reject()
    def test_wrong_job_run(self):self.jobs['jobs'][0]['run_id']=999;self.reject()
    def test_boolean_job_run(self):self.jobs['jobs'][0]['run_id']=True;self.reject()
    def test_wrong_job_head(self):self.jobs['jobs'][0]['head_sha']='b'*40;self.reject()
    def test_wrong_runner(self):self.jobs['jobs'][0]['labels']=['macos-15'];self.reject()
    def test_wrong_job_url(self):self.jobs['jobs'][0]['html_url']='https://example.test';self.reject()
    def test_failed_step(self):self.jobs['jobs'][0]['steps'][2]['conclusion']='failure';self.reject()
    def test_skipped_step(self):self.jobs['jobs'][1]['steps'][2]['conclusion']='skipped';self.reject()
    def test_missing_step(self):self.jobs['jobs'][0]['steps'].pop(3);self.reject()
    def test_unknown_step(self):self.jobs['jobs'][0]['steps'][2]['name']='arbitrary';self.reject()
    def test_duplicate_step(self):self.jobs['jobs'][0]['steps'][3]['name']=self.jobs['jobs'][0]['steps'][2]['name'];self.reject()
    def test_reordered_step(self):s=self.jobs['jobs'][0]['steps'];s[2]['name'],s[3]['name']=s[3]['name'],s[2]['name'];self.reject()
    def test_boolean_step_number(self):self.jobs['jobs'][0]['steps'][0]['number']=True;self.reject()
    def test_duplicate_step_number(self):self.jobs['jobs'][0]['steps'][1]['number']=1;self.reject()
    def test_outside_job_step_time(self):self.jobs['jobs'][0]['steps'][0]['started_at']=utc(-1);self.reject()
    def test_previous_attempt_artifact_time(self):self.artifacts['artifacts'][0]['created_at']=utc(-1);self.reject()
    def test_naive_timestamp(self):self.artifacts['artifacts'][0]['created_at']='2026-10-13T00:00:16';self.reject()
    def test_offset_timestamp(self):self.artifacts['artifacts'][0]['created_at']='2026-10-13T00:00:16+03:00';self.reject()
    def test_incomplete_artifact_page(self):self.artifacts['total_count']=3;self.reject()
    def test_extra_artifact(self):self.artifacts['artifacts'].append(deepcopy(self.artifacts['artifacts'][0]));self.reject()
    def test_expired_artifact(self):self.artifacts['artifacts'][0]['expired']=True;self.reject()
    def test_numeric_expired(self):self.artifacts['artifacts'][0]['expired']=0;self.reject()
    def test_wrong_artifact_name(self):self.artifacts['artifacts'][0]['name']='different';self.reject()
    def test_swapped_artifact_hosts(self):a=self.artifacts['artifacts'];a[0]['name'],a[1]['name']=a[1]['name'],a[0]['name'];self.reject()
    def test_missing_original_digest(self):self.artifacts['artifacts'][0]['digest']='';self.reject()
    def test_unbounded_zip_size(self):self.artifacts['artifacts'][0]['size_in_bytes']=c.MAX_ZIP_BYTES+1;self.reject()
    def test_boolean_zip_size(self):self.artifacts['artifacts'][0]['size_in_bytes']=True;self.reject()
    def test_wrong_artifact_run(self):self.artifacts['artifacts'][0]['workflow_run']['id']=999;self.reject()
    def test_wrong_artifact_head(self):self.artifacts['artifacts'][0]['workflow_run']['head_sha']='b'*40;self.reject()
    def test_wrong_download_url(self):self.artifacts['artifacts'][0]['archive_download_url']='https://evil.test/zip';self.reject()
    def test_explicit_boolean_provenance(self):
        for args in ((True,HEAD,IDS,1),(RUN,HEAD,IDS,True),(RUN,HEAD,{**IDS,next(iter(IDS)):True},1)):
            with self.subTest(args=args),self.assertRaises(ValueError):c.metadata(self.run,self.jobs,self.artifacts,*args)
    def test_explicit_artifact_map_closure(self):
        for ids in ({},dict.fromkeys(c.HOSTS,202),{**IDS,'extra':204}):
            with self.subTest(ids=ids),self.assertRaises(ValueError):c.metadata(self.run,self.jobs,self.artifacts,RUN,HEAD,ids)


class ContainerTests(unittest.TestCase):
    def test_safe_container_is_not_native_proof(self):
        self.assertEqual(set(c.zip_members(archive())),c.BUNDLE_FILES)
        with self.assertRaises((ValueError,KeyError)):c.event_closure(c.zip_members(archive()))
    def test_duplicate_names(self):
        with self.assertRaises(ValueError):c.zip_members(archive(extra=[('design.json',b'duplicate')]))
    def test_unsafe_paths(self):
        for path in ('../evil','/absolute','event/../a','event//a','event/./a','event\\a','C:drive','event/a\x01b'):
            with self.subTest(path=path),self.assertRaises(ValueError):c.zip_members(archive(extra=[(path,b'x')]))
    def test_extra_top_member(self):
        with self.assertRaises(ValueError):c.zip_members(archive(extra=[('unexpected',b'x')]))
    def test_unknown_prefix(self):
        with self.assertRaises(ValueError):c.zip_members(archive(extra=[('other/file',b'x')]))
    def test_empty_extra_directory(self):
        with self.assertRaises(ValueError):c.zip_members(archive(extra=[('event/empty/',b'')]))
    def test_casefold_alias(self):
        with self.assertRaises(ValueError):c.zip_members(archive(extra=[('event/a',b'x'),('event/A',b'x')]))
    def test_unicode_alias(self):
        with self.assertRaises(ValueError):c.zip_members(archive(extra=[('event/é',b'x'),('event/e\u0301',b'x')]))
    def test_file_directory_collision(self):
        with self.assertRaises(ValueError):c.zip_members(archive(extra=[('event/a',b'x'),('event/a/b',b'x')]))
    def test_symlink_or_special_file(self):
        for kind in (stat.S_IFLNK,stat.S_IFIFO,stat.S_IFSOCK):
            info=zipfile.ZipInfo('event/special');info.create_system=3;info.external_attr=(kind|0o600)<<16
            with self.subTest(kind=kind),self.assertRaises(ValueError):c.zip_members(archive(extra=[(info,b'outside')]))
    def test_member_expansion_bound(self):
        with patch.object(c,'MAX_MEMBER_BYTES',4),self.assertRaises(ValueError):c.zip_members(archive(extra=[('event/big',b'x'*5)]))
    def test_total_expansion_bound(self):
        with patch.object(c,'MAX_TOTAL_BYTES',15),self.assertRaises(ValueError):c.zip_members(archive())
    def test_member_count_bound(self):
        with patch.object(c,'MAX_MEMBERS',7),self.assertRaises(ValueError):c.zip_members(archive())
    def test_compressed_zip_bound(self):
        with patch.object(c,'MAX_ZIP_BYTES',10),self.assertRaises(ValueError):c.zip_members(archive())
    def test_crc_tamper(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_STORED) as z:
            for name in c.BUNDLE_FILES:z.writestr(name,b'CRC_MARKER')
        raw=buf.getvalue().replace(b'CRC_MARKER',b'BAD_MARKER',1)
        with self.assertRaises(ValueError):c.zip_members(raw)
    def test_malformed_archive(self):
        with self.assertRaises(ValueError):c.zip_members(b'notzip')
    def test_no_zip_extract_calls(self):
        with (patch.object(zipfile.ZipFile,'extract',side_effect=AssertionError('unsafe extraction')),
              patch.object(zipfile.ZipFile,'extractall',side_effect=AssertionError('unsafe extraction'))):
            self.assertEqual(set(c.zip_members(archive())),c.BUNDLE_FILES)
    def test_export_tamper_and_extra_empty_directory(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/'export';members=c.zip_members(archive());c.safe_export(members,dest)
            self.assertEqual(c.directory_members(dest),members)
            (dest/'design.json').write_bytes(b'changed');self.assertNotEqual(c.directory_members(dest),members)
            (dest/'empty').mkdir()
            with self.assertRaises(ValueError):c.directory_members(dest)
    def test_export_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/'export';c.safe_export(c.zip_members(archive()),dest)
            (dest/'linked').symlink_to(dest/'design.json')
            with self.assertRaises(ValueError):c.directory_members(dest)
    def test_safe_export_requires_fresh_directory(self):
        with tempfile.TemporaryDirectory() as td,self.assertRaises(ValueError):c.safe_export({},Path(td))
    def test_strict_json_duplicate_and_nonfinite(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):c.decode(raw)
    def test_typed_json_comparison(self):self.assertFalse(c.same({'v':1},{'v':True}))


class NativeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.source_paths={'eval/resources/real-v1/protocol.json'}
        self.binding={p:c.sha((c.event.ROOT/p).read_bytes()) for p in self.source_paths}
    def members(self,host):
        prefix=bytearray(4096)
        if host=='x86_64-unknown-linux-gnu':prefix[:6]=b'\x7fELF\x02\x01';prefix[18:20]=(62).to_bytes(2,'little')
        else:prefix[:4]=b'\xcf\xfa\xed\xfe';prefix[4:8]=(0x0100000c).to_bytes(4,'little')
        binaries={p:bytes(prefix) for p in c.BINARIES}
        value={'schema_version':'xrai.eval.resources.real-preregistration.v1',
            'environment':{'repository':c.REPOSITORY,'head_sha':HEAD,'run_id':RUN,'run_attempt':1,'platform':c.HOSTS[host][1],'host':host},
            'binary_sha256':{p:c.sha(v) for p,v in binaries.items()},'source_bindings_sha256':self.binding}
        return {'event/preregistered.json':json.dumps(value).encode(),**{'event/'+p:b for p,b in binaries.items()},
            'rustc.txt':f'rustc 1.98.1 (fixture)\nhost: {host}\n'.encode(),'cargo.txt':b'cargo 1.98.1 (fixture)\n','python.txt':b'Python 3.13.13\n'}
    def checked(self,members,host):
        with patch.object(c.event,'SOURCE_PATHS',self.source_paths,create=True):return c.bind_native(members,host,RUN,HEAD,1)
    def test_native_envelope_shape_only_no_execution(self):
        for host in c.HOSTS:self.assertEqual(self.checked(self.members(host),host)['environment']['host'],host)
    def test_wrong_native_host_magic(self):
        host=next(iter(c.HOSTS));m=self.members(host);m['event/native-bin/worker-spike']=b'x'*4096
        v=c.decode(m['event/preregistered.json']);v['binary_sha256']['native-bin/worker-spike']=c.sha(m['event/native-bin/worker-spike']);m['event/preregistered.json']=json.dumps(v).encode()
        with self.assertRaises(ValueError):self.checked(m,host)
    def test_native_binary_tamper(self):
        host=next(iter(c.HOSTS));m=self.members(host);m['event/native-bin/worker-spike']+=b'changed'
        with self.assertRaises(ValueError):self.checked(m,host)
    def test_missing_native_binary_identity(self):
        host=next(iter(c.HOSTS));m=self.members(host);v=c.decode(m['event/preregistered.json']);v['binary_sha256']={};m['event/preregistered.json']=json.dumps(v).encode()
        with self.assertRaises(ValueError):self.checked(m,host)
    def test_environment_typed_bool_run(self):
        host=next(iter(c.HOSTS));m=self.members(host);v=c.decode(m['event/preregistered.json']);v['environment']['run_id']=True;m['event/preregistered.json']=json.dumps(v).encode()
        with self.assertRaises(ValueError):self.checked(m,host)
    def test_environment_extra_field(self):
        host=next(iter(c.HOSTS));m=self.members(host);v=c.decode(m['event/preregistered.json']);v['environment']['claimed_verified']=True;m['event/preregistered.json']=json.dumps(v).encode()
        with self.assertRaises(ValueError):self.checked(m,host)
    def test_source_binding_changed(self):
        host=next(iter(c.HOSTS));m=self.members(host);v=c.decode(m['event/preregistered.json']);v['source_bindings_sha256'][next(iter(self.source_paths))]='0'*64;m['event/preregistered.json']=json.dumps(v).encode()
        with self.assertRaises(ValueError):self.checked(m,host)
    def test_wrong_toolchain(self):
        host=next(iter(c.HOSTS));m=self.members(host);m['cargo.txt']=b'cargo 1.99.0\n'
        with self.assertRaises(ValueError):self.checked(m,host)
    def test_wrong_python_version(self):
        host=next(iter(c.HOSTS));m=self.members(host);m['python.txt']=b'Python 3.15.0\n'
        with self.assertRaises(ValueError):self.checked(m,host)


def closure_members():
    _,manifest=c.event.frozen();ids=[s['id'] for s in manifest['sources']]
    members={p:b'{}' for p in c.BUNDLE_FILES}
    for p in ('preregistered.json','reference.json','producers.json'):members['event/'+p]=b'{}'
    for p in c.BINARIES:members['event/'+p]=b'illustrative-not-native'
    for sid in ids:
        members['event/sources/'+sid]=b'illustrative-source'
        for config in (0,1):members[f'event/reference-responses/{sid}--{config}.response.gz']=b'illustrative-response'
    for p in ('input.json','stdout','stderr','resources.json','calibration.json'):members['event/calibration/'+p]=b'{}'
    common=('input.json','stdout','stderr','resources.json','control/idle.ready','control/idle.start','control/warm_idle.ready','control/warm_idle.start')
    for mode in c.MODES:
        for p in common:members[f'event/equivalence-{mode}/'+p]=b'{}'
        for index in range(160):members[f'event/equivalence-{mode}/control/references/{index}.response.gz']=b'illustrative-response'
        for session in range(3):
            for concurrency in (1,2):
                for p in common:members[f'event/session-{session}-c{concurrency}-{mode}/'+p]=b'{}'
    return members


class CompleteClosureTests(unittest.TestCase):
    def test_exact_illustrative_file_closure_only(self):
        members=closure_members();self.assertEqual(c.event_closure(members)['schema_version'],'xrai.eval.resources.real-sources.v1')
        self.assertEqual(len(members),1123)
    def test_missing_equivalence_mode_response(self):
        members=closure_members();del members['event/equivalence-xrw2/control/references/159.response.gz']
        with self.assertRaises(ValueError):c.event_closure(members)
    def test_missing_configuration_reference(self):
        members=closure_members();del members['event/reference-responses/rust-small-0--1.response.gz']
        with self.assertRaises(ValueError):c.event_closure(members)
    def test_undeclared_session_output(self):
        members=closure_members();members['event/session-3-c1-direct/stdout']=b'{}'
        with self.assertRaises(ValueError):c.event_closure(members)
    def test_extra_unconsumed_proof_claim(self):
        members=closure_members();members['event/claimed-success.json']=b'{"verified":true}'
        with self.assertRaises(ValueError):c.event_closure(members)


class NativeWindowTests(unittest.TestCase):
    def setUp(self):
        _,jobs,_=envelopes();self.job=jobs['jobs'][0]
        step=next(s for s in self.job['steps'] if s['name']=='Measure owned workers on frozen captured sources')
        self.epoch=int(c.instant(step['started_at']).timestamp()*1e9)+100_000_000
        self.native={'frozen_epoch_ns':self.epoch,'output_root':'/ci/resource-evidence/event'}
        self.members={'event/reference.json':json.dumps({'equivalence_completed_epoch_ns':self.epoch+1}).encode()}
        self.dirs=[f'equivalence-{m}' for m in c.MODES]+[f'session-{s}-c{cc}-{m}' for s in range(3) for cc in (1,2) for m in c.MODES]
        for directory in self.dirs:
            receipt={'epoch_started_ns':self.epoch+2,'epoch_finished_ns':self.epoch+3,'observer_epoch_finished_ns':self.epoch+4,
                'pid':333,'command':['/ci/resource-evidence/event/native-bin/worker-benchmark-real']}
            self.members[f'event/{directory}/resources.json']=json.dumps(receipt).encode()
            self.members[f'event/{directory}/stdout']=b'{"parent_pid":333}'
    def test_observed_epochs_and_target_structure_only(self):c.native_time_window(self.members,self.job,self.native)
    def test_previous_attempt_native_preregistration(self):
        self.native['frozen_epoch_ns']=self.epoch-10_000_000_000
        with self.assertRaises(ValueError):c.native_time_window(self.members,self.job,self.native)
    def test_epoch_boolean(self):
        self.native['frozen_epoch_ns']=True
        with self.assertRaises(ValueError):c.native_time_window(self.members,self.job,self.native)
    def test_unbound_command(self):
        key=f'event/{self.dirs[0]}/resources.json';value=c.decode(self.members[key]);value['command']=['/other/binary'];self.members[key]=json.dumps(value).encode()
        with self.assertRaises(ValueError):c.native_time_window(self.members,self.job,self.native)
    def test_observer_and_native_pid_mismatch(self):
        key=f'event/{self.dirs[0]}/resources.json';value=c.decode(self.members[key]);value['pid']=444;self.members[key]=json.dumps(value).encode()
        with self.assertRaises(ValueError):c.native_time_window(self.members,self.job,self.native)
    def test_session_from_later_execution(self):
        key=f'event/{self.dirs[0]}/resources.json';value=c.decode(self.members[key]);value['observer_epoch_finished_ns']+=10_000_000_000;self.members[key]=json.dumps(value).encode()
        with self.assertRaises(ValueError):c.native_time_window(self.members,self.job,self.native)


class PrivateCopyTests(unittest.TestCase):
    def test_complete_container_recomputed_only_from_original_zip_private_copy(self):
        # This tests plumbing with an explicit owned-verifier mock. The artificial
        # binaries/responses are never accepted by the actual native verifier.
        run,jobs,artifacts=envelopes();mock_result={'verified':True,'data_only':True,'m0_06_complete':False,'production_recommendation':None}
        with tempfile.TemporaryDirectory() as td:
            acquisition=Path(td);called=[]
            for host in c.HOSTS:
                members=closure_members();fixture=NativeBoundaryTests();fixture.setUp()
                fixture.source_paths=set(c.event.SOURCE_PATHS);fixture.binding={p:c.sha((c.event.ROOT/p).read_bytes()) for p in fixture.source_paths}
                members.update(fixture.members(host));native=c.decode(members['event/preregistered.json'])
                window=NativeWindowTests();window.setUp();native.update(window.native)
                members['event/preregistered.json']=json.dumps(native).encode();members.update(window.members)
                members['collector.json']=members['verification.json']=json.dumps(mock_result).encode()
                members['design.json']=json.dumps({'verified':True,'data_only':True,'measured':False,'sources':80,'protocol_sha256':c.sha((c.event.DESIGN/'protocol.json').read_bytes())}).encode()
                members['receipt-tests.stdout']=b'';members['receipt-tests.stderr']=b'Ran 2 tests in 0.010s\n\nOK\n'
                raw=archive(members);target=acquisition/host;target.mkdir();(target/'original.zip').write_bytes(raw);c.safe_export(members,target/'export')
                artifact=next(a for a in artifacts['artifacts'] if a['name']==f'c04-real-resources-{host}');artifact['digest']='sha256:'+c.sha(raw);artifact['size_in_bytes']=len(raw)
            for name,value in (('run.json',run),('jobs.json',jobs),('artifacts.json',artifacts)):(acquisition/name).write_text(json.dumps(value))
            def verify_private(path):
                self.assertNotIn(str(acquisition),str(path));self.assertEqual(path.name,'event')
                self.assertEqual((path/'sources/rust-small-0').read_bytes(),b'illustrative-source');called.append(str(path));return mock_result
            with patch.object(c.event,'verify',side_effect=verify_private):proof=c.reconcile(acquisition,RUN,HEAD,IDS)
            self.assertEqual(len(called),2);self.assertEqual(set(proof['hosts']),set(c.HOSTS));self.assertFalse(proof['m0_06_complete'])
            self.assertNotEqual(called[0],called[1]);self.assertTrue(all(not Path(path).exists() for path in called))
            self.assertIn('arbitrary local JSON is not a signature',proof['limits'][0])


class OriginalZipTests(unittest.TestCase):
    def test_api_digest_required_before_proof(self):
        run,jobs,artifacts=envelopes()
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            for name,value in (('run.json',run),('jobs.json',jobs),('artifacts.json',artifacts)):(d/name).write_text(json.dumps(value))
            host=next(iter(c.HOSTS));(d/host).mkdir();(d/host/'original.zip').write_bytes(archive())
            with patch.object(c.event,'verify',side_effect=AssertionError('verification must not be reached')),self.assertRaises(ValueError):c.reconcile(d,RUN,HEAD,IDS)
    def test_zip_matches_api_but_export_differs(self):
        run,jobs,artifacts=envelopes();raw=archive();host=next(iter(c.HOSTS));a=artifacts['artifacts'][0];a['digest']='sha256:'+c.sha(raw);a['size_in_bytes']=len(raw)
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            for name,value in (('run.json',run),('jobs.json',jobs),('artifacts.json',artifacts)):(d/name).write_text(json.dumps(value))
            (d/host).mkdir();(d/host/'original.zip').write_bytes(raw);c.safe_export(c.zip_members(raw),d/host/'export');(d/host/'export/design.json').write_bytes(b'tamper')
            with patch.object(c.event,'verify',side_effect=AssertionError('verification must not be reached')),self.assertRaises(ValueError):c.reconcile(d,RUN,HEAD,IDS)
    @unittest.skipUnless(os.environ.get('XRAI_REAL_RESOURCES_CI_PROOF'),'authenticated original two-host API/ZIP acquisition absent')
    def test_optional_authenticated_actual_two_host_proof(self):
        d=Path(os.environ['XRAI_REAL_RESOURCES_CI_PROOF']);run=c.decode((d/'run.json').read_bytes());artifacts=c.decode((d/'artifacts.json').read_bytes())
        ids={host:next(a['id'] for a in artifacts['artifacts'] if a['name']==f'c04-real-resources-{host}') for host in c.HOSTS}
        proof=c.reconcile(d,run['id'],run['head_sha'],ids,run['run_attempt'])
        self.assertTrue(proof['verified']);self.assertEqual(set(proof['hosts']),set(c.HOSTS));self.assertFalse(proof['m0_06_complete'])


if __name__=='__main__':unittest.main()
