"""Controlled response-token measurement over the fixed lexical producer.

No label/oracle inputs in selection, no ranking redesign, provider, native or
upstream execution. Synthetic counter injection is explicit and test-only.
"""
from copy import deepcopy
import base64
from hashlib import sha256
import json
from pathlib import Path
import os
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
from lexical_retrieval import LexicalIndex
from offline_measurement import canonical, tokenizer
import freeze

MAX_ARTIFACT_BYTES=64*1024*1024
MAX_RECORD_BYTES=512*1024


def sha(raw):return sha256(raw).hexdigest()


def need(value,message):
    if not value:raise ValueError(message)


def integer(value,low,high):return type(value) is int and low<=value<=high


def source_bindings():
    names=[str((HERE/n).relative_to(ROOT)) for n in ('freeze.py','protocol.json','external-rubric.json','matrix.json','driver.py','verifier.py')]
    names+=['.github/workflows/l5-lexical-token.yml','crates/xrai-eval/harness/tests/test_lexical_tokens.py','docs/contracts/examples/requirements.txt']
    return {p:sha((ROOT/p).read_bytes()) for p in names}


def protocol():return json.loads((HERE/'protocol.json').read_bytes())


class LexicalTokenDelivery:
    def __init__(self,index,encoding,profile,config,*,synthetic_test_mode=False):
        need(type(synthetic_test_mode) is bool,'typed synthetic-test flag')
        need(profile==config['profile'],'exact fixed L4 profile')
        if not synthetic_test_mode:need(encoding.name==profile['config']['name'],'configured L4 encoding')
        else:need(encoding.name.startswith('synthetic-test-'),'explicitly named synthetic own-test counter')
        self.index=index;self.encoding=encoding;self.profile=deepcopy(profile)
        # Only selection-policy scalars enter the selector; annotations/rubric/matrix stay outside.
        keys=('methods','top_k','original_byte_ceiling','controlled_wire_byte_ceiling','fixed_point_iterations','operation_bounds','search_selection','expansion_selection')
        self.config={k:deepcopy(config[k]) for k in keys};self.synthetic=synthetic_test_mode
        self.profile_id=('synthetic-test:'+encoding.name) if synthetic_test_mode else 'l4:'+profile['fingerprint_sha256']

    def _ids(self,raw):
        return self.encoding.encode(raw.decode('utf-8'),allowed_special=set(),disallowed_special=())

    def _count(self,wire):
        seen=set()
        for _ in range(self.config['fixed_point_iterations']):
            raw=canonical(wire);ids=self._ids(raw);state=(len(raw),len(ids))
            if wire['budget']['wire_bytes']==state[0] and wire['budget']['controlled_wire_tokens']==state[1]:return raw,ids
            need(state not in seen,'controlled whole-wrapper count fixed-point cycle; fail closed')
            seen.add(state);wire['budget']['wire_bytes'],wire['budget']['controlled_wire_tokens']=state
        raise ValueError('controlled whole-wrapper count did not converge; fail closed')

    def _fits(self,raw,ids,ceiling):
        return len(raw)<=self.config['controlled_wire_byte_ceiling'] and len(ids)<=ceiling

    def _validate_ceiling(self,ceiling):
        need(integer(ceiling,1,self.config['operation_bounds']['token_ceiling_max']),'integer controlled token ceiling, bool forbidden')

    def _wire(self,original,operation,ceiling,ids,request):
        return {'schema':'lexical-token-delivery.v1',
            'producer':{'snapshot_id':self.index.snapshot_id,'configuration_id':self.index.configuration_id,
                'lexical_producer_sha256':self.index.producer_sha256,'wrapper_producer_sha256':sha(Path(__file__).read_bytes()),
                'original_delivery_sha256':sha(canonical(original)) if original is not None else None,
                'original_delivery_wire_bytes':original['wire_bytes'] if original is not None else None},
            'operation':operation,'request':request,'status':'controlled_limits_refusal' if ids else 'no_match_captured_scope',
            'selection':{'policy':self.config['search_selection'] if operation=='search' else self.config['expansion_selection'],
                'candidate_ids':list(ids),'delivered_ids':[],
                'omitted':[{'id':handle,'reason':'whole_item_not_admitted_under_controlled_limits'} for handle in ids]},
            'snippets':[],'coverage':deepcopy(original['coverage']) if original is not None else {
                'captured_scope_only':True,'whole_repository':False,'parse_status':'unknown','semantic_status':'unknown'},
            'model_tokens':None,
            'budget':{'profile':self.profile_id,'counting':'synthetic-test-units-not-tokens' if self.synthetic else 'exact-controlled-response-wire',
                'controlled_wire_tokens':0,'wire_bytes':0,'controlled_token_ceiling':ceiling,
                'controlled_wire_byte_ceiling':self.config['controlled_wire_byte_ceiling'],
                'original_retriever_byte_ceiling':self.config['original_byte_ceiling'],
                'provider_tokens':None,'provider_charge':None}}

    def _sidecar(self,wire,original,request,checks):
        raw,ids=self._count(wire);request_raw=canonical(request);request_ids=self._ids(request_raw)
        return {'schema':'lexical-token-sidecar.v1','synthetic_test_mode':self.synthetic,
            'profile':deepcopy(self.profile),'serialized_base64':base64.b64encode(raw).decode(),
            'serialized_sha256':sha(raw),'serialized_bytes':len(raw),'controlled_wire_tokens':len(ids),
            'token_ids_sha256':sha(canonical(ids)),'original_delivery':deepcopy(original),
            'original_delivery_controlled_tokens':len(self._ids(canonical(original))) if original is not None else None,
            'request_projection':deepcopy(request),'request_serialized_base64':base64.b64encode(request_raw).decode(),
            'controlled_request_projection_tokens':len(request_ids),'request_token_ids_sha256':sha(canonical(request_ids)),
            'omission_checks':checks,'provider_tokens':None,'provider_charge':None,
            'scope':'synthetic own-test units; never L4 token evidence' if self.synthetic else 'controlled own response wire; initial own request projection separate; provider schema/orientation/prompts/billing unknown'}

    def search(self,query,*,method='bm25',controlled_token_ceiling=2000):
        self._validate_ceiling(controlled_token_ceiling)
        need(isinstance(query,str) and len(query.encode())<=self.config['operation_bounds']['query_utf8_bytes'],'bounded query text')
        need(method in self.config['methods'],'fixed lexical method')
        original=self.index.search(query,method=method,top_k=self.config['top_k'],max_wire_bytes=self.config['original_byte_ceiling'])
        request={'operation':'search','query':query,'query_sha256':sha(query.encode()),'method':method,'top_k':self.config['top_k'],
            'controlled_token_ceiling':controlled_token_ceiling,'original_byte_ceiling':self.config['original_byte_ceiling']}
        candidate_ids=[s['id'] for s in original['snippets']]
        wire=self._wire(original,'search',controlled_token_ceiling,candidate_ids,request);checks=[]
        raw,units=self._count(wire);need(self._fits(raw,units,controlled_token_ceiling),'controlled limit cannot hold complete metadata/refusal; fail closed')
        for candidate in original['snippets']:
            proposed=deepcopy(wire);proposed['snippets'].append(deepcopy(candidate))
            proposed['selection']['delivered_ids'].append(candidate['id'])
            proposed['selection']['omitted']=[v for v in proposed['selection']['omitted'] if v['id']!=candidate['id']]
            proposed['status']='delivered'
            raw,units=self._count(proposed);fits=self._fits(raw,units,controlled_token_ceiling)
            checks.append({'id':candidate['id'],'proposed_controlled_wire_tokens':len(units),'proposed_wire_bytes':len(raw),
                'within_token_ceiling':len(units)<=controlled_token_ceiling,'within_byte_ceiling':len(raw)<=self.config['controlled_wire_byte_ceiling'],'admitted':fits})
            if fits:wire=proposed
        raw,units=self._count(wire);need(self._fits(raw,units,controlled_token_ceiling),'final complete response exceeds controlled ceiling')
        return {'wire':wire,'sidecar':self._sidecar(wire,original,request,checks)}

    def expand(self,handles,*,controlled_token_ceiling=2000):
        self._validate_ceiling(controlled_token_ceiling)
        need(type(handles) is list and len(handles)<=self.config['operation_bounds']['expansion_handles'],'bounded handle list')
        need(all(type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v) for v in handles),'exact lowercase SHA handle shape')
        need(len(set(handles))==len(handles),'distinct expansion handles')
        request={'operation':'expand','handles':list(handles),'controlled_token_ceiling':controlled_token_ceiling,
            'original_byte_ceiling':self.config['original_byte_ceiling']}
        original=self.index.expand(handles,max_wire_bytes=self.config['original_byte_ceiling']) if handles else None
        wire=self._wire(original,'expand',controlled_token_ceiling,handles,request);checks=[]
        if original is None:wire['status']='not_requested_no_delivered_handles';wire['selection']['omitted']=[]
        elif original['status']!='expanded_full_captured_files':
            wire['status']='original_byte_ceiling_refusal' if original['status']=='insufficient_byte_budget' else 'original_handle_refusal'
            wire['selection']['omitted']=[{'id':v,'reason':'original_producer_refused'} for v in handles]
        else:
            proposed=deepcopy(wire);proposed['snippets']=deepcopy(original['snippets'])
            proposed['selection']['delivered_ids']=list(handles);proposed['selection']['omitted']=[];proposed['status']='expanded_full_captured_files'
            raw,units=self._count(proposed);fits=self._fits(raw,units,controlled_token_ceiling)
            checks.append({'requested_ids':list(handles),'proposed_controlled_wire_tokens':len(units),'proposed_wire_bytes':len(raw),
                'within_token_ceiling':len(units)<=controlled_token_ceiling,'within_byte_ceiling':len(raw)<=self.config['controlled_wire_byte_ceiling'],'admitted':fits})
            if fits:wire=proposed
            else:
                wire['status']='controlled_byte_ceiling_refusal' if len(raw)>self.config['controlled_wire_byte_ceiling'] else 'controlled_token_ceiling_refusal'
        raw,units=self._count(wire);need(self._fits(raw,units,controlled_token_ceiling),'complete expansion/refusal metadata exceeds controlled ceiling; fail closed')
        return {'wire':wire,'sidecar':self._sidecar(wire,original,request,checks)}


