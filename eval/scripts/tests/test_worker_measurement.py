import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

FILE=Path(__file__).resolve().parents[1]/'verify_worker_measurement.py'
SPEC=importlib.util.spec_from_file_location('worker_verifier',FILE)
V=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(V)

def write(path,value): path.write_text(json.dumps(value))

def fixture(root):
    dialects=['rust','javascript','jsx','typescript','tsx','python','go']
    descriptors=[{'key':f'{d}/small/{p}/0','source_bytes':1,'source_sha256':V.hashlib.sha256(b'x').hexdigest()} for d in dialects for p in ('repeated','distinct')]
    with tarfile.open(root/'sources.tar.gz','w:gz') as archive:
        for d in dialects:
            member=tarfile.TarInfo(f'{d}-small-0.txt'); member.size=1; archive.addfile(member,io.BytesIO(b'x'))
    plan={'sessions':1,'requests_per_class_pattern':1,'modes':['direct','xrw1','xrw2'],'mode_order':[['direct','xrw1','xrw2']], 'classes':['small'],'patterns':['repeated','distinct'],'dialects':dialects,'descriptors':descriptors,'concurrency':1,'sources_archive_sha256':V.sha(root/'sources.tar.gz'),'limitations':['synthetic']}
    write(root/'preregistered.json',plan)
    rows=[{'key':d['key'],'request':n,'warmup':False,'response_blake3':'response','source_blake3':V.blake3.blake3(b'x').hexdigest(),'source_bytes':1,'producer':'producer','configuration':'configuration','dialect':d['key'].split('/')[0],'attempts':1,'end_to_end_ns':1000,'pid':1,'incarnation':'incarnation'} for n,d in enumerate(descriptors)]
    write(root/'reference.json',{'samples':rows})
    def receipt(target,payload):
        target.mkdir(); write(target/'stdout',payload); (target/'stderr').write_bytes(b'')
        r={'exit':0,'timed_out':False,'pid':1,'output_sha256':V.sha(target/'stdout'),'stderr_sha256':V.sha(target/'stderr'),'cpu_user_seconds':1.3,'cpu_system_seconds':.3,'observer_self_user_seconds':0,'observer_self_system_seconds':0,'observer_ps_user_seconds':0,'observer_ps_system_seconds':0,'sampled_peak_sum_rss':3000,'samples':[{'begin_ns':1,'end_ns':2,'error':None,'sum_rss_bytes':3000,'processes':[{'pid':pid,'ppid':0 if pid==1 else 1,'start_observed':'date','rss_bytes':1000} for pid in (1,2,3)]}]}
        write(target/'resources.json',r)
    receipt(root/'calibration',{'self_user':1,'self_system':.2,'child_usage':[{'user':.3,'system':.1}]})
    write(root/'calibration/calibration.json',{'cpu_inclusive_validated':True,'maximum_simultaneous_processes':3})
    sessions=[]
    for mode in plan['modes']:
        target=root/f'session-0-{mode}'
        receipt(target,{'samples':rows,'mode':mode,'parent_pid':1,'retention':{'held_ticket_reserved_bytes':100,'after_transfer_reserved_bytes':0,'full_direct_equal':True}})
        write(target/'input.json',{'mode':mode,'requests':rows})
        sessions.append({'session':0,'mode':mode,'requests':len(rows),'worker_pids_missed_by_sampler':[],'cpu_user_seconds':1.3,'cpu_system_seconds':.3,'sampled_peak_sum_rss':3000})
    write(root/'summary.json',{'schema':'xrai.eval.worker.comparison.v1','preregistration_sha256':V.sha(root/'preregistered.json'),'complete_synthetic_matrix':False,'m0_06_complete':False,'production_mode_recommendation':None,'sessions':sessions})

class WorkerMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name); fixture(self.root)
    def alter(self,path,change):
        target=self.root/path; data=V.load(target); change(data); write(target,data)
    def test_valid(self): self.assertTrue(V.verify(self.root)['full_response_equivalent'])
    def test_nonzero_exit(self):
        self.alter('session-0-direct/resources.json',lambda d:d.update(exit=1))
        with self.assertRaisesRegex(ValueError,'failed session'): V.verify(self.root)
    def test_missing_output(self):
        (self.root/'session-0-direct/stdout').unlink()
        with self.assertRaises(FileNotFoundError): V.verify(self.root)
    def test_rss_peak_is_simultaneous_sum(self):
        self.alter('session-0-direct/resources.json',lambda d:d['samples'][0].update(sum_rss_bytes=9999))
        with self.assertRaisesRegex(ValueError,'RSS sum'): V.verify(self.root)
    def test_duplicate_pid(self):
        self.alter('session-0-direct/resources.json',lambda d:d['samples'][0]['processes'].append(d['samples'][0]['processes'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate PID'): V.verify(self.root)
    def test_unvalidated_host_cpu(self):
        self.alter('calibration/calibration.json',lambda d:d.update(cpu_inclusive_validated=False))
        with self.assertRaisesRegex(ValueError,'calibration'): V.verify(self.root)
    def test_duplicate_session(self):
        self.alter('summary.json',lambda d:d['sessions'].__setitem__(2,d['sessions'][1]))
        with self.assertRaisesRegex(ValueError,'duplicate session'): V.verify(self.root)
    def test_source_archive_tamper(self):
        with (self.root/'sources.tar.gz').open('ab') as file: file.write(b'x')
        with self.assertRaisesRegex(ValueError,'archive hash'): V.verify(self.root)
    def test_direct_response_mismatch_even_with_output_hash_updated(self):
        self.alter('session-0-xrw2/stdout',lambda d:d['samples'][0].update(response_blake3='wrong'))
        self.alter('session-0-xrw2/resources.json',lambda d:d.update(output_sha256=V.sha(self.root/'session-0-xrw2/stdout')))
        with self.assertRaisesRegex(ValueError,'reference mismatch'): V.verify(self.root)
    def test_request_duplicate_even_with_output_hash_updated(self):
        self.alter('session-0-xrw2/stdout',lambda d:d['samples'][1].update(request=0))
        self.alter('session-0-xrw2/resources.json',lambda d:d.update(output_sha256=V.sha(self.root/'session-0-xrw2/stdout')))
        with self.assertRaisesRegex(ValueError,'request identities'): V.verify(self.root)
    def test_nonfinite_cpu(self):
        self.alter('session-0-direct/resources.json',lambda d:d.update(cpu_user_seconds=float('nan')))
        with self.assertRaisesRegex(ValueError,'CPU value'): V.verify(self.root)
    def test_foreign_process_tree(self):
        self.alter('session-0-direct/resources.json',lambda d:d['samples'][0]['processes'][1].update(ppid=9999))
        with self.assertRaisesRegex(ValueError,'outside experiment'): V.verify(self.root)
    def test_dishonest_calibration_overlap(self):
        self.alter('calibration/calibration.json',lambda d:d.update(maximum_simultaneous_processes=100))
        with self.assertRaisesRegex(ValueError,'calibration'): V.verify(self.root)
    def test_dishonest_synthetic_completeness(self):
        self.alter('summary.json',lambda d:d.update(complete_synthetic_matrix=True))
        with self.assertRaisesRegex(ValueError,'synthetic completeness'): V.verify(self.root)

if __name__=='__main__': unittest.main()
