"""Frozen scripted retrieval evaluation, never an agent/provider benchmark."""
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'crates/xrai-eval/harness'))
from lexical_retrieval import LexicalIndex, wire_bytes
import freeze_inputs


def load_inputs():
    checked = freeze_inputs.verify()
    receipt = json.loads((ROOT/'docs/relatorios/logs/L5-C04/lexical/freeze-before-algorithm.json').read_bytes())
    if checked != receipt['inputs'] or receipt['retriever_source_existed'] or receipt['results_existed']:
        raise ValueError('input freeze receipt mismatch')
    manifest = json.loads((HERE/'manifest.json').read_bytes())
    protocol = json.loads((HERE/'protocol.json').read_bytes())
    indexes = {}
    for unit in manifest['universes']:
        files = {}
        for path, meta in unit['files'].items():
            raw = (HERE/meta['asset']).read_bytes()
            if len(raw) != meta['bytes'] or sha256(raw).hexdigest() != meta['sha256']:
                raise ValueError('captured source mismatch')
            files[path] = raw
        indexes[unit['family']] = LexicalIndex(files, **{k:protocol[k] for k in
            ('chunk_lines','overlap_lines','path_term_weight','k1','b')})
    return indexes, manifest, protocol, checked


def run():
    indexes, manifest, protocol, checked = load_inputs()
    queries = {q['query_id']:q for q in json.loads((HERE/'queries.json').read_bytes())}
    matrix = json.loads((HERE/'matrix.json').read_bytes())
    records = []
    for row in matrix:
        q = queries[row['query_id']]
        if q['family'] != row['family']: raise ValueError('matrix family mismatch')
        output = indexes[row['family']].search(q['query'], method=row['method'],
            top_k=protocol['top_k'],max_wire_bytes=protocol['max_wire_bytes'])
        for snippet in output['snippets']:
            source = indexes[row['family']]._files[snippet['path']]
            if source[snippet['start']:snippet['end']] != snippet['text'].encode() or sha256(snippet['text'].encode()).hexdigest() != snippet['snippet_sha256']:
                raise ValueError('retrieved bytes mismatch')
        if output['wire_bytes'] != len(wire_bytes(output)) or output['wire_bytes'] > protocol['max_wire_bytes']:
            raise ValueError('whole-envelope byte budget violated')
        records.append({**row,'output':output})
    # Labels enter only after all method outputs have been collected.
    labels = {v['query_id']:v for v in json.loads((HERE/'expected-labels.json').read_bytes())['labels']}
    metrics = defaultdict(list)
    repetition_checks = {}
    for record in records:
        label = labels[record['query_id']]
        output = record['output']
        key = (record['query_id'],record['method'])
        serialized = wire_bytes(output)
        if key in repetition_checks and repetition_checks[key] != serialized:
            raise ValueError('repetition changed retrieval output')
        repetition_checks[key] = serialized
        snippets = output['snippets']
        if label['relevant_path'] is None:
            result = {'negative_empty':int(not snippets)}
        else:
            ranks = [s['rank'] for s in snippets if s['path']==label['relevant_path']]
            rank = min(ranks) if ranks else 0
            a = label['anchor']
            result = {**{f'file_hit_at_{k}':int(bool(rank) and rank<=k) for k in (1,3,5)},
                'file_reciprocal_rank':1/rank if rank else 0,
                'anchor_covered_at_5':int(any(s['path']==label['relevant_path'] and s['start']<=a['start'] and s['end']>=a['end'] for s in snippets))}
        record['evaluation'] = result
        for name,value in result.items():
            for scope in ('all', record['family']): metrics[(record['method'],scope,name)].append(value)
    aggregated = [{'method':method,'scope':scope,'metric':name,'sum':sum(values),'n':len(values),'mean':sum(values)/len(values)}
        for (method,scope,name),values in sorted(metrics.items())]
    if freeze_inputs.verify() != checked: raise ValueError('frozen inputs changed during run')
    return {'schema':'xrai.eval.lexical.scripted-results.v1','data_only':True,
        'execution_mode':'scripted_retrieval','records':records,'metrics':aggregated,
        'frozen_input_sha256':checked['artifact_sha256'],
        'producer_sha256':indexes['Rust'].producer_sha256,
        'benchmark_source_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
        'snapshots':{f:{'snapshot_id':x.snapshot_id,'configuration_id':x.configuration_id,
            'files':len(x._files),'bytes':sum(map(len,x._files.values())),'chunks':len(x._chunks)} for f,x in indexes.items()},
        'deterministic_repetitions_verified':True,'model_tokens':None,'provider':None,
        'tokenizer':None,'agent_success':None,'latency':None,'financial_cost':None,
        'limits':['captured subtree only','labels by implementer; independent review pending',
                  'no semantic recall/precision, repository completeness, performance or agent-success claims']}


if __name__ == '__main__':
    print(json.dumps(run(),ensure_ascii=False,sort_keys=True,indent=2))
