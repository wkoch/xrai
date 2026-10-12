"""Finite native namespace adversaries with positive execution sentinels.

No fork bombs; each escaped test child has its own hard six-second lifetime.
Tests own the host workspace and clean it after all finite probes have ended.
"""
import base64
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters import MacDisposableAdapter
from runner import execute, record, replay, payload
from supervisor import KnownSmokeDomain, supervise, verify_receipt, map_held_user_namespace


def wait_file(path, seconds=4):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(.01)
    raise AssertionError(f'positive control did not execute: {path}')


class ReceiptTests(unittest.TestCase):
    def test_mac_disposable_is_explicitly_unavailable(self):
        self.assertFalse(MacDisposableAdapter.available)
        with self.assertRaises(RuntimeError):
            MacDisposableAdapter().create()
        with tempfile.TemporaryDirectory() as temp, patch('supervisor.platform.system', return_value='Darwin'):
            r = execute(['/bin/sh', '-c', 'touch must-not-run'], temp, arbitrary_agent=True)
            self.assertEqual(r['status'], 'containment_unavailable')
            self.assertFalse(Path(temp, 'must-not-run').exists())
            self.assertFalse(r['eligible_for_agent_run'])
            verify_receipt(r)

    def test_incomplete_or_tampered_namespace_receipts_are_rejected(self):
        # Synthetic contract row only; never treated as native process evidence.
        r={'containment':'linux_pid_namespace','cleanup_status':'confirmed','status':'ok',
           'eligible_for_agent_run':True,'domain_id':str(uuid.uuid4()),
           'termination_evidence':{'init_pid':123,'pid_namespace':'pid:[456]',
                'init_held_before_pin':True,'pidfd_exit_observed':True,'wrapper_reaped':True,
                'user_namespace_mapping':{'uid':1001,'gid':1001,'count':1,'setgroups':'deny'}}}
        verify_receipt(r)
        for field in ['init_pid','pid_namespace','init_held_before_pin','pidfd_exit_observed','wrapper_reaped','user_namespace_mapping']:
            broken=copy.deepcopy(r);del broken['termination_evidence'][field]
            with self.assertRaises(ValueError,msg=field): verify_receipt(broken)
        for key,value in [('init_pid',True),('init_pid',0),('pid_namespace',''),('pid_namespace','pid:[0]')]:
            broken=copy.deepcopy(r);broken['termination_evidence'][key]=value
            with self.assertRaises(ValueError):verify_receipt(broken)
        for key,value in [('uid',True),('uid',-1),('count',True),('setgroups','allow')]:
            broken=copy.deepcopy(r);broken['termination_evidence']['user_namespace_mapping'][key]=value
            with self.assertRaises(ValueError):verify_receipt(broken)
        broken=copy.deepcopy(r);broken['domain_id']='invented-domain'
        with self.assertRaises(ValueError):verify_receipt(broken)
        complete={**r,'phase':'test','command':['/bin/true'],'execution_status':'ok','exit_code':0,
                  'sandbox':'Linux bubblewrap','diagnostic':None,'elapsed_seconds':0,
                  'stdout':payload(b'',0),'stderr':payload(b'',0)}
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                record({'id':'synthetic','family':'Rust'},'test',[complete,complete],0,temp)

    def test_external_user_namespace_mapping_is_single_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            proc=Path(temp)/'4242';proc.mkdir()
            for name in ['uid_map','gid_map','setgroups']:
                (proc/name).touch()
            original_path=Path
            def mapped_path(value):
                return original_path(temp) if value == '/proc' else original_path(value)
            with patch('supervisor.Path',side_effect=mapped_path),patch('supervisor.os.getuid',return_value=1001),patch('supervisor.os.getgid',return_value=1002):
                mapping=map_held_user_namespace(4242)
                self.assertEqual((proc/'uid_map').read_text(),'1001 1001 1\n')
                self.assertEqual((proc/'gid_map').read_text(),'1002 1002 1\n')
                self.assertEqual((proc/'setgroups').read_text(),'deny')
                self.assertEqual(mapping['count'],1)
                with self.assertRaises(RuntimeError):
                    map_held_user_namespace(4242)

    def test_cancelled_before_launch_never_executes(self):
        cancel = threading.Event(); cancel.set()
        with tempfile.TemporaryDirectory() as temp:
            result=execute(['/bin/sh','-c','touch must-not-run'],temp,cancel=cancel)
            self.assertEqual(result['status'],'cancelled')
            self.assertEqual(result['cleanup_status'],'not_created')
            self.assertFalse(Path(temp,'must-not-run').exists())
            verify_receipt(result)

    def test_exception_after_launch_always_cleans_even_exited_wrapper(self):
        for already_exited in [False, True]:
            class ObservedCleanup(KnownSmokeDomain):
                destroyed = False
                def launch(self, *args):
                    process=super().launch(*args)
                    if already_exited:
                        process.wait(timeout=2)
                    return process
                def destroy(self, process):
                    type(self).destroyed=True
                    return super().destroy(process)
            with tempfile.TemporaryDirectory() as temp, patch('supervisor.selectors.DefaultSelector', side_effect=OSError('injected after launch')):
                result=supervise(['/bin/sh','-c','printf partial'],temp,timeout=2,output_limit=65536,
                                 domain_factory=ObservedCleanup)
            self.assertTrue(ObservedCleanup.destroyed)
            self.assertTrue(result['termination_evidence']['wrapper_reaped'])
            self.assertEqual(result['status'],'spawn_error')
            self.assertIn('injected',result['diagnostic'])
            verify_receipt(result)

    def test_version_one_bytes_remain_replayable(self):
        with tempfile.TemporaryDirectory() as temp:
            row = record({'id':'legacy', 'family':'Rust'}, 'test', [], 0, temp)
            row['schema_version'] = 'xrai.eval.local.v1'
            self.assertEqual(replay(row)['captured_bytes'], 0)
        root = Path(__file__).resolve().parents[4]
        samples = [Path(__file__).with_name('replay-v1.json')]
        samples += list((root/'docs/relatorios/logs/L2/ci-native').rglob('D0-*.json'))
        # Local historical artifacts are checked when present; CI also checks v1
        # via the committed fixture below, not an absent external artifact.
        for path in samples:
            self.assertEqual(json.loads(path.read_text())['schema_version'], 'xrai.eval.local.v1')
            replay(json.loads(path.read_text()))

    def test_teardown_failure_is_preserved_and_ineligible(self):
        class FailedCleanup(KnownSmokeDomain):
            def destroy(self, process):
                super().destroy(process)
                return 'incomplete', ['injected teardown failure after auxiliary cleanup']
        with tempfile.TemporaryDirectory() as temp:
            r = supervise(['/bin/sh','-c','printf partial'], temp, timeout=2,
                          output_limit=65536, domain_factory=FailedCleanup)
        self.assertEqual(r['execution_status'], 'ok')
        self.assertEqual(r['status'], 'teardown_failed')
        self.assertEqual(r['streams']['stdout'], b'partial')
        self.assertFalse(r['eligible_for_agent_run'])
        verify_receipt(r)
        broken=copy.deepcopy(r); broken['status']='ok'
        with self.assertRaises(ValueError):
            verify_receipt(broken)


