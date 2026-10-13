"""Data-only proof checker for one controlled captured ESM semantic session."""
from pathlib import Path
import argparse
import base64
import json
import math
import re
import blake3
import verify_tsjs_semantics as semantics
from verify_state_event import need, sha

ROOT = semantics.ROOT
ASSETS = ROOT / 'eval/semantics/tsjs-session-v1'
SCHEMA = 'xrai.eval.tsjs-semantic-session.v1'
PROFILE = 'captured-relative-exact-v1'
STRATEGY = 'conservative_full_semantic_rebuild'
SOURCE_BIN = 'crates/xrai-eval/src/bin/tsjs-semantic-session.rs'
KNOWN_PATH = 'docs/relatorios/logs/L5-C04/TSJS/native-proof/export/event/outputs/real-uuid-v4-unsafeStringify.json'
KNOWN_SHA = 'e6f9ff38e7e54b00d98271a3bdb9ee6a82b85faeec7eec3b015e91be860b2717'
SOURCES = [SOURCE_BIN, 'crates/xrai-eval/src/tsjs_semantics.rs', 'crates/xrai-eval/src/parsing_spike.rs',
           'crates/xrai-eval/src/worker_spike.rs', 'crates/xrai-eval/queries/javascript.scm',
           'crates/xrai-eval/queries/typescript.scm', 'crates/xrai-eval/parsing-provenance.json',
           'eval/scripts/run_tsjs_semantic_session.py', 'eval/scripts/verify_tsjs_semantic_session.py',
           'eval/scripts/test_tsjs_semantic_session.py', 'eval/scripts/run_state_event.py',
           'eval/scripts/verify_state_event.py', 'eval/scripts/verify_tsjs_semantics.py',
           'Cargo.lock', 'rust-toolchain.toml', KNOWN_PATH, '.github/workflows/l5-tsjs-session.yml']
INPUTS = ['protocol.json', 'freeze-before-session.json', 'input-a.json', 'input-b.json', 'input-invalid.json']
MAX_MEMBER = 32 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
# Process helper has a tighter 4MiB request/response transport than session 8/16MiB.
FRAME = 4 * 1024 * 1024


