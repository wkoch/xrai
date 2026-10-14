"""Own-data substitutions; authentic native proof is opt-in and never re-executes ELF."""
import base64
import copy
import os
import shutil
from pathlib import Path
import tempfile
import unittest
import store_bridge_verify as v


def captured(raw):return {'base64':base64.b64encode(raw).decode(),'bytes':len(raw),'sha256':v.sha(raw)}

def row(request,response):
    a=v.canonical(request)+b'\n'
    b=v.canonical(response)+b'\n'
    return {'command_id':request['command_id'],'started_monotonic':1.0,'elapsed_seconds':.001,'timeout_ms':30000,'request':captured(a),'written_bytes':len(a),'response':captured(b),'outcome':'response','operation_may_have_applied':True}

def example():
    request={'command_id':1,'operation':'close'}
    response={'profile':v.PROFILE,'command_id':1,'instance_id':'a'*64,'operation':'close','revision_role':'base_head_or_retained','result':{'closed':True,'retained_contexts':0},'error':None,'outer_wire_bytes':0,'model_tokens':None,'meter_unit':'serialized_bytes'}
    for _ in range(16):
        n=len(v.canonical(response))
        if response['outer_wire_bytes']==n:break
        response['outer_wire_bytes']=n
    record={'schema_version':'xrai.eval.store-process.v1','command':['/owned/native-bin/context-store-session'],'pid':123,'frame_limit':v.FRAME,'stderr_limit':65536,'stderr':captured(b''),'active':False,'native_execution_authorized_by_helper':False,'rows':[row(request,response)],'termination':{'reason':'explicit_close','exit_code':0,'parent_reaped':True,'process_group_absent':True,'signal_error':None,'stderr_limit_exceeded':False}}
    return request,response,record

