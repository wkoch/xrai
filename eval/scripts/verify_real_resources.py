#!/usr/bin/env python3
"""Data-only checks of frozen sources, complete Response equivalence and measurements."""
import argparse
import bisect
import gzip
import hashlib
import io
import json
import math
from collections import defaultdict
from pathlib import Path
import blake3

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'eval/resources/real-v1'
BINARIES = ('worker-benchmark-real', 'worker-spike', 'worker-persistent')
SOURCE_PATHS = (
    'Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml', 'crates/xrai-eval/Cargo.toml',
    'crates/xrai-eval/src/lib.rs', 'crates/xrai-eval/src/bin/worker-benchmark-real.rs',
    'crates/xrai-eval/src/bin/worker-spike.rs', 'crates/xrai-eval/src/bin/worker-persistent.rs',
    'crates/xrai-eval/src/worker_spike.rs', 'crates/xrai-eval/src/worker_persistent.rs',
    'crates/xrai-eval/src/parsing_spike.rs', 'crates/xrai-eval/parsing-provenance.json',
    'eval/scripts/run_real_resources.py', 'eval/scripts/verify_real_resources.py',
    'eval/scripts/test_real_resources.py', 'eval/scripts/measure_workers.py',
    'eval/resources/real-v1/protocol.json', 'eval/resources/real-v1/source-manifest.json',
    'eval/resources/real-v1/freeze-before-driver.json', 'docs/contracts/examples/requirements.txt',
    '.github/workflows/l5-real-resources.yml',
) + tuple('crates/xrai-eval/queries/' + d + '.scm' for d in ('rust','javascript','typescript','tsx','python','go'))
CACHE_POLICY = 'XRW2 dialect-only parser/query; reset before/after; no old tree/edit/source/response cache'
GRAMMARS = {
    'rust': ('tree-sitter-rust','0.24.2','src/node-types.json',15,'rust'),
    'javascript': ('tree-sitter-javascript','0.25.0','src/node-types.json',15,'javascript'),
    'jsx': ('tree-sitter-javascript','0.25.0','src/node-types.json',15,'javascript'),
    'typescript': ('tree-sitter-typescript','0.23.2','typescript/src/node-types.json',14,'typescript'),
    'tsx': ('tree-sitter-typescript','0.23.2','tsx/src/node-types.json',14,'tsx'),
    'python': ('tree-sitter-python','0.25.0','src/node-types.json',15,'python'),
    'go': ('tree-sitter-go','0.25.0','src/node-types.json',15,'go'),
}


def sha(raw): return hashlib.sha256(raw).hexdigest()
def need(value, message):
    if not value: raise ValueError(message)
