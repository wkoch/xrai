"""Data-only contraproofs. Fake ELF is never run or accepted as API authority."""
import base64
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import p3_diff_native_verify as v


def synthetic(output):
    output.mkdir();(output/'inputs').mkdir();(output/'native-bin').mkdir();(output/'session').mkdir()
    for n in v.INPUTS:shutil.copyfile(v.ASSETS/n,output/'inputs'/n)
    binary=b'\x7fELFsynthetic fixture bytes never executed'
    (output/'native-bin/context-diff-spike').write_bytes(binary)
    receipt={'schema':'xrai.eval.p3-diff-native-receipt.v1','source_sha256':{n:v.sha((v.ROOT/n).read_bytes()) for n in v.SOURCES},
             'input_sha256':{n:v.sha((v.ASSETS/n).read_bytes()) for n in v.INPUTS},
             'binary':{'path':'native-bin/context-diff-spike','sha256':v.sha(binary),'bytes':len(binary)},
             'environment':{'github_actions':'true','system':'Linux','machine':'fake','github_sha':'a'*40,'github_run_id':'1'},
             'admitted':False,'quota_event_credit':False,'competitive_runs_allowed':False,'new_eligible_dossier':False}
    (output/'receipt.json').write_text(json.dumps(receipt))
    (output/'rebuild').mkdir()
    for name in ['session','rebuild']:
        commands=v.commands(1000 if name=='session' else 1001,fresh=name=='rebuild');rows=[];stdout=b''
        for n,(rq,rs) in enumerate(commands):
            a=v.canonical(rq)+b'\n';b=v.canonical(rs)+b'\n';stdout+=b
            rows.append({'sequence':n,'request_base64':base64.b64encode(a).decode(),'response_base64':base64.b64encode(b).decode(),'request_sha256':v.sha(a),'response_sha256':v.sha(b)})
        (output/name/'transcript.jsonl').write_bytes(b'\n'.join(v.canonical(r) for r in rows)+b'\n')
        (output/name/'stdout.jsonl').write_bytes(stdout);(output/name/'stderr.bin').write_bytes(b'')
        metadata={'pid':1000 if name=='session' else 1001,'exit_code':0,'unread_output_bytes':0,'explicit_close':True,'wrapper_reaped':True,
                  'command_count':len(commands),'closed_response':commands[-1][1]}
        (output/name/'process.json').write_text(json.dumps(metadata))


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.original=Path(cls.temp.name)/'original';synthetic(cls.original)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def fresh(self):
        p=Path(self.temp.name)/self.id().split('.')[-1];shutil.copytree(self.original,p);return p

    def mutate_response(self,p,change):
        transcript=p/'session/transcript.jsonl';rows=[v.decode(r) for r in transcript.read_bytes().splitlines()]
        response=v.decode(base64.b64decode(rows[0]['response_base64']));change(response)
        raw=v.canonical(response)+b'\n';rows[0]['response_base64']=base64.b64encode(raw).decode();rows[0]['response_sha256']=v.sha(raw)
        transcript.write_bytes(b'\n'.join(v.canonical(r) for r in rows)+b'\n')
        (p/'session/stdout.jsonl').write_bytes(b''.join(base64.b64decode(r['response_base64']) for r in rows))

    def test_synthetic_data_receipt_is_not_native_authority(self):
        result=v.verify(self.original);self.assertEqual(result['accepted_cases'],21);self.assertGreater(result['omitted_evidence'],0)

    def test_all_presence_cases(self):
        _,cases,_=v.assets();kinds={c['kind'] for _,i in cases for c in i['changes']};self.assertEqual(kinds,{'modify','create','delete'})
        self.assertTrue(any(not i['base'] or any(c['kind']=='create' for c in i['changes']) for _,i in cases))

    def test_empty_present_distinct_from_absent(self):
        _,cases,_=v.assets()
        c=next(v.prepare(i,1) for name,i in cases if name=='create-empty')
        present=[o for o in c['manifest']['obligations'] if o['kind']=='file_presence']
        self.assertEqual([o['present'] for o in present],[False,True]);self.assertEqual(c['evidence'][0]['raw'],b'')

    def test_original_negatives_preserved(self):self.assertEqual(len(v.assets()[2]),34)
    def test_frozen_bounds(self):self.assertLessEqual(len(v.commands(1)),512)
    def test_source_pin(self):
        p=self.fresh();r=v.decode((p/'receipt.json').read_bytes());r['source_sha256'][v.SOURCES[0]]='0'*64;(p/'receipt.json').write_text(json.dumps(r))
        with self.assertRaises(ValueError):v.verify(p)
    def test_binary_pin(self):
        p=self.fresh();(p/'native-bin/context-diff-spike').write_bytes(b'\x7fELFother')
        with self.assertRaises(ValueError):v.verify(p)
    def test_closure(self):
        p=self.fresh();(p/'unexpected.txt').write_text('extra')
        with self.assertRaises(ValueError):v.verify(p)
    def test_missing_stdout(self):
        p=self.fresh();(p/'session/stdout.jsonl').unlink()
        with self.assertRaises(ValueError):v.verify(p)
    def test_stderr(self):
        p=self.fresh();(p/'session/stderr.bin').write_bytes(b'error')
        with self.assertRaises(ValueError):v.verify(p)
    def test_process_pid(self):
        p=self.fresh();r=v.decode((p/'session/process.json').read_bytes());r['pid']=0;(p/'session/process.json').write_text(json.dumps(r))
        with self.assertRaises(ValueError):v.verify(p)
    def test_duplicate_json(self):
        with self.assertRaises(ValueError):v.decode(b'{"a":1,"a":2}')
    def test_local_collection_refused(self):
        import p3_diff_native_collect as c
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'false'}):
            with self.assertRaises(ValueError):c.collect('/not/executed',Path(self.temp.name)/'local')
    def test_actual_retained_receipt(self):
        path=os.environ.get('XRAI_C06_P3_OUTPUT')
        if not path:self.skipTest('actual native receipt not provided; synthetic receipt never establishes provenance')
        self.assertTrue(v.verify(path)['native_typed_consumer_verified'])

    def edit_row(self,p,change):
        transcript=p/'session/transcript.jsonl';rows=[v.decode(r) for r in transcript.read_bytes().splitlines()];change(rows[0])
        transcript.write_bytes(b'\n'.join(v.canonical(r) for r in rows)+b'\n')

    def test_reject_sequence_boolean(self):
        p=self.fresh();self.edit_row(p,lambda r:r.__setitem__('sequence',False))
        with self.assertRaises(ValueError):v.verify(p)

    def test_reject_sequence_float(self):
        p=self.fresh();self.edit_row(p,lambda r:r.__setitem__('sequence',0.0))
        with self.assertRaises(ValueError):v.verify(p)

    def mutate_process(self,p,key,value):
        q=p/'session/process.json';r=v.decode(q.read_bytes());r[key]=value;q.write_text(json.dumps(r))

    def test_reject_exit_boolean(self):
        p=self.fresh();self.mutate_process(p,'exit_code',False)
        with self.assertRaises(ValueError):v.verify(p)

    def test_reject_unread_boolean(self):
        p=self.fresh();self.mutate_process(p,'unread_output_bytes',False)
        with self.assertRaises(ValueError):v.verify(p)

    def test_reject_command_count_float(self):
        p=self.fresh();self.mutate_process(p,'command_count',182.0)
        with self.assertRaises(ValueError):v.verify(p)

    def change_request_span(self,p,value):
        def change(row):
            request=v.decode(base64.b64decode(row['request_base64']))
            request['intake']['changes'][0]['hunks'][0]['base_span'][0]=value
            raw=v.canonical(request)+b'\n';row['request_base64']=base64.b64encode(raw).decode();row['request_sha256']=v.sha(raw)
        self.edit_row(p,change)

    def test_reject_request_span_boolean(self):
        p=self.fresh();self.change_request_span(p,False)
        with self.assertRaises(ValueError):v.verify(p)

    def test_reject_request_span_float(self):
        p=self.fresh();self.change_request_span(p,0.0)
        with self.assertRaises(ValueError):v.verify(p)

    def test_reject_binary_size_float(self):
        p=self.fresh();q=p/'receipt.json';r=v.decode(q.read_bytes());r['binary']['bytes']=float(r['binary']['bytes']);q.write_text(json.dumps(r))
        with self.assertRaises(ValueError):v.verify(p)

    def test_reject_stored_verification_count_float(self):
        p=self.fresh();r=v.verify(p);r['accepted_cases']=21.0;(p/'verification.json').write_text(json.dumps(r))
        with self.assertRaises(ValueError):v.verify(p)

    def test_reject_closed_response_count_float(self):
        p=self.fresh();q=p/'session/process.json';r=v.decode(q.read_bytes());r['closed_response']['wire_bytes']=float(r['closed_response']['wire_bytes']);q.write_text(json.dumps(r))
        with self.assertRaises(ValueError):v.verify(p)

    def test_independent_rebuild_complete(self):
        self.assertTrue(v.verify(self.original)['complete_rebuild_equal'])

    def test_independent_rebuild_missing(self):
        p=self.fresh();(p/'rebuild/stdout.jsonl').unlink()
        with self.assertRaises(ValueError):v.verify(p)

    def test_reject_rebuild_source_span(self):
        p=self.fresh();q=p/'rebuild/transcript.jsonl';rows=[v.decode(r) for r in q.read_bytes().splitlines()]
        r=v.decode(base64.b64decode(rows[0]['response_base64']));r['result']['items'][0]['delivered_span']=[0,0]
        raw=v.canonical(r)+b'\n';rows[0]['response_base64']=base64.b64encode(raw).decode();rows[0]['response_sha256']=v.sha(raw)
        q.write_bytes(b'\n'.join(v.canonical(r) for r in rows)+b'\n');(p/'rebuild/stdout.jsonl').write_bytes(b''.join(base64.b64decode(r['response_base64']) for r in rows))
        with self.assertRaises(ValueError):v.verify(p)