def load_indexes(encoding,profile,config):
    manifest=json.loads((ROOT/'eval/context/lexical/manifest.json').read_bytes())
    old=json.loads((ROOT/'eval/context/lexical/protocol.json').read_bytes());result={}
    for unit in manifest['universes']:
        files={p:(ROOT/'eval/context/lexical'/v['asset']).read_bytes() for p,v in unit['files'].items()}
        index=LexicalIndex(files,**{k:old[k] for k in ('chunk_lines','overlap_lines','path_term_weight','k1','b')})
        result[unit['family']]=LexicalTokenDelivery(index,encoding,profile,config)
    return result


def baseline_rows(deliveries,queries,config):
    rows=[]
    for q in queries:
        for method in config['methods']:
            d=deliveries[q['family']];original=d.index.search(q['query'],method=method,top_k=config['top_k'],max_wire_bytes=config['original_byte_ceiling'])
            raw=canonical(original);ids=d._ids(raw)
            rows.append({'query_id':q['query_id'],'family':q['family'],'method':method,'original_delivery':original,
                'serialized_sha256':sha(raw),'serialized_bytes':len(raw),'controlled_original_response_tokens':len(ids),
                'token_ids_sha256':sha(canonical(ids)),'legacy_model_tokens':None})
    return rows


def compute_records(deliveries,queries,matrix):
    by_id={q['query_id']:q for q in queries};rows=[]
    for item in matrix:
        q=by_id[item['query_id']];need(q['family']==item['family'],'frozen family/query pairing')
        d=deliveries[q['family']];search=d.search(q['query'],method=item['method'],controlled_token_ceiling=item['controlled_token_ceiling'])
        expansion=d.expand(search['wire']['selection']['delivered_ids'],controlled_token_ceiling=item['controlled_token_ceiling'])
        rows.append({'matrix':item,'search':search,'expansion':expansion})
    return rows


