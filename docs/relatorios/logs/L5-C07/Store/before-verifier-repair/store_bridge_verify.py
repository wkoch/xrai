"""Read-only native Store bridge verification. Retained ELF is never executed."""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT/'eval/context/store-bridge-v1'
INPUTS=['protocol.json','cases.json','freeze-before-native.json']
SOURCES=['crates/xrai-eval/src/context_spike.rs','crates/xrai-eval/src/context_spike/validated_diff.rs','crates/xrai-eval/src/bin/context-store-session.rs','crates/xrai-eval/src/semantics_spike.rs','crates/xrai-eval/src/semantics_spike/r3.rs','crates/xrai-eval/src/worker_spike.rs','crates/xrai-eval/harness/store_process_protocol.py','eval/scripts/store_bridge_collect.py','eval/scripts/store_bridge_verify.py','eval/scripts/test_store_bridge.py','Cargo.lock','rust-toolchain.toml','crates/xrai-eval/Cargo.toml','.github/workflows/l5-store-bridge.yml']
MAX_FILE=32*1024*1024
MAX_TOTAL=128*1024*1024
FRAME=512*1024
PROFILE='xrai.eval.store-session.v1'


def need(condition,message):
    if not condition: raise ValueError(message)

def sha(raw): return hashlib.sha256(raw).hexdigest()