def rejection(name,change):
    def test(self):
        p=self.fresh();self.mutate_response(p,change)
        with self.assertRaises(ValueError):v.verify(p)
    test.__name__='test_reject_'+name;return test

MUTATIONS={
    'wire_bytes':lambda r:r.__setitem__('wire_bytes',0),
    'model_tokens':lambda r:r.__setitem__('model_tokens',1),
    'controlled_tokens':lambda r:r.__setitem__('controlled_tokens',1),
    'producer':lambda r:r.__setitem__('producer','0'*64),
    'pid':lambda r:r.__setitem__('pid',1001),
    'intake_sha256':lambda r:r['result']['manifest'].__setitem__('intake_sha256','0'*64),
    'intake_native_sha_promotion':lambda r:r['result']['manifest'].__setitem__('intake_sha256_checked_natively',True),
    'integral_head':lambda r:r['result']['manifest'].__setitem__('integral_head_verified',False),
    'base_revision':lambda r:r['result']['manifest'].__setitem__('base_snapshot_id','0'*64),
    'head_revision':lambda r:r['result']['manifest'].__setitem__('head_snapshot_id','0'*64),
    'context_revision':lambda r:r['result'].__setitem__('context_id','0'*64),
    'raw_diff':lambda r:r['result']['manifest'].__setitem__('raw_diff_hex',''),
    'decoder_origin':lambda r:r['result']['manifest'].__setitem__('decoder_profile','other'),
    'omissions':lambda r:r['result'].__setitem__('omitted',[{'handle':'forged','reason':'budget'}]),
    'source_bytes':lambda r:r['result']['items'][0].__setitem__('content_hex','78'),
    'source_hash':lambda r:r['result']['items'][0].__setitem__('source_hash','0'*64),
    'source_span':lambda r:r['result']['items'][0].__setitem__('delivered_span',[0,0]),
    'presence':lambda r:r['result']['manifest']['obligations'][0].__setitem__('present',False),
    'handle':lambda r:r['result']['items'][0].__setitem__('handle','foreign'),
    'semantic_promotion':lambda r:r['result']['manifest'].__setitem__('semantic_support','resolved'),
}
for name,change in MUTATIONS.items():setattr(Tests,'test_reject_'+name,rejection(name,change))

if __name__=='__main__':unittest.main()
