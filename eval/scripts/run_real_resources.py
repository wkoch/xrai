#!/usr/bin/env python3
"""Disposable-CI-only owned parser measurements; upstream sources remain inert bytes."""
import argparse
import gzip
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import sys
import threading
import time

import measure_workers as historical
import verify_real_resources as checks


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream: json.dump(value,stream,sort_keys=True,indent=2);stream.write('\n')


def compress(path,raw):
    with Path(path).open('xb') as stream:
        with gzip.GzipFile(fileobj=stream,mode='wb',mtime=0) as archive:archive.write(raw)


def budget(output,protocol):
    size=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    checks.need(size<=protocol['limits']['artifact_uncompressed_bytes'],'evidence budget exhausted; incomplete proof retained')


def observe(binary,input_,output,timeout,calibration_hash):
    """External observer owns wait4; ps children are outside the measured tree."""
    output.mkdir();save(output/'input.json',input_);control=output/'control';control.mkdir()
    self_before=resource.getrusage(resource.RUSAGE_SELF);children_before=resource.getrusage(resource.RUSAGE_CHILDREN)
    samples=[];baselines={};done=threading.Event();timed_out=[];observer_errors=[];started=time.monotonic_ns();epoch_started=time.time_ns()
    with (output/'input.json').open('rb') as stdin,(output/'stdout').open('wb') as stdout,(output/'stderr').open('wb') as stderr:
        child=subprocess.Popen([str(binary)],stdin=stdin,stdout=stdout,stderr=stderr,start_new_session=True)
        def sampler():
            while not done.is_set():
                begin=time.monotonic_ns();epoch_begin=time.time_ns();phase='capture_setup'
                active=None
                for name in ('idle','warm_idle'):
                    if (control/(name+'.ready')).exists() and not (control/(name+'.start')).exists():active=name;phase=name
                if active is None and (control/'idle.start').exists():phase='warmup'
                if active is None and (control/'warm_idle.start').exists():phase='measured_dispatch_shutdown'
                try:rows=historical.ps_tree(child.pid);error=None
                except (OSError,ValueError,subprocess.CalledProcessError) as exc:rows=[];error=str(exc)
                end=time.monotonic_ns();epoch_end=time.time_ns();index=len(samples)
                samples.append({'begin_ns':begin,'end_ns':end,'epoch_begin_ns':epoch_begin,'epoch_end_ns':epoch_end,'phase':phase,'processes':rows,'sum_rss_bytes':sum(r['rss_bytes'] for r in rows) if error is None else None,'error':error})
                if active and error is None and any(r['pid']==child.pid for r in rows):
                    try:
                        text=(control/(active+'.ready')).read_text()
                        if len(text)!=19 or not text.isdigit():
                            done.wait(.005);continue
                        ready=int(text);baseline=baselines.setdefault(active,{'ready_epoch_ns':ready,'ack_epoch_ns':None,'sample_indices':[]})
                        if ready<=epoch_begin:baseline['sample_indices'].append(index)
                        if len(baseline['sample_indices'])>=3:
                            ack=time.time_ns();baseline['ack_epoch_ns']=ack;(control/(active+'.start')).write_text(str(ack))
                    except (OSError,ValueError) as exc:observer_errors.append(str(exc));done.set();os.killpg(child.pid,signal.SIGKILL)
                done.wait(max(0,.025-(end-begin)/1e9))
        def watchdog():
            if not done.wait(timeout):
                timed_out.append(True)
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
        observer=threading.Thread(target=sampler);guard=threading.Thread(target=watchdog);observer.start();guard.start()
        _,status,usage=os.wait4(child.pid,0);child.returncode=os.waitstatus_to_exitcode(status);epoch_finished=time.time_ns();done.set();observer.join();guard.join()
    self_after=resource.getrusage(resource.RUSAGE_SELF);children_after=resource.getrusage(resource.RUSAGE_CHILDREN)
    valid=[s['sum_rss_bytes'] for s in samples if s['error'] is None and s['processes']]
    try:payload=checks.read(output/'stdout')
    except (ValueError,UnicodeError):payload={'samples':[]}
    seen={p['pid'] for s in samples for p in s['processes']}
    receipt={'schema_version':'xrai.eval.resources.real-observer.v1','pid':child.pid,'exit':child.returncode,'timed_out':bool(timed_out),'command':[str(binary)],
        'epoch_started_ns':epoch_started,'epoch_finished_ns':epoch_finished,'observer_epoch_finished_ns':time.time_ns(),'elapsed_ns':time.monotonic_ns()-started,'cpu_user_seconds':usage.ru_utime,'cpu_system_seconds':usage.ru_stime,
        'cpu_origin':'wait4 target parent plus its waited descendants; calibration validated once on this host','cpu_inclusive_calibrated':True,'calibration_sha256':calibration_hash,
        'observer_self_user_seconds':self_after.ru_utime-self_before.ru_utime,'observer_self_system_seconds':self_after.ru_stime-self_before.ru_stime,
        'observer_ps_user_seconds':max(0,children_after.ru_utime-children_before.ru_utime-usage.ru_utime),'observer_ps_system_seconds':max(0,children_after.ru_stime-children_before.ru_stime-usage.ru_stime),
        'samples':samples,'baselines':baselines,'sample_interval_seconds':.025,'sampled_peak_sum_rss':max(valid) if valid else None,
        'worker_pids_missed_by_sampler':sorted({s['pid'] for s in payload['samples']}-seen),'observer_errors':observer_errors,
        'stdout_sha256':checks.sha((output/'stdout').read_bytes()),'stderr_sha256':checks.sha((output/'stderr').read_bytes()),
        'rss_limit':'Common ps snapshots sum alive RSS; shared pages double count, sampling misses short workers and between-sample peaks; lstart has platform display granularity.',
        'cpu_scope':'Inclusive whole native session: capture/setup/idling/warmup/measurement/validation/serialization/shutdown; no per-query CPU inference.'}
    save(output/'resources.json',receipt)
    checks.need(child.returncode==0 and not timed_out and not observer_errors,'native session failed; complete available outputs retained: '+str(output))
    return payload,receipt


