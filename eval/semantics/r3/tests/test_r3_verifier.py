import importlib.util,json,tempfile,unittest,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
SPEC=importlib.util.spec_from_file_location('verify_semantics',ROOT/'eval/scripts/verify_semantics.py')
V=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(V)
LOG=Path(os.environ.get('XRAI_R3_RECEIPT_DIR', ROOT/'docs/relatorios/logs/L5-continuacao/r3/final'))
MATRIX=ROOT/'eval/semantics/r3'
class R3VerifierTests(unittest.TestCase):
    def reject(self,stem,mutate):
        data=json.loads((LOG/(stem+'-completed.stdout')).read_text());mutate(data)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'changed.json';p.write_text(json.dumps(data))
            with self.assertRaises((AssertionError,KeyError,StopIteration,UnicodeDecodeError,IndexError)):
                V.verify(MATRIX/(stem+'.json'),p)
    def test_all_originals(self):
        for stem in ['rust-r3','counterproofs-r3','counterproofs-extra','tokio-test-development','incremental-events','p3-consumer']:
            V.verify(MATRIX/(stem+'.json'),LOG/(stem+'-completed.stdout'))
    def test_condition_state(self):
        self.reject('rust-r3',lambda d:d['rows'][23]['snapshot']['conditions'][0].update(state='known_false'))
    def test_binding_name(self):
        self.reject('rust-r3',lambda d:d['rows'][1]['snapshot']['bindings'][0].update(name='forged'))
    def test_binding_temporal_range(self):
        self.reject('rust-r3',lambda d:d['rows'][1]['snapshot']['bindings'][0].update(visible_start=0))
    def test_binding_parent_scope(self):
        self.reject('rust-r3',lambda d:d['rows'][1]['snapshot']['bindings'][0].update(parent_scope_local_id=999))
    def test_alias_initializer(self):
        self.reject('rust-r3',lambda d:d['rows'][12]['snapshot']['bindings'][0].update(function_path='other'))
    def test_scope_parent(self):
        self.reject('rust-r3',lambda d:d['rows'][0]['snapshot']['scopes'][1].update(parent_scope_local_id=999))
    def test_occurrence_witness(self):
        self.reject('p3-consumer',lambda d:d['rows'][0]['result']['evidence'].pop(0))
    def test_wrong_snapshot(self):
        self.reject('p3-consumer',lambda d:d['rows'][0]['result']['evidence'][0].update(snapshot_id='snap_wrong'))
    def test_incremental_gap_difference(self):
        self.reject('incremental-events',lambda d:d['events'][0]['incremental']['gaps'].append({'reason':'forged','module':'','evidence':None}))
    def test_incremental_generation(self):
        self.reject('incremental-events',lambda d:d['events'][0].update(generation_after=100))
    def test_incremental_source(self):
        self.reject('incremental-events',lambda d:d['events'][0]['incremental']['input']['files'].update({'src/lib.rs':'forged'}))
    def test_shared_forged_event_target(self):
        def change(d):
            for name in ['incremental','rebuild']:
                d['events'][0][name]['references'][0]['resolution'].update(state='unknown',target_id=None,candidate_ids=[])
        self.reject('incremental-events',change)
    def test_preregistered_denominator(self):
        self.reject('rust-r3',lambda d:d.update(resolvable=15))
if __name__=='__main__':unittest.main()
