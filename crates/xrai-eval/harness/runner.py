"""Offline development executor. OS sandbox mandatory; no paid model adapter enabled."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'eval/scripts'))
from materialize_task import materialize  # noqa: E402

VERSION = 'xrai.eval.local.v2'
LEGACY_VERSION = 'xrai.eval.local.v1'
from adapters import sandbox  # public L2 helper used by packaging/incremental smokes



def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def payload(data, observed):
    return {'base64': base64.b64encode(data).decode('ascii'), 'sha256': sha(data),
            'captured_bytes': len(data), 'observed_bytes': observed,
            'truncated': observed > len(data)}



def execute(command, workspace, *, timeout=5.0, output_limit=65536, phase='reading',
            cancel=None, arbitrary_agent=False):
    """A fresh execution domain per operation; never reuse an inconclusive domain."""
    from supervisor import supervise
    result = supervise(command, workspace, timeout=timeout, output_limit=output_limit,
                       cancel=cancel, arbitrary_agent=arbitrary_agent)
    streams = result.pop('streams')
    observed = result.pop('observed')
    return {'phase': phase, 'command': command, **result,
            **{key: payload(streams[key], observed[key]) for key in streams}}


def replay(record):
    """Verify the original wire bytes, not a decoded/reformatted transcript."""
    if record['schema_version'] not in (VERSION, LEGACY_VERSION):
        raise ValueError('unsupported local record version')
    count = 0
    domains = set()
    for turn in record['rounds']:
        if record['schema_version'] == VERSION:
            from supervisor import verify_receipt
            verify_receipt(turn)
            if turn['domain_id'] in domains:
                raise ValueError('execution domain reused across operations')
            domains.add(turn['domain_id'])
        for channel in ['stdout', 'stderr']:
            item = turn[channel]
            data = base64.b64decode(item['base64'], validate=True)
            if len(data) != item['captured_bytes'] or sha(data) != item['sha256']:
                raise ValueError('replay bytes/hash mismatch')
            if item['observed_bytes'] < len(data) or item['truncated'] != (item['observed_bytes'] > len(data)):
                raise ValueError('replay capture accounting mismatch')
            count += len(data)
    transcript = canonical(record['rounds'])
    if sha(transcript) != record['transcript_sha256']:
        raise ValueError('replay transcript mismatch')
    if record['measurement']['captured_bytes'] != count:
        raise ValueError('replay total byte count mismatch')
    # There is no configured model/tokenizer in local scripted runs.
    if record['measurement']['model_tokens'] is not None or record['usage'] is not None:
        raise ValueError('local record cannot invent model usage')
    if any(record[field] is not None for field in ['model','tokenizer','financial_cost']):
        raise ValueError('local record cannot invent model/tokenizer/cost')
    return {'transcript_sha256': sha(transcript), 'captured_bytes': count,
            'tokenizer': None, 'model_tokens': None, 'status': 'verified_bytes_tokens_unknown'}


def record(task, arm, rounds, setup_seconds, workspace):
    result = {'schema_version': VERSION, 'task_id': task['id'], 'family': task['family'],
              'run_kind': 'scripted_retrieval', 'adapter': arm,
              'model': None, 'tokenizer': None, 'usage': None, 'financial_cost': None,
              'outcome': 'not_judged', 'setup_seconds': setup_seconds,
              'permission_policy': 'workspace_only_no_network',
              'environment': {'system': platform.system(), 'release': platform.release(),
                              'machine': platform.machine(), 'python': platform.python_version(),
                              'executor_sha256': sha(Path(__file__).read_bytes()),
                              'containment_sources_sha256': {name:sha(Path(__file__).with_name(name).read_bytes())
                                    for name in ['adapters.py','supervisor.py']}},
              'input_sha256': sha(canonical(task)), 'rounds': rounds,
              'measurement': {'captured_bytes': sum(t[c]['captured_bytes'] for t in rounds for c in ['stdout', 'stderr']),
                              'model_tokens': None},
              'limitations': ['scripted retrieval; no agent success or competitive advantage measured',
                              'no model tokenizer configured; token counts and model costs unknown'],
              'transcript_sha256': sha(canonical(rounds))}
    # Hash inventory is evaluator evidence only, never used to choose source snippets.
    result['workspace_sha256'] = sha(canonical({str(p.relative_to(workspace)): sha(p.read_bytes())
                                  for p in sorted(Path(workspace).rglob('*')) if not p.is_symlink() and p.is_file()}))
    replay(result)
    return result


STOP = set('localize explique encontre função funções caminho pública público genérica genericamente como que para uma por seu sua com dos das sobre linhas fonte estado depois qual quais esse essa deve'.split())


def baseline(task, workspace):
    words = [w for w in re.findall(r'[\w]+', task['prompt']) if len(w) >= 3 and w.lower() not in STOP]
    # Prompt-only keyword selection: no oracle anchors or private relevant_sources.
    pattern = '|'.join(re.escape(w) for w in words[:16]) or 'TODO'
    options = ['--include=*.rs', '--include=*.ts', '--include=*.tsx', '--include=*.js',
               '--include=*.jsx', '--include=*.py', '--include=*.go', '--exclude-dir=.git']
    return [execute(['/usr/bin/find', '.', '-type', 'f'], workspace, phase='inventory', output_limit=16384),
            execute(['/usr/bin/grep', '-R', '-n', '-I', '-i', '-m', '3', '-C', '3', '-E',
                     *options, pattern, '.'], workspace, phase='selective_reading', output_limit=32768)]


def run_d0(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    public_tasks = [json.loads(line) for line in (ROOT / 'eval/tasks/dev.jsonl').read_text().splitlines()]
    summaries = []
    for row in public_tasks:
        with tempfile.TemporaryDirectory(prefix='xrai-arm-') as temp:
            start = time.monotonic()
            materialize(row['id'], temp)
            setup = time.monotonic()-start
            public = json.loads((Path(temp) / 'request.json').read_text())
            workspace = Path(temp) / 'workspace'
            rounds = baseline(public, workspace)
            result = record(public, 'selective-grep-v1', rounds, setup, workspace)
            (output / (row['id']+'.json')).write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
            summaries.append({'id': row['id'], 'family': row['family'],
                              'statuses': [r['status'] for r in rounds], 'replay': replay(result)})
    return {'schema_version': VERSION, 'tasks': summaries, 'count': len(summaries),
            'run_kind': 'scripted_retrieval', 'agent_success': None, 'model_usage': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='mode', required=True)
    run = sub.add_parser('baseline')
    run.add_argument('--output', required=True)
    rep = sub.add_parser('replay')
    rep.add_argument('record')
    args = parser.parse_args()
    result = run_d0(args.output) if args.mode == 'baseline' else replay(json.loads(Path(args.record).read_text()))
    print(json.dumps(result, indent=2, ensure_ascii=False))