def decode(raw):
    need(len(raw) <= MAX_MEMBER, 'JSON member bound')
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def reject(value):
        raise ValueError('nonfinite JSON constant ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)


def same(left, right):
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(right, sort_keys=True, separators=(',', ':'), allow_nan=False)


def producer():
    return blake3.blake3(b''.join((ROOT / p).read_bytes() for p in
                                [SOURCE_BIN, 'crates/xrai-eval/src/tsjs_semantics.rs', 'Cargo.lock', 'rust-toolchain.toml'])).hexdigest()


def assets():
    frozen = decode((ASSETS / 'freeze-before-session.json').read_bytes())
    need(frozen['session_implementation_present'] is False and frozen['native_executed'] is False,
         'frozen-before-session/native evidence')
    need(set(frozen['assets_sha256']) == set(INPUTS) - {'freeze-before-session.json'}, 'frozen asset closure')
    for path, digest in frozen['assets_sha256'].items():
        need(sha((ASSETS / path).read_bytes()) == digest, 'frozen source/protocol changed')
    for path, digest in frozen['prior_sources_sha256'].items():
        need(sha((ROOT / path).read_bytes()) == digest, 'prior frozen resolver/source changed')
    values = {p: decode((ASSETS / p).read_bytes()) for p in INPUTS}
    protocol = values['protocol.json']
    need(protocol['schema'] == 'xrai.eval.tsjs-semantic-session-protocol.v1' and protocol['profile'] == PROFILE and
         protocol['admitted'] is False and protocol['new_eligible_dossier'] is False and protocol['quota_event_credit'] is False,
         'controlled session profile/nonadmission')
    need(len(protocol['operations']) == 15 and len(protocol['rebuild_operations']) == 6 and len(protocol['queries']) == 3,
         'frozen operation/query closure')
    known_raw = (ROOT / KNOWN_PATH).read_bytes()
    need(sha(known_raw) == KNOWN_SHA, 'known accepted grammar/snapshot binding')
    known = decode(known_raw)
    need(same(known['input'], values['input-b.json']), 'controlled B equals prior accepted captured source')
    for q in protocol['queries']:
        need(type(q['offset']) is int and q['offset'] >= 0 and q['callable'] == 'unknown', 'query UTF8/type/callable profile')
        for name in ['input-a.json', 'input-b.json']:
            source = values[name]['files'][q['path']]['source'].encode('utf-8')
            need(q['offset'] < len(source), 'query source span')
            source[:q['offset']].decode('utf-8')
    return values, known


def validate_snapshot(value, input_value, known):
    need(same(value.get('input'), input_value), 'snapshot exact consumed sources/configuration')
    semantics.snapshot(value, input_value)
    need(same(value['producer_components'], known['producer_components']) and
         value['producer_fingerprint'] == known['producer_fingerprint'], 'current/known native grammar producer binding')
    shapes = {
        'scopes': {'id','parent','path','start','end','function_depth','kind'},
        'bindings': {'id','name','path','scope','kind','initialized_at','evidence','imported_name','source_specifier'},
        'exports': {'path','name','local','evidence'}, 'gaps': {'scope','name','reason','evidence'},
        'references': {'name','scope','evidence','resolution','callable'},
    }
    for field, shape in shapes.items():
        need(type(value[field]) is list, 'snapshot list type')
        for item in value[field]:
            need(type(item) is dict and set(item) == shape, 'snapshot collection full field shape')
            path = item['path'] if 'path' in item else item['evidence']['path']
            need(path in input_value['files'], 'snapshot path binding')
            for k in ['scope', 'initialized_at', 'function_depth', 'id' if field == 'scopes' else 'scope']:
                if k in item:
                    need(type(item[k]) is int and item[k] >= 0, 'snapshot integer type')
            if field == 'scopes':
                source = input_value['files'][path]['source'].encode()
                need(type(item['start']) is int and type(item['end']) is int and
                     0 <= item['start'] <= item['end'] <= len(source), 'scope byte span')
                source[:item['start']].decode(); source[:item['end']].decode()
    need(all(type(v) is str for v in value['coverage'].values()), 'coverage full typed states')
    for ref in value['references']:
        for key in ['resolution', 'callable']:
            resolution = ref[key]
            need(type(resolution['evidence']) is list and type(resolution['dependencies']) is list and
                 all(type(x) is str for x in resolution['dependencies']) and type(resolution['diagnostic']) is str,
                 'full resolution dependencies/diagnostic types')
    return value


def requests(a, b, invalid, sid, queries, fresh=False):
    qr = [{'operation':'query', 'path':q['path'], 'offset':q['offset']} for q in queries]
    if fresh:
        return [{'operation':'open','input':b},{'operation':'snapshot'}] + qr + [{'operation':'close'}]
    return [{'operation':'open','input':a},{'operation':'snapshot'}] + qr + [
        {'operation':'update','expected_snapshot':'intentionally-stale-revision','input':b},
        {'operation':'snapshot'}, {'operation':'update','expected_snapshot':sid,'input':invalid},
        {'operation':'snapshot'}, {'operation':'update','expected_snapshot':sid,'input':b},
        {'operation':'snapshot'}] + qr + [{'operation':'close'}]


def process(directory, expected_requests):
    raw = (directory / 'transcript.jsonl').read_bytes()
    need(len(raw) <= MAX_MEMBER, 'bounded transcript')
    lines = raw.splitlines()
    need(len(lines) == len(expected_requests) and all(lines), 'complete operations transcript')
    responses, stdout = [], bytearray()
    for sequence, (line, expected) in enumerate(zip(lines, expected_requests)):
        row = decode(line)
        need(set(row) == {'sequence','request_base64','response_base64','request_sha256','response_sha256'} and
             type(row['sequence']) is int and row['sequence'] == sequence, 'sequence/frame typed closure')
        rq = base64.b64decode(row['request_base64'], validate=True)
        rs = base64.b64decode(row['response_base64'], validate=True)
        need(0 < len(rq) <= FRAME and 0 < len(rs) <= FRAME and rq.endswith(b'\n') and rs.endswith(b'\n'), 'bounded complete frame')
        need(b'\n' not in rq[:-1] and b'\n' not in rs[:-1], 'single physical JSONL frame')
        need(sha(rq) == row['request_sha256'] and sha(rs) == row['response_sha256'] and same(decode(rq), expected),
             'exact consumed requests/frame hashes')
        responses.append(decode(rs)); stdout.extend(rs)
    need(bytes(stdout) == (directory / 'stdout.jsonl').read_bytes() and (directory / 'stderr.bin').read_bytes() == b'',
         'complete stdout and no stderr')
    meta = decode((directory / 'process.json').read_bytes())
    need(set(meta) == {'pid','exit_code','closed_response','elapsed_seconds','command_count','transport','unread_output_bytes','explicit_close','wrapper_reaped'},
         'process metadata field closure')
    need(type(meta['pid']) is int and meta['pid'] > 1 and type(meta['exit_code']) is int and meta['exit_code'] == 0 and
         meta['explicit_close'] is True and meta['wrapper_reaped'] is True and type(meta['unread_output_bytes']) is int and meta['unread_output_bytes'] == 0 and
         type(meta['command_count']) is int and meta['command_count'] == len(expected_requests) and
         meta['transport'] == 'bounded newline JSON' and type(meta['elapsed_seconds']) in (int,float) and
         math.isfinite(meta['elapsed_seconds']) and 0 <= meta['elapsed_seconds'] <= 300, 'process close/limits')
    need(same(meta['closed_response'], responses[-1]), 'closed raw acknowledgement')
    sid, session, generation = None, None, 0
    counts = {'requests':0,'build_attempts':0,'successful_builds':0,'queries':0,'failed_updates':0}
    for request, response in zip(expected_requests, responses):
        op = request['operation']; counts['requests'] += 1
        rejected = op == 'update' and (request['expected_snapshot'] != sid or request['input']['configuration']['module'] != 'esm')
        if rejected:
            counts['failed_updates'] += 1
            if request['expected_snapshot'] == sid:
                counts['build_attempts'] += 1
            diagnostic = ('expected snapshot mismatch; previous snapshot preserved' if request['expected_snapshot'] != sid else
                          'update build failed; previous snapshot preserved: explicit ESM captured-relative-exact-v1 profile required')
            need(set(response) == {'status','diagnostic','schema','pid','counters','session_id','session_producer_fingerprint','snapshot_id','generation'} and
                 response['status'] == 'error' and response['diagnostic'] == diagnostic, 'failed update explicit refusal')
            value = response
        else:
            need(set(response) == {'status','response'} and response['status'] == 'ok', 'successful native operation')
            value = response['response']
            need(set(value) == {'schema','pid','counters','session_id','session_producer_fingerprint','snapshot_id','generation','operation','result'} and
                 value['operation'] == op, 'session complete envelope shape')
            if op in ('open','update'):
                counts['build_attempts'] += 1; counts['successful_builds'] += 1
                generation += 1; sid = value['snapshot_id']
                need(same(value['result'], {'strategy':STRATEGY}), 'conservative semantic rebuild declared')
            if op == 'query':
                counts['queries'] += 1
            if session is None:
                session = value['session_id']
        need(value['schema'] == SCHEMA and type(value['pid']) is int and value['pid'] == meta['pid'] and
             isinstance(session, str) and re.fullmatch('[0-9a-f]{64}',session) and value['session_id'] == session,
             'PID/session/index continuity')
        need(type(value['generation']) is int and value['generation'] == generation and value['snapshot_id'] == sid and
             isinstance(sid,str) and re.fullmatch('[0-9a-f]{64}',sid), 'full snapshot/generation binding')
        need(same(value['counters'],counts) and all(type(v) is int for v in value['counters'].values()), 'complete operation/build/query counters')
        need(value['session_producer_fingerprint'] == producer(), 'session native source producer')
        if op == 'snapshot':
            need(value['result']['snapshot_id'] == sid, 'snapshot envelope/body identity')
    need(same(responses[-1]['response']['result'], {'closed':True}), 'explicit close once')
    return meta, responses, session


def verify(directory):
    directory = Path(directory)
    values, known = assets()
    expected_files = {'receipt.json','native-bin/tsjs-semantic-session'} | {'inputs/' + n for n in INPUTS} | {
        side + '/' + n for side in ['incremental','rebuild'] for n in ['transcript.jsonl','stdout.jsonl','stderr.bin','process.json']}
    paths, total = set(), 0
    for path in directory.rglob('*'):
        need(not path.is_symlink(), 'proof symlink refused')
        if not path.is_dir():
            need(path.is_file() and path.stat().st_size <= MAX_MEMBER, 'regular bounded proof file')
            total += path.stat().st_size; paths.add(path.relative_to(directory).as_posix())
    need(total <= MAX_TOTAL and paths in [expected_files, expected_files | {'verification.json'}], 'bounded exact proof closure')
    m = decode((directory / 'receipt.json').read_bytes())
    need(set(m) == {'schema','source_sha256','input_sha256','binary','environment','scope','strategy','normalization','admitted','competitive_runs_allowed','quota_event_credit','new_eligible_dossier','native_process_helper_frame_bytes'},
         'receipt exact field closure')
    need(m['schema'] == 'xrai.eval.tsjs-semantic-session-receipt.v1' and m['scope'] == PROFILE and m['strategy'] == STRATEGY and
         m['normalization'] == [] and m['admitted'] is False and m['competitive_runs_allowed'] is False and
         m['quota_event_credit'] is False and m['new_eligible_dossier'] is False and type(m['native_process_helper_frame_bytes']) is int and
         m['native_process_helper_frame_bytes'] == FRAME, 'receipt scope/nonadmission/transport')
    need(set(m['input_sha256']) == set(INPUTS) and set(m['source_sha256']) == set(SOURCES), 'frozen source/code binding set')
    for name, digest in m['input_sha256'].items():
        raw = (directory / 'inputs' / name).read_bytes()
        need(raw == (ASSETS / name).read_bytes() and sha(raw) == digest, 'consumed immutable frozen asset bytes')
    for name, digest in m['source_sha256'].items():
        need(sha((ROOT / name).read_bytes()) == digest, 'producer/verifier/helper/query/lock source changed')
    raw_binary = (directory / 'native-bin/tsjs-semantic-session').read_bytes()
    need(set(m['binary']) == {'path','sha256','bytes'} and m['binary']['path'] == 'native-bin/tsjs-semantic-session' and
         type(m['binary']['bytes']) is int and m['binary']['bytes'] == len(raw_binary) and sha(raw_binary) == m['binary']['sha256'] and
         raw_binary.startswith(b'\x7fELF') and 4096 <= len(raw_binary) <= MAX_MEMBER, 'retained consumed ELF byte identity')
    need(set(m['environment']) == {'platform','machine','github_sha','github_run_id'} and m['environment']['platform'].startswith('Linux-') and
         m['environment']['machine'] == 'x86_64' and re.fullmatch('[0-9a-f]{40}',m['environment']['github_sha']) and
         re.fullmatch('[1-9][0-9]*',m['environment']['github_run_id']), 'native environment profile (API authentication external)')
    a, b, invalid, p = [values[n] for n in ['input-a.json','input-b.json','input-invalid.json','protocol.json']]
    first_rows = (directory / 'incremental/transcript.jsonl').read_bytes().splitlines()
    need(len(first_rows) == 15 and all(first_rows), 'complete live operation sequence before decoding')
    first = decode(base64.b64decode(decode(first_rows[0])['response_base64'], validate=True))
    a_id = first['response']['snapshot_id']
    left, live, session = process(directory / 'incremental', requests(a,b,invalid,a_id,p['queries']))
    right, fresh, other = process(directory / 'rebuild', requests(a,b,invalid,a_id,p['queries'],fresh=True))
    need(left['pid'] != right['pid'] and session != other, 'independent rebuilt process and index')
    before = validate_snapshot(live[1]['response']['result'],a,known)
    after = validate_snapshot(live[10]['response']['result'],b,known)
    rebuilt = validate_snapshot(fresh[1]['response']['result'],b,known)
    need(same(before, live[6]['response']['result']) and same(before, live[8]['response']['result']), 'failed updates preserve full A snapshot')
    need(same(after, rebuilt) and same(after, known), 'full B equals independent B and prior accepted snapshot without normalization')
    for i, q in enumerate(p['queries']):
        for side, snapshot_value, row in [('before',before,live[2+i]),('after',after,live[11+i]),('after',rebuilt,fresh[2+i])]:
            result = row['response']['result']
            refs = [r for r in snapshot_value['references'] if r['evidence']['path'] == q['path'] and r['evidence']['start'] == q['offset']]
            need(len(refs) == 1, 'frozen query exact occurrence')
            reference = refs[0]
            need(same(result, {'kind':'lexical_reference','path':q['path'],'offset':q['offset'],'reference':reference}) and
                 type(result['offset']) is int, 'complete query equals current snapshot Reference')
            need(reference['resolution']['state'] == q[side + '_state'] and reference['callable']['state'] == q['callable'] and
                 reference['resolution']['target'] == q.get('target_' + side), 'frozen lexical/callable states and targets')
        need(same(live[11+i]['response']['result'],fresh[2+i]['response']['result']), 'full warmed B and fresh B query equality')
    return {'schema':'xrai.eval.tsjs-semantic-session-verified.v1','verified':True,'data_only':True,'same_process':True,'same_index':True,
            'full_B_snapshot_equal':True,'full_B_prior_accepted_equal':True,'failed_updates_preserve_full_A':True,
            'operations':15,'rebuild_operations':6,'queries':3,'changed_reference_expectations':1,'callable_targets_promoted':0,
            'normalization':[],'before_snapshot':before['snapshot_id'],'after_snapshot':after['snapshot_id'],
            'pid':left['pid'],'rebuild_pid':right['pid'],'session_id':session,'rebuild_session_id':other,
            'binary_sha256':m['binary']['sha256'],'protocol_sha256':m['input_sha256']['protocol.json'],
            'session_producer_fingerprint':producer(),'analysis_producer_fingerprint':after['producer_fingerprint'],
            'native_grammar_components':after['producer_components'],'native_grammar_matches_prior_accepted_snapshot':True,
            'code_commit':m['environment']['github_sha'],'run_id':m['environment']['github_run_id'],
            'file_sha256':{name:sha((directory/name).read_bytes()) for name in sorted(expected_files)},
            'admitted':False,'competitive_runs_allowed':False,'quota_event_credit':False,'new_eligible_dossier':False,
            'limits':['Controlled captured source availability; not upstream bug/history or new natural task.',
                      'Experimental exact-relative lexical references only; runtime callable always unknown.',
                      'Owned native execution is CI-only; historical recheck requires root authenticated API/ZIP.',
                      'Conservative full rebuild; no incremental cache performance claim.',
                      'Native grammar identity agrees with hash-pinned prior accepted native Snapshot; no grammar execution here.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs-only', '--design-only', action='store_true')
    parser.add_argument('--event', '--output', type=Path)
    args = parser.parse_args()
    if args.inputs_only:
        v,k = assets(); result = {'verified':True,'data_only':True,'queries':len(v['protocol.json']['queries']),'native_executed':False}
    elif args.event:
        result = verify(args.event)
    else:
        parser.error('--inputs-only or --event required')
    print(json.dumps(result,sort_keys=True,indent=2))
