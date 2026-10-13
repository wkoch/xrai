import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path('/Users/wkoch/Projetos/xrai')
logs = root / 'docs/relatorios/logs/L5-C06/root-preflight'
sources = [
    'crates/xrai-eval/harness/immutable_request_dispatch.py',
    'crates/xrai-eval/harness/tests/test_immutable_request_dispatch.py',
    'crates/xrai-eval/harness/guarded_smoke.py',
    'crates/xrai-eval/harness/tests/test_guarded_smoke.py',
    'eval/adapters/guarded-smoke-v1/verify.py',
    'docs/relatorios/logs/L5-C06/D01-request/proof.json',
    'docs/relatorios/logs/L5-C06/guarded-smoke/owned-output.zip',
]
def hashes():
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources}
before = hashes()
commands = [
    ('v4-request-tests', ['-m', 'unittest', 'discover', '-s', 'crates/xrai-eval/harness/tests', '-p', 'test_immutable_request_dispatch.py', '-v'], True),
    ('v3-consumer-tests', ['-m', 'unittest', 'discover', '-s', 'crates/xrai-eval/harness/tests', '-p', 'test_guarded_smoke.py', '-v'], True),
    ('v4-request-proof', ['eval/adapters/immutable-request-v1/verify.py'], False),
    ('v3-consumer-proof', ['eval/adapters/guarded-smoke-v1/verify.py', '--archive', 'docs/relatorios/logs/L5-C06/guarded-smoke/owned-output.zip'], False),
]
results = []
for name, args, tests in commands:
    result = subprocess.run([sys.executable, '-B', *args], cwd=root, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    (logs / (name + '.stdout')).write_bytes(result.stdout)
    (logs / (name + '.stderr')).write_bytes(result.stderr)
    item = {'name': name, 'command': [sys.executable, '-B', *args], 'exit_code': result.returncode}
    assert result.returncode == 0, name + ': ' + result.stderr.decode(errors='replace')[-2000:]
    if tests:
        text = result.stderr.decode()
        found = re.search(r'Ran (\d+) tests? in .*\n\nOK\n\Z', text)
        assert found is not None and not re.search(r'\.\.\. skipped ', text), name + ': non-exact tests status'
        item.update(tests=int(found.group(1)), skips=0)
    else:
        output = json.loads(result.stdout)
        assert output['verified'] is True, name
        item['output'] = output
    results.append(item)
assert hashes() == before, 'concurrent source/evidence mutation during preflight'
receipt = {'verified': True, 'runtime': sys.version, 'source_and_evidence_hashes': before, 'commands': results,
           'scope': 'Owned Python/fake tests and readonly retained proof verification; no native/upstream/provider execution.'}
(logs / 'v4-integration-preflight.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'verified': True, 'commands': [{k: v for k, v in item.items() if k != 'output'} for item in results]}))
