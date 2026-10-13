"""Recompute a complete captured-source-presence event; no native execution."""
from pathlib import Path
import base64
import json
import re
from verify_state_event import decode, need, sha, native_hash, rust_json, ROOT

SCHEMA = 'xrai.eval.c04.source-presence.session.v1'
SOURCES = ['eval/scripts/run_presence_events.py','eval/scripts/verify_presence_event.py',
           'eval/scripts/run_state_event.py','crates/xrai-eval/src/bin/source-presence-session.rs',
           'Cargo.lock','rust-toolchain.toml']
PROFILE = 'captured-source-presence-v1'


def same(left, right):
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(right, sort_keys=True, separators=(',', ':'), allow_nan=False)


def expected_snapshot(inputs):
    need(set(inputs) == {'configuration','files'} and inputs['configuration'] == {'profile':PROFILE}, 'presence input/profile shape')
    producer = native_hash((ROOT/SOURCES[3]).read_bytes()+(ROOT/'Cargo.lock').read_bytes()+(ROOT/'rust-toolchain.toml').read_bytes()+PROFILE.encode())
    input_value = {'configuration':dict(sorted(inputs['configuration'].items())), 'files':dict(sorted(inputs['files'].items()))}
    return {'schema':'xrai.eval.c04.source-presence.snapshot.v1',
            'snapshot_id':'presence-snap_'+native_hash(rust_json([input_value,producer])),
            'configuration_id':'presence-cfg_'+native_hash(rust_json(inputs['configuration'])),
            'producer_fingerprint':producer,'input':inputs,
            'files':{p:{'file_id':'presence-file_'+native_hash(p.encode()),'source_hash':native_hash(s.encode()),
                        'byte_length':len(s.encode()),'parse_state':'unknown','semantic_state':'unknown'}for p,s in inputs['files'].items()},
            'coverage':{p:{'source_capture':'complete_for_declared_bytes','parse':'not_evaluated','semantics':'not_evaluated'}for p in inputs['files']},
            'unknowns':[{'dimension':'parse','reason':'source_presence_profile_only'}, {'dimension':'semantics','reason':'source_presence_profile_only'}],
            'diagnostics':['Absence is limited to captured sources; no whole-program absence claim.']}


def expected_query(snapshot, query):
    path = query['path']; file = snapshot['files'].get(path)
    return {'kind':'source_presence','path':path,'available':file is not None,
        'source_hash':file['source_hash']if file else None,
        'evidence':{'file_id':file['file_id'],'path':path,'snapshot_id':snapshot['snapshot_id'],
                    'source_hash':file['source_hash'],'start':0,'end':file['byte_length']}if file else None,
        'dependencies':[snapshot['snapshot_id']+':'+snapshot['configuration_id']+':'+('captured'if file else 'absent_in_capture')+':'+path],
        'coverage':'captured_sources_only','parse_state':'unknown','semantic_state':'unknown',
        'diagnostics':['No parsing or semantic resolution performed.']}


