"""Read-only complete receipt verifier for prospective native typed P3 presence context."""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'eval/context/diff-native-v1'
INPUTS = ['protocol.json', 'cases.json', 'freeze-before-native.json']
SOURCES = ['crates/xrai-eval/src/bin/context-diff-spike.rs', 'eval/scripts/p3_diff_native_verify.py',
           'eval/scripts/p3_diff_native_collect.py', 'eval/scripts/test_c06_p3.py',
           'eval/scripts/run_state_event.py', 'crates/xrai-eval/harness/unified_diff.py',
           'Cargo.lock', 'rust-toolchain.toml', 'crates/xrai-eval/Cargo.toml',
           '.github/workflows/l5-p3-diff-native.yml']
SCHEMA = 'xrai.eval.p3-diff-native.v1'
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024

def sha(raw): return hashlib.sha256(raw).hexdigest()

def canonical(value): return json.dumps(value, separators=(',', ':'), ensure_ascii=False, sort_keys=True).encode()

def decode(raw):
    def pairs(items):
        d = {}
        for k,v in items:
            if k in d: raise ValueError('duplicate JSON key')
            d[k] = v
        return d
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('JSON constant')))

def b3(raw):
    import blake3
    return blake3.blake3(raw).hexdigest()

def identity(value): return b3(canonical(value))

def decoder():
    p = ROOT / 'crates/xrai-eval/harness/unified_diff.py'
    spec = importlib.util.spec_from_file_location('_c06_owned_diff', p)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)
    return m

def assets(directory=ASSETS):
    frozen = decode((directory/'freeze-before-native.json').read_bytes())
    for name,digest in frozen['sha256'].items():
        local = directory/Path(name).name if name.startswith('eval/context/diff-native-v1/') else ROOT/name
        if sha(local.read_bytes()) != digest: raise ValueError('design freeze changed: '+name)
    protocol = decode((directory/'protocol.json').read_bytes())
    cases = decode((directory/'cases.json').read_bytes())['cases']
    m = decoder(); accepted = []; rejected = []
    for c in cases:
        base,head = [{p:bytes.fromhex(h) for p,h in c[s].items()} for s in ['base','head']]
        try: d = m.decode_unified(bytes.fromhex(c['diff_hex']), base, head)
        except m.DiffError as e:
            if c['expected']!='rejected' or c['reason']!=e.code: raise ValueError('decoder negative label changed')
            rejected.append(c['id']); continue
        if c['expected']!='accepted': raise ValueError('decoder accepted frozen negative')
        changes = [{'path':x.path,'kind':x.kind,'base_present':x.base_present,'head_present':x.head_present,
                    'hunks':[{'base_span':[h.base_start,h.base_end],'head_span':[h.head_start,h.head_end],
                              'removed_hex':h.removed.hex(),'replacement_hex':h.replacement.hex()} for h in x.hunks]} for x in d.changes]
        # Intentionally preserve Rust typed struct field order for typed identity.
        intake = {'raw_diff_hex':c['diff_hex'], 'decoder_profile':m.PROFILE,
                  'decoder_source_sha256':sha((ROOT/'crates/xrai-eval/harness/unified_diff.py').read_bytes()),
                  'diff_sha256':d.diff_sha256,'base':dict(sorted(c['base'].items())),
                  'head':dict(sorted(c['head'].items())),'changes':changes}
        accepted.append((c['id'], intake))
    if [x[0] for x in accepted]!=protocol['cases'] or rejected!=protocol['decoder_negative_cases']:
        raise ValueError('frozen case closure changed')
    return protocol, accepted, rejected

def producer():
    return b3(b''.join((ROOT/p).read_bytes() for p in [SOURCES[0], 'Cargo.lock', 'rust-toolchain.toml']))

def intake_identity(i):
    # Rust structs serialize in definition order; maps are sorted BTreeMaps.
    return b3(json.dumps(i, ensure_ascii=False, separators=(',', ':')).encode())

