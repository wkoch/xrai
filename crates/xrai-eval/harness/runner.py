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

VERSION = 'xrai.eval.local.v1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def payload(data, observed):
    return {'base64': base64.b64encode(data).decode('ascii'), 'sha256': sha(data),
            'captured_bytes': len(data), 'observed_bytes': observed,
            'truncated': observed > len(data)}


def sandbox(command, workspace, profile_dir):
    """A fail-closed sandbox: only workspace writable, evaluator/other arms absent."""
    workspace = Path(workspace).resolve(strict=True)
    if not command or not Path(command[0]).is_absolute():
        raise ValueError('adapter executable must be absolute')
    if platform.system() == 'Darwin':
        executable = str(Path(command[0]).resolve(strict=True))
        # No global file-read permission: even same-user evaluator files are denied.
        paths = ['/System', '/usr', '/bin', '/dev', '/etc', '/private/etc', '/Library/Apple',
                 '/private/var/db/dyld', str(workspace)]
        rules = ' '.join('(subpath ' + json.dumps(p) + ')' for p in paths)
        profile = '(version 1)(deny default)(allow process-fork)(allow process-exec)(allow sysctl-read)(allow mach-lookup)(allow file-read-metadata)'
        profile += '(allow file-read* ' + rules + ' (literal ' + json.dumps(executable) + '))'
        profile += '(allow file-map-executable ' + rules + ' (literal ' + json.dumps(executable) + '))'
        profile += '(allow file-read* (literal "/"))'
        profile += '(allow file-write* (subpath ' + json.dumps(str(workspace)) + ') (literal "/dev/null"))'
        p = Path(profile_dir) / 'sandbox.sb'
        p.write_text(profile, encoding='utf-8')
        return ['/usr/bin/sandbox-exec', '-f', str(p), *command], 'macOS Seatbelt'
    if platform.system() == 'Linux':
        bwrap = shutil.which('bwrap')
        if not bwrap:
            raise RuntimeError('bubblewrap required: refusing an unsandboxed run')
        args = [bwrap, '--unshare-all', '--die-with-parent', '--new-session']
        for p in ['/usr', '/bin', '/lib', '/lib64']:
            if Path(p).exists():
                args += ['--ro-bind', p, p]
        args += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
                 '--bind', str(workspace), '/workspace', '--chdir', '/workspace',
                 '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8']
        exe = Path(command[0]).resolve(strict=True)
        if not any(exe.is_relative_to(Path(p)) for p in ['/usr', '/bin', '/lib', '/lib64']):
            args += ['--ro-bind', str(exe), '/adapter']
            command = ['/adapter', *command[1:]]
        return [*args, '--', *command], 'Linux bubblewrap'
    raise RuntimeError('no sandbox for this platform')


def execute(command, workspace, *, timeout=5.0, output_limit=65536, phase='reading'):
    if timeout <= 0 or output_limit < 1:
        raise ValueError('positive timeout/output_limit required')
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='xrai-profile-') as profiles:
        wrapped, mechanism = sandbox(command, workspace, profiles)
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': str(Path(workspace).resolve()),
               'TMPDIR': str(Path(workspace).resolve())}
        try:
            process = subprocess.Popen(wrapped, cwd=workspace, env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        except OSError as e:
            return {'phase': phase, 'command': command, 'status': 'spawn_error', 'exit_code': None,
                    'sandbox': mechanism, 'diagnostic': str(e), 'elapsed_seconds': time.monotonic()-start,
                    'stdout': payload(b'', 0), 'stderr': payload(b'', 0)}
        saved = {'stdout': bytearray(), 'stderr': bytearray()}
        observed = {'stdout': 0, 'stderr': 0}
        status = None
        drain_deadline = None
        cleanup_errors = []
        with selectors.DefaultSelector() as sel:
            for key in saved:
                pipe = getattr(process, key)
                os.set_blocking(pipe.fileno(), False)
                sel.register(pipe, selectors.EVENT_READ, key)
            while sel.get_map() or process.poll() is None:
                if status is None and time.monotonic()-start >= timeout:
                    status = 'timeout'
                    drain_deadline = time.monotonic()+.25
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except OSError as error:
                        cleanup_errors.append(str(error))
                if drain_deadline is not None and time.monotonic() >= drain_deadline:
                    # A detached descendant may retain the pipe. Closing it is
                    # essential to bound the evaluator; never wait for its EOF.
                    for key in list(sel.get_map().values()):
                        sel.unregister(key.fileobj)
                        key.fileobj.close()
                    break
                for event, _ in sel.select(0.02):
                    chunk = os.read(event.fd, 16384)
                    if not chunk:
                        sel.unregister(event.fileobj)
                        event.fileobj.close()
                        continue
                    key = event.data
                    observed[key] += len(chunk)
                    room = max(0, output_limit-sum(len(v) for v in saved.values()))
                    saved[key].extend(chunk[:room])
                    if status is None and sum(observed.values()) > output_limit:
                        status = 'output_limit'
                        drain_deadline = time.monotonic()+.25
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except OSError as error:
                            cleanup_errors.append(str(error))
        try:
            code = process.wait(timeout=.25)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                code = process.wait(timeout=.25)
            except (OSError, subprocess.TimeoutExpired) as error:
                cleanup_errors.append(str(error))
                code = None
        return {'phase': phase, 'command': command, 'status': status or ('ok' if code == 0 else 'error'),
                'exit_code': code, 'sandbox': mechanism, 'diagnostic': '; '.join(cleanup_errors) or None,
                'elapsed_seconds': time.monotonic()-start,
                **{key: payload(bytes(saved[key]), observed[key]) for key in saved}}


def replay(record):
    """Verify the original wire bytes, not a decoded/reformatted transcript."""
    count = 0
    for turn in record['rounds']:
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
                              'executor_sha256': sha(Path(__file__).read_bytes())},
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