def canonical(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def decode(raw):
    def pairs(items):
        result={}
        for k,v in items:
            need(k not in result,'duplicate JSON key');result[k]=v
        return result
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
    return value

def same(actual,expected,message): need(canonical(actual)==canonical(expected),message)

def b3(raw):
    import blake3
    return blake3.blake3(raw).hexdigest()

def identity(value,prefix=None):
    digest=b3(canonical(value));return digest if prefix is None else prefix+'_'+digest

def revision_identity(r): return identity([r[k] for k in ['external_revision','frontend','root','edition','configuration','rules','files']])

def source_map(r):
    out={}
    for path,presence in r['files'].items():
        if presence['state']=='present':out[path]=bytes.fromhex(presence['bytes_hex']).decode('utf8')
        else:need(presence=={'state':'absent'},'unavailable capture cannot be complete')
    return out

def validate_diff(diff):
    """Independent data reconstruction, not selection or semantic analysis."""
    a,b=[source_map(diff[side]) for side in ['base','head']]
    for side in ['base','head']:need(diff[side]['capture_blake3']==revision_identity(diff[side]),'capture identity')
    need(set(diff['base']['files'])==set(diff['head']['files']),'presence universe')
    rebuilt=dict(a);seen=set()
    for c in diff['changes']:
        path=c['path'];need(path not in seen,'duplicate change');seen.add(path)
        need((path in a,path in b)=={'create':(False,True),'delete':(True,False),'modify':(True,True)}[c['kind']],'change presence')
        raw=a.get(path,'').encode();destination=b.get(path,'').encode();cursor=0;out=b''
        for h in c['hunks']:
            start,end=h['base_span'];u,v=h['head_span']
            need(all(type(n)is int for n in [start,end,u,v]) and cursor<=start<=end<=len(raw) and 0<=u<=v<=len(destination),'span')
            for text,x,y in [(raw,start,end),(destination,u,v)]:text[:x].decode();text[x:y].decode();text[y:].decode()
            need(raw[start:end]==bytes.fromhex(h['removed_hex']) and destination[u:v]==bytes.fromhex(h['replacement_hex']),'hunk bytes')
            out+=raw[cursor:start];need(len(out)==u,'head hunk start');out+=bytes.fromhex(h['replacement_hex']);need(len(out)==v,'head hunk end');cursor=end
        out+=raw[cursor:];need(out==destination,'whole file reconstruction')
        if path in b:rebuilt[path]=out.decode()
        else:rebuilt.pop(path,None)
    same(rebuilt,b,'integral HEAD changed outside hunks')

def assets(directory=ASSETS):
    freeze=decode((directory/'freeze-before-native.json').read_bytes())
    for path,digest in freeze['sha256'].items():
        local=directory/Path(path).name if path.startswith('eval/context/store-bridge-v1/') else ROOT/path
        need(sha(local.read_bytes())==digest,'pre-native source/fixture freeze changed')
    if 'method_sha256' in freeze:same(freeze['method_sha256'],{name:sha((ROOT/name).read_bytes()) for name in SOURCES},'pre-native method freeze changed')
    protocol=decode((directory/'protocol.json').read_bytes());cases=decode((directory/'cases.json').read_bytes())['cases']
    same([c['id'] for c in cases],protocol['cases'],'case closure')
    for case in cases:
        validate_diff(case['diff'])
        for anchor in case['request']['anchors']:
            source=source_map(case['diff'][anchor['side']])[anchor['path']].encode();need(source[anchor['start']:anchor['end']].decode()==anchor['lookup']['path'],'public byte-derived lookup anchor')
    return protocol,cases

def retained(raw):
    need(type(raw)is dict and set(raw)=={'base64','bytes','sha256'},'captured fields')
    need(type(raw['bytes'])is int and 0<=raw['bytes']<=MAX_FILE,'captured size')
    data=base64.b64decode(raw['base64'],validate=True)
    need(len(data)==raw['bytes'] and sha(data)==raw['sha256'],'captured byte integrity');return data

class Reader:
    def __init__(self,record,executable):
        need(record['schema_version']=='xrai.eval.store-process.v1' and set(record)==set(['schema_version','command','pid','frame_limit','stderr_limit','stderr','active','rows','termination','native_execution_authorized_by_helper']),'complete process record')
        need(type(record['pid'])is int and record['pid']>0,'native PID')
        same(record['command'],[executable],'executed owned command binding')
        same(record['termination'],{'reason':'explicit_close','exit_code':0,'parent_reaped':True,'process_group_absent':True,'signal_error':None,'stderr_limit_exceeded':False},'complete native termination')
        need(record['active'] is False and record['native_execution_authorized_by_helper'] is False,'process scope')
        need(record['frame_limit']==FRAME and type(record['frame_limit'])is int and record['stderr_limit']==65536,'process bounds')
        need(retained(record['stderr'])==b'','native stderr unexpected')
        self.rows=record['rows'];self.at=0;self.instance=None;self.request_bytes=0;self.response_bytes=0
    def call(self,request):
        need(self.at<len(self.rows),'native row omitted');row=self.rows[self.at];self.at+=1
        same(decode(retained(row['request'])),request,'exact public command')
        need(retained(row['request'])==canonical(request)+b'\n','request canonical fullframe')
        response_raw=retained(row['response']);need(response_raw.endswith(b'\n') and response_raw.count(b'\n')==1 and len(response_raw)<=FRAME,'response frame')
        response=decode(response_raw)
        need(type(row['command_id'])is int and row['command_id']==request['command_id'] and type(row['written_bytes'])is int and row['written_bytes']==row['request']['bytes'] and row['outcome']=='response' and row['operation_may_have_applied']is True,'operation lifecycle')
        need(type(row['timeout_ms'])is int and 1<=row['timeout_ms']<=60000,'deadline bound')
        need(type(row['elapsed_seconds'])in (int,float) and math.isfinite(row['elapsed_seconds']) and 0<=row['elapsed_seconds']<=row['timeout_ms']/1000+.05,'complete I/O deadline')
        need(type(row['started_monotonic'])in (int,float) and math.isfinite(row['started_monotonic']) and row['started_monotonic']>=0,'start clock')
        need(set(response)==set(['profile','command_id','instance_id','operation','revision_role','result','error','outer_wire_bytes','model_tokens','meter_unit']),'outer fields')
        need(response['profile']==PROFILE and type(response['command_id'])is int and response['command_id']==request['command_id'] and response['operation']==request['operation'],'public native identity')
        need(type(response['instance_id'])is str and len(response['instance_id'])==64 and all(c in '0123456789abcdef' for c in response['instance_id']),'operational instance')
        if self.instance is None:self.instance=response['instance_id']
        need(response['instance_id']==self.instance,'process identity changed')
        need(type(response['outer_wire_bytes'])is int and response['outer_wire_bytes']==len(response_raw)-1 and response['model_tokens']is None and response['meter_unit']=='serialized_bytes','full outer bytes and units')
        if response['error']is None and request['operation']in ['context_validated','expand']:
            limits=request['request']['limits'] if request['operation']=='context_validated' else request['limits']
            need(len(response_raw)<=min(limits['max_bytes'],limits['max_tokens']),'final envelope budget')
            need(type(response['result']['budget']['used_tokens'])is int and response['result']['budget']['used_tokens']==len(response_raw),'functional byte meter finalwire')
            need(response['result']['budget']['used_bytes']==len(canonical(response['result'])),'complete Store envelope bytes')
        self.request_bytes+=row['request']['bytes'];self.response_bytes+=row['response']['bytes'];return response
    def finish(self):need(self.at==len(self.rows),'extra native rows')


def expected_input(r):return {'files':source_map(r),'root':r['root'],'edition':r['edition'],'configuration':r['configuration'],'rules':r['rules']}

def validate_export(export,case,instance):
    need(set(export)=={'manifest','snapshots','expansions'},'native full audit closure')
    m=export['manifest'];snapshots=export['snapshots'];need(len(snapshots)==2,'BASE/HEAD retained')
    need(set(m)==set(['context_id','selection_fingerprint','retention_epoch','incarnation','retention_policy','snapshots','request','normalized_request','rules_version','selector_fingerprint','candidates','resolutions','obligations','selected','gaps','created_ms','expires_ms','retained_bytes']),'manifest field closure')
    expected=copy.deepcopy(case['request']);expected['limits']['max_tokens']=min(expected['limits']['max_tokens'],expected['limits']['max_bytes'])
    for change in case['diff']['changes']:
        for edit in change['hunks']:
            expected['hunks'].append({'path':change['path'],'base_start':edit['base_span'][0],'base_end':edit['base_span'][1],'head_start':edit['head_span'][0],'head_end':edit['head_span'][1],'removed':bytes.fromhex(edit['removed_hex']).decode(),'added':bytes.fromhex(edit['replacement_hex']).decode()})
            for side,span in [('base',edit['base_span']),('head',edit['head_span'])]:
                if change['path']in source_map(case['diff'][side]) and span[0]!=span[1]:expected['anchors'].append({'side':side,'path':change['path'],'start':span[0],'end':span[1],'lookup':None})
    same(m['normalized_request'],expected,'native request/diff obligations binding')
    need(m['retention_epoch']==instance and type(m['incarnation'])is int and 1<=m['incarnation']<=7,'operational domain binding')
    need(m['context_id']==identity([m['selection_fingerprint'],m['retention_epoch'],m['incarnation'],m['created_ms'],m['expires_ms'],m['retention_policy']],'ctx'),'native handle generation')
    need(m['selector_fingerprint']==b3((ROOT/SOURCES[0]).read_bytes()),'Store selector fingerprint')
    need(m['expires_ms']==m['created_ms']+60000 and type(export['expansions'])is int,'TTL and attempts')
    producer=b3((ROOT/SOURCES[0]).read_bytes()+(ROOT/SOURCES[1]).read_bytes())
    for side,snapshot,descriptor in zip(['base','head'],snapshots,m['snapshots'],strict=True):
        revision=case['diff'][side]
        need(set(snapshot)=={'snapshot_id','configuration_id','configuration_fingerprint','producer_fingerprint','capture','input','ir'},'captured/IR export closure')
        same(snapshot['capture'],revision,'full captured revision')
        same(snapshot['input'],expected_input(revision),'full source input')
        need(snapshot['producer_fingerprint']==producer and snapshot['snapshot_id']==identity([revision['capture_blake3'],producer],'snap'),'capture native identity')
        need(descriptor['snapshot_id']==snapshot['snapshot_id'],'descriptor binding')
        cfg=identity([revision['frontend'],revision['edition'],revision['configuration'],revision['rules']])
        need(snapshot['configuration_fingerprint']==cfg and snapshot['configuration_id']=='cfg_'+cfg,'native config binding')
        ir=snapshot['ir']
        if revision['frontend']=='bytes':need(ir is None,'React executed/adverts Rust IR')
        else:
            need(type(ir)is dict,'native Rust IR absent');same(ir['input'],expected_input(revision),'IR source binding')
            for declaration in ir['declarations']:
                evidence=declaration['evidence'];source=source_map(revision)[evidence['path']].encode();need(0<=evidence['start']<=evidence['end']<=len(source),'IR evidence span')
            names={d['name'] for d in ir['declarations']}
            need(('cstr' in names)==(side=='base') and {'ArcFd','UringFd'}<=names,'Tokio declaration facts')
    by_snapshot={s['snapshot_id']:s for s in snapshots}
    candidate_ids=set()
    for c in m['candidates']:
        need(c['id']not in candidate_ids,'duplicate candidate');candidate_ids.add(c['id'])
        need(c['snapshot_id']in by_snapshot,'foreign candidate capture');s=by_snapshot[c['snapshot_id']];r=s['capture']
        if 'presence'in c:
            presence=r['files'][c['path']];need(c['presence']==('absent' if presence['state']=='absent' else 'present_empty'),'candidate presence facts')
            if presence['state']=='present':need(presence['bytes_hex']=='','empty candidate source')
            side='base' if s==snapshots[0] else 'head';need(c['id']==identity([s['snapshot_id'],c['path'],side,c['presence']],'item_presence'),'presence handle')
        else:
            source=s['input']['files'][c['path']].encode();need(c['source_hash']==b3(source) and c['full']==[0,len(source)],'candidate fullsource hash')
            for span in [c['minimum'],c['container'],c['full']]:need(all(type(n)is int for n in span) and 0<=span[0]<=span[1]<=len(source),'candidate spans')
    need(set(m['selected'])<=candidate_ids,'selected foreign handle')
    for obligation in m['obligations']:
        need(set(obligation['item_ids'])<=candidate_ids,'foreign obligation handle')
        if obligation['minimum_view']=='presence':need(obligation['minimum_span']is None,'presence is not source span')
    actual_queries=[]
    for r in m['resolutions']:
        side='base' if r['snapshot_id']==snapshots[0]['snapshot_id'] else 'head';need(r['snapshot_id']in by_snapshot,'foreign resolution')
        actual_queries.append({'side':side,'path':r['lookup']['path'],'state':r['result']['state'],'occurrence':r['occurrence']is not None})
        if r['occurrence']is None:need(r['query_origin']['kind']=='removed_base_occurrence' and r['query_origin']['snapshot_id']==snapshots[0]['snapshot_id'],'derived query is not HEAD occurrence')
        if r['result']['state']=='resolved':need(any(d['id']==r['result']['target_id'] for d in by_snapshot[r['snapshot_id']]['ir']['declarations']),'resolved target not in native IR')
    same(sorted(actual_queries,key=lambda x:(x['side'],x['path'])),sorted(case['expected_queries'],key=lambda x:(x['side'],x['path'])),'Tokio frozen state labels')
    need(type(export['expansions'])is int,'attempt counter');return m


def run_plan(peer,cases,*,fresh=None):
    """Own deterministic command schedule; native results supply handles only."""
    commands=[];samples={};next_id=1
    def call(op,**kwargs):
        nonlocal next_id
        request={'command_id':next_id,'operation':op,**kwargs};next_id+=1;commands.append(request);return peer.call(request)
    for index,case in enumerate(cases):
        if fresh is not None:next_id=fresh['start_id']
        now=index if fresh is None else fresh['now_ms']
        start_id=next_id
        opened=call('context_validated',diff=case['diff'],request=case['request'],now_ms=now);need(opened['error']is None,'native context refused')
        cid=opened['result']['context_id']
        inspected=call('inspect',context_id=cid,now_ms=now,max_bytes=FRAME);need(inspected['error']is None,'native inspect refused')
        validate_export(inspected['result'],case,opened['instance_id']);need(inspected['result']['expansions']==0,'new context attempt count')
        ids=[c['id'] for c in inspected['result']['manifest']['candidates']]
        need(ids,'frozen diff has no candidates')
        expanded=call('expand',context_id=cid,item_ids=ids,limits=case['request']['limits'],now_ms=now);need(expanded['error']is None,'native expansion refused')
        after=call('inspect',context_id=cid,now_ms=now,max_bytes=FRAME);need(after['error']is None and after['result']['expansions']==1,'admitted successful expansion')
        samples[case['id']]={'start_id':start_id,'now_ms':now,'context':opened,'inspect':inspected,'expand':expanded,'after_expand':after}
        if fresh is None and index==0:
            altered=copy.deepcopy(case['diff']);altered['head']['capture_blake3']='0'*64
            refused=call('context_validated',diff=altered,request=case['request'],now_ms=now);need(refused['error']=='invalid_diff:capture_identity_or_profile','invalid B refusal')
            kept=call('inspect',context_id=cid,now_ms=now,max_bytes=FRAME);same(kept['result'],after['result'],'failed B evicted/changed A')
            failed_limits=copy.deepcopy(case['request']['limits']);failed_limits['max_bytes']=1024;failed_limits['max_tokens']=1024
            for _ in range(3):need(call('expand',context_id=cid,item_ids=ids,limits=failed_limits,now_ms=now)['error']=='budget_below_envelope','failed admitted expansion budget')
            need(call('expand',context_id=cid,item_ids=ids,limits=case['request']['limits'],now_ms=now)['error']=='expansion_limit','failed attempts spend cap')
            counted=call('inspect',context_id=cid,now_ms=now,max_bytes=FRAME);need(counted['result']['expansions']==4,'all admitted attempts counted')
        if fresh is not None:break
    if fresh is None:
        last=samples[cases[-1]['id']]['inspect']['result']['manifest'];need(call('inspect',context_id=last['context_id'],now_ms=last['expires_ms'],max_bytes=FRAME)['error']=='context_expired','TTL expiration')
    closed=call('close');need(closed['error']is None and closed['result']['closed']is True and type(closed['result']['retained_contexts'])is int and 0<=closed['result']['retained_contexts']<=2,'native close result');return samples,commands


def normalize_pair(live,fresh):
    """Apply only pre-frozen operational mapping AFTER validating each domain."""
    a=copy.deepcopy(live);b=copy.deepcopy(fresh)
    am=a['inspect']['result']['manifest'];bm=b['inspect']['result']['manifest']
    mapping={b['context']['instance_id']:a['context']['instance_id'],bm['context_id']:am['context_id'],b['expand']['result']['request_id']:a['expand']['result']['request_id']}
    def remap(v):
        if type(v)is str:return mapping.get(v,v)
        if type(v)is list:return [remap(x) for x in v]
        if type(v)is dict:return {k:remap(x) for k,x in v.items()}
        return v
    b=remap(b)
    for name in ['inspect','after_expand']:b[name]['result']['manifest']['incarnation']=am['incarnation']
    same(a,b,'complete live/fresh artifacts differ');return True


def closure(cases):return set(['inputs/'+n for n in INPUTS]+['native-bin/context-store-session','session.json','receipt.json','verification.json']+['rebuild/'+c['id']+'.json' for c in cases])

def verify(directory):
    directory=Path(directory);_,cases=assets(directory/'inputs')
    members={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    need(members in [closure(cases),closure(cases)-{'verification.json'}],'complete artifact closure')
    need(not any(p.is_symlink() for p in directory.rglob('*')),'artifact symlink')
    need(all(p.stat().st_size<=MAX_FILE for p in directory.rglob('*') if p.is_file()) and sum(p.stat().st_size for p in directory.rglob('*') if p.is_file())<=MAX_TOTAL,'artifact size caps')
    receipt=decode((directory/'receipt.json').read_bytes())
    need(receipt['profile']=='xrai.eval.store-bridge-receipt.v1' and receipt['binary']['path']=='native-bin/context-store-session','receipt profile')
    same(receipt['source_sha256'],{p:sha((ROOT/p).read_bytes()) for p in SOURCES},'owned method/source binding')
    same(receipt['input_sha256'],{n:sha((ASSETS/n).read_bytes()) for n in INPUTS},'frozen input binding')
    binary=(directory/'native-bin/context-store-session').read_bytes();need(binary.startswith(b'\x7fELF') and sha(binary)==receipt['binary']['sha256'] and len(binary)==receipt['binary']['bytes'],'retained owned binary bytes')
    need(receipt['environment']['system']=='Linux' and receipt['environment']['github_actions']=='true' and receipt['admitted']is False and receipt['model_tokens']is None and receipt['provider_used']is False,'contained native scope')
    live_record=decode((directory/'session.json').read_bytes());live=Reader(live_record,receipt['executed_binary']);samples,_=run_plan(live,cases);live.finish()
    pids=[live_record['pid']];epochs=[live.instance];commands=len(live_record['rows']);requests=live.request_bytes;replies=live.response_bytes
    for case in cases:
        record=decode((directory/'rebuild'/(case['id']+'.json')).read_bytes());reader=Reader(record,receipt['executed_binary'])
        rebuilt,_=run_plan(reader,[case],fresh=samples[case['id']]);reader.finish();normalize_pair(samples[case['id']],rebuilt[case['id']])
        pids.append(record['pid']);epochs.append(reader.instance);commands+=len(record['rows']);requests+=reader.request_bytes;replies+=reader.response_bytes
    need(len(set(pids))==len(pids) and len(set(epochs))==len(epochs),'independent processes/retention domains')
    result={'profile':'xrai.eval.store-bridge-verification.v1','cases':len(cases),'commands':commands,'independent_rebuilds':len(cases),'complete_public_and_inspect_equal':True,'native_store_used':True,'react_rust_ir_absent':True,'native_handle_bindings_checked':True,'failed_B_preserved_A':True,'failed_expansions_counted':True,'request_frame_bytes':requests,'response_frame_bytes':replies,'total_session_frame_bytes':requests+replies,'model_tokens':None,'provider_used':False,'admitted':False,'binary_sha256':sha(binary)}
    if (directory/'verification.json').exists():same(decode((directory/'verification.json').read_bytes()),result,'saved result is not proof')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);p.add_argument('--design-only',action='store_true');args=p.parse_args()
    if args.design_only:
        _,cases=assets();print(json.dumps({'design_only':True,'native_executed':False,'cases':len(cases)},sort_keys=True))
    elif args.output:print(json.dumps(verify(args.output),indent=2,sort_keys=True))
    else:p.error('--output or --design-only required')