def prepare(i, incarnation):
    """Independent byte reconstruction; never trusts integral_head_verified flags."""
    base,head = [{p:bytes.fromhex(h) for p,h in i[s].items()} for s in ['base','head']]
    rebuilt = dict(base); seen=set(); n=0
    for files in [base,head]:
        if len(files)>128: raise ValueError('file_limit')
        if sum(map(len,files.values()))>33554432: raise ValueError('source_limit')
        for p,raw in files.items():
            if len(raw)>8388608: raise ValueError('source_limit')
            try: raw.decode('utf8')
            except UnicodeDecodeError: raise ValueError('utf8') from None
    for c in i['changes']:
        p=c['path']
        if p in seen: raise ValueError('duplicate_path')
        seen.add(p)
        if c['kind'] not in ['create','delete','modify']: raise ValueError('kind')
        flags={'create':(False,True),'delete':(True,False),'modify':(True,True)}[c['kind']]
        if (c['base_present'],c['head_present'])!=flags or (p in base)!=c['base_present'] or (p in head)!=c['head_present']:
            raise ValueError('presence')
        if not c['hunks']: raise ValueError('hunks')
        old,new=base.get(p,b''),head.get(p,b''); out=b''; pos=0
        for h in c['hunks']:
            n+=1; s,e=h['base_span']; a,b=h['head_span']
            if n>4096 or s<pos or s>e or e>len(old) or a>b or b>len(new): raise ValueError('span')
            replacement=bytes.fromhex(h['replacement_hex'])
            if old[s:e]!=bytes.fromhex(h['removed_hex']) or new[a:b]!=replacement: raise ValueError('hunk_bytes')
            try:
                old[:s].decode();old[:e].decode();new[:a].decode();new[:b].decode()
            except UnicodeDecodeError: raise ValueError('utf8_span') from None
            out+=old[pos:s]
            if len(out)!=a: raise ValueError('head_location')
            out+=replacement
            if len(out)!=b: raise ValueError('head_location')
            pos=e
        out+=old[pos:]
        if out!=new: raise ValueError('file_reconstruction')
        if c['head_present']: rebuilt[p]=out
        else: rebuilt.pop(p)
    if rebuilt!=head: raise ValueError('integral_head')
    ids={s:identity(i[s]) for s in ['base','head']}; iid=intake_identity(i)
    cid=identity({'intake':iid,'incarnation':incarnation,'producer':producer()})
    obligations=[]; evidence=[]
    for c in i['changes']:
        for side in ['base','head']:
            p=c['path']; present=c[side+'_present']; snapshot=ids[side]
            obligations.append({'path':p,'side':side,'kind':'file_presence','present':present,'snapshot_id':snapshot,'proof':'integral_typed_reconstruction'})
            if not present: continue
            raw={'base':base,'head':head}[side][p]
            for ordinal,h in enumerate(c['hunks']):
                metadata={'path':p,'side':side,'kind':'changed_source_bytes','present':True,'snapshot_id':snapshot,
                          'source_hash':b3(raw),'source_bytes':len(raw),'span':h[side+'_span'],'hunk_ordinal':ordinal,'semantic_state':'unknown'}
                handle=identity({'context_id':cid,'evidence':metadata}); metadata['handle']=handle
                obligations.append({'path':p,'side':side,'kind':'changed_source_bytes','span':h[side+'_span'],'evidence_handle':handle,'snapshot_id':snapshot})
                evidence.append({'metadata':metadata,'raw':raw})
    manifest={'context_id':cid,'intake_id':iid,'diff_sha256':i['diff_sha256'],'intake_identity_algorithms':{'intake_id':'BLAKE3','intake_sha256':'SHA-256'},
              'intake_sha256':sha(json.dumps(i,ensure_ascii=False,separators=(',',':')).encode()),'intake_sha256_checked_natively':False,'raw_diff_hex':i['raw_diff_hex'],
              'raw_diff_blake3':b3(bytes.fromhex(i['raw_diff_hex'])),'decoder_profile':i['decoder_profile'],
              'decoder_source_sha256':i['decoder_source_sha256'],'base_snapshot_id':ids['base'],'head_snapshot_id':ids['head'],
              'integral_head_verified':True,'obligations':obligations,'evidence':[e['metadata'] for e in evidence],
              'semantic_support':'unknown','raw_diff_decoded_natively':False}
    return {'id':cid,'manifest':manifest,'evidence':evidence}

