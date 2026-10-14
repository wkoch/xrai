"""Actual pipes of small owned Python fixtures; no project/native/upstream execution."""
import base64
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from store_process_protocol import SessionProcess, SessionFault, MAX_FRAME, decode

ECHO = '''import json,sys
for line in sys.stdin.buffer:
 request=json.loads(line)
 print(json.dumps({'command_id':request['command_id'],'result':request.get('value')}),flush=True)
 if request.get('operation')=='close':break
'''


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.instances = []
    def tearDown(self):
        for instance in self.instances:
            instance.abort()
        self.directory.cleanup()
    def instance(self, source=ECHO, **limits):
        p=Path(self.directory.name)/('fixture-'+str(len(self.instances))+'.py')
        p.write_text(source)
        instance=SessionProcess([sys.executable,'-I','-u',str(p)],**limits)
        self.instances.append(instance)
        return instance
    def test_same_process_echo_complete_bytes_and_explicit_close(self):
        p=self.instance()
        for command_id in range(1,4):
            self.assertEqual(p.call({'command_id':command_id,'value':'Olá'}),{'command_id':command_id,'result':'Olá'})
        p.close(4)
        r=p.record();self.assertFalse(r['active']);self.assertTrue(r['termination']['parent_reaped'])
        self.assertTrue(r['termination']['process_group_absent'])
        self.assertEqual([row['command_id'] for row in r['rows']],[1,2,3,4])
        for row in r['rows']:
            request=base64.b64decode(row['request']['base64']);response=base64.b64decode(row['response']['base64'])
            self.assertEqual(row['written_bytes'],len(request));self.assertEqual(decode(response)['command_id'],row['command_id'])
    def test_nonblocking_write_is_inside_deadline(self):
        p=self.instance('import time;time.sleep(60)')
        began=time.monotonic()
        with self.assertRaisesRegex(SessionFault,'write_read_deadline'):
            p.call({'command_id':1,'value':'x'*200000},timeout_ms=150)
        self.assertLess(time.monotonic()-began,2)
        row=p.record()['rows'][0]
        self.assertGreater(row['written_bytes'],0);self.assertLess(row['written_bytes'],row['request']['bytes'])
        self.assertTrue(row['operation_may_have_applied'])
        with self.assertRaisesRegex(SessionFault,'instance_ended'):p.call({'command_id':2})
    def test_partial_reply_timeout_retained_and_instance_never_reused(self):
        p=self.instance('import sys,time;sys.stdin.buffer.readline();sys.stdout.write("{\\\"command_id\\\":");sys.stdout.flush();time.sleep(60)')
        with self.assertRaisesRegex(SessionFault,'write_read_deadline'):p.call({'command_id':1},timeout_ms=150)
        row=p.record()['rows'][0];self.assertGreater(row['response']['bytes'],0)
        self.assertEqual(base64.b64decode(row['response']['base64']),b'{"command_id":')
        with self.assertRaisesRegex(SessionFault,'instance_ended'):p.call({'command_id':2})
    def test_partial_eof_is_fatal(self):
        p=self.instance('import sys;sys.stdin.buffer.readline();sys.stdout.write("{");sys.stdout.flush()')
        with self.assertRaisesRegex(SessionFault,'partial_response_eof'):p.call({'command_id':1})
        self.assertFalse(p.record()['active'])
    def test_wrong_identity_duplicate_nonfinite_and_extra_frames(self):
        for raw in ['{"command_id":2}', '{"command_id":1,"command_id":1}', '{"command_id":1,"v":NaN}', '{"command_id":1,"v":1e999}', '{}', '{"command_id":true}', '{"command_id":1}\n{"command_id":2}']:
            with self.subTest(raw=raw):
                p=self.instance('import sys;sys.stdin.buffer.readline();sys.stdout.write('+repr(raw+'\n')+');sys.stdout.flush()')
                with self.assertRaises(SessionFault):p.call({'command_id':1})
                self.assertFalse(p.record()['active'])
    def test_late_old_reply_cannot_answer_next_command(self):
        p=self.instance('import sys,time;sys.stdin.buffer.readline();time.sleep(2);print("{\\\"command_id\\\":1}",flush=True);time.sleep(60)')
        with self.assertRaisesRegex(SessionFault,'write_read_deadline'):p.call({'command_id':1},timeout_ms=100)
        with self.assertRaisesRegex(SessionFault,'instance_ended'):p.call({'command_id':2})
        self.assertEqual(p.record()['termination']['reason'],'write_read_deadline')
    def test_unsolicited_reply_before_request_is_fatal(self):
        p=self.instance('import time;print("{\\\"command_id\\\":1}",flush=True);time.sleep(60)')
        time.sleep(.08)
        with self.assertRaisesRegex(SessionFault,'unsolicited_stdout'):p.call({'command_id':1})
        self.assertEqual(p.record()['rows'][0]['written_bytes'],0)
    def test_output_and_stderr_caps_checked_before_unbounded_capture(self):
        for channel,reason in [('stdout','response_frame_limit'),('stderr','stderr_limit')]:
            with self.subTest(channel=channel):
                p=self.instance('import sys,time;sys.stdin.buffer.readline();sys.'+channel+'.write("x"*20000);sys.'+channel+'.flush();time.sleep(60)',frame_limit=1024,stderr_limit=128)
                with self.assertRaisesRegex(SessionFault,reason):p.call({'command_id':1})
                self.assertLessEqual(p.record()['rows'][0]['response']['bytes'],1025)
                self.assertLessEqual(p.record()['stderr']['bytes'],129)
    def test_local_request_caps_monotonic_ids_and_booleans(self):
        p=self.instance()
        for request in [{'command_id':True},{'command_id':0},{'command_id':513},{'command_id':1,'v':'x'*MAX_FRAME}]:
            with self.assertRaises(ValueError):p.call(request)
        p.call({'command_id':1})
        with self.assertRaises(ValueError):p.call({'command_id':1})
        p.close(2)
    def test_concurrent_operation_refuses_without_mixing_frames(self):
        p=self.instance('import json,sys,time\nfor line in sys.stdin.buffer:\n r=json.loads(line);time.sleep(.1);print(json.dumps({"command_id":r["command_id"]}),flush=True)\n if r.get("operation")=="close":break\n')
        errors=[]
        def first():
            try:p.call({'command_id':1})
            except Exception as error:errors.append(error)
        thread=threading.Thread(target=first);thread.start();time.sleep(.04)
        with self.assertRaisesRegex(SessionFault,'session_busy'):p.call({'command_id':2})
        thread.join(2);self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        p.close(2)
    def test_close_timeout_reaps_instance(self):
        p=self.instance('import json,sys,time;print(json.dumps({"command_id":json.loads(sys.stdin.buffer.readline())["command_id"]}),flush=True);time.sleep(60)')
        with self.assertRaisesRegex(SessionFault,'shutdown_deadline'):p.close(1,timeout_ms=150)
        self.assertTrue(p.record()['termination']['parent_reaped'])
    def test_final_stderr_after_stdout_eof_is_retained(self):
        p=self.instance('import json,os,sys,time;print(json.dumps({"command_id":json.loads(sys.stdin.buffer.readline())["command_id"]}),flush=True);os.close(1);time.sleep(.05);sys.stderr.write("FINAL_AUDIT\\n");sys.stderr.flush()')
        p.close(1)
        self.assertEqual(base64.b64decode(p.record()['stderr']['base64']),b'FINAL_AUDIT\n')
    def test_final_stderr_is_bounded_and_fatal_when_oversize(self):
        p=self.instance('import json,os,sys,time;print(json.dumps({"command_id":json.loads(sys.stdin.buffer.readline())["command_id"]}),flush=True);os.close(1);time.sleep(.05);sys.stderr.write("x"*20000);sys.stderr.flush()',stderr_limit=128)
        with self.assertRaisesRegex(SessionFault,'stderr_limit'):p.close(1)
        self.assertEqual(p.record()['stderr']['bytes'],129)

    def test_cancel_does_not_wait_for_io_lock_and_never_claims_rollback(self):
        p=self.instance('import sys,time;sys.stdin.buffer.readline();time.sleep(60)')
        errors=[]
        def active():
            try:p.call({'command_id':1},timeout_ms=5000)
            except Exception as error:errors.append(str(error))
        thread=threading.Thread(target=active);thread.start();time.sleep(.05)
        began=time.monotonic();p.cancel();self.assertLess(time.monotonic()-began,.2)
        thread.join(2);self.assertFalse(thread.is_alive());self.assertEqual(errors,['operation_cancelled'])
        r=p.record();self.assertFalse(r['active']);self.assertTrue(r['rows'][0]['operation_may_have_applied'])
        self.assertTrue(r['termination']['parent_reaped'])
        with self.assertRaisesRegex(SessionFault,'instance_ended'):p.call({'command_id':2})


if __name__=='__main__':unittest.main()