def evaluate(rows):
    """External evaluator; labels loaded only after deliveries are already selected."""
    rubric=json.loads((HERE/'external-rubric.json').read_bytes());labels={v['query_id']:v for v in rubric['entries']}
    result=[]
    for row in rows:
        item=row['matrix'];label=labels[item['query_id']];target=label['target_label_unchanged'];dist={v['path'] for v in label['declared_distractor_paths']}
        for op in ('search','expansion'):
            wire=row[op]['wire'];snippets=wire['snippets'];path=target['relevant_path'];anchor=target['anchor']
            result.append({**item,'operation':op,'status':wire['status'],
                'file_hit':any(s['path']==path for s in snippets) if path else None,
                'anchor_covered':any(s['path']==path and s['start']<=anchor['start'] and s['end']>=anchor['end'] for s in snippets) if anchor else None,
                'negative_empty':not snippets if path is None else None,
                'same_file_nonanchor_chunks':sum(s['path']==path and not(s['start']<=anchor['start'] and s['end']>=anchor['end']) for s in snippets) if anchor else 0,
                'declared_distractor_file_chunks':sum(s['path'] in dist for s in snippets),
                'unannotated_other_file_chunks':sum(s['path']!=path and s['path'] not in dist for s in snippets),
                'delivered_chunks':len(snippets),'original_candidate_chunks':len(row[op]['sidecar']['original_delivery']['snippets']) if row[op]['sidecar']['original_delivery'] else 0,
                'chunks_omitted_by_controlled_limits':len(row[op]['sidecar']['original_delivery']['snippets'])-len(snippets) if row[op]['sidecar']['original_delivery'] and row[op]['sidecar']['original_delivery']['status'] in ('lexical_matches','expanded_full_captured_files') else 0,
                'controlled_wire_tokens':wire['budget']['controlled_wire_tokens'],
                'controlled_request_projection_tokens':row[op]['sidecar']['controlled_request_projection_tokens'],
                'wire_bytes':wire['budget']['wire_bytes'],'annotation':protocol()['annotations'].get(item['query_id'])})
    return {'schema':'xrai.eval.lexical-token.evaluation.v1','records':result,'semantic_precision':None,
        'limits':['fixed original labels including GO-02/RS-03 caveats; no relabel/denominator removal',
            'declared distractor paths incomplete; other paths unknown relevance',
            'controlled response wire only; provider orientation/schema/prompts/billing unknown',
            'original top5/65536-byte candidates remain fixed']}


