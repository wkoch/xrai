"""Prospective measurement protocol only; fixed ranking and immutable L5 inputs."""
from hashlib import sha256
import datetime
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
LEXICAL=ROOT/'eval/context/lexical'
LOG=ROOT/'docs/relatorios/logs/L5-C05/lexical-tokens'
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
from offline_measurement import canonical, SERIALIZER


def sha(raw):return sha256(raw).hexdigest()


def profile_expected():
    config=json.loads((ROOT/'crates/xrai-eval/harness/tokenizer-assets/cl100k-config.json').read_bytes())
    p={'config':config,'config_sha256':sha(canonical(config)),'serializer':SERIALIZER,'serializer_sha256':sha(canonical(SERIALIZER))}
    p['fingerprint_sha256']=sha(canonical(p));return p


def pin_inputs():
    manifest=json.loads((LEXICAL/'manifest.json').read_bytes())
    names=['eval/context/lexical/'+n for n in ('manifest.json','queries.json','expected-labels.json','protocol.json','matrix.json','freeze_inputs.py')]
    names += ['eval/context/lexical/'+m['asset'] for unit in manifest['universes'] for m in unit['files'].values()]
    names += ['crates/xrai-eval/harness/'+n for n in ('lexical_retrieval.py','offline_measurement.py','runner.py','requirements-measurement.txt','tokenizer-assets/cl100k-config.json','tokenizer-assets/cl100k_base.tiktoken')]
    names += ['eval/context/measure_wire.py','docs/relatorios/L5-LEXICAL-REVISAO.md','docs/relatorios/logs/L5-C04/lexical/review-independent.json','docs/relatorios/logs/L5-C04/lexical/benchmark.json','docs/relatorios/logs/L5-C04/lexical/freeze-before-algorithm.json']
    return {n:sha((ROOT/n).read_bytes()) for n in sorted(names)}


