#!/usr/bin/env python3
"""Development measurement bridge: L4 tokenizer, complete canonical envelope.

Reads one hex encoded envelope per line. No source lookup, network or labels.
The caller bounds the bridge process and each request by a deadline.
"""
import hashlib
import json
from pathlib import Path
import sys
from blake3 import blake3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'crates/xrai-eval/harness'))
from offline_measurement import tokenizer, canonical

encoding, profile = tokenizer()
print(json.dumps({'profile': 'l4:' + profile['fingerprint_sha256'], 'metadata': profile}), flush=True)
for line in sys.stdin:
    raw = bytes.fromhex(line.strip())
    value = json.loads(raw)
    if canonical(value) != raw:
        raise ValueError('noncanonical envelope')
    ids = encoding.encode(raw.decode('utf-8'), disallowed_special=())
    print(json.dumps({'tokens': len(ids), 'wire_sha256': hashlib.sha256(raw).hexdigest(), 'wire_blake3':blake3(raw).hexdigest()}), flush=True)