class OwnDataTests(unittest.TestCase):
    def test_frozen_design_seven_cases(self):
        protocol,cases=v.assets();self.assertEqual(len(cases),7);self.assertEqual(protocol['tokio_pin'],'2fb5757a97a94b3173f8fdd7b6280423b63da6e6')
    def test_valid_captured_frame_reader(self):
        req,res,record=example();reader=v.Reader(record,record['command'][0]);self.assertEqual(reader.call(req),res);reader.finish()
    def test_diff_identity_changed(self):
        _,cases=v.assets();diff=copy.deepcopy(cases[0]['diff']);diff['head']['capture_blake3']='0'*64
        with self.assertRaises(ValueError):v.validate_diff(diff)
    def test_diff_presence_changed_with_rehash(self):
        _,cases=v.assets();diff=copy.deepcopy(cases[0]['diff']);diff['base']['files']['src/a.jsx']={'state':'present','bytes_hex':''};diff['base']['capture_blake3']=v.revision_identity(diff['base'])
        with self.assertRaises(ValueError):v.validate_diff(diff)
    def test_integral_head_changed_with_valid_capture_hash(self):
        _,cases=v.assets();diff=copy.deepcopy(cases[4]['diff']);diff['head']['files']['src/a.jsx']['bytes_hex']+='78';diff['head']['capture_blake3']=v.revision_identity(diff['head'])
        with self.assertRaises(ValueError):v.validate_diff(diff)
    def test_utf8_boundary_changed(self):
        _,cases=v.assets();diff=copy.deepcopy(cases[4]['diff']);diff['changes'][0]['hunks'][0]['base_span'][0]=7
        with self.assertRaises((ValueError,UnicodeError)):v.validate_diff(diff)
    def test_duplicate_json_key(self):
        with self.assertRaises(ValueError):v.decode(b'{"command_id":1,"command_id":2}')
    def test_nonfinite_json(self):
        with self.assertRaises(ValueError):v.decode(b'{"a":NaN}')
    def test_captured_integrity(self):
        payload=captured(b'abc');payload['base64']=base64.b64encode(b'xyz').decode()
        with self.assertRaises(ValueError):v.retained(payload)
    def test_captured_bool_size(self):
        payload=captured(b'x');payload['bytes']=True
        with self.assertRaises(ValueError):v.retained(payload)
    def check_row_mutation(self,mutate):
        req,res,record=example();mutate(record);reader=v.Reader(record,record['command'][0])
        with self.assertRaises(ValueError):reader.call(req)
    def test_row_command_bool(self):self.check_row_mutation(lambda r:r['rows'][0].__setitem__('command_id',True))
    def test_row_written_truncated(self):self.check_row_mutation(lambda r:r['rows'][0].__setitem__('written_bytes',1))
    def test_row_outcome_forged(self):self.check_row_mutation(lambda r:r['rows'][0].__setitem__('outcome','timeout'))
    def test_row_deadline_exceeded(self):self.check_row_mutation(lambda r:r['rows'][0].__setitem__('elapsed_seconds',31))
    def test_row_nonfinite_elapsed(self):self.check_row_mutation(lambda r:r['rows'][0].__setitem__('elapsed_seconds',float('inf')))
    def response_mutation(self,mutate):
        req,res,record=example();mutate(res);record['rows'][0]=row(req,res);reader=v.Reader(record,record['command'][0])
        with self.assertRaises(ValueError):reader.call(req)
    def test_response_foreign_command(self):self.response_mutation(lambda r:r.__setitem__('command_id',2))
    def test_response_command_bool(self):self.response_mutation(lambda r:r.__setitem__('command_id',True))
    def test_response_missing_field(self):self.response_mutation(lambda r:r.pop('model_tokens'))
    def test_response_outer_count_changed(self):self.response_mutation(lambda r:r.__setitem__('outer_wire_bytes',1))
    def test_response_provider_token_claim(self):self.response_mutation(lambda r:r.__setitem__('model_tokens',123))
    def test_response_extra_field(self):self.response_mutation(lambda r:r.__setitem__('private_reference','forbidden'))
    def test_response_fake_instance(self):self.response_mutation(lambda r:r.__setitem__('instance_id','fake'))
    def test_omitted_row(self):
        req,_,record=example();record['rows']=[];reader=v.Reader(record,record['command'][0])
        with self.assertRaises(ValueError):reader.call(req)
    def test_extra_row(self):
        req,_,record=example();record['rows'].append(copy.deepcopy(record['rows'][0]));reader=v.Reader(record,record['command'][0]);reader.call(req)
        with self.assertRaises(ValueError):reader.finish()
    def test_process_termination_not_complete(self):
        _,_,record=example();record['termination']['process_group_absent']=False
        with self.assertRaises(ValueError):v.Reader(record,record['command'][0])
    def test_process_wrong_schema(self):
        _,_,record=example();record['schema_version']='wrong'
        with self.assertRaises(ValueError):v.Reader(record,record['command'][0])
    def test_process_extra_field(self):
        _,_,record=example();record['hidden']='forged'
        with self.assertRaises(ValueError):v.Reader(record,record['command'][0])
    def test_process_rows_wrong_type(self):
        _,_,record=example();record['rows']={}
        with self.assertRaises(ValueError):v.Reader(record,record['command'][0])
    def test_process_stderr_limit_bool(self):
        _,_,record=example();record['stderr_limit']=True
        with self.assertRaises(ValueError):v.Reader(record,record['command'][0])
    def test_row_extra_field(self):self.check_row_mutation(lambda r:r['rows'][0].__setitem__('hidden','forged'))
    def test_row_missing_field(self):self.check_row_mutation(lambda r:r['rows'][0].pop('elapsed_seconds'))
    def test_row_boolean_start(self):self.check_row_mutation(lambda r:r['rows'][0].__setitem__('started_monotonic',True))
    def test_row_boolean_deadline(self):self.check_row_mutation(lambda r:r['rows'][0].__setitem__('timeout_ms',True))
    def mapped_examples(self):
        def sample(epoch,context,incarnation,expand_id):
            manifest={'context_id':context,'retention_epoch':epoch,'incarnation':incarnation,'input':{'source':'frozen semantic text'}}
            return {'start_id':1,'now_ms':0,'context':{'instance_id':epoch,'result':{'context_id':context,'next':[{'context_id':context}],'request_id':'context-query-stable','source':'frozen semantic text'}},'inspect':{'instance_id':epoch,'result':{'manifest':copy.deepcopy(manifest),'snapshots':[{'capture':'frozen semantic text'}]}},'expand':{'instance_id':epoch,'result':{'context_id':context,'request_id':expand_id,'next':[]}},'after_expand':{'instance_id':epoch,'result':{'manifest':copy.deepcopy(manifest),'snapshots':[{'ir':'frozen semantic text'}]}}}
        return sample('a'*64,'ctx_'+'a'*64,2,'request_'+'a'*64),sample('b'*64,'ctx_'+'b'*64,1,'request_'+'b'*64)
    def test_exact_operational_mapping(self):
        live,fresh=self.mapped_examples();self.assertTrue(v.normalize_pair(live,fresh))
    def test_semantic_epoch_string_not_remapped(self):
        live,fresh=self.mapped_examples();live['inspect']['result']['snapshots'][0]['capture']=live['context']['instance_id'];fresh['inspect']['result']['snapshots'][0]['capture']=fresh['context']['instance_id']
        with self.assertRaisesRegex(ValueError,'outside allowed metadata'):v.normalize_pair(live,fresh)
    def test_semantic_context_string_not_remapped(self):
        live,fresh=self.mapped_examples();live['context']['result']['source']=live['context']['result']['context_id'];fresh['context']['result']['source']=fresh['context']['result']['context_id']
        with self.assertRaisesRegex(ValueError,'outside allowed metadata'):v.normalize_pair(live,fresh)
    def test_semantic_source_difference_never_dropped(self):
        live,fresh=self.mapped_examples();fresh['after_expand']['result']['snapshots'][0]['ir']='different source'
        with self.assertRaises(ValueError):v.normalize_pair(live,fresh)
    def test_wrong_operational_slot_identity(self):
        live,fresh=self.mapped_examples();fresh['expand']['result']['context_id']='ctx_foreign'
        with self.assertRaises(ValueError):v.normalize_pair(live,fresh)
    def test_process_pid_bool(self):
        _,_,record=example();record['pid']=True
        with self.assertRaises(ValueError):v.Reader(record,record['command'][0])
    def test_design_mutated_source_fixture(self):
        with tempfile.TemporaryDirectory()as tmp:
            dest=Path(tmp)
            for n in v.INPUTS:(dest/n).write_bytes((v.ASSETS/n).read_bytes())
            (dest/'cases.json').write_bytes((dest/'cases.json').read_bytes()+b' ')
            with self.assertRaises(ValueError):v.assets(dest)
    @unittest.skipUnless(os.environ.get('XRAI_C07_STORE_OUTPUT'),'factual native producer absent; no ELF executed locally')
    def test_authentic_native_export_substitutions(self):
        source=Path(os.environ['XRAI_C07_STORE_OUTPUT'])
        original=v.decode((source/'session.json').read_bytes())
        def altered_record(mutate):
            record=copy.deepcopy(original)
            rows=record['rows']
            index=next(i for i,row in enumerate(rows) if v.decode(v.retained(row['request']))['operation']=='inspect')
            response=v.decode(v.retained(rows[index]['response']))
            mutate(response['result'])
            response['outer_wire_bytes']=0
            for _ in range(16):
                size=len(v.canonical(response))
                if response['outer_wire_bytes']==size:break
                response['outer_wire_bytes']=size
            rows[index]['response']=captured(v.canonical(response)+b'\n')
            return record
        changes=[lambda e:e['snapshots'][0]['capture'].__setitem__('external_revision','forged'),lambda e:e['snapshots'][0]['input']['files'].__setitem__('src/a.jsx','invented'),lambda e:e['snapshots'][1].__setitem__('ir',{'fake':'Rust parse'}),lambda e:e['manifest'].__setitem__('context_id','ctx_'+'0'*64),lambda e:e['manifest']['candidates'][0].__setitem__('snapshot_id','snap_'+'0'*64),lambda e:e['manifest']['normalized_request'].__setitem__('description','evaluator-hidden'),lambda e:e['manifest'].__setitem__('incarnation',True)]
        with tempfile.TemporaryDirectory()as tmp:
            dest=Path(tmp)/'event';shutil.copytree(source,dest)
            for mutate in changes:
                (dest/'session.json').write_bytes(v.canonical(altered_record(mutate)))
                with self.assertRaises(ValueError):v.verify(dest)

    @unittest.skipUnless(os.environ.get('XRAI_C07_STORE_OUTPUT'),'factual native producer absent; no ELF executed locally')
    def test_authentic_native_artifact(self):
        result=v.verify(Path(os.environ['XRAI_C07_STORE_OUTPUT']));self.assertEqual(result['cases'],7);self.assertTrue(result['complete_public_and_inspect_equal'])

if __name__=='__main__':unittest.main()