@unittest.skipUnless(platform.system() == 'Linux', 'Linux PID namespace native proof required')
class NamespaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='xrai-containment-')
        self.workspace=Path(self.temp.name)
        self.rows=[]

    def tearDown(self):
        # An adverse child remains finite even if implementation regresses.
        evidence = os.environ.get('XRAI_CONTAINMENT_EVIDENCE')
        if evidence:
            with open(evidence, 'a') as stream:
                stream.write(json.dumps({'test': self.id(), 'system':platform.system(), 'release':platform.release(), 'python':platform.python_version(), 'rounds':self.rows})+'\n')
        self.temp.cleanup()

    def run_code(self, code, *, workspace=None, **kwargs):
        result=execute(['/usr/bin/python3','-c',code], workspace or self.workspace,
                       arbitrary_agent=True, **kwargs)
        self.rows.append(result)
        return result

    def confirmed(self, result):
        self.assertEqual(result['cleanup_status'], 'confirmed', result)
        self.assertTrue(result['eligible_for_agent_run'], result)
        self.assertTrue(result['termination_evidence']['pidfd_exit_observed'], result)
        verify_receipt(result)

    def descendant(self, kind, parent_wait=True):
        # All children write started before announcing readiness to the parent.
        # Child waits for release; after the run host releases it. A dead child
        # cannot write late. Its hard lifetime bounds even a regressed harness.
        return f'''import os,time
kind={kind!r}
if os.fork()==0:
    if kind in ('setsid','doublefork'): os.setsid()
    if kind=='doublefork' and os.fork()!=0: os._exit(0)
    open('started','w').write('executed')
    end=time.monotonic()+6
    while time.monotonic()<end and not os.path.exists('release'): time.sleep(.01)
    if os.path.exists('release'): open('late','w').write('survived')
    os._exit(0)
while not os.path.exists('started'): time.sleep(.01)
print('positive',flush=True)
{'time.sleep(6)' if parent_wait else 'os._exit(0)'}
'''

    def assert_no_late(self, result):
        self.confirmed(result)
        self.assertEqual((self.workspace/'started').read_text(), 'executed')
        (self.workspace/'release').write_text('release')
        # Deadline covers scheduling after release; teardown proof is pidfd,
        # not this observation delay. Positive control proves probe sensitivity.
        time.sleep(.15)
        self.assertFalse((self.workspace/'late').exists(), result)

    def test_repeated_adverse_descendants_and_normal_child_exit(self):
        for repetition in range(2):
            for kind, parent_wait in [('setsid',True),('doublefork',True),('pipes',True),('setsid',False)]:
                with self.subTest(repetition=repetition, kind=kind, parent_wait=parent_wait):
                    for name in ['started','release','late']:
                        (self.workspace/name).unlink(missing_ok=True)
                    result=self.run_code(self.descendant(kind,parent_wait), timeout=1)
                    self.assertEqual(result['status'], 'timeout' if parent_wait else 'ok', result)
                    self.assert_no_late(result)

    def test_positive_descendant_sentinel(self):
        code="import os,time; open('started','w').write('executed'); open('late','w').write('survived')"
        result=self.run_code(code)
        self.assertEqual(result['status'], 'ok', result)
        self.confirmed(result)
        self.assertEqual((self.workspace/'late').read_text(),'survived')

    def test_bounded_fork_output_limit_and_closed_pipes(self):
        fork="""import os,time
for i in range(4):
    if os.fork()==0:
        open('child'+str(i),'w').write('started'); time.sleep(6); os._exit(0)
while not all(os.path.exists('child'+str(i)) for i in range(4)): time.sleep(.01)
print('all-started',flush=True); time.sleep(6)
"""
        for repetition in range(2):
            result=self.run_code(fork,timeout=1)
            self.assertEqual(result['status'],'timeout',result); self.confirmed(result)
            self.assertIn(b'all-started',base64.b64decode(result['stdout']['base64']))
            result=self.run_code("import os;\nwhile True: os.write(1,b'x'*4096)",output_limit=100)
            self.assertEqual(result['status'],'output_limit',result); self.confirmed(result)
            self.assertEqual(result['stdout']['captured_bytes'],100)
            result=self.run_code('import os,time; os.close(1); os.close(2); time.sleep(6)',timeout=1)
            self.assertEqual(result['status'],'timeout',result); self.confirmed(result)

    def test_two_arms_isolation_and_independent_cancellation(self):
        arm_a=self.workspace/'A'; arm_b=self.workspace/'B'; arm_a.mkdir(); arm_b.mkdir()
        (arm_b/'secret').write_text('hidden-B')
        cancel=threading.Event()
        code="import time; open('started','w').write('yes'); time.sleep(6)"
        other=f"""import os,time
assert not os.path.exists({str(arm_a/'started')!r})
try: open({str(arm_a/'bad')!r},'w').write('leaked')
except OSError: pass
else: raise AssertionError('cross-arm write allowed')
open('started','w').write('yes')
while not os.path.exists('release'): time.sleep(.01)
open('finished','w').write('independent')
"""
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(self.run_code,code,workspace=arm_a,cancel=cancel,timeout=5)
            b=pool.submit(self.run_code,other,workspace=arm_b,timeout=5)
            wait_file(arm_a/'started'); wait_file(arm_b/'started')
            cancel.set(); ra=a.result(timeout=3)
            self.assertEqual(ra['status'],'cancelled',ra); self.confirmed(ra)
            (arm_b/'release').write_text('continue')
            rb=b.result(timeout=3); self.assertEqual(rb['status'],'ok',rb); self.confirmed(rb)
        self.assertFalse((arm_a/'bad').exists())
        self.assertEqual((arm_b/'finished').read_text(),'independent')
        self.assertNotEqual(ra['domain_id'],rb['domain_id'])
        self.assertNotEqual(ra['termination_evidence']['pid_namespace'],rb['termination_evidence']['pid_namespace'])

    def test_evaluator_death_destroys_namespace(self):
        harness=Path(__file__).resolve().parents[1]
        snippet=f"import sys,json;sys.path.insert(0,{str(harness)!r});from runner import execute;from supervisor import LinuxDomain;original=LinuxDomain.launch\ndef launch(self,*a):\n p=original(self,*a);open({str(self.workspace/'identity')!r},'w').write(json.dumps(self.evidence));return p\nLinuxDomain.launch=launch\nexecute(['/usr/bin/python3','-c',{self.descendant('doublefork')!r}],{str(self.workspace)!r},timeout=5,arbitrary_agent=True)"
        for repetition in range(2):
            for name in ['started','release','late','identity']:
                (self.workspace/name).unlink(missing_ok=True)
            parent=subprocess.Popen([sys.executable,'-c',snippet],start_new_session=True,
                                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                wait_file(self.workspace/'started')
                identity=json.loads((self.workspace/'identity').read_text())
                pidfd=os.pidfd_open(identity['init_pid'])
                try:
                    parent.kill(); parent.wait(timeout=2)
                    import select
                    dead=bool(select.select([pidfd],[],[],2)[0])
                    self.assertTrue(dead, 'init must die when evaluator dies')
                    self.rows.append({'parent_death':True,'termination_evidence':identity,'external_pidfd_exit_observed':dead})
                finally:
                    os.close(pidfd)
                (self.workspace/'release').write_text('after evaluator death')
                time.sleep(.2)
                self.assertFalse((self.workspace/'late').exists())
            finally:
                if parent.poll() is None:
                    parent.kill(); parent.wait(timeout=2)


if __name__=='__main__':
    unittest.main()
