"""Collect one real Rust C03 event using only the owned experimental analyzer in CI."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'eval/qualification/state-events/rust'
LIMIT = 4 * 1024 * 1024


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Process:
    def __init__(self, binary, directory):
        self.directory = directory
        directory.mkdir()
        self.stderr = (directory / 'stderr.bin').open('wb')
        self.process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.stderr, start_new_session=True)
        self.started = time.monotonic()
        self.rows, self.buffer = [], b''
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)

    def call(self, request):
        raw = (json.dumps(request, separators=(',', ':')) + '\n').encode()
        if len(raw) > LIMIT:
            raise ValueError('request frame limit')
        self.process.stdin.write(raw)
        self.process.stdin.flush()
        deadline = time.monotonic() + 30
        while b'\n' not in self.buffer:
            if time.monotonic() >= deadline or not self.selector.select(max(0, deadline-time.monotonic())):
                raise TimeoutError('native session response deadline')
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise ValueError('native session EOF before response')
            self.buffer += chunk
            if len(self.buffer) > LIMIT:
                raise ValueError('response frame limit')
        response_raw, self.buffer = self.buffer.split(b'\n', 1)
        response_raw += b'\n'
        response = json.loads(response_raw)
        row = {'sequence': len(self.rows), 'request_base64': base64.b64encode(raw).decode(),
               'response_base64': base64.b64encode(response_raw).decode(),
               'request_sha256': sha(raw), 'response_sha256': sha(response_raw)}
        self.rows.append(row)
        with (self.directory / 'transcript.jsonl').open('a') as f:
            f.write(json.dumps(row, separators=(',', ':')) + '\n')
        with (self.directory / 'stdout.jsonl').open('ab') as f:
            f.write(response_raw)
        return response

    def close(self):
        response = self.call({'operation':'close'})
        self.process.stdin.close()
        code = self.process.wait(timeout=10)
        remainder = self.buffer + self.process.stdout.read(LIMIT+1)
        self.selector.close()
        self.process.stdout.close()
        self.stderr.close()
        if code != 0 or remainder or (self.directory/'stderr.bin').read_bytes():
            raise ValueError('unexpected termination/output after close')
        metadata = {'pid': self.process.pid, 'exit_code': code, 'closed_response': response,
                    'elapsed_seconds': time.monotonic()-self.started, 'command_count':len(self.rows),
                    'transport':'bounded newline JSON', 'unread_output_bytes': len(remainder),
                    'explicit_close':True, 'wrapper_reaped': True}
        (self.directory/'process.json').write_text(json.dumps(metadata, indent=2)+'\n')

    def abort(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, 9)
            self.process.wait(timeout=10)
        self.stderr.close()
        self.selector.close()


def successful(row):
    if row.get('status') != 'ok':
        raise ValueError('native request refused: '+json.dumps(row))
    return row['response']


def collect(binary, output):
    if platform.system() != 'Linux' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('native collection restricted to disposable Linux CI; local data-only verification remains available')
    import prepare_state_events
    prepare_state_events.verify()
    binary = Path(binary).resolve(strict=True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    frozen = output/'inputs'
    frozen.mkdir()
    for name in ['descriptor.json','a.json','b.json','queries.json','oracle.json']:
        shutil.copyfile(ASSETS/name, frozen/name)
    artifact_binary = output/'native-bin'
    artifact_binary.mkdir()
    shutil.copyfile(binary, artifact_binary/'semantics-session')
    binary = (artifact_binary/'semantics-session').resolve(strict=True)
    binary.chmod(0o500)
    binary_hash = sha(binary.read_bytes())
    # Parse the retained copies that are actually sent to the child.
    descriptor, a, b, queries = [json.loads((frozen/n).read_bytes()) for n in
                                ['descriptor.json','a.json','b.json','queries.json']]
    for name, binding in descriptor['artifacts'].items():
        if (frozen/name).is_file() and sha((frozen/name).read_bytes()) != binding['sha256']:
            raise ValueError('copied input differs from frozen descriptor')
    source_names = ['eval/scripts/run_state_event.py','eval/scripts/verify_state_event.py',
                    'crates/xrai-eval/src/bin/semantics-session.rs',
                    'crates/xrai-eval/src/semantics_spike.rs','crates/xrai-eval/src/semantics_spike/r3.rs']
    manifest = {'schema':'xrai.eval.c03.real-event.receipt.v1','task_id':descriptor['task_id'],
                'slot_id':descriptor['slot_id'],'family':'Rust','event_role':'required',
                'descriptor_sha256':sha((frozen/'descriptor.json').read_bytes()),
                'input_sha256':{n:sha((frozen/n).read_bytes()) for n in ['a.json','b.json','queries.json','oracle.json']},
                'binary':{'path':'native-bin/semantics-session','sha256':binary_hash,'bytes':binary.stat().st_size},
                'source_sha256':{n:sha((ROOT/n).read_bytes()) for n in source_names},
                'environment':{'platform':platform.platform(),'machine':platform.machine(),
                    'github_run_id':os.environ['GITHUB_RUN_ID'],'github_sha':os.environ['GITHUB_SHA']},
                'strategy':'conservative_full_rebuild','scope':descriptor['capacity'],
                'normalization':[], 'admitted':False,'competitive_runs_allowed':False}
    (output/'receipt.json').write_text(json.dumps(manifest,indent=2)+'\n')
    live, rebuild = None, None
    try:
        live = Process(binary, output/'incremental')
        opened = successful(live.call({'operation':'open','input':a}))
        successful(live.call({'operation':'snapshot'}))
        for query in queries:
            successful(live.call({'operation':'query', **{k:query[k]for k in ['module','path','namespace']}}))
        rejected = live.call({'operation':'update','expected_snapshot':'intentionally-stale-revision','input':b})
        if rejected['status'] != 'error':
            raise ValueError('stale expected revision unexpectedly accepted')
        successful(live.call({'operation':'snapshot'}))
        successful(live.call({'operation':'update','expected_snapshot':opened['snapshot_id'],'input':b}))
        successful(live.call({'operation':'snapshot'}))
        for query in queries:
            successful(live.call({'operation':'query', **{k:query[k]for k in ['module','path','namespace']}}))
        live.close()
        rebuild = Process(binary, output/'rebuild')
        successful(rebuild.call({'operation':'open','input':b}))
        successful(rebuild.call({'operation':'snapshot'}))
        for query in queries:
            successful(rebuild.call({'operation':'query', **{k:query[k]for k in ['module','path','namespace']}}))
        rebuild.close()
        if sha(binary.read_bytes()) != binary_hash or sha((artifact_binary/'semantics-session').read_bytes()) != binary_hash:
            raise ValueError('executed/retained binary changed')
        from verify_state_event import verify
        result = verify(output)
        (output/'verification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        return result
    finally:
        for process in [live,rebuild]:
            if process and process.process.poll() is None:
                process.abort()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.binary,args.output),indent=2))