def envelope(operation,result,status,pid):
    v={'status':status,'schema':SCHEMA,'pid':pid,'producer':producer(),'operation':operation,'result':result,
       'wire_bytes':0,'model_tokens':None,'controlled_tokens':None,'meter':'canonical_response_utf8_bytes_excluding_newline'}
    for _ in range(16):
        n=len(canonical(v))
        if n==v['wire_bytes']: return v
        v['wire_bytes']=n
    raise ValueError('wire_counter')

def failure(op,code,pid): return envelope(op,{'code':code},'error',pid)

def delivery(c,handles,expanded,budget,pid):
    items=[]; omitted=[]
    selected=[e for e in c['evidence'] if e['metadata']['handle'] in handles]
    if len(selected)>128 or sum(len(e['raw']) if expanded else e['metadata']['span'][1]-e['metadata']['span'][0] for e in selected)>2097152:
        raise ValueError('selection_work_limit')
    for e in c['evidence']:
        if e['metadata']['handle'] not in handles: continue
        item=copy.deepcopy(e['metadata']); span=[0,len(e['raw'])] if expanded else item['span']
        item['delivered_span']=span;item['content_hex']=e['raw'][span[0]:span[1]].hex();items.append(item)
    while True:
        wire=envelope('expand' if expanded else 'open',{'context_id':c['id'],'manifest':c['manifest'],
            'requested_handles':handles,'expanded':expanded,'items':items,'omitted':omitted,'budget_bytes':budget,'complete':not omitted},'ok',pid)
        if wire['wire_bytes']<=budget: return wire
        if not items: raise ValueError('metadata_budget_floor')
        omitted.insert(0,{'handle':items.pop()['handle'],'reason':'whole_wire_byte_budget','identified':True})

def mutations(i):
    out=[]
    for kind in ['wrong_head','wrong_presence','wrong_kind','wrong_span','wrong_replacement','duplicate_path','invalid_utf8']:
        x=copy.deepcopy(i);c=x['changes'][0]
        if kind=='wrong_head':x['head']['untouched.txt']='78'
        elif kind=='wrong_presence':c['base_present']=not c['base_present']
        elif kind=='wrong_kind':c['kind']='rename'
        elif kind=='wrong_span':c['hunks'][0]['base_span'][1]=999999
        elif kind=='wrong_replacement':c['hunks'][0]['replacement_hex']='78'
        elif kind=='duplicate_path':x['changes'].append(copy.deepcopy(c))
        else:x['head']['untouched.txt']='ff'
        out.append((kind,x))
    return out

