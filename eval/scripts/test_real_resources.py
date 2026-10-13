#!/usr/bin/env python3
"""Data-only adversarial checks; real-CI environment adds retained proof checks."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import blake3
import verify_real_resources as v


def wire(payload=None,producer='12'*32,state=1,spans=((1,2),)):
    source=b'x\ny';diagnostic={'kind':'error','start_byte':1,'end_byte':2,'start_line':1,'start_column_byte':1,'end_line':2,'end_column_byte':0}
    if payload is None:payload={'dialect':'python','complete':False,'source_bytes':3,'node_count':1,'query_matches':0,'tree':'(module (ERROR))','diagnostics':[diagnostic]}
    def number(n):return n.to_bytes(8,'little')
    def blob(raw):return number(len(raw))+raw
    raw=number(0)+(0).to_bytes(4,'little')+blob(b'python')+blake3.blake3(source).digest()+bytes.fromhex(producer)+blake3.blake3(b'configuration-A').digest()+bytes([state])+number(3)+number(1)+number(0)+number(len(spans))
    raw+=b''.join(number(a)+number(b) for a,b in spans)+blob(json.dumps(payload,sort_keys=True).encode())
    return raw,{'dialect':'python','raw':source},payload


class FrozenDesign(unittest.TestCase):
    def test_frozen_denominator_and_real_losses(self):
        protocol,manifest=v.frozen();self.assertEqual(len(manifest['sources']),80)
        self.assertEqual([(x['dialect'],x['class']) for x in manifest['availability'] if not x['available']],[('tsx','dense'),('tsx','large')])
        self.assertEqual(v.sha(v.file(v.DESIGN/'protocol.json')),'1a5aff585dc9546c19cc36ba3f3519a7dd417c99ad5d88a88b908becb3deb17d')
    def test_frozen_query_matrix(self):
        protocol,manifest=v.frozen()
        for lanes in (1,2):
            rows=v.matrix(protocol,manifest,lanes,'measurement');self.assertEqual(sum(not r['warmup'] for r in rows),2400);self.assertEqual(sum(r['warmup'] for r in rows),2*lanes)
            self.assertFalse(any(r['key'].startswith(('tsx/dense/','tsx/large/')) for r in rows))
        self.assertEqual(len(v.matrix(protocol,manifest,1,'equivalence')),160)
    def test_typed_input_comparison(self):self.assertFalse(v.same({'concurrency':1},{'concurrency':True}))
    def test_duplicate_json_and_nonfinite(self):
        with self.assertRaises(ValueError):v.decode(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):v.decode(b'{"a":NaN}')
    def test_native_execution_local_guard(self):
        import run_real_resources as runner
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'false'}),self.assertRaisesRegex(ValueError,'disposable GitHub CI'):runner.run(None)


class FullResponse(unittest.TestCase):
    def check(self,raw,source):return v.response(raw,source,'configuration-A','12'*32)
    def test_valid_complete_encoded_partial_contract(self):
        raw,source,_=wire();self.assertEqual(self.check(raw,source)['diagnostics'],1)
    def test_unknown_producer(self):
        raw,source,_=wire(producer='00'*32)
        with self.assertRaisesRegex(ValueError,'producer'):self.check(raw,source)
    def test_response_truncation_and_trailing_bytes(self):
        raw,source,_=wire()
        for changed in (raw[:-1],raw+b'x'):
            with self.subTest(length=len(changed)),self.assertRaises(ValueError):self.check(changed,source)
    def test_boolean_counters(self):
        _,source,payload=wire()
        for field,value in [('node_count',True),('query_matches',False)]:
            changed=copy.deepcopy(payload);changed[field]=value;raw,_,_=wire(payload=changed)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'strict integer'):self.check(raw,source)
    def test_bad_diagnostic_kind_coordinates_or_extra_fields(self):
        _,source,payload=wire()
        for field,value in [('kind','invented'),('start_line',-10),('end_line',True),('start_column_byte',1.0),('extra','field')]:
            changed=copy.deepcopy(payload);changed['diagnostics'][0][field]=value;raw,_,_=wire(payload=changed)
            with self.subTest(field=field),self.assertRaises(ValueError):self.check(raw,source)
    def test_diagnostic_bounds(self):
        raw,source,_=wire(spans=((1,4),))
        with self.assertRaises(ValueError):self.check(raw,source)
    def test_wrong_source_and_config(self):
        raw,source,_=wire();source['raw']=b'bad'
        with self.assertRaisesRegex(ValueError,'source/configuration'):self.check(raw,source)
    def test_complete_with_diagnostics(self):
        _,source,payload=wire();payload['complete']=True;raw,_,_=wire(payload=payload,state=0)
        with self.assertRaisesRegex(ValueError,'complete/diagnostic'):self.check(raw,source)


class ResourceReceipt(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.control=Path(self.temp.name)
        for name,ready,ack in [('idle',100,103),('warm_idle',103,106)]:
            (self.control/(name+'.ready')).write_text(str(ready));(self.control/(name+'.start')).write_text(str(ack))
        samples=[{'begin_ns':i,'end_ns':i,'epoch_begin_ns':100+i,'epoch_end_ns':100+i,'phase':'idle' if i<3 else 'warm_idle','processes':[{'pid':1,'ppid':0,'rss_bytes':123,'start_observed':'Mon Oct 12 01:00:00 2026'}],'sum_rss_bytes':123,'error':None} for i in range(6)]
        self.receipt={'schema_version':'xrai.eval.resources.real-observer.v1','pid':1,'exit':0,'timed_out':False,'calibration_sha256':'ab'*32,'cpu_inclusive_calibrated':True,'cpu_user_seconds':.1,'cpu_system_seconds':.01,'observer_self_user_seconds':.01,'observer_self_system_seconds':.01,'observer_ps_user_seconds':.01,'observer_ps_system_seconds':.01,'sample_interval_seconds':.025,'observer_errors':[],'cpu_origin':'wait4 target parent plus its waited descendants; calibration validated once on this host','samples':samples,'sampled_peak_sum_rss':123,'baselines':{'idle':{'sample_indices':[0,1,2],'ready_epoch_ns':100,'ack_epoch_ns':103},'warm_idle':{'sample_indices':[3,4,5],'ready_epoch_ns':103,'ack_epoch_ns':106}},'worker_pids_missed_by_sampler':[],'epoch_started_ns':99,'epoch_finished_ns':110,'observer_epoch_finished_ns':111}
        self.payload={'parent_pid':1,'samples':[{'pid':1}]}
    def tearDown(self):self.temp.cleanup()
    def check(self,value):v.resource(value,self.payload,self.control,'ab'*32)
    def test_actual_baselines_pass(self):self.check(self.receipt)
    def test_infinite_or_boolean_cpu_rejected(self):
        for value in (float('inf'),float('nan'),True,-1):
            changed=copy.deepcopy(self.receipt);changed['cpu_user_seconds']=value
            with self.subTest(value=value),self.assertRaises(ValueError):self.check(changed)
    def test_duplicate_negative_or_out_of_range_baseline_indices(self):
        for indices in ([0,0,0],[-1,0,1],[0,1,999],[True,1,2]):
            changed=copy.deepcopy(self.receipt);changed['baselines']['idle']['sample_indices']=indices
            with self.subTest(indices=indices),self.assertRaises(ValueError):self.check(changed)
    def test_ack_and_start_incarnation_types(self):
        changed=copy.deepcopy(self.receipt);changed['baselines']['idle']['ack_epoch_ns']=103.0
        with self.assertRaises(ValueError):self.check(changed)
        changed=copy.deepcopy(self.receipt);changed['samples'][0]['processes'][0]['start_observed']=True
        with self.assertRaises(ValueError):self.check(changed)
    def test_rss_integer_domain(self):
        for change in ('sampled_peak_sum_rss','sum_rss_bytes'):
            changed=copy.deepcopy(self.receipt)
            if change=='sampled_peak_sum_rss':changed[change]=123.0
            else:changed['samples'][0][change]=123.0
            with self.subTest(field=change),self.assertRaises(ValueError):self.check(changed)
    def test_calibration_binding_and_sampling_loss(self):
        changed=copy.deepcopy(self.receipt);changed['calibration_sha256']='ff'*32
        with self.assertRaises(ValueError):self.check(changed)
        changed=copy.deepcopy(self.receipt);changed['worker_pids_missed_by_sampler']=[999]
        with self.assertRaises(ValueError):self.check(changed)
    def test_wrong_target_pid(self):
        changed=copy.deepcopy(self.receipt);changed['pid']=999
        with self.assertRaises(ValueError):self.check(changed)
    def test_old_epoch_or_post_ack_sample(self):
        for epoch in (98,112):
            changed=copy.deepcopy(self.receipt);changed['samples'][0]['epoch_begin_ns']=epoch;changed['samples'][0]['epoch_end_ns']=epoch
            with self.subTest(epoch=epoch),self.assertRaises(ValueError):self.check(changed)


@unittest.skipUnless(os.environ.get('XRAI_REAL_RESOURCES_OUTPUT'),'actual retained CI proof required')
class ActualProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.output=Path(os.environ['XRAI_REAL_RESOURCES_OUTPUT']).resolve()
    def test_actual_native_proof(self):
        proof=v.verify(self.output);self.assertEqual(len(proof['sessions']),24);self.assertTrue(proof['full_response_equivalent'])
    def reject_json(self,relative,mutate):
        original=v.read;target=self.output/relative
        def changed(path):
            value=original(path)
            if Path(path)==target:value=copy.deepcopy(value);mutate(value)
            return value
        with patch.object(v,'read',side_effect=changed),self.assertRaises(ValueError):v.verify(self.output)
    def test_24_duplicated_sessions_rejected(self):self.reject_json('preregistered.json',lambda x:x['sessions'].__setitem__(1,copy.deepcopy(x['sessions'][0])))
    def test_missing_native_binary_rejected(self):self.reject_json('preregistered.json',lambda x:x['binary_sha256'].pop('native-bin/worker-spike'))
    def test_arbitrary_producer_rejected(self):self.reject_json('producers.json',lambda x:x['grammars'][0].__setitem__('producer','00'*32))
    def test_reference_equivalence_after_measurement_rejected(self):self.reject_json('reference.json',lambda x:x.__setitem__('equivalence_completed_epoch_ns',10**30))
    def test_two_arbitrary_configurations_rejected(self):self.reject_json('reference.json',lambda x:x['responses'][0].__setitem__('configuration','arbitrary'))
    def test_actual_baseline_duplicated_indices_rejected(self):
        self.reject_json('session-0-c1-direct/resources.json',lambda x:x['baselines']['idle'].__setitem__('sample_indices',[x['baselines']['idle']['sample_indices'][0]]*3))
    def test_actual_frozen_pattern_count_rejected(self):self.reject_json('session-0-c1-direct/input.json',lambda x:x['requests'].pop())
    def test_actual_boolean_concurrency_rejected(self):self.reject_json('session-0-c1-direct/stdout',lambda x:x.__setitem__('concurrency',True))

if __name__=='__main__':unittest.main()