def run(args):
    checks.need(os.environ.get('GITHUB_ACTIONS')=='true' and platform.system() in ('Linux','Darwin'),'native workload restricted to disposable GitHub CI')
    protocol,manifest=checks.frozen();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    (output/'sources').mkdir();sources={}
    for item in manifest['sources']:
        raw=checks.file(checks.DESIGN/item['relative_path']);(output/'sources'/item['id']).write_bytes(raw);sources[item['id']]=dict(item,raw=raw)
    (output/'native-bin').mkdir();provided={'worker-benchmark-real':args.binary,'worker-spike':args.single_worker,'worker-persistent':args.persistent_worker}
    binaries={};binary_hashes={}
    for name,path in provided.items():
        raw=checks.file(path.resolve());target=output/'native-bin'/name;target.write_bytes(raw);target.chmod(0o755);binaries[name]=target;binary_hashes['native-bin/'+name]=checks.sha(raw)
    sessions=[{'session':s,'mode':m,'concurrency':c,'directory':f'session-{s}-c{c}-{m}'} for c in (1,2) for s,order in enumerate(protocol['mode_rotation']) for m in order]
    metadata={'schema_version':'xrai.eval.resources.real-preregistration.v1','frozen_epoch_ns':time.time_ns(),'output_root':str(output),
        'protocol_sha256':checks.sha(checks.file(checks.DESIGN/'protocol.json')),'source_manifest_sha256':checks.sha(checks.file(checks.DESIGN/'source-manifest.json')),
        'source_bindings_sha256':{p:checks.sha(checks.file(checks.ROOT/p)) for p in checks.SOURCE_PATHS},'binary_sha256':binary_hashes,'sessions':sessions,
        'native_executed_locally':False,'upstream_executed':False,
        'environment':{'repository':os.environ['GITHUB_REPOSITORY'],'head_sha':os.environ['GITHUB_SHA'],'run_id':int(os.environ['GITHUB_RUN_ID']),'run_attempt':int(os.environ['GITHUB_RUN_ATTEMPT']),
            'platform':platform.system(),'host':os.environ['EXPECTED_HOST']},'python_version':platform.python_version(),
        'cache_state_limit':'Warmups cover only Rust small; other grammars first compiled inside matrix. Sequential latency and concurrency2 throughput reported separately. Cold never claims OS page-cache cold.'}
    save(output/'preregistered.json',metadata)
    # Owned producer probe emits grammar metadata only; no upstream binary is invoked.
    producer_result=subprocess.run([str(binaries['worker-benchmark-real']),'--producers'],capture_output=True,check=True,timeout=30)
    checks.need(producer_result.stderr==b'','producer metadata stderr');producer_data=checks.decode(producer_result.stdout);checks.producers(producer_data);save(output/'producers.json',producer_data)
    historical.calibrate(output/'calibration',.025);calibration_hash=checks.calibration(output)
    (output/'reference-responses').mkdir();references=[];canonical={};equivalence_finished=0
    for mode in protocol['modes']:
        directory='equivalence-'+mode;input_=checks.plan(protocol,manifest,output,directory,mode,1,'equivalence',sources)
        print('Checking complete Response equivalence: '+mode,file=sys.stderr,flush=True)
        payload,receipt=observe(binaries['worker-benchmark-real'],input_,output/directory,protocol['limits']['session_watchdog_seconds'],calibration_hash)
        equivalence_finished=max(equivalence_finished,receipt['epoch_finished_ns'])
        checks.need(len(payload['samples'])==len(input_['requests']),'complete equivalence rows')
        for index,(item,row) in enumerate(zip(input_['requests'],payload['samples'])):
            path=output/directory/'control'/'references'/f'{index}.response';raw=checks.file(path);key=(item['source_id'],item['configuration'])
            checks.need(row['request']==index and row['response_blake3']==checks.blake3.blake3(raw).hexdigest(),'full response byte/hash correlation')
            checks.response(raw,sources[item['source_id']],item['configuration'],producer_data['grammars'][protocol['dialects'].index(item['dialect'])]['producer'])
            if mode=='direct':
                canonical[key]=raw;config_index=protocol['configuration_cycle'].index(item['configuration']);rel=f'reference-responses/{item["source_id"]}--{config_index}.response.gz';compress(output/rel,raw)
                references.append({'source_id':item['source_id'],'configuration':item['configuration'],'relative_path':rel,'sha256':checks.sha(raw),'blake3':checks.blake3.blake3(raw).hexdigest(),'bytes':len(raw)})
            else:checks.need(raw==canonical[key],'complete Response divergence before measurement')
            compress(path.with_suffix('.response.gz'),raw);path.unlink()
        budget(output,protocol)
    # Decisions and actual finish timestamps are retained only after all literal comparisons.
    save(output/'reference.json',{'responses':references,'equivalence_completed_epoch_ns':max(time.time_ns(),equivalence_finished),'normalization':['identity.request']})
    canonical.clear();expected={(r['source_id'],r['configuration']):r for r in references}
    for session in sessions:
        directory=session['directory'];input_=checks.plan(protocol,manifest,output,directory,session['mode'],session['concurrency'],'measurement',sources)
        print('Measuring '+directory+' ('+str(len(input_['requests']))+' requests)',file=sys.stderr,flush=True)
        payload,_=observe(binaries['worker-benchmark-real'],input_,output/directory,protocol['limits']['session_watchdog_seconds'],calibration_hash)
        checks.need(len(payload['samples'])==len(input_['requests']),'complete measured rows')
        for item,row in zip(input_['requests'],payload['samples']):checks.need(row['response_blake3']==expected[(item['source_id'],item['configuration'])]['blake3'],'measured response differs from frozen reference')
        budget(output,protocol)
    result=checks.verify(output);print(json.dumps(result,indent=2,sort_keys=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True);parser.add_argument('--single-worker',type=Path,required=True);parser.add_argument('--persistent-worker',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args())
if __name__=='__main__':main()