def integer(value, minimum=0): return type(value) is int and value >= minimum
def decode(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            need(key not in result, 'duplicate JSON key'); result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
def same(a,b): return json.dumps(a,sort_keys=True,separators=(',',':'),allow_nan=False)==json.dumps(b,sort_keys=True,separators=(',',':'),allow_nan=False)
def read(path): return decode(Path(path).read_bytes())
def file(path):
    path=Path(path);need(path.is_file() and not path.is_symlink(),'regular retained file');return path.read_bytes()
def unpack(path):
    with gzip.GzipFile(fileobj=io.BytesIO(file(path))) as stream: raw=stream.read(16*1024*1024+1)
    need(len(raw)<=16*1024*1024,'bounded decompressed Response');return raw


def frozen():
    freeze=read(DESIGN/'freeze-before-driver.json')
    need(freeze['benchmark_real_implementation_present'] is False and freeze['measured'] is False,'before-driver source/protocol freeze')
    for rel,digest in freeze['files_sha256'].items(): need(sha(file(DESIGN/rel))==digest,'immutable source/protocol binding: '+rel)
    manifest=read(DESIGN/'source-manifest.json');protocol=read(DESIGN/'protocol.json')
    need(len(manifest['sources'])==freeze['source_units_total']==80,'source unit closure')
    by_id={s['id']:s for s in manifest['sources']};need(len(by_id)==80,'duplicate source identity');total=0
    for source in manifest['sources']:
        raw=file(DESIGN/source['relative_path']);raw.decode();total+=len(raw)
        need(source['relative_path']=='sources/'+source['id'] and len(raw)==source['bytes'] and sha(raw)==source['sha256'],'source actual bytes')
        if source['origin']=='controlled_prefix_of_real_unit':
            base=by_id[source['base_source_id']];original=file(DESIGN/base['relative_path'])
            need(source['base_sha256']==base['sha256'] and raw==original[:source['prefix_bytes']] and len(raw)<len(original),'controlled prefix lineage')
        else: need(source['origin'] in ('real_whole_unit','historical_synthetic_control_only'),'explicit source origin')
    need(total==freeze['source_bytes'],'source byte closure')
    need(protocol['modes']==['direct','direct_cached','xrw1','xrw2'] and protocol['concurrency_values']==[1,2] and protocol['sessions_per_mode_concurrency']==3 and protocol['requests_per_dialect_class_pattern_session']==30,'frozen matrix dimensions')
    need(protocol['dialects']==list(GRAMMARS),'seven declared dialects')
    cells={(x['dialect'],x['class']):x for x in manifest['availability']}
    need(len(cells)==42 and {(d,c) for d in protocol['dialects'] for c in protocol['classes']}==set(cells),'complete availability matrix')
    for (d,c),cell in cells.items():
        actual=[s for s in by_id.values() if s['dialect']==d and s['class']==c]
        need(len(actual)==(2 if cell['available'] else 0),'class source denominator')
    need({(d,c) for (d,c),x in cells.items() if not x['available']}=={('tsx','dense'),('tsx','large')},'frozen missing classes')
    return protocol,manifest


def matrix(protocol, manifest, concurrency, phase):
    """Pure replay plan; transport/source paths appended separately by plan()."""
    sources={(x['dialect'],x['class'],x['variant']):x for x in manifest['sources']}
    rows=[]
    def append(source,key,config,warm): rows.append({'key':key,'source_id':source['id'],'dialect':source['dialect'],'configuration':config,'warmup':warm})
    if phase=='equivalence':
        for source in manifest['sources']:
            for i,config in enumerate(protocol['configuration_cycle']): append(source,'equivalence/'+source['id']+'/'+str(i),config,False)
    else:
        for turn in range(protocol['warmup_requests_per_lane']):
            for lane in range(concurrency):
                source=sources[('rust','small',turn%2)]
                append(source,f'warmup/{turn}/{lane}',protocol['configuration_cycle'][turn%2],True)
        for dialect in protocol['dialects']:
            for kind in protocol['classes']:
                if (dialect,kind,0) not in sources: continue
                for pattern in protocol['patterns']:
                    for n in range(protocol['requests_per_dialect_class_pattern_session']):
                        variant=0 if pattern=='repeated' else n%2
                        append(sources[(dialect,kind,variant)],f'{dialect}/{kind}/{pattern}/{n}',protocol['configuration_cycle'][n%2],False)
    return rows


def plan(protocol,manifest,root,directory,mode,concurrency,phase,sources):
    root=Path(root);worker='worker-persistent' if mode=='xrw2' else 'worker-spike'
    rows=matrix(protocol,manifest,concurrency,phase)
    hashes={key:blake3.blake3(source['raw']).hexdigest() for key,source in sources.items()}
    for row in rows:
        row['source']=str(root/'sources'/row['source_id']);row['source_blake3']=hashes[row['source_id']]
    return {'mode':mode,'phase':phase,'worker':str(root/'native-bin'/worker),'concurrency':concurrency,'control_directory':str(root/directory/'control'),'requests':rows}


def producers(design):
    need(type(design) is dict and design['schema_version']=='xrai.eval.resources.real-producers.v1' and design['tree_sitter']=='0.27.1','producer schema/runtime')
    provenance=file(ROOT/'crates/xrai-eval/parsing-provenance.json')
    need(design['provenance'].encode()==provenance,'producer exact frozen provenance')
    packages={p['crate']:p for p in decode(provenance)['packages']};records={r['dialect']:r for r in design['grammars']}
    need(len(design['grammars'])==7 and set(records)==set(GRAMMARS),'producer grammar closure');result={}
    for dialect,(crate,version,node_path,abi,query_name) in GRAMMARS.items():
        row=records[dialect];node_types=row['node_types'].encode();query=file(ROOT/f'crates/xrai-eval/queries/{query_name}.scm')
        need(packages[crate]['version']==version and row['crate']==crate and row['version']==version and integer(row['abi']) and row['abi']==abi,'pinned grammar version/ABI')
        need(sha(node_types)==packages[crate]['native_source_sha256'][node_path] and row['query'].encode()==query,'node-types provenance and query bytes')
        hash_=blake3.blake3()
        for value in [b'tree-sitter=0.27.1',crate.encode(),version.encode(),node_types,query,provenance]: hash_.update(len(value).to_bytes(8,'little'));hash_.update(value)
        hash_.update(abi.to_bytes(8,'little'));result[dialect]=hash_.hexdigest()
        need(row['producer']==result[dialect],'recomputed real producer fingerprint')
    return result


def response(raw,source,configuration,expected_producer):
    need(0<len(raw)<=16*1024*1024,'complete response byte limit');position=0
    def take(count):
        nonlocal position
        need(0<=count<=len(raw)-position,'truncated response');result=raw[position:position+count];position+=count;return result
    def number(): return int.from_bytes(take(8),'little')
    def blob(limit):
        count=number();need(count<=limit,'response blob bound');return take(count)
    request=number();attempt=int.from_bytes(take(4),'little');dialect=blob(32).decode();source_hash=take(32).hex();producer=take(32).hex();config_hash=take(32).hex();state=take(1)[0]
    source_bytes,node_count,query_matches=number(),number(),number();count=number();need(count<=len(raw)//16,'span count');spans=[(number(),number()) for _ in range(count)];payload=decode(blob(16*1024*1024))
    need(position==len(raw) and request==0 and attempt==0 and state in [0,1],'canonical complete response identity/state')
    need(dialect==source['dialect'] and source_hash==blake3.blake3(source['raw']).hexdigest() and config_hash==blake3.blake3(configuration.encode()).hexdigest(),'response consumed source/configuration')
    need(producer==expected_producer and producer!='00'*32,'real grammar/query producer identity')
    need(set(payload)=={'dialect','complete','source_bytes','node_count','query_matches','tree','diagnostics'} and type(payload['complete']) is bool and isinstance(payload['tree'],str) and payload['tree'].startswith('('),'complete parser payload')
    need(all(integer(payload[k]) for k in ('source_bytes','node_count','query_matches')) and node_count>=1,'strict integer payload counters')
    need(payload['dialect']==dialect and payload['source_bytes']==source_bytes==len(source['raw']) and payload['node_count']==node_count and payload['query_matches']==query_matches and payload['complete']==(state==0),'duplicate response fields')
    diagnostics=payload['diagnostics'];need(type(diagnostics) is list and len(diagnostics)==len(spans),'all diagnostic records retained')
    starts=[0]+[i+1 for i,b in enumerate(source['raw']) if b==10]
    fields={'kind','start_byte','end_byte','start_line','start_column_byte','end_line','end_column_byte'}
    for d,(a,b) in zip(diagnostics,spans):
        need(type(d) is dict and set(d)==fields and d['kind'] in ('error','missing') and all(integer(d[k]) for k in fields-{'kind'}),'strict diagnostic types/kind/fields')
        need(d['start_byte']==a and d['end_byte']==b and 0<=a<=b<=source_bytes,'diagnostic byte bounds')
        for offset,prefix in ((a,'start'),(b,'end')):
            line=bisect.bisect_right(starts,offset);need(d[prefix+'_line']==line and d[prefix+'_column_byte']==offset-starts[line-1],'actual source diagnostic coordinates')
    need(payload['complete']==(not diagnostics),'complete/diagnostic contract')
    return {'producer':producer,'state':state,'node_count':node_count,'query_matches':query_matches,'diagnostics':len(spans),'bytes':len(raw)}


def calibration(output):
    path=output/'calibration';payload=read(path/'stdout');receipt=read(path/'resources.json');result=read(path/'calibration.json')
    need(receipt['exit']==0 and receipt['timed_out'] is False and receipt['output_sha256']==sha(file(path/'stdout')) and receipt['stderr_sha256']==sha(file(path/'stderr'))==sha(b''),'actual successful host calibration')
    need(type(payload['self_user']) in (int,float) and math.isfinite(payload['self_user']) and payload['self_user']>=0 and type(payload['self_system']) in (int,float) and math.isfinite(payload['self_system']) and payload['self_system']>=0,'calibration self CPU domain')
    need(all(type(c[k]) in (int,float) and math.isfinite(c[k]) and c[k]>=0 for c in payload['child_usage'] for k in ('user','system')),'calibration child CPU domain')
    need(all(type(receipt[k]) in (int,float) and math.isfinite(receipt[k]) and receipt[k]>=0 for k in ('cpu_user_seconds','cpu_system_seconds')),'calibration terminal CPU domain')
    need(file(path/'input.json')==b'{}','actual calibration input')
    import measure_workers
    need(type(receipt['command']) is list and len(receipt['command'])==3 and receipt['command'][1:]==['-c',measure_workers.CALIBRATION],'pinned owned host calibration program')
    expected_user=payload['self_user']+sum(c['user'] for c in payload['child_usage']);expected_system=payload['self_system']+sum(c['system'] for c in payload['child_usage'])
    need(len(payload['children'])==3 and len(payload['child_usage'])==3 and {c['pid'] for c in payload['child_usage']}==set(payload['children']),'calibration waited child closure')
    need(abs(receipt['cpu_user_seconds']-expected_user)<=.03 and abs(receipt['cpu_system_seconds']-expected_system)<=.03 and result['expected_user']==expected_user and result['expected_system']==expected_system and result['cpu_inclusive_validated'] is True,'terminal inclusive CPU recalibration')
    observed={p['pid'] for s in receipt['samples'] for p in s['processes']}
    maximum=max(len(s['processes']) for s in receipt['samples'])
    need(maximum>=3 and result['maximum_simultaneous_processes']==maximum and result['children_missed_by_sampler']==sorted(set(payload['children'])-observed),'actual simultaneous calibration/missed short process')
    need(result['short_child_cpu_accounted_at_exit']==payload['child_usage'][-1],'short process exit CPU')
    return sha(file(path/'calibration.json'))


def resource(receipt,payload,control,calibration_hash):
    need(receipt['schema_version']=='xrai.eval.resources.real-observer.v1' and receipt['exit']==0 and receipt['timed_out'] is False,'successful measured session')
    need(integer(receipt['pid'],1) and receipt['pid']==payload['parent_pid'],'actual measured target PID binding')
    need(receipt['calibration_sha256']==calibration_hash and receipt['cpu_inclusive_calibrated'] is True,'same-host observed calibration binding')
    need(all(type(receipt[k]) in (int,float) and math.isfinite(receipt[k]) and receipt[k]>=0 for k in ('cpu_user_seconds','cpu_system_seconds','observer_self_user_seconds','observer_self_system_seconds','observer_ps_user_seconds','observer_ps_system_seconds')),'terminal CPU values')
    need(receipt['cpu_origin']=='wait4 target parent plus its waited descendants; calibration validated once on this host','CPU counter origin')
    need(type(receipt['sample_interval_seconds']) is float and receipt['sample_interval_seconds']==.025 and receipt['observer_errors']==[],'frozen observer cadence/errors')
    samples=receipt['samples'];need(type(samples) is list and samples,'RSS samples');valid=[]
    need(all(samples[i]['end_ns']<=samples[i+1]['begin_ns'] for i in range(len(samples)-1)),'nonoverlapping observer sample order')
    for sample in samples:
        need(sample['phase'] in ('capture_setup','idle','warm_idle','warmup','measured_dispatch_shutdown'),'declared observer phase')
        need(all(integer(sample[k]) for k in ('begin_ns','end_ns','epoch_begin_ns','epoch_end_ns')) and sample['begin_ns']<=sample['end_ns'] and sample['epoch_begin_ns']<=sample['epoch_end_ns'],'sample interval')
        need(len({p['pid'] for p in sample['processes']})==len(sample['processes']),'common snapshot PID uniqueness')
        for process in sample['processes']: need(integer(process['pid'],1) and integer(process['ppid']) and integer(process['rss_bytes']) and type(process['start_observed']) is str and bool(process['start_observed']),'actual process incarnation/RSS fields')
        if sample['error'] is None:
            need(integer(sample['sum_rss_bytes']) and sample['sum_rss_bytes']==sum(p['rss_bytes'] for p in sample['processes']),'simultaneous RSS sum')
            if sample['processes']:valid.append(sample['sum_rss_bytes'])
        else:need(type(sample['error']) is str and bool(sample['error']) and sample['sum_rss_bytes'] is None and sample['processes']==[],'failed sample explicit gap without invented observed processes')
    need((integer(receipt['sampled_peak_sum_rss']) if valid else receipt['sampled_peak_sum_rss'] is None) and receipt['sampled_peak_sum_rss']==(max(valid) if valid else None),'sampled simultaneous RSS peak')
    need(set(receipt['baselines'])=={'idle','warm_idle'},'both synchronized baseline phases')
    for name,b in receipt['baselines'].items():
        indices=b['sample_indices'];need(type(indices) is list and len(indices)>=3 and all(integer(i) and i<len(samples) for i in indices) and len(set(indices))==len(indices),'distinct nonnegative in-range baseline sample indices')
        ready=int(file(control/(name+'.ready')));ack=int(file(control/(name+'.start')))
        need(integer(b['ready_epoch_ns']) and integer(b['ack_epoch_ns']) and ready==b['ready_epoch_ns'] and ack==b['ack_epoch_ns'] and ready<=ack,'actual synchronized gates')
        need(all(samples[i]['phase']==name and samples[i]['error'] is None and ready<=samples[i]['epoch_begin_ns']<=samples[i]['epoch_end_ns']<=ack and any(p['pid']==payload['parent_pid'] for p in samples[i]['processes']) for i in indices),'baseline samples precede actual release')
    seen={p['pid'] for s in samples for p in s['processes']};missing=sorted({row['pid'] for row in payload['samples']}-seen)
    need(receipt['worker_pids_missed_by_sampler']==missing,'sampling loss explicit')
    need(integer(receipt['epoch_started_ns']) and integer(receipt['epoch_finished_ns']) and receipt['epoch_started_ns']<=receipt['epoch_finished_ns'],'resource epoch ordering')
    need(all(receipt['epoch_started_ns']<=s['epoch_begin_ns']<=s['epoch_end_ns'] for s in samples),'all samples belong to observed epoch domain')
    # The final ps call can finish after target reaping; retain that observer tail explicitly.
    need(integer(receipt['observer_epoch_finished_ns']) and receipt['epoch_finished_ns']<=receipt['observer_epoch_finished_ns'] and all(s['epoch_end_ns']<=receipt['observer_epoch_finished_ns'] for s in samples),'bounded observer tail')


def native_session(output,directory,mode,concurrency,phase,metadata,protocol,manifest,sources,expected,calibration_hash):
    path=output/directory;inp=read(path/'input.json');payload=read(path/'stdout');receipt=read(path/'resources.json')
    need(same(inp,plan(protocol,manifest,metadata['output_root'],directory,mode,concurrency,phase,sources)),'exact frozen input matrix and actual retained executable/source paths')
    need(payload['schema_version']=='xrai.eval.resources.real-native-session.v1' and payload['mode']==mode and payload['phase']==phase and integer(payload['concurrency'],1) and payload['concurrency']==concurrency,'native session metadata')
    need(integer(payload['parent_pid'],1) and integer(payload['reserved_at_shutdown']) and payload['reserved_at_shutdown']==0 and payload['operational_response_normalization']==['identity.request'] and payload['cache_policy']==CACHE_POLICY and payload['upstream_executed'] is False,'cache/shutdown/normalization boundary')
    need(all(integer(payload[k]) for k in ('capture_ns','setup_ns','shutdown_ns','elapsed_ns','idle_epoch_ns')),'observed native setup/serialization/shutdown timings')
    need(receipt['command']==[str(Path(metadata['output_root'])/'native-bin'/'worker-benchmark-real')],'actual driver command consumes retained bytes')
    need(receipt['epoch_started_ns']>=metadata['frozen_epoch_ns'],'preregistration precedes native sessions')
    need(len(payload['samples'])==len(inp['requests']),'complete native response row matrix')
    for index,(item,row) in enumerate(zip(inp['requests'],payload['samples'])):
        need(row['request']==index and integer(row['request']) and row['key']==item['key'] and row['source_id']==item['source_id'] and row['warmup'] is item['warmup'] and integer(row['lane']) and row['lane']==index%concurrency,'request correlation')
        key=(item['source_id'],item['configuration']);need(row['response_blake3']==expected[key]['blake3'] and row['response_bytes']==expected[key]['bytes'],'complete Response hash/bytes equivalence')
        need(all(integer(row[f]) for f in ('dispatch_ns','source_read_ns','request_prepare_ns','encode_request_ns','encode_response_ns','end_to_end_ns','completed_from_session_start_ns','request_bytes','response_bytes')),'observed timings/counters')
        need(row['end_to_end_ns']>=row['dispatch_ns'] and all(row[f] is None for f in ('inner_queue_ns','inner_codec_ns','inner_roundtrip_ns')) and bool(row['unavailable_components_reason']),'timing boundaries/unobservable components')
        need(integer(row['attempts'],1) and row['attempts']==1 and integer(row['pid'],1) and type(row['first_seen_by_lane']) is bool,'process/lane and no unrecorded retry')
        need((integer(row['compile_ns']) if mode=='direct_cached' else row['compile_ns'] is None),'cache compile observability')
        if mode in ('direct','direct_cached'): need(row['pid']==payload['parent_pid'] and row['ipc_bytes'] is None and row['incarnation'] is None,'direct process boundary')
        elif mode=='xrw1': need(integer(row['ipc_bytes']) and integer(row['stderr_captured_bytes']) and row['incarnation'] is None,'single worker observed counters')
        else: need(row['ipc_bytes'] is None and row['stderr_captured_bytes'] is None and type(row['incarnation']) is str and len(row['incarnation'])==64,'persistent incarnation/opaque counters')
    need(receipt['stdout_sha256']==sha(file(path/'stdout')) and receipt['stderr_sha256']==sha(file(path/'stderr'))==sha(b''),'actual output hashes')
    resource(receipt,payload,path/'control',calibration_hash)
    return inp,payload,receipt


def verify(output):
    output=Path(output);protocol,manifest=frozen();metadata=read(output/'preregistered.json')
    need(metadata['schema_version']=='xrai.eval.resources.real-preregistration.v1' and metadata['protocol_sha256']==sha(file(DESIGN/'protocol.json')) and metadata['source_manifest_sha256']==sha(file(DESIGN/'source-manifest.json')),'frozen preregistration')
    need(integer(metadata['frozen_epoch_ns']),'preregistration timestamp')
    need(metadata['native_executed_locally'] is False and metadata['upstream_executed'] is False and metadata['environment']['platform'] in ('Linux','Darwin'),'disposable native execution boundary')
    need(metadata['source_bindings_sha256']=={p:sha(file(ROOT/p)) for p in SOURCE_PATHS},'complete current producer/method source binding')
    need(set(metadata['binary_sha256'])=={'native-bin/'+n for n in BINARIES},'exact three measured binaries')
    for rel,digest in metadata['binary_sha256'].items(): need(sha(file(output/rel))==digest,'actual retained measured executable')
    need(Path(metadata['output_root']).is_absolute(),'captured original output path')
    sources={}
    for item in manifest['sources']:
        raw=file(output/'sources'/item['id']);need(sha(raw)==item['sha256'],'actually measured source bytes');sources[item['id']]=dict(item,raw=raw)
    need({p.name for p in (output/'sources').iterdir()}==set(sources),'source closure')
    producer_hashes=producers(read(output/'producers.json'));calibration_hash=calibration(output)
    reference=read(output/'reference.json');expected={};reference_order=[]
    for row in reference['responses']:
        key=(row['source_id'],row['configuration']);need(key not in expected,'duplicate reference source/configuration');i=protocol['configuration_cycle'].index(row['configuration'])
        need(row['relative_path']==f'reference-responses/{row["source_id"]}--{i}.response.gz','reference path closure')
        raw=unpack(output/row['relative_path']);need(sha(raw)==row['sha256'] and blake3.blake3(raw).hexdigest()==row['blake3'],'complete reference bytes')
        observation=response(raw,sources[row['source_id']],row['configuration'],producer_hashes[sources[row['source_id']]['dialect']]);need(observation['bytes']==row['bytes'],'reference byte count')
        expected[key]=row;reference_order.append(key)
    need(set(expected)=={(s,c) for s in sources for c in protocol['configuration_cycle']},'exact source/configuration reference keyset')
    equivalence_receipts=[]
    for mode in protocol['modes']:
        directory='equivalence-'+mode;inp,payload,receipt=native_session(output,directory,mode,1,'equivalence',metadata,protocol,manifest,sources,expected,calibration_hash)
        for index,item in enumerate(inp['requests']):
            raw=unpack(output/directory/'control'/'references'/f'{index}.response.gz');reference_row=expected[(item['source_id'],item['configuration'])]
            need(raw==unpack(output/reference_row['relative_path']),'actual all-mode complete byte-for-byte equivalence')
        equivalence_receipts.append(receipt)
    need(reference['equivalence_completed_epoch_ns']>=max(r['epoch_finished_ns'] for r in equivalence_receipts),'actual equivalence finished before reference decision')
    sessions=metadata['sessions'];keys={(s['session'],s['mode'],s['concurrency']) for s in sessions}
    need(len(sessions)==len(keys)==24 and keys=={(s,m,c) for s in range(3) for m in protocol['modes'] for c in (1,2)} and len({s['directory'] for s in sessions})==24,'bijection of independent sessions')
    scheduled=[{'session':s,'mode':m,'concurrency':c,'directory':f'session-{s}-c{c}-{m}'} for c in (1,2) for s,order in enumerate(protocol['mode_rotation']) for m in order]
    need(same(sessions,scheduled),'frozen mode order/independent session paths')
    summaries=[];previous=reference['equivalence_completed_epoch_ns']
    for session in sessions:
        _,payload,receipt=native_session(output,session['directory'],session['mode'],session['concurrency'],'measurement',metadata,protocol,manifest,sources,expected,calibration_hash)
        need(previous<=receipt['epoch_started_ns'],'equivalence precedes nonoverlapping independent measured sessions');previous=receipt['epoch_finished_ns']
        grouped=defaultdict(list)
        for row in payload['samples']:
            if not row['warmup']:
                dialect,kind,pattern,_=row['key'].split('/');grouped[(dialect,kind,pattern)].append(row)
        classes=[]
        for (dialect,kind,pattern),rows in grouped.items():
            need(len(rows)==30,'exact class/pattern query denominator');values=sorted(r['end_to_end_ns'] for r in rows)
            classes.append({'dialect':dialect,'class':kind,'pattern':pattern,'requests':30,'p50_end_to_end_ns':values[14],'p95_end_to_end_ns':values[28],'sum_end_to_end_ns':sum(values),'first_seen_by_lane':sum(r['first_seen_by_lane'] for r in rows)})
        measured=[r for r in payload['samples'] if not r['warmup']];completion=max(r['completed_from_session_start_ns'] for r in measured)-min(r['completed_from_session_start_ns']-r['end_to_end_ns'] for r in measured)
        summaries.append(dict(session,requests=len(measured),classes=classes,measured_makespan_ns=completion,requests_per_second=len(measured)*1e9/completion,cpu_user_seconds=receipt['cpu_user_seconds'],cpu_system_seconds=receipt['cpu_system_seconds'],sampled_peak_sum_rss=receipt['sampled_peak_sum_rss'],worker_pids_missed_by_sampler=receipt['worker_pids_missed_by_sampler'],capture_ns=payload['capture_ns'],setup_ns=payload['setup_ns'],shutdown_ns=payload['shutdown_ns']))
    need(sum(p.stat().st_size for p in output.rglob('*') if p.is_file())<=protocol['limits']['artifact_uncompressed_bytes'],'bounded evidence artifact')
    return {'schema_version':'xrai.eval.resources.real-verification.v1','verified':True,'data_only':True,'sessions':summaries,'full_response_equivalent':True,'sources':80,'real_whole_units':52,'derived_incomplete_units':14,'historical_comment_controls':14,'missing_classes':[x for x in manifest['availability'] if not x['available']],'m0_06_complete':False,'production_recommendation':None,'limits':protocol['known_gaps']+['Frozen prose omitted TSX dense gap; immutable availability also records dense unavailable.','Warmup covers Rust small only; other dialect caches become warm during measured matrix; first dialect calls remain included.','Source read_ns belongs to one unique capture and is repeated per row; never sum per query.','Pool setup is lazy; spawn/handshake/compile remain in outer dispatch, not inferred as zero.','RSS PID incarnation uses ps lstart granularity; loss counts use PID sets and cannot prove every native incarnation was sampled; peaks and short workers may be missed.']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--design-only',action='store_true');parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.design_only:
        _,manifest=frozen();result={'verified':True,'data_only':True,'measured':False,'sources':len(manifest['sources']),'protocol_sha256':sha(file(DESIGN/'protocol.json')),'missing_classes':[x for x in manifest['availability'] if not x['available']]}
    elif args.output: result=verify(args.output)
    else: parser.error('--design-only or --output required')
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__':main()