def load_process(directory, requests):
    rows = [decode(line)for line in (directory/'transcript.jsonl').read_bytes().splitlines()if line]
    need(len(rows) == len(requests), 'complete operation sequence')
    responses, stdout = [], b''
    for i,(row, request)in enumerate(zip(rows,requests)):
        need(type(row['sequence']) is int and row['sequence'] == i, 'operation sequence identity')
        rq = base64.b64decode(row['request_base64'],validate=True); rs=base64.b64decode(row['response_base64'],validate=True)
        need(rq.endswith(b'\n') and rs.endswith(b'\n') and max(len(rq),len(rs))<=4*1024*1024,'bounded complete frame')
        need(sha(rq)==row['request_sha256'] and sha(rs)==row['response_sha256'] and same(decode(rq),request),'consumed request/frame binding')
        responses.append(decode(rs));stdout+=rs
    need(stdout==(directory/'stdout.jsonl').read_bytes() and (directory/'stderr.bin').read_bytes()==b'','complete stdout/no stderr')
    process=decode((directory/'process.json').read_bytes())
    need(type(process['pid'])is int and process['pid']>1 and type(process['exit_code'])is int and process['exit_code']==0 and
         process['explicit_close']is True and process['wrapper_reaped']is True and type(process['unread_output_bytes'])is int and process['unread_output_bytes']==0 and
         type(process['command_count'])is int and process['command_count']==len(requests) and process['transport']=='bounded newline JSON' and
         type(process['elapsed_seconds'])in[int,float] and 0<=process['elapsed_seconds']<=300,'process closure/limits')
    session,snapshot,generation=None,None,0
    for request,response in zip(requests,responses):
        if request['operation']=='update' and request['expected_snapshot']=='intentionally-stale-revision':
            need(set(response)=={'status','diagnostic','session_id','snapshot_id','generation'} and response['status']=='error' and response['diagnostic']=='expected snapshot mismatch; previous snapshot preserved' and
                 response['session_id']==session and response['snapshot_id']==snapshot and type(response['generation'])is int and response['generation']==generation,'stale revision/index control')
            continue
        need(set(response)=={'status','response'} and response['status']=='ok','native operation failed/shape')
        value=response['response']
        need(set(value)=={'schema','session_id','pid','generation','snapshot_id','operation','result'} and value['schema']==SCHEMA and value['operation']==request['operation'] and type(value['pid'])is int and value['pid']==process['pid'],'process/protocol identity')
        if session is None:session=value['session_id']
        need(value['session_id']==session and isinstance(session,str)and re.fullmatch('[0-9a-f]{64}',session),'session/index continuity')
        if request['operation']in['open','update']:
            need(same(value['result'],{'strategy':'conservative_full_rebuild'}),'declared conservative strategy result')
            generation+=1;snapshot=value['snapshot_id']
        need(type(value['generation'])is int and value['generation']==generation and value['snapshot_id']==snapshot,'generation/snapshot continuity')
        if request['operation']=='snapshot':need(value['result']['snapshot_id']==snapshot,'envelope snapshot mismatch')
    need(same(process['closed_response'],responses[-1]) and same(responses[-1]['response']['result'],{'closed':True}),'close acknowledgment')
    return process,responses,session


