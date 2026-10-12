#!/usr/bin/env python3
"""Preregistered synthetic calibration, exit CPU and simultaneous sampled RSS (L5-03)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import threading
import time
import gzip
import tarfile

ROOT = Path(__file__).resolve().parents[2]
DIALECTS = ['rust', 'javascript', 'jsx', 'typescript', 'tsx', 'python', 'go']
CLASSES = ['small', 'medium', 'dense', 'large-comments', 'error']
MODES = ['direct', 'xrw1', 'xrw2']

def digest(data):
    return hashlib.sha256(data).hexdigest()

def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')

def source(dialect, kind, variant):
    if dialect == 'rust':
        unit = f'fn item_{variant}_IDX() -> u64 {{ 42 }}\n'
    elif dialect == 'python':
        unit = f'def item_{variant}_IDX():\n    return 42\n'
    elif dialect == 'go':
        unit = f'func Item{variant}IDX() int {{ return 42 }}\n'
    elif dialect in ('jsx', 'tsx'):
        unit = f'function item_{variant}_IDX() {{ return <div>42</div>; }}\n'
    else:
        unit = f'function item_{variant}_IDX() {{ return 42; }}\n'
    count = {'small': 1, 'medium': 128, 'dense': 1024, 'large-comments': 1, 'error': 128}[kind]
    text = ''.join(unit.replace('IDX', str(i)) for i in range(count))
    if dialect == 'go':
        text = 'package sample\n' + text
    if kind == 'large-comments':
        comment = '# ' if dialect == 'python' else '// '
        text = (comment + '0123456789' * 9 + '\n') * 5600 + text
    if kind == 'error':
        text += 'def broken(:\n' if dialect == 'python' else 'function broken( {\n'
    return text.encode()

def ps_tree(root):
    result = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss=,lstart='], capture_output=True, text=True, check=True)
    all_rows = {}
    for line in result.stdout.splitlines():
        fields = line.split(maxsplit=3)
        if len(fields) == 4:
            pid, ppid, rss = map(int, fields[:3])
            all_rows[pid] = {'pid': pid, 'ppid': ppid, 'rss_bytes': rss * 1024, 'start_observed': fields[3]}
    selected = {root}
    while True:
        extra = {pid for pid, row in all_rows.items() if row['ppid'] in selected}
        if extra <= selected:
            break
        selected |= extra
    return [all_rows[pid] for pid in sorted(selected) if pid in all_rows]

def observe(command, input_data, output, timeout, interval):
    """wait4 owns the only reap. Observer ps children are outside the target tree."""
    output.mkdir()
    (output / 'input.json').write_bytes(input_data)
    before_self = resource.getrusage(resource.RUSAGE_SELF)
    before_children = resource.getrusage(resource.RUSAGE_CHILDREN)
    samples, done = [], threading.Event()
    started = time.monotonic_ns()
    with (output / 'input.json').open('rb') as stdin, (output / 'stdout').open('wb') as stdout, (output / 'stderr').open('wb') as stderr:
        child = subprocess.Popen(command, stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True)
        def sampler():
            while not done.is_set():
                begin = time.monotonic_ns()
                try:
                    rows = ps_tree(child.pid)
                    error = None
                except (OSError, ValueError, subprocess.CalledProcessError) as exc:
                    rows, error = [], str(exc)
                end = time.monotonic_ns()
                samples.append({'begin_ns': begin, 'end_ns': end, 'processes': rows, 'sum_rss_bytes': sum(r['rss_bytes'] for r in rows) if error is None else None, 'error': error})
                done.wait(max(0, interval - (end - begin) / 1e9))
        timed_out = []
        def watchdog():
            if not done.wait(timeout):
                timed_out.append(True)
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        observer = threading.Thread(target=sampler)
        guard = threading.Thread(target=watchdog)
        observer.start(); guard.start()
        _, status, usage = os.wait4(child.pid, 0)
        child.returncode = os.waitstatus_to_exitcode(status)
        done.set(); observer.join(); guard.join()
    after_self = resource.getrusage(resource.RUSAGE_SELF)
    after_children = resource.getrusage(resource.RUSAGE_CHILDREN)
    valid = [s['sum_rss_bytes'] for s in samples if s['error'] is None and s['processes']]
    receipt = {'schema': 'xrai.eval.worker.resources.v1', 'pid': child.pid, 'command': command,
        'exit': child.returncode, 'timed_out': bool(timed_out), 'started_ns': started, 'elapsed_ns': time.monotonic_ns() - started,
        'cpu_user_seconds': usage.ru_utime, 'cpu_system_seconds': usage.ru_stime,
        'cpu_origin': 'wait4 terminal rusage of experiment parent, including its waited descendants; host calibration must validate inclusivity',
        'observer_self_user_seconds': after_self.ru_utime - before_self.ru_utime,
        'observer_self_system_seconds': after_self.ru_stime - before_self.ru_stime,
        'observer_ps_user_seconds': max(0, after_children.ru_utime - before_children.ru_utime - usage.ru_utime),
        'observer_ps_system_seconds': max(0, after_children.ru_stime - before_children.ru_stime - usage.ru_stime),
        'sample_interval_seconds': interval, 'sampled_peak_sum_rss': max(valid) if valid else None,
        'samples': samples, 'rss_limit': 'ps snapshot sum of simultaneous live RSS; shared pages double count; between-sample peaks and short children can be missed',
        'output_sha256': digest((output / 'stdout').read_bytes()), 'stderr_sha256': digest((output / 'stderr').read_bytes())}
    save(output / 'resources.json', receipt)
    if child.returncode != 0 or timed_out:
        raise RuntimeError(f'experiment failed: {output}, exit={child.returncode}, timeout={bool(timed_out)}')
    try:
        payload = json.loads((output / 'stdout').read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError(f'invalid experiment output: {output}') from exc
    return payload, receipt

CALIBRATION = r'''
import json, os, resource, subprocess, sys, time
code = 'import time; a=bytearray(16*1024*1024); end=time.process_time()+0.15\nwhile time.process_time()<end: pass\ntime.sleep(0.3)'
children = [subprocess.Popen([sys.executable, '-c', code]) for _ in range(2)]
short = subprocess.Popen([sys.executable, '-c', 'pass'])
ids=[c.pid for c in children]+[short.pid]
usage=[]
for c in children+[short]:
 _, status, r=os.wait4(c.pid,0); c.returncode=os.waitstatus_to_exitcode(status); assert c.returncode==0
 usage.append({'pid':c.pid,'user':r.ru_utime,'system':r.ru_stime})
self_usage=resource.getrusage(resource.RUSAGE_SELF)
print(json.dumps({'parent':os.getpid(),'children':ids,'child_usage':usage,'self_user':self_usage.ru_utime,'self_system':self_usage.ru_stime}))
'''

def calibrate(output, interval):
    payload, receipt = observe([sys.executable, '-c', CALIBRATION], b'{}', output, 20, interval)
    expected_user = payload['self_user'] + sum(c['user'] for c in payload['child_usage'])
    expected_sys = payload['self_system'] + sum(c['system'] for c in payload['child_usage'])
    observed = {p['pid'] for s in receipt['samples'] for p in s['processes']}
    result = {'cpu_inclusive_validated': abs(receipt['cpu_user_seconds'] - expected_user) <= 0.03 and abs(receipt['cpu_system_seconds'] - expected_sys) <= 0.03,
        'expected_user': expected_user, 'expected_system': expected_sys,
        'maximum_simultaneous_processes': max((len(s['processes']) for s in receipt['samples']), default=0),
        'children_missed_by_sampler': sorted(set(payload['children']) - observed),
        'short_child_cpu_accounted_at_exit': payload['child_usage'][-1],
        'idle_baseline': 'First sample before requests; process startup timing is observed, not synchronized idle RSS'}
    save(output / 'calibration.json', result)
    if not result['cpu_inclusive_validated'] or result['maximum_simultaneous_processes'] < 3:
        raise RuntimeError('resource calibration failed')
    return result

def run(args):
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    classes = args.classes.split(',')
    if not classes or any(c not in CLASSES for c in classes) or args.sessions < 1 or args.requests < 1:
        raise ValueError('matrix parameters')
    sources_dir = output / 'sources'; sources_dir.mkdir()
    inputs, descriptors = [], []
    for dialect in DIALECTS:
        for kind in classes:
            for pattern in ('repeated', 'distinct'):
                for n in range(args.requests):
                    variant = 0 if pattern == 'repeated' else n
                    key = f'{dialect}/{kind}/{pattern}/{n}'
                    name = f'{dialect}-{kind}-{variant}.txt'
                    path = sources_dir / name
                    data = source(dialect, kind, variant)
                    if not path.exists(): path.write_bytes(data)
                    descriptor = {'key': key, 'dialect': dialect, 'source': str(path), 'configuration': f'alternating-{n % 2}', 'warmup': False}
                    inputs.append(descriptor)
                    descriptors.append({'key': key, 'source_sha256': digest(data), 'source_bytes': len(data), 'origin': 'deterministic synthetic generator, not a real project'})
    binary = args.binary.resolve()
    with (output / 'sources.tar.gz').open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w|') as archive:
        for path in sorted(sources_dir.iterdir()):
            info = archive.gettarinfo(str(path), arcname=path.name)
            info.mtime = 0
            with path.open('rb') as data: archive.addfile(info, data)
    binaries = {m: binary if m == 'direct' else binary.with_name('worker-spike' if m == 'xrw1' else 'worker-persistent') for m in MODES}
    preregistration = {'schema': 'xrai.eval.worker.matrix.v1', 'frozen_at_ns': time.time_ns(), 'host': platform.platform(), 'python': platform.python_version(),
        'commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        'binary_sha256': {m: digest(p.read_bytes()) for m,p in binaries.items()}, 'driver_sha256': digest(binary.read_bytes()),
        'method_sha256': digest(Path(__file__).read_bytes()), 'sessions': args.sessions, 'requests_per_class_pattern': args.requests,
        'sources_archive_sha256': digest((output/'sources.tar.gz').read_bytes()),
        'classes': classes, 'dialects': DIALECTS, 'patterns': ['repeated','distinct'], 'modes': MODES, 'concurrency': 1,
        'mode_order': [MODES[s % 3:] + MODES[:s % 3] for s in range(args.sessions)],
        'warmup_requests_per_session': 2, 'idle_ms': 80, 'hold_ms': 100, 'sample_interval_seconds': args.interval,
        'session_timeout_seconds': args.timeout, 'descriptors': descriptors,
        'reference_scope': 'separate direct session; normalize only request number after verifying response correlation; hash entire encoded Response',
        'limitations': ['Synthetic-only first measurement; real small/medium and real dense corpus still required', 'Sequential latency only; concurrency throughput separate remains pending', 'Cold means process/cache startup, never OS page-cache cold', 'CPU includes loading, warmup, validation, retention calibration and shutdown; not attributed per request', 'XRW2 IPC/stderr totals and queue/codec/roundtrip timings unavailable']}
    save(output / 'preregistered.json', preregistration)
    calibrate(output / 'calibration', args.interval)
    def plan(mode, warmup=True):
        return {'mode': mode, 'worker': str(binaries[mode]), 'requests': ([dict(inputs[i], key='warmup/'+str(i), warmup=True) for i in range(2)] if warmup else []) + inputs,
            'idle_ms': 80, 'hold_ms': 100}
    # Reference replay is deliberately outside the measured resource domain.
    reference_plan = plan('direct', False)
    reference = subprocess.run([str(binary)], input=json.dumps(reference_plan).encode(), capture_output=True, check=True, timeout=args.timeout)
    reference_payload = json.loads(reference.stdout)
    save(output / 'reference.json', reference_payload)
    summary = []
    for session, order in enumerate(preregistration['mode_order']):
        for mode in order:
            target = output / f'session-{session}-{mode}'
            payload, receipt = observe([str(binary)], json.dumps(plan(mode)).encode(), target, args.timeout, args.interval)
            expected = {s['key']: s['response_blake3'] for s in reference_payload['samples']}
            rows = [s for s in payload['samples'] if not s['warmup']]
            if any(expected.get(s['key']) != s['response_blake3'] for s in rows) or len(rows) != len(inputs):
                raise RuntimeError('direct Response divergence')
            observed = {p['pid'] for s in receipt['samples'] for p in s['processes']}
            missing = sorted({s['pid'] for s in payload['samples']} - observed)
            summary.append({'session':session,'mode':mode,'requests':len(rows),'full_response_equivalent':True,'cpu_user_seconds':receipt['cpu_user_seconds'],'cpu_system_seconds':receipt['cpu_system_seconds'],'sampled_peak_sum_rss':receipt['sampled_peak_sum_rss'],'worker_pids_missed_by_sampler':missing,'rss_sample_count':len(receipt['samples'])})
            save(target / 'verified.json', summary[-1])
    save(output / 'summary.json', {'schema':'xrai.eval.worker.comparison.v1','preregistration_sha256':digest((output/'preregistered.json').read_bytes()),'sessions':summary,'complete_synthetic_matrix':classes==CLASSES and args.sessions>=3 and args.requests>=30,'m0_06_complete':False,'production_mode_recommendation':None})
    print(json.dumps({'output':str(output),'sessions':len(summary),'requests':sum(s['requests'] for s in summary),'m0_06_complete':False}))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=ROOT/'target/release/worker-benchmark')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sessions', type=int, default=3)
    parser.add_argument('--requests', type=int, default=30)
    parser.add_argument('--classes', default=','.join(CLASSES))
    parser.add_argument('--interval', type=float, default=.025)
    parser.add_argument('--timeout', type=float, default=600)
    args=parser.parse_args()
    if args.interval <= 0 or args.timeout <= 0: parser.error('positive interval/timeout required')
    run(args)

if __name__ == '__main__': main()
