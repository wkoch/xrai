"""Own data-only contraproofs; no upstream module is imported or executed."""
from hashlib import sha256
import importlib.util
import math
from pathlib import Path
import sys
import unittest

HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HARNESS))
from lexical_retrieval import LexicalIndex, tokenize, wire_bytes
ROOT = HARNESS.parents[2]


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.files = {'src/alpha.py':b'def load_value():\n    return 17\n',
            'src/other.py':b'def close_socket():\n    return 9\n','src/empty.py':b''}
        self.index = LexicalIndex(self.files)

    def test_identifier_components_preserve_whole(self):
        self.assertEqual(tokenize('HTTPServer load_value camelCase'),
            ['httpserver','http','server','load_value','load','value','camelcase','camel','case'])

    def test_unicode_words_preserve_spelling(self):
        self.assertEqual(tokenize('Árvore Δέλτα'), ['árvore','δέλτα'])

    def test_both_methods_find_identifier(self):
        for method in ('bm25','tfidf_cosine'):
            result=self.index.search('load_value',method=method)
            self.assertEqual(result['snippets'][0]['path'],'src/alpha.py')
            self.assertGreater(result['snippets'][0]['score'],0)
            self.assertIsNone(result['model_tokens'])
            self.assertEqual(result['coverage']['semantic_status'],'unknown')

    def test_path_terms_are_searchable(self):
        self.assertEqual(self.index.search('alpha')['snippets'][0]['path'],'src/alpha.py')

    def test_absent_term_never_fabricates_hit(self):
        for method in ('bm25','tfidf_cosine'):
            result=self.index.search('xyznegative78129',method=method)
            self.assertEqual(result['status'],'no_lexical_match_captured_scope')
            self.assertEqual(result['snippets'],[])

    def test_empty_query(self):
        self.assertEqual(self.index.search('')['snippets'],[])

    def test_empty_source_remains_coverage(self):
        self.assertEqual(self.index.search('load')['coverage']['empty_files'],1)
        empty=LexicalIndex({'empty.py':b''})
        self.assertEqual(empty.search('load')['coverage']['indexed_chunks'],0)

    def test_owned_bytes_and_input_mapping_are_immutable(self):
        original=bytearray(b'load_value')
        files={'a':original}; index=LexicalIndex(files)
        before=index.search('load')
        original[:]=b'otherthing';files.clear()
        self.assertEqual(index.search('load'),before)

    def test_configuration_and_owned_mapping_are_readonly(self):
        with self.assertRaises(TypeError): self.index.configuration["k1"]=9
        with self.assertRaises(TypeError): self.index._files["src/alpha.py"]=b"other"

    def test_whole_envelope_wire_size(self):
        result=self.index.search('load_value')
        self.assertEqual(result['wire_bytes'],len(wire_bytes(result)))
        fitted=self.index.search('load_value',max_wire_bytes=result['wire_bytes'])
        self.assertEqual(fitted,result)
        refused=self.index.search('load_value',max_wire_bytes=result['wire_bytes']-1)
        self.assertEqual(refused['snippets'],[])
        self.assertEqual(refused['status'],'insufficient_byte_budget')
        self.assertLessEqual(refused['wire_bytes'],result['wire_bytes']-1)

    def test_minimal_envelope_cannot_be_clipped(self):
        with self.assertRaises(ValueError): self.index.search('load',max_wire_bytes=10)

    def test_utf8_exact_spans_and_hashes(self):
        raw='Árvore\nload_value é\nΔέλτα\n'.encode()
        index=LexicalIndex({'unicode.py':raw},chunk_lines=1,overlap_lines=0)
        found=index.search('load_value')['snippets'][0]
        self.assertEqual(raw[found['start']:found['end']],found['text'].encode())
        self.assertEqual(found['source_sha256'],sha256(raw).hexdigest())
        self.assertEqual(found['snippet_sha256'],sha256(found['text'].encode()).hexdigest())

    def test_duplicate_overlap_removed(self):
        index=LexicalIndex({'a.py':b'match\n'*10},chunk_lines=4,overlap_lines=2)
        chunks=index.search('match')['snippets']
        self.assertGreater(len(chunks),1)
        for i,a in enumerate(chunks):
            for b in chunks[i+1:]:
                self.assertFalse(a['start']<b['end'] and b['start']<a['end'])

    def test_tie_break_order_and_same_content_handles(self):
        a=LexicalIndex({'z':b'word','a':b'word'},path_term_weight=0)
        b=LexicalIndex({'a':b'word','z':b'word'},path_term_weight=0)
        self.assertEqual(a.search('word'),b.search('word'))
        self.assertEqual(a.search('word')['snippets'][0]['path'],'a')

    def test_expand_full_bytes_deduplicates_paths(self):
        raw=b'load_value\n'*10
        index=LexicalIndex({'a':raw},chunk_lines=2,overlap_lines=0)
        hits=index.search('load_value')['snippets']
        result=index.expand([hits[0]['id'],hits[1]['id'],hits[0]['id']])
        self.assertEqual(len(result['snippets']),1)
        self.assertEqual(result['snippets'][0]['text'].encode(),raw)
        self.assertEqual(result['snippets'][0]['end'],len(raw))
        self.assertEqual(result['wire_bytes'],len(wire_bytes(result)))

    def test_expansion_all_or_none_under_budget(self):
        index=LexicalIndex({'a':b'word\n'*400},chunk_lines=2,overlap_lines=0)
        hit=index.search('word')['snippets'][0]['id']
        result=index.expand([hit],max_wire_bytes=1200)
        self.assertEqual(result['status'],'insufficient_byte_budget')
        self.assertEqual(result['snippets'],[])
        self.assertEqual(result['refusals'][0]['reason'],'full_files_exceed_budget')

    def test_unknown_expansion_handle(self):
        result=self.index.expand(['bad'])
        self.assertEqual(result['status'],'unknown_handles')
        self.assertEqual(result['snippets'],[])
        self.assertEqual(result['refusals'][0]['id'],'bad')

    def test_changed_snapshot_rejects_handle(self):
        handle=self.index.search('load')['snippets'][0]['id']
        changed=LexicalIndex({**self.files,'src/alpha.py':b'changed'})
        self.assertNotEqual(changed.snapshot_id,self.index.snapshot_id)
        self.assertEqual(changed.expand([handle])['status'],'unknown_handles')
        self.assertEqual(self.index.expand([handle])['status'],'expanded_full_captured_files')

    def test_changed_configuration_rejects_handle(self):
        changed=LexicalIndex(self.files,path_term_weight=2)
        handle=self.index.search('load')['snippets'][0]['id']
        self.assertNotEqual(changed.configuration_id,self.index.configuration_id)
        self.assertEqual(changed.expand([handle])['status'],'unknown_handles')

    def test_bm25_single_term_formula(self):
        index=LexicalIndex({'a':b'word word','b':b'else'},path_term_weight=0)
        actual=index.search('word')['snippets'][0]['score']
        expected=math.log(2)*2*2.2/(2+1.2*(.25+.75*2/1.5))
        self.assertAlmostEqual(actual,expected)

    def test_tfidf_cosine_normalization(self):
        index=LexicalIndex({'a':b'word word','b':b'else'},path_term_weight=0)
        self.assertAlmostEqual(index.search('word',method='tfidf_cosine')['snippets'][0]['score'],1)

    def test_invalid_relative_paths(self):
        for path in ('../a','/a','a//b','a/./b','a\\b','a\x00b',''):
            with self.subTest(path=path),self.assertRaises(ValueError): LexicalIndex({path:b'data'})

    def test_invalid_source_encoding_and_types(self):
        for raw in ('word',b'\xff',b'a'*1048577):
            with self.subTest(raw_type=type(raw)),self.assertRaises(ValueError): LexicalIndex({'a':raw})

    def test_limits_and_nan(self):
        for params in ({'chunk_lines':0},{'overlap_lines':40},{'path_term_weight':True},{'k1':float('nan')},{'b':True}):
            with self.subTest(params=params),self.assertRaises(ValueError): LexicalIndex({'a':b'data'},**params)
        with self.assertRaises(ValueError): LexicalIndex({})
        with self.assertRaises(ValueError): LexicalIndex({str(n):b'x' for n in range(129)})
        with self.assertRaises(ValueError): LexicalIndex({'a':b'x\n'*4100},chunk_lines=1,overlap_lines=0)

    def test_search_refuses_bad_inputs(self):
        for args in ({'method':'semantic'},{'top_k':True},{'top_k':21},{'max_wire_bytes':True}):
            with self.subTest(args=args),self.assertRaises(ValueError): self.index.search('word',**args)
        for query in (b'word','x'*16385):
            with self.assertRaises(ValueError): self.index.search(query)

    def test_expand_refuses_invalid_lists(self):
        for ids in ('handle',[],[3],['x']*21):
            with self.subTest(ids=ids),self.assertRaises(ValueError): self.index.expand(ids)

    def test_real_frozen_matrix_and_proofs(self):
        path=ROOT/'eval/context/lexical/benchmark.py'
        sys.path.insert(0,str(path.parent))
        spec=importlib.util.spec_from_file_location('own_lexical_benchmark',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        result=module.run()
        self.assertEqual(len(result['records']),64)
        self.assertEqual(len(result['snapshots']),4)
        self.assertTrue(result['deterministic_repetitions_verified'])
        self.assertIsNone(result['agent_success'])
        for r in result['records']:
            self.assertLessEqual(r['output']['wire_bytes'],65536)


if __name__=='__main__': unittest.main()