def verify(directory):
    directory=Path(directory);m=decode((directory/'receipt.json').read_bytes())
    need(m['schema']=='xrai.eval.c04.source-presence.receipt.v1' and m['scope']==PROFILE and m['family']in['TSJS','Python','Go']and
         m['strategy']=='conservative_full_rebuild'and m['normalization']==[] and m['admitted']is False and m['competitive_runs_allowed']is False,'receipt profile/admission')
    expected={'receipt.json','native-bin/source-presence-session'}|{'inputs/'+n for n in ['descriptor.json','a.json','b.json','queries.json','oracle.json']}|{side+'/'+n for side in ['incremental','rebuild']for n in ['transcript.jsonl','stdout.jsonl','stderr.bin','process.json']}
    paths=set()
    for p in directory.rglob('*'):
        need(not p.is_symlink(),'export symlink')
        if not p.is_dir():need(p.is_file(),'nonregular export');paths.add(p.relative_to(directory).as_posix())
    need(paths in [expected,expected|{'verification.json'}],'exact event file closure')
    folder={'TSJS':'js','Python':'python','Go':'go'}[m['family']];assets=ROOT/'eval/qualification/state-events'/folder
    d=decode((directory/'inputs/descriptor.json').read_bytes())
    need((directory/'inputs/descriptor.json').read_bytes()==(assets/'descriptor.json').read_bytes() and sha((directory/'inputs/descriptor.json').read_bytes())==m['descriptor_sha256'],'frozen descriptor')
    need(d['kind']=='state_config'and d['event_role']=='required'and d['prepared']is True and
         d['capacity']==PROFILE and d['task_id']==m['task_id']and d['slot_id']==m['slot_id']and d['family']==m['family'],'task/slot/event-role identity')
    need(set(m['input_sha256'])=={'a.json','b.json','queries.json','oracle.json'},'frozen input binding set')
    for n,digest in m['input_sha256'].items():
        raw=(directory/'inputs'/n).read_bytes();need(raw==(assets/n).read_bytes()and sha(raw)==digest==d['artifacts'][n]['sha256'],'frozen consumed source/config/query/oracle')
    need(set(m['source_sha256'])==set(SOURCES),'producer source set')
    for n,digest in m['source_sha256'].items():need(sha((ROOT/n).read_bytes())==digest,'producer/verifier source changed')
    binary=directory/'native-bin/source-presence-session'
    need(m['binary']['path']=='native-bin/source-presence-session' and sha(binary.read_bytes())==m['binary']['sha256'] and type(m['binary']['bytes'])is int and binary.stat().st_size==m['binary']['bytes'],'consumed executable byte binding')
    a,b,queries,oracle=[decode((directory/'inputs'/n).read_bytes())for n in ['a.json','b.json','queries.json','oracle.json']]
    need(a!=b and a['configuration']==b['configuration'] and oracle['task_id']==m['task_id']and oracle['labels_frozen_before_results']is True,'real frozen restoration event')
    need(all(q['kind']=='source_presence'for q in queries)and len(queries)==3 and len({q['id']for q in queries})==3,'complete query set')
    before,after=expected_snapshot(a),expected_snapshot(b)
    qr=[{'operation':'query',**{k:q[k]for k in ['kind','path']}}for q in queries]
    requests=[{'operation':'open','input':a},{'operation':'snapshot'}]+qr+[
        {'operation':'update','expected_snapshot':'intentionally-stale-revision','input':b}, {'operation':'snapshot'},
        {'operation':'update','expected_snapshot':before['snapshot_id'],'input':b},{'operation':'snapshot'}]+qr+[{'operation':'close'}]
    left,rows,session=load_process(directory/'incremental',requests)
    right,fresh,independent=load_process(directory/'rebuild',[{'operation':'open','input':b},{'operation':'snapshot'}]+qr+[{'operation':'close'}])
    need(left['pid']!=right['pid']and session!=independent,'independent rebuild process/index')
    n=len(queries)
    need(same(rows[1]['response']['result'],before) and same(rows[3+n]['response']['result'],before),'A complete or failed update changed A')
    need(same(rows[5+n]['response']['result'],after) and same(fresh[1]['response']['result'],after),'B full snapshot/rebuild/source/unknown/coverage/diagnostics')
    changed=0
    for i,q in enumerate(queries):
        warmed=rows[2+i]['response']['result'];result=rows[6+n+i]['response']['result'];rebuilt=fresh[2+i]['response']['result']
        need(same(warmed,expected_query(before,q))and same(result,expected_query(after,q))and same(rebuilt,expected_query(after,q)),'complete warmed/live/rebuild queries')
        for side,snapshot,response in [('a',before,warmed),('b',after,result)]:
            source=snapshot['input']['files'].get(q['path'])
            label={'available':source is not None,'sha256':sha(source.encode())if source is not None else None}
            need(same(label,oracle['answers'][q['id']][side])and type(response['available'])is bool and response['available']==label['available'],'frozen presence oracle')
        changed+=int(oracle['answers'][q['id']]['a']!=oracle['answers'][q['id']]['b'])
    need(changed==1 and all(r['response']['generation']==1 for r in fresh),'restoration/stable controls/rebuild generations')
    return {'schema':'xrai.eval.c04.source-presence.verified.v1','verified':True,'data_only':True,
        'family':m['family'],'task_id':m['task_id'],'frozen_slot_id':m['slot_id'],'scope':PROFILE,
        'required_event_executed':True,'same_process':True,'same_index':True,'full_B_snapshot_equal':True,
        'queries':n,'changed_query_expectations':changed,'normalization':[],
        'before_snapshot':before['snapshot_id'],'after_snapshot':after['snapshot_id'],
        'session_id':session,'rebuild_session_id':independent,'pid':left['pid'],'rebuild_pid':right['pid'],
        'binary_sha256':m['binary']['sha256'],'descriptor_sha256':m['descriptor_sha256'],
        'code_commit':m['environment']['github_sha'],'run_id':m['environment']['github_run_id'],
        'file_sha256':{p:sha((directory/p).read_bytes())for p in sorted(expected)},
        'admitted':False,'competitive_runs_allowed':False,
        'limits':['Captured source availability only; parsing and semantics remain unknown.',
                  'Conservative rebuild within retained index; no cache/performance claim.',
                  'Historical data-only recheck requires authenticated original CI ZIP/head/job acquisition.',
                  'Not a new individually eligible dossier or global corpus admission.']}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    print(json.dumps(verify(p.parse_args().directory),indent=2,sort_keys=True))