def write(path,value):
    raw=canonical(value)+b'\n';need(len(raw)<=MAX_RECORD_BYTES,'record byte bound');path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(raw)


def run(output):
    receipt=freeze.verify();config=protocol();encoding,profile=tokenizer();need(profile==config['profile'],'actual pinned L4 profile')
    output=Path(output);need(not output.exists(),'fresh measurement output');output.mkdir(parents=True)
    queries=json.loads((ROOT/'eval/context/lexical/queries.json').read_bytes());matrix=json.loads((HERE/'matrix.json').read_bytes())
    metadata={'schema':'xrai.eval.lexical-token.preregistration.v1','profile':profile,
        'original_input_sha256':receipt['original_input_sha256'],'prospective_sha256':receipt['prospective_sha256'],'source_sha256':source_bindings(),
        'environment':{'repository':os.environ.get('GITHUB_REPOSITORY'),'head_sha':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT')},
        'provider_tokens':None,'provider_charge':None,'synthetic_test_mode':False,'matrix_cells':len(matrix)}
    write(output/'preregistered.json',metadata);deliveries=load_indexes(encoding,profile,config)
    baselines=baseline_rows(deliveries,queries,config)
    for i,row in enumerate(baselines):write(output/f'baselines/{i:03}.json',row)
    rows=compute_records(deliveries,queries,matrix)
    for row in rows:write(output/f'records/{row["matrix"]["order"]:03}.json',row)
    write(output/'evaluation.json',evaluate(rows))
    need(sum(p.stat().st_size for p in output.rglob('*') if p.is_file())<=MAX_ARTIFACT_BYTES,'measurement artifact byte bound')
    need(freeze.verify()==receipt,'frozen sources unchanged after measurement')
    from verifier import verify
    return verify(output)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:
        print(json.dumps(run(args.output),indent=2,sort_keys=True))
    except Exception as error:
        if args.output.is_dir() and not (args.output/'incident.json').exists():
            write(args.output/'incident.json',{'schema':'xrai.eval.lexical-token.fail-closed-incident.v1','verified':False,'error_type':type(error).__name__,'error':str(error),'provider_tokens':None,'provider_charge':None})
        raise
