"""Derived controlled-content tokens; never provider usage or historic mutation."""
import argparse
import base64
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

from runner import canonical, replay as replay_local, sha

HERE = Path(__file__).parent
ASSETS = HERE / 'tokenizer-assets'
VERSION = 'xrai.eval.measurement.v1'
SERIALIZER = {'name': 'xrai.canonical-json.v1', 'encoding': 'utf-8',
              'ensure_ascii': False, 'sort_keys': True, 'separators': [',', ':'],
              'normalization': 'none', 'truncation': 'captured-prefix-only',
              'binary_projection': 'base64-on-invalid-utf8', 'special_tokens': 'ordinary-text'}


def tokenizer():
    """Load only vendored bytes; no cache lookup, model selection or network."""
    import tiktoken
    from tiktoken.load import load_tiktoken_bpe
    config = json.loads((ASSETS / 'cl100k-config.json').read_text())
    if platform.python_version() != config['python_version']:
        raise ValueError('serializer Python runtime version mismatch')
    for package, expected in config['packages'].items():
        if importlib.metadata.version(package) != expected:
            raise ValueError(f'tokenizer implementation version mismatch: {package}')
    vocab = ASSETS / 'cl100k_base.tiktoken'
    if sha(vocab.read_bytes()) != config['vocab_merges_sha256']:
        raise ValueError('tokenizer vocabulary/merges hash mismatch')
    encoding = tiktoken.Encoding(name=config['name'], pat_str=config['pattern'],
                               mergeable_ranks=load_tiktoken_bpe(str(vocab), expected_hash=config['vocab_merges_sha256']),
                               special_tokens=config['special_tokens'])
    profile = {'config': config, 'config_sha256': sha(canonical(config)),
               'serializer': SERIALIZER, 'serializer_sha256': sha(canonical(SERIALIZER))}
    profile['fingerprint_sha256'] = sha(canonical(profile))
    return encoding, profile


def project_stream(item):
    data = base64.b64decode(item['base64'], validate=True)
    try:
        content, encoding = data.decode('utf-8', errors='strict'), 'utf-8'
    except UnicodeDecodeError:
        content, encoding = base64.b64encode(data).decode('ascii'), 'base64'
    return {'encoding': encoding, 'content': content, 'source_sha256': item['sha256'],
            'observed_bytes': item['observed_bytes'], 'captured_bytes': len(data),
            'truncated': item['truncated']}


def projection(record, tools):
    return {'projection_version': 'xrai.local-tool-projection.v1', 'tool_definitions': tools,
            'rounds': [{'phase': turn['phase'], 'command': turn['command'],
                        'stdout': project_stream(turn['stdout']), 'stderr': project_stream(turn['stderr'])}
                       for turn in record['rounds']]}


def measure(record, *, tools=None):
    replay_local(record)
    encoding, profile = tokenizer()
    controlled = projection(record, [] if tools is None else tools)
    wire = canonical(controlled)
    tokens = encoding.encode(wire.decode('utf-8'), allowed_special=set(), disallowed_special=())
    return {'schema_version': VERSION, 'original_record_sha256': sha(canonical(record)),
            'transcript_sha256': record['transcript_sha256'], 'profile': profile,
            'projection': controlled, 'serialized_base64': base64.b64encode(wire).decode('ascii'),
            'serialized_sha256': sha(wire), 'serialized_bytes': len(wire),
            'controlled_content_tokens': len(tokens), 'token_ids_sha256': sha(canonical(tokens)),
            'provider_usage': None, 'provider_cost': None,
            'scope': 'exact-controlled-content-profile-only-not-provider-wire-or-billing'}


def verify_measurement(sidecar, record):
    if sidecar.get('schema_version') != VERSION:
        raise ValueError('unsupported measurement version')
    expected = measure(record, tools=sidecar['projection']['tool_definitions'])
    if sidecar != expected:
        raise ValueError('derived measurement/profile/projection mismatch')
    return {'status': 'verified_controlled_content', 'controlled_content_tokens': expected['controlled_content_tokens'],
            'serialized_sha256': expected['serialized_sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('record')
    parser.add_argument('--verify')
    args = parser.parse_args()
    source = json.loads(Path(args.record).read_text())
    result = verify_measurement(json.loads(Path(args.verify).read_text()), source) if args.verify else measure(source)
    print(json.dumps(result, indent=2, ensure_ascii=False))