def build():
    protocol={'schema':'xrai.eval.lexical-token.protocol.v1','hypothesis':'Measure complete controlled response-wire budget effects on the fixed lexical producer; no ranking redesign or third ranking alternative.',
        'methods':['bm25','tfidf_cosine'],'controlled_token_ceilings':[2000,4000,8000,16000,32000],'repetitions':2,
        'top_k':5,'original_byte_ceiling':65536,'controlled_wire_byte_ceiling':65536,
        'search_selection':'rank-order greedy, whole original chunks only; skip oversized chunk and try later ranks; original ranks preserved; no oracle or evaluator data enters selection',
        'expansion_selection':'full captured files deduplicated by original index, all-or-none; original producer byte refusal and controlled wrapper byte/token refusal kept distinct',
        'wrapper_schema':'lexical-token-delivery.v1','measurement_schema':'lexical-token-sidecar.v1','profile':profile_expected(),
        'fixed_point_iterations':32,'fixed_point_cycle_policy':'fail closed, preserve incident, no tuning to avoid cycles',
        'operation_bounds':{'query_utf8_bytes':16384,'expansion_handles':5,'handle_lowercase_hex_chars':64,'token_ceiling_max':1000000},
        'evaluation_metrics':['file_hit','anchor_covered','same_file_nonanchor_chunks','declared_distractor_file_chunks','unannotated_other_file_chunks','delivered_chunks','controlled_wire_tokens','controlled_request_projection_tokens','original_candidate_chunks','chunks_omitted_by_controlled_limits'],
        'annotations':{'RS-03':'EOF of stdout/stderr versus child.wait() in adjacent function; no behaviour proof','GO-02':'file URL conversion target valid, invalid-authority clause unsupported; do not infer clause correctness'},
        'provider_usage':None,'provider_charge':None,'latency':None,
        'scope':'Whole canonical controlled response wrapper, including budget counters/candidate IDs/omissions/hash metadata/snippets. Initial owned request projection measured separately; actual provider schema, orientation, prompts and billing unknown.',
        'legacy_preservation':'Original lexical-delivery.v1 retained byte-for-byte as sidecar original_delivery with model_tokens=null. New selected wrapper uses its own schema, never impersonates legacy envelope.',
        'candidate_scope':'Original top5 and 65536-byte ceiling remain; 32k token allowance does not increase original candidates.',
        'no_gate':True,'semantic_precision':None,'experimental_versions':'This is measurement v1 over fixed existing BM25/TFIDF alternatives; no second redesigned ranking version.'}
    manifest=json.loads((LEXICAL/'manifest.json').read_bytes());sources={u['family']:u['files'] for u in manifest['universes']}
    paths={'Rust':['crates/stdx/src/anymap.rs','crates/stdx/src/non_empty_vec.rs'],
           'TSJS':['packages/react/src/BadMapPolyfill.js','packages/react/src/ReactMemo.js'],
           'Python':['sklearn/metrics/cluster/_bicluster.py','sklearn/metrics/cluster/_supervised.py'],
           'Go':['modules/util/color.go','modules/util/sec_to_time.go']}
    queries=json.loads((LEXICAL/'queries.json').read_bytes())
    labels=json.loads((LEXICAL/'expected-labels.json').read_bytes())['labels'];by={l['query_id']:l for l in labels}
    distractors={'schema':'xrai.eval.lexical-token.external-rubric.v1','author':'implementer/e02_allocation',
        'scope':'Declared non-target files for exact declaration-location only; not exhaustive relevance or semantic distractor labels. Original ranking/results already visible before this measurement; not blind/holdout.',
        'selection_use':'Never consumed by the retriever or budget selection; evaluator reads after all controlled deliveries.',
        'entries':[{'query_id':q['query_id'],'family':q['family'],'target_label_unchanged':by[q['query_id']],
            'declared_distractor_paths':[{'path':p,'source_sha256':sources[q['family']][p]['sha256']} for p in paths[q['family']]],
            'rationale':'Distinct declared functions/utilities from named target; other paths remain unannotated, never automatically false positives.'} for q in queries]}
    matrix=[{'order':i,'query_id':q['query_id'],'family':q['family'],'method':method,'controlled_token_ceiling':budget,'repetition':rep} for i,(q,method,budget,rep) in enumerate((q,m,b,r) for q in queries for m in protocol['methods'] for b in protocol['controlled_token_ceilings'] for r in range(protocol['repetitions']))]
    return {'protocol.json':protocol,'external-rubric.json':distractors,'matrix.json':matrix}


def verify():
    receipt=json.loads((LOG/'freeze-before-driver.json').read_bytes())
    if receipt['driver_existed'] or receipt['results_existed']:raise ValueError('freeze did not precede new driver/results')
    for path,digest in receipt['original_input_sha256'].items():
        p=ROOT/path
        if not p.is_file() or p.is_symlink() or sha(p.read_bytes())!=digest:raise ValueError('immutable input changed: '+path)
    if pin_inputs()!=receipt['original_input_sha256']:raise ValueError('input source closure changed')
    for path,digest in receipt['prospective_sha256'].items():
        if sha((HERE/path).read_bytes())!=digest:raise ValueError('prospective protocol/rubric/matrix changed')
    if sha(Path(__file__).read_bytes())!=receipt['freezer_sha256']:raise ValueError('freeze source changed')
    return receipt


def freeze():
    if (HERE/'driver.py').exists() or (LOG/'results.json').exists() or (LOG/'freeze-before-driver.json').exists():raise ValueError('refuse freeze after driver/results or replacement receipt')
    prospective=build()
    for name,value in prospective.items(): (HERE/name).write_bytes(canonical(value)+b'\n')
    receipt={'schema':'xrai.eval.lexical-token.prospective-freeze.v1','frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'driver_existed':False,'results_existed':False,
        'original_input_sha256':pin_inputs(),'prospective_sha256':{p:sha((HERE/p).read_bytes()) for p in prospective},'freezer_sha256':sha(Path(__file__).read_bytes()),'measured_tokens':False,'native_execution':False,'new_downloads':0}
    (LOG/'freeze-before-driver.json').write_bytes(canonical(receipt)+b'\n');print(json.dumps(verify(),indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['freeze','verify']);args=parser.parse_args()
    freeze() if args.action=='freeze' else print(json.dumps(verify(),indent=2))
