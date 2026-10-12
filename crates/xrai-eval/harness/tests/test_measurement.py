import base64
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from offline_measurement import ASSETS, measure, project_stream, tokenizer, verify_measurement
from runner import canonical, payload, sha
from agent_ledger import replay_versioned

ROOT = Path(__file__).resolve().parents[4]
V1 = ROOT / 'docs/relatorios/logs/L2/ci-native/native-x86_64-unknown-linux-gnu/baseline/D0-RS-01.json'
V2 = ROOT / 'docs/relatorios/logs/L3/ci-native/native-x86_64-unknown-linux-gnu/baseline/D0-RS-01.json'


class MeasurementTests(unittest.TestCase):
    def test_pinned_reference_vectors(self):
        encoding, profile = tokenizer()
        reference = json.loads((ASSETS / 'reference-vectors.json').read_text())
        self.assertEqual(reference['profile_fingerprint_sha256'], profile['fingerprint_sha256'])
        self.assertEqual(encoding.encode('hello world'), [15339, 1917])
        for vector in reference['vectors']:
            self.assertEqual(encoding.encode(vector['text'], allowed_special=set(), disallowed_special=()), vector['tokens'])

    def test_pinned_configuration_matches_upstream_constructor_offline(self):
        import tiktoken
        from tiktoken.load import load_tiktoken_bpe
        from tiktoken_ext import openai_public
        encoding, profile = tokenizer()
        local_ranks = load_tiktoken_bpe(str(ASSETS / 'cl100k_base.tiktoken'))
        with patch.object(openai_public, 'load_tiktoken_bpe', return_value=local_ranks):
            upstream = openai_public.cl100k_base()
        self.assertEqual(upstream['pat_str'], profile['config']['pattern'])
        self.assertEqual(upstream['special_tokens'], profile['config']['special_tokens'])
        upstream_encoding = tiktoken.Encoding(**upstream)
        for vector in json.loads((ASSETS / 'reference-vectors.json').read_text())['vectors']:
            self.assertEqual(upstream_encoding.encode(vector['text'], disallowed_special=()), vector['tokens'])

    def test_text_unicode_crlf_empty_and_binary_projection(self):
        for data in [b'', 'ação 🌱 e\u0301\r\n'.encode(), b'\x00\xff\r\n']:
            item = project_stream(payload(data, len(data) + 3))
            decoded = item['content'].encode() if item['encoding'] == 'utf-8' else base64.b64decode(item['content'])
            self.assertEqual(decoded, data)
            self.assertTrue(item['truncated'])
            self.assertEqual(item['source_sha256'], sha(data))

    def test_existing_v1_v2_sidecars_without_mutation(self):
        for path in [V1, V2]:
            original = path.read_bytes()
            value = json.loads(original)
            before = canonical(value)
            sidecar = measure(value, tools=[{'name': 'read', 'description': 'tool <|endoftext|>'}])
            self.assertEqual(sidecar['original_record_sha256'], sha(before))
            self.assertGreater(sidecar['controlled_content_tokens'], 0)
            self.assertEqual(replay_versioned(sidecar, original=value)['status'], 'verified_controlled_content')
            self.assertEqual(canonical(value), before)
            self.assertEqual(path.read_bytes(), original)
            self.assertIsNone(value['model']); self.assertIsNone(value['tokenizer'])
            self.assertIsNone(value['measurement']['model_tokens']); self.assertIsNone(value['financial_cost'])
            self.assertEqual(replay_versioned(value)['status'], 'verified_bytes_tokens_unknown')

    def test_measurement_tampering_profile_projection_and_count(self):
        record = json.loads(V2.read_text())
        sidecar = measure(record)
        mutations = [lambda x: x.__setitem__('controlled_content_tokens', x['controlled_content_tokens']+1),
                     lambda x: x['profile']['config'].__setitem__('name', 'changed'),
                     lambda x: x['profile']['serializer'].__setitem__('normalization', 'NFC'),
                     lambda x: x['projection']['rounds'][0]['stdout'].__setitem__('content', 'changed'),
                     lambda x: x.__setitem__('serialized_sha256', '0'*64),
                     lambda x: x.__setitem__('original_record_sha256', '0'*64)]
        for mutation in mutations:
            changed = copy.deepcopy(sidecar); mutation(changed)
            with self.assertRaises(ValueError):
                verify_measurement(changed, record)

    def test_router_rejects_unknown_version_or_missing_original(self):
        with self.assertRaisesRegex(ValueError, 'unsupported record version'):
            replay_versioned({'schema_version': 'xrai.eval.future.v99'})
        with self.assertRaisesRegex(ValueError, 'requires original'):
            replay_versioned(measure(json.loads(V1.read_text())))


if __name__ == '__main__':
    unittest.main()
