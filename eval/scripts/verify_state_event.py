"""Recompute complete C03 event comparison from retained bytes; no native execution."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
from blake3 import blake3

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT/'eval/qualification/state-events/rust'


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(rows):
    result = {}
    for k,v in rows:
        need(k not in result, 'duplicate JSON field')
        result[k] = v
    return result


def decode(raw):
    return json.loads(raw,object_pairs_hook=pairs)


def native_hash(raw):
    return blake3(raw).hexdigest()


def rust_json(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()


def validate_snapshot(snapshot, input_value, query_resolution=None):
    required = {'snapshot_id','configuration_id','configuration_fingerprint','producer_fingerprint',
                'input','declarations','imports','modules','gaps','references','scopes','coverage'}
    need(required <= set(snapshot) <= required|{'bindings','conditions'}, 'complete snapshot field closure')
    need(all(type(snapshot[k]) is list for k in ['declarations','imports','gaps','references','scopes']) and
         type(snapshot['modules']) is dict and type(snapshot['coverage']) is dict, 'snapshot collection types')
    need(snapshot['input'] == input_value, 'snapshot consumed different source/configuration')
    fp = native_hash(rust_json([input_value['edition'],dict(sorted(input_value['configuration'].items()))]))
    need(snapshot['configuration_fingerprint'] == fp and snapshot['configuration_id'] == 'cfg_'+fp,
         'configuration identity mismatch')
    ordered_input = {k:dict(sorted(input_value[k].items())) if k in ['files','configuration'] else input_value[k]
                     for k in ['files','root','edition','configuration','rules']}
    expected_id = 'snap_'+native_hash(rust_json([ordered_input,snapshot['producer_fingerprint']]))
    need(snapshot['snapshot_id'] == expected_id, 'snapshot content identity mismatch')
    declarations = {d['id']: d for d in snapshot['declarations']}
    need(len(declarations) == len(snapshot['declarations']), 'duplicate declaration identity')
    def visit(value):
        if isinstance(value,dict):
            if {'file_id','snapshot_id','source_hash','path','start','end'} <= value.keys():
                need(value['snapshot_id'] == snapshot['snapshot_id'] and value['path'] in input_value['files'], 'mixed evidence snapshot/path')
                raw = input_value['files'][value['path']].encode()
                need(value['file_id'] == 'fi_'+native_hash(value['path'].encode()) and value['source_hash'] == native_hash(raw), 'evidence source hash mismatch')
                need(type(value['start']) is int and type(value['end']) is int and 0 <= value['start'] <= value['end'] <= len(raw), 'evidence byte span')
                raw[:value['start']].decode(); raw[value['start']:value['end']].decode()
            if {'state','target_id','candidate_ids','method','dependencies'} <= value.keys():
                need(value['method'] == 'semantic_resolution', 'different semantic method')
                need(value['state'] in ['resolved','unknown','external','candidate'], 'unknown resolution state')
                need(all(isinstance(d,str) and snapshot['snapshot_id'] in d for d in value['dependencies']), 'mixed resolution dependencies')
                if value['state'] == 'resolved':
                    need(value['target_id'] in declarations and value['candidate_ids'] == [] and value['evidence'] and value['dependencies'], 'unproven resolved target')
                else:
                    need(value['target_id'] is None, 'nonresolved target promotion')
            for child in value.values(): visit(child)
        elif isinstance(value,list):
            for child in value: visit(child)
    visit(snapshot)
    if query_resolution is not None:
        visit(query_resolution)


def load_process(directory, requests):
    rows = [decode(line) for line in (directory/'transcript.jsonl').read_bytes().splitlines() if line]
    need(len(rows) == len(requests), 'operation sequence length')
    responses, stdout = [], b''
    for sequence,(row,request) in enumerate(zip(rows,requests)):
        need(type(row['sequence']) is int and row['sequence'] == sequence, 'operation sequence identity')
        rq = base64.b64decode(row['request_base64'],validate=True)
        rs = base64.b64decode(row['response_base64'],validate=True)
        need(len(rq) <= 4*1024*1024 and len(rs) <= 4*1024*1024 and rq.endswith(b'\n') and rs.endswith(b'\n'), 'bounded complete protocol frame')
        need(sha(rq) == row['request_sha256'] and sha(rs) == row['response_sha256'], 'frame digest mismatch')
        need(decode(rq) == request, 'wrong consumed request/case/configuration')
        responses.append(decode(rs)); stdout += rs
    need(stdout == (directory/'stdout.jsonl').read_bytes() and (directory/'stderr.bin').read_bytes() == b'', 'raw stdout closure or stderr failure')
    process = decode((directory/'process.json').read_bytes())
    need(type(process['pid']) is int and process['pid'] > 1 and type(process['exit_code']) is int and process['exit_code'] == 0 and
         process['explicit_close'] is True and process['wrapper_reaped'] is True and process['unread_output_bytes'] == 0 and
         process['command_count'] == len(requests) and process['transport'] == 'bounded newline JSON' and
         type(process['elapsed_seconds']) in [int,float] and 0 <= process['elapsed_seconds'] <= 300,
         'process closure/command count/deadline')
    session, current_snapshot, generation = None, None, 0
    for request,response in zip(requests,responses):
        if request['operation'] == 'update' and request['expected_snapshot'] == 'intentionally-stale-revision':
            need(response['status'] == 'error' and response['diagnostic'] == 'expected snapshot mismatch; previous snapshot preserved', 'stale revision control not rejected')
            need(response['session_id'] == session, 'stale control replaced session')
            need(response['snapshot_id'] == current_snapshot and type(response['generation']) is int and
                 response['generation'] == generation, 'stale control changed snapshot/generation')
            continue
        need(response['status'] == 'ok', 'native operation failure')
        row = response['response']
        need(row['schema'] == 'xrai.eval.c03.rust-session.v1' and row['operation'] == request['operation'] and
             type(row['pid']) is int and row['pid'] == process['pid'] and type(row['generation']) is int,
             'native protocol/process identity')
        if session is None: session = row['session_id']
        need(row['session_id'] == session and isinstance(session,str) and len(session) == 64, 'index/session replaced')
        if request['operation'] in ['open','update']:
            generation += 1
            current_snapshot = row['snapshot_id']
        need(row['snapshot_id'] == current_snapshot and row['generation'] == generation, 'protocol snapshot/generation differs')
        if request['operation'] == 'snapshot':
            need(row['snapshot_id'] == row['result']['snapshot_id'], 'envelope differs from complete snapshot')
    need(process['closed_response'] == responses[-1] and responses[-1]['response']['result'] == {'closed':True}, 'explicit close response differs')
    return process, responses, session


def verify(directory):
    directory = Path(directory)
    manifest = decode((directory/'receipt.json').read_bytes())
    need(manifest['schema'] == 'xrai.eval.c03.real-event.receipt.v1' and manifest['event_role'] == 'required' and
         manifest['family'] == 'Rust' and manifest['strategy'] == 'conservative_full_rebuild' and manifest['normalization'] == [] and
         manifest['admitted'] is False and manifest['competitive_runs_allowed'] is False, 'event identity/strategy/admission')
    expected = {'receipt.json','native-bin/semantics-session'} | {'inputs/'+n for n in ['descriptor.json','a.json','b.json','queries.json','oracle.json']} | {side+'/'+n for side in ['incremental','rebuild'] for n in ['transcript.jsonl','stdout.jsonl','stderr.bin','process.json']}
    actual = set()
    for path in directory.rglob('*'):
        need(not path.is_symlink(), 'event export symlink')
        if not path.is_dir():
            need(path.is_file(), 'nonregular event file')
            actual.add(path.relative_to(directory).as_posix())
    need(actual in [expected, expected|{'verification.json'}], 'event exact file closure')
    descriptor = decode((directory/'inputs/descriptor.json').read_bytes())
    need(sha((directory/'inputs/descriptor.json').read_bytes()) == manifest['descriptor_sha256'] and
         (directory/'inputs/descriptor.json').read_bytes() == (ASSETS/'descriptor.json').read_bytes(), 'frozen descriptor mismatch')
    need(descriptor['prepared'] is True and descriptor['kind'] == 'state_config' and descriptor['event_role'] == 'required' and
         descriptor['task_id'] == manifest['task_id'] and descriptor['slot_id'] == manifest['slot_id'] and
         descriptor['capacity'] == manifest['scope'], 'case/slot/profile substitution')
    for name, digest in manifest['input_sha256'].items():
        raw = (directory/'inputs'/name).read_bytes()
        need(sha(raw) == digest == descriptor['artifacts'][name]['sha256'] and raw == (ASSETS/name).read_bytes(), 'frozen source/query/oracle mismatch')
    need(set(manifest['input_sha256']) == {'a.json','b.json','queries.json','oracle.json'}, 'input binding set')
    for name,digest in manifest['source_sha256'].items():
        need((ROOT/name).is_file() and sha((ROOT/name).read_bytes()) == digest, 'owned analyzer/verifier source differs')
    need(set(manifest['source_sha256']) == {'eval/scripts/run_state_event.py','eval/scripts/verify_state_event.py','crates/xrai-eval/src/bin/semantics-session.rs','crates/xrai-eval/src/semantics_spike.rs','crates/xrai-eval/src/semantics_spike/r3.rs'}, 'producer source binding set')
    binary = directory/'native-bin/semantics-session'
    need(manifest['binary']['path'] == 'native-bin/semantics-session' and sha(binary.read_bytes()) == manifest['binary']['sha256'] and binary.stat().st_size == manifest['binary']['bytes'], 'native executable byte provenance')
    a,b,queries,oracle = [decode((directory/'inputs'/n).read_bytes()) for n in ['a.json','b.json','queries.json','oracle.json']]
    need(a != b and oracle['task_id'] == manifest['task_id'] and oracle['labels_frozen_before_results'] is True, 'no observable event or changed oracle')
    need(oracle['operational_normalization'] == ['session_id','operation_id','generation','pid','timing'], 'normalization policy changed')
    query_requests = [{'operation':'query',**{k:q[k]for k in ['module','path','namespace']}} for q in queries]
    # The content identity of A is recomputed from the first retained snapshot.
    lines = (directory/'incremental/transcript.jsonl').read_bytes().splitlines()
    before = decode(base64.b64decode(decode(lines[1])['response_base64'],validate=True))['response']['result']
    requests = [{'operation':'open','input':a},{'operation':'snapshot'}]+query_requests+[
        {'operation':'update','expected_snapshot':'intentionally-stale-revision','input':b},
        {'operation':'snapshot'},{'operation':'update','expected_snapshot':before['snapshot_id'],'input':b},
        {'operation':'snapshot'}]+query_requests+[{'operation':'close'}]
    left,rows,session = load_process(directory/'incremental',requests)
    right,fresh,independent = load_process(directory/'rebuild',[{'operation':'open','input':b},{'operation':'snapshot'}]+query_requests+[{'operation':'close'}])
    need(left['pid'] != right['pid'] and session != independent, 'rebuild is not an independent process/index')
    count = len(queries)
    before = rows[1]['response']['result']
    preserved = rows[3+count]['response']['result']
    after = rows[5+count]['response']['result']
    rebuilt = fresh[1]['response']['result']
    need(before == preserved, 'failed update replaced A')
    need(after == rebuilt, 'complete B snapshot differs; no fields may be normalized away')
    validate_snapshot(before,a); validate_snapshot(after,b)
    need(before['producer_fingerprint'] == after['producer_fingerprint'], 'producer changed across state event')
    generations = [r['response']['generation'] for r in rows if r['status'] == 'ok']
    expected_generations = [1]*(3+count)+[2]*(3+count)
    need(generations == expected_generations and all(r['response']['generation'] == 1 for r in fresh), 'cold B/restarted index or wrong generation sequence')
    changed = 0
    for i,q in enumerate(queries):
        warmed = rows[2+i]['response']['result']
        result = rows[6+count+i]['response']['result']
        original = fresh[2+i]['response']['result']
        need(result == original, 'complete query B differs including unknown/evidence/dependencies')
        need(set(warmed) == set(result) == {'module','path','namespace','resolution','target'}, 'query response field closure')
        for side,response,snapshot in [('a',warmed,before),('b',result,after)]:
            need({k:response[k]for k in ['module','path','namespace']} == {k:q[k]for k in ['module','path','namespace']}, 'query identity substituted')
            labels = oracle['answers'][q['id']][side]
            need(response['resolution']['state'] == labels['state'] and response['target'] == labels['target'], 'frozen oracle mismatch')
            # Validate query resolutions with the same evidence/declaration checks.
            validate_snapshot(snapshot,a if side=='a' else b,response['resolution'])
        changed += int(oracle['answers'][q['id']]['a'] != oracle['answers'][q['id']]['b'])
    need(changed > 0 and before != after, 'no stale-result detecting change')
    return {'schema':'xrai.eval.c03.real-event.verified.v1','verified':True,'data_only':True,
            'task_id':manifest['task_id'],'slot_id':manifest['slot_id'],'family':'Rust','required_event_executed':True,
            'source_scope':manifest['scope'],'strategy':manifest['strategy'],'queries':count,'changed_query_expectations':changed,
            'snapshot_comparison':'full exact equality; zero normalized fields','query_comparison':'full exact equality',
            'session_id':session,'independent_session_id':independent,'binary_sha256':manifest['binary']['sha256'],
            'descriptor_sha256':manifest['descriptor_sha256'],'code_commit':manifest['environment']['github_sha'],
            'run_id':manifest['environment']['github_run_id'],'before_snapshot':before['snapshot_id'],'after_snapshot':after['snapshot_id'],
            'file_sha256':{name:sha((directory/name).read_bytes()) for name in sorted(expected)},
            'admitted':False,'competitive_runs_allowed':False,
            'limits':['Owned analyzer only; no analyzed source executed.','One selected source unit and declared Rust experimental configuration, not complete upstream semantic resolution.',
                      'Conservative full rebuild within the retained index; no incremental performance/cache gain claim.',
                      'Process continuity is recorded by owned protocol/collector and independently observed/reaped Popen PID; historical data-only recheck cannot independently observe past execution.',
                      'Caller must authenticate CI metadata/head/job and original ZIP bytes; three other real events are prepared, unexecuted.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory),indent=2,sort_keys=True))