def commands(pid, directory=ASSETS, fresh=False):
    protocol,cases,_=assets(directory); current=None;incarnation=0;rows=[];previous=None
    def add(req,expected): rows.append((req,expected))
    for case_id,i in cases:
        c=prepare(i,incarnation+1);handles=[e['metadata']['handle'] for e in c['evidence']]
        add({'operation':'open','intake':i,'intake_sha256':sha(json.dumps(i,ensure_ascii=False,separators=(',',':')).encode()),'budget_bytes':65536},delivery(c,handles,False,65536,pid));incarnation+=1;current=c
        if fresh:
            add({'operation':'expand','context_id':c['id'],'handles':handles,'budget_bytes':65536},delivery(c,handles,True,65536,pid))
            continue
        if previous:
            add({'operation':'expand','context_id':previous,'handles':[],'budget_bytes':65536},failure('expand','stale_context',pid))
        for expanded,budget,hs in [(True,65536,handles),(True,512,handles),(True,65536,['forged-handle'])]:
            req={'operation':'expand','context_id':c['id'],'handles':hs,'budget_bytes':budget}
            try:
                if hs==['forged-handle']:raise ValueError('foreign_or_duplicate_handle')
                result=delivery(c,hs,expanded,budget,pid)
            except ValueError as e:result=failure('expand',str(e),pid)
            add(req,result)
        bad=copy.deepcopy(i);bad['head']['unmentioned-created-file']=''
        add({'operation':'open','intake':bad,'intake_sha256':sha(json.dumps(bad,ensure_ascii=False,separators=(',',':')).encode()),'budget_bytes':65536},failure('open','integral_head',pid))
        add({'operation':'expand','context_id':c['id'],'handles':handles,'budget_bytes':65536},delivery(c,handles,True,65536,pid))
        # At the exact metadata floor, content can be omitted without erasing manifest.
        empty_wire=envelope('expand',{'context_id':c['id'],'manifest':c['manifest'],'requested_handles':handles,
            'expanded':True,'items':[],'omitted':[{'handle':h,'reason':'whole_wire_byte_budget','identified':True} for h in handles],
            'budget_bytes':0,'complete':not handles},'ok',pid)
        budget=empty_wire['wire_bytes']+32
        try: result=delivery(c,handles,True,budget,pid)
        except ValueError as e: result=failure('expand',str(e),pid)
        add({'operation':'expand','context_id':c['id'],'handles':handles,'budget_bytes':budget},result)
        previous=c['id']
    for _,i in ([] if fresh else mutations(cases[0][1])):
        try:prepare(i,incarnation+1)
        except ValueError as e:result=failure('open',str(e),pid)
        else:raise ValueError('frozen typed mutation accepted by oracle')
        add({'operation':'open','intake':i,'intake_sha256':sha(json.dumps(i,ensure_ascii=False,separators=(',',':')).encode()),'budget_bytes':65536},result)
        handles=[e['metadata']['handle'] for e in current['evidence']]
        add({'operation':'expand','context_id':current['id'],'handles':handles,'budget_bytes':65536},delivery(current,handles,True,65536,pid))
    add({'operation':'close'},envelope('close',{'closed':True},'ok',pid))
    if len(rows)>protocol['max_operations']:raise ValueError('operation bound')
    return rows

def verify_process(output,name):
    metadata=decode((output/name/'process.json').read_bytes());pid=metadata['pid']
    if type(pid) is not int or pid<=0 or type(metadata['exit_code']) is not int or metadata['exit_code']!=0 or type(metadata['unread_output_bytes']) is not int or metadata['unread_output_bytes']!=0 or type(metadata['command_count']) is not int or metadata['explicit_close'] is not True or metadata['wrapper_reaped'] is not True or (output/name/'stderr.bin').read_bytes():raise ValueError('process closure')
    expected_rows=commands(pid,output/'inputs',fresh=name=='rebuild');rows=[decode(r) for r in (output/name/'transcript.jsonl').read_bytes().splitlines()]
    if len(rows)!=len(expected_rows) or metadata['command_count']!=len(rows):raise ValueError('command closure')
    stdout=b'';omissions=0;errors=0
    for ordinal,(row,(request,response)) in enumerate(zip(rows,expected_rows)):
        rq=base64.b64decode(row['request_base64'],validate=True);rs=base64.b64decode(row['response_base64'],validate=True);stdout+=rs
        if type(row['sequence']) is not int or row['sequence']!=ordinal or row['request_sha256']!=sha(rq) or row['response_sha256']!=sha(rs):raise ValueError('transcript identity')
        if not rq.endswith(b'\n') or canonical(decode(rq))!=canonical(request) or rs!=canonical(response)+b'\n':raise ValueError('exact typed consumer/byte context response')
        if response['wire_bytes']!=len(rs)-1:raise ValueError('whole wire count')
        errors+=response['status']=='error';omissions+=len(response['result'].get('omitted',[]))
    if stdout!=(output/name/'stdout.jsonl').read_bytes() or canonical(metadata['closed_response'])!=canonical(expected_rows[-1][1]):raise ValueError('complete stdout/close')
    results=[response for _,response in expected_rows]
    return results, errors, omissions


