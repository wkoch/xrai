"""Own synthetic-counter tests; factual L4 quantities only from pinned CI replay."""
from copy import deepcopy
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'eval/context/lexical-token-v1'))
import driver
import verifier
from lexical_retrieval import LexicalIndex


class ByteSpy:
    name='synthetic-test-utf8-byte-units'
    def encode(self,text,*,allowed_special,disallowed_special):
        if allowed_special!=set() or disallowed_special!=():raise ValueError('special token policy changed')
        return list(range(len(text.encode('utf-8'))))


class CyclicSpy:
    name='synthetic-test-count-cycle'
    def encode(self,text,**kwargs):
        n=json.loads(text)['budget']['controlled_wire_tokens']
        return [1]*(1 if n!=1 else 2)


class LexicalTokenTests(unittest.TestCase):
    def setUp(self):
        self.config=driver.protocol();self.profile=deepcopy(self.config['profile'])
        self.raw={'a.py':b'needle '*2000,'b.py':b'def needle():\n    return 1\n'}
        self.index=LexicalIndex(self.raw)
        self.delivery=driver.LexicalTokenDelivery(self.index,ByteSpy(),self.profile,self.config,synthetic_test_mode=True)
    def test_freeze_preceded_driver_and_inputs_unchanged(self):
        receipt=driver.freeze.verify();self.assertFalse(receipt['driver_existed']);self.assertFalse(receipt['results_existed'])
        self.assertEqual(len(verifier.read(driver.HERE/'matrix.json')),320)
    def test_complete_wire_and_sidecar_exact_bytes_with_explicit_spy(self):
        result=self.delivery.search('needle',controlled_token_ceiling=100000);wire=result['wire'];side=result['sidecar']
        raw=driver.canonical(wire)
        self.assertEqual(wire['budget']['wire_bytes'],len(raw));self.assertEqual(wire['budget']['controlled_wire_tokens'],len(raw))
        self.assertEqual(base64.b64decode(side['serialized_base64']),raw)
        self.assertEqual(side['serialized_sha256'],driver.sha(raw));self.assertTrue(side['synthetic_test_mode'])
        self.assertEqual(wire['budget']['counting'],'synthetic-test-units-not-tokens')
    def test_original_envelope_intact_and_original_model_tokens_null(self):
        original=self.index.search('needle',method='bm25',top_k=5,max_wire_bytes=65536)
        result=self.delivery.search('needle',controlled_token_ceiling=5000)
        self.assertEqual(result['sidecar']['original_delivery'],original)
        self.assertEqual(result['wire']['producer']['original_delivery_sha256'],driver.sha(driver.canonical(original)))
        self.assertIsNone(original['model_tokens']);self.assertIsNone(result['wire']['model_tokens'])
        self.assertEqual(result['wire']['schema'],'lexical-token-delivery.v1')
    def test_rank_preserved_after_oversized_first_chunk_skipped(self):
        result=self.delivery.search('needle',controlled_token_ceiling=5000)
        snippets=result['wire']['snippets'];self.assertEqual([s['path'] for s in snippets],['b.py'])
        self.assertEqual(snippets[0]['rank'],2)
        self.assertEqual(len(result['wire']['selection']['omitted']),1)
        self.assertLessEqual(result['wire']['budget']['controlled_wire_tokens'],5000)
    def test_full_metadata_candidate_ids_omissions_budget_accounted(self):
        result=self.delivery.search('needle',controlled_token_ceiling=5000);wire=result['wire']
        self.assertEqual(len(wire['selection']['candidate_ids']),2)
        raw=driver.canonical(wire);self.assertGreater(len(raw),sum(len(s['text'].encode()) for s in wire['snippets']))
        self.assertEqual(result['sidecar']['controlled_wire_tokens'],len(raw))
        self.assertEqual(len(result['sidecar']['omission_checks']),2)
    def test_metadata_too_small_fails_without_clipping(self):
        with self.assertRaises(ValueError):self.delivery.search('needle',controlled_token_ceiling=1)
    def test_bool_float_negative_and_unbounded_budget_rejected(self):
        for ceiling in (True,False,2000.0,0,-1,1000001):
            with self.subTest(ceiling=ceiling),self.assertRaises(ValueError):self.delivery.search('needle',controlled_token_ceiling=ceiling)
    def test_fixed_point_cycle_fails_closed(self):
        cyclic=driver.LexicalTokenDelivery(self.index,CyclicSpy(),self.profile,self.config,synthetic_test_mode=True)
        with self.assertRaisesRegex(ValueError,'cycle'):cyclic.search('needle',controlled_token_ceiling=100000)
    def test_synthetic_counter_requires_explicit_mode_and_name(self):
        with self.assertRaises(ValueError):driver.LexicalTokenDelivery(self.index,ByteSpy(),self.profile,self.config)
        invalid=ByteSpy();invalid.name='cl100k_base'
        with self.assertRaises(ValueError):driver.LexicalTokenDelivery(self.index,invalid,self.profile,self.config,synthetic_test_mode=True)
    def test_profile_tamper_rejected_before_counting(self):
        altered=deepcopy(self.profile);altered['fingerprint_sha256']='0'*64
        with self.assertRaises(ValueError):driver.LexicalTokenDelivery(self.index,ByteSpy(),altered,self.config,synthetic_test_mode=True)
    def test_utf8_exact_source_spans_and_ordinary_special_text(self):
        raw='def needle():\n    # café 漢字 <|endoftext|>\r\n    return 1\n'.encode()
        index=LexicalIndex({'unicode.py':raw});delivery=driver.LexicalTokenDelivery(index,ByteSpy(),self.profile,self.config,synthetic_test_mode=True)
        result=delivery.search('needle',controlled_token_ceiling=100000);snippet=result['wire']['snippets'][0]
        self.assertEqual(raw[snippet['start']:snippet['end']],snippet['text'].encode())
        self.assertEqual(snippet['snippet_sha256'],driver.sha(snippet['text'].encode()))
    def test_expansion_full_file_or_controlled_refusal_never_truncates(self):
        search=self.delivery.search('needle',controlled_token_ceiling=100000);handles=search['wire']['selection']['delivered_ids']
        full=self.delivery.expand(handles,controlled_token_ceiling=100000)
        self.assertEqual(full['wire']['status'],'expanded_full_captured_files')
        self.assertEqual({s['path']:s['text'].encode() for s in full['wire']['snippets']},self.raw)
        refused=self.delivery.expand(handles,controlled_token_ceiling=5000)
        self.assertEqual(refused['wire']['status'],'controlled_token_ceiling_refusal');self.assertEqual(refused['wire']['snippets'],[])
        self.assertLessEqual(refused['wire']['budget']['controlled_wire_tokens'],5000)
    def test_original_byte_refusal_distinct_from_controlled_token_refusal(self):
        index=LexicalIndex({'large.py':b'needle\n'*12000})
        delivery=driver.LexicalTokenDelivery(index,ByteSpy(),self.profile,self.config,synthetic_test_mode=True)
        found=delivery.search('needle',controlled_token_ceiling=100000)
        expanded=delivery.expand(found['wire']['selection']['delivered_ids'],controlled_token_ceiling=100000)
        self.assertEqual(expanded['wire']['status'],'original_byte_ceiling_refusal');self.assertEqual(expanded['wire']['snippets'],[])
        self.assertEqual(expanded['sidecar']['original_delivery']['status'],'insufficient_byte_budget')
    def test_duplicate_or_bad_handle_lists_rejected(self):
        handle=self.delivery.search('needle',controlled_token_ceiling=100000)['wire']['selection']['delivered_ids'][0]
        for values in ('notlist',[True],[[]],['a'*63],['A'*64],[handle,handle],['0'*64]*6):
            with self.subTest(values=values),self.assertRaises(ValueError):self.delivery.expand(values,controlled_token_ceiling=100000)
    def test_unknown_handle_refused_without_promotion(self):
        result=self.delivery.expand(['0'*64],controlled_token_ceiling=100000)
        self.assertEqual(result['wire']['status'],'original_handle_refusal');self.assertEqual(result['wire']['snippets'],[])
    def test_changed_snapshot_handles_refused(self):
        handle=self.delivery.search('needle',controlled_token_ceiling=100000)['wire']['selection']['delivered_ids'][0]
        changed=driver.LexicalTokenDelivery(LexicalIndex({'changed.py':b'needle'}),ByteSpy(),self.profile,self.config,synthetic_test_mode=True)
        self.assertEqual(changed.expand([handle],controlled_token_ceiling=100000)['wire']['status'],'original_handle_refusal')
    def test_absent_query_no_fake_source_and_expansion_not_requested(self):
        result=self.delivery.search('qzvksndpwbf467901',controlled_token_ceiling=100000)
        self.assertEqual(result['wire']['snippets'],[])
        expansion=self.delivery.expand([],controlled_token_ceiling=100000)
        self.assertEqual(expansion['wire']['status'],'not_requested_no_delivered_handles')
        self.assertIsNone(expansion['sidecar']['original_delivery'])
    def test_initial_request_projection_separate_provider_unknown(self):
        result=self.delivery.search('needle',controlled_token_ceiling=100000);side=result['sidecar']
        self.assertEqual(side['controlled_request_projection_tokens'],len(driver.canonical(side['request_projection'])))
        self.assertNotEqual(side['controlled_request_projection_tokens'],side['controlled_wire_tokens'])
        self.assertIsNone(side['provider_tokens']);self.assertIsNone(side['provider_charge'])
    def test_deterministic_repetition(self):
        self.assertEqual(self.delivery.search('needle',controlled_token_ceiling=5000),self.delivery.search('needle',controlled_token_ceiling=5000))
    def test_synthetic_sidecar_cannot_be_promoted_by_verifier(self):
        result=self.delivery.search('needle',controlled_token_ceiling=100000)
        with self.assertRaisesRegex(ValueError,'synthetic'):verifier.validate_delivery(result,result)
    def test_tampered_whole_wrapper_or_sidecar_rejected_typed(self):
        result=self.delivery.search('needle',controlled_token_ceiling=100000)
        for mutate in (lambda r:r['wire']['budget'].__setitem__('controlled_wire_tokens',True),
                       lambda r:r['sidecar'].__setitem__('serialized_base64',base64.b64encode(b'clipped').decode()),
                       lambda r:r['wire']['snippets'][0].__setitem__('rank',1)):
            altered=deepcopy(result);mutate(altered)
            if altered==result:altered['wire']['snippets'][0]['rank']=99
            with self.assertRaises(ValueError):verifier.validate_delivery(altered,result)
    def test_evaluation_not_called_during_search_or_expand(self):
        with patch.object(driver,'evaluate',side_effect=AssertionError('labels entered selector')):
            result=self.delivery.search('needle',controlled_token_ceiling=100000)
            self.delivery.expand(result['wire']['selection']['delivered_ids'],controlled_token_ceiling=100000)
    def test_captured_real_GO02_integrity_only_no_authority_claim(self):self._real_case('GO-02')
    def test_captured_real_RS03_integrity_only_no_child_wait_claim(self):self._real_case('RS-03')
    def _real_case(self,query_id):
        queries=json.loads((ROOT/'eval/context/lexical/queries.json').read_bytes());q=next(q for q in queries if q['query_id']==query_id)
        manifest=json.loads((ROOT/'eval/context/lexical/manifest.json').read_bytes());unit=next(u for u in manifest['universes'] if u['family']==q['family'])
        files={p:(ROOT/'eval/context/lexical'/v['asset']).read_bytes() for p,v in unit['files'].items()}
        delivery=driver.LexicalTokenDelivery(LexicalIndex(files),ByteSpy(),self.profile,self.config,synthetic_test_mode=True)
        result=delivery.search(q['query'],controlled_token_ceiling=100000)
        self.assertTrue(result['sidecar']['synthetic_test_mode']);self.assertEqual(result['wire']['coverage']['semantic_status'],'unknown')
        for s in result['wire']['snippets']:
            self.assertEqual(s['text'].encode(),files[s['path']][s['start']:s['end']]);self.assertEqual(s['source_sha256'],driver.sha(files[s['path']]))
        self.assertIn(query_id,self.config['annotations'])
    def test_no_output_written_when_pinned_counter_unavailable(self):
        with tempfile.TemporaryDirectory() as td,patch.object(driver,'tokenizer',side_effect=ValueError('fixed runtime absent')):
            output=Path(td)/'event'
            with self.assertRaises(ValueError):driver.run(output)
            self.assertFalse(output.exists())
    def test_source_binding_includes_workflow_tests_and_requirements(self):
        bindings=driver.source_bindings()
        self.assertIn('.github/workflows/l5-lexical-token.yml',bindings)
        self.assertIn('crates/xrai-eval/harness/tests/test_lexical_tokens.py',bindings)
        self.assertIn('docs/contracts/examples/requirements.txt',bindings)
    def test_strict_json_and_typed_canonical_equality(self):
        for raw in (b'{"count":NaN}',b'{"count":1,"count":2}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):verifier.decode(raw)
        self.assertFalse(verifier.same({'count':True},{'count':1}))
    @unittest.skipUnless(os.environ.get('XRAI_LEXICAL_TOKEN_OUTPUT'),'actual pinned CI measurement absent; synthetic own tests only')
    def test_actual_pinned_complete_measurement_replayed(self):
        result=verifier.verify(Path(os.environ['XRAI_LEXICAL_TOKEN_OUTPUT']))
        self.assertTrue(result['tokenizer_measured']);self.assertEqual(result['matrix_cells'],320)
        self.assertEqual(result['search_and_expansion_deliveries'],640);self.assertEqual(result['artifact_files'],354)
        self.assertIsNone(result['provider_tokens']);self.assertFalse(result['ranking_redesigned'])


if __name__=='__main__':unittest.main()