def verify(output):
    output=Path(output);members={p.relative_to(output).as_posix():p for p in output.rglob('*') if p.is_file()}
    expected={'inputs/'+x for x in INPUTS}|{'native-bin/context-diff-spike','session/transcript.jsonl','session/stdout.jsonl','session/stderr.bin','session/process.json','receipt.json'}|{'rebuild/'+n for n in ['transcript.jsonl','stdout.jsonl','stderr.bin','process.json']}
    if set(members)-{'verification.json'}!=expected or any(p.is_symlink() for p in output.rglob('*')):raise ValueError('receipt closure')
    if sum(p.stat().st_size for p in members.values())>MAX_TOTAL or any(p.stat().st_size>MAX_FILE for p in members.values()):raise ValueError('receipt bounds')
    p,accepted,rejected=assets(output/'inputs');receipt=decode((output/'receipt.json').read_bytes())
    source={n:sha((ROOT/n).read_bytes()) for n in SOURCES}
    if receipt['schema']!='xrai.eval.p3-diff-native-receipt.v1':raise ValueError('receipt schema')
    if receipt['source_sha256']!=source or receipt['input_sha256']!={n:sha((ASSETS/n).read_bytes()) for n in INPUTS}:raise ValueError('source/input identity')
    for n in INPUTS:
        if (output/'inputs'/n).read_bytes()!=(ASSETS/n).read_bytes():raise ValueError('retained input changed')
    binary=(output/'native-bin/context-diff-spike').read_bytes()
    if not binary.startswith(b'\x7fELF') or canonical(receipt['binary'])!=canonical({'path':'native-bin/context-diff-spike','sha256':sha(binary),'bytes':len(binary)}):raise ValueError('native ELF identity')
    env=receipt['environment']
    if env['github_actions']!='true' or env['system']!='Linux' or type(env['github_sha']) is not str or len(env['github_sha'])!=40 or any(c not in '0123456789abcdef' for c in env['github_sha']) or type(env['github_run_id']) is not str or not env['github_run_id'].isdigit():raise ValueError('disposable CI environment')
    for key in ['admitted','quota_event_credit','competitive_runs_allowed','new_eligible_dossier']:
        if receipt[key] is not False:raise ValueError('scope promotion')
    main_rows,errors,omissions=verify_process(output,'session')
    rebuild_rows,_,_=verify_process(output,'rebuild')
    main_payloads={}
    for response in main_rows:
        if response['status']=='ok' and response['operation'] in ['open','expand'] and response['result']['budget_bytes']==65536:
            result=response['result'];main_payloads[(response['operation'],result['context_id'])]=result
    for response in rebuild_rows:
        if response['operation'] in ['open','expand']:
            result=response['result']
            if canonical(result)!=canonical(main_payloads[(response['operation'],result['context_id'])]):raise ValueError('complete independent rebuild mismatch')
    if omissions==0:raise ValueError('no factual omission exercised')
    result={'schema':'xrai.eval.p3-diff-native-verification.v1','native_typed_consumer_verified':True,
            'accepted_cases':len(accepted),'python_decoder_negatives':len(rejected),'commands':len(main_rows),'independent_rebuild_commands':len(rebuild_rows),'complete_rebuild_equal':True,
            'typed_mutations':7,'refusals':errors,'omitted_evidence':omissions,'complete_wire_checked':True,
            'integral_head_recomputed':True,'native_raw_diff_parser':False,'legacy_planner_used':False,
            'model_tokens':None,'controlled_tokens':None,'provider_used':False,'admitted':False,
            'source_sha256':source,'binary_sha256':sha(binary)}
    if 'verification.json' in members and canonical(decode(members['verification.json'].read_bytes()))!=canonical(result):raise ValueError('stored verification changed')
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--design-only',action='store_true');ap.add_argument('--output',type=Path);args=ap.parse_args()
    if args.design_only:
        p,a,r=assets();result={'accepted_cases':len(a),'python_decoder_negatives':len(r),'native_run_performed':False,'command_count':len(commands(1000)),'independent_rebuild_command_count':len(commands(1000,fresh=True)),'freeze_sha256':sha((ASSETS/'freeze-before-native.json').read_bytes())}
    elif args.output:result=verify(args.output)
    else:ap.error('choose --design-only or --output')
    print(json.dumps(result,indent=2,sort_keys=True))
