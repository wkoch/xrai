"""Replay all controlled lexical-token deliveries as own data; no native/provider."""
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import driver
import freeze


def decode(raw):
    def pairs(values):
        result={}
        for k,v in values:
            driver.need(k not in result,'duplicate JSON key');result[k]=v
        return result
    def reject(value):raise ValueError('nonfinite JSON: '+value)
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=reject)


def same(a,b):return driver.canonical(a)==driver.canonical(b)


def read(path):
    driver.need(path.is_file() and not path.is_symlink() and path.stat().st_size<=driver.MAX_RECORD_BYTES,'bounded ordinary measurement record')
    return decode(path.read_bytes())


def design():
    receipt=freeze.verify();config=driver.protocol()
    driver.need(config['profile']==freeze.profile_expected(),'fixed configured L4 profile')
    return {'schema':'xrai.eval.lexical-token.design-verification.v1','verified':True,'data_only':True,
        'tokenizer_measured':False,'profile_fingerprint':config['profile']['fingerprint_sha256'],
        'source_inputs':len(receipt['original_input_sha256']),'matrix_cells':len(read(HERE/'matrix.json')),
        'controlled_token_ceilings':config['controlled_token_ceilings'],'provider_tokens':None,'provider_charge':None}


def validate_delivery(result,delivery):
    driver.need(same(result,delivery),'whole wrapper/sidecar/profile/tokens/source/selection differs from deterministic replay')
    wire=result['wire'];sidecar=result['sidecar']
    driver.need(sidecar['synthetic_test_mode'] is False and wire['budget']['counting']=='exact-controlled-response-wire','synthetic units cannot be promoted to measured tokens')
    driver.need(type(wire['budget']['controlled_wire_tokens']) is int and type(wire['budget']['wire_bytes']) is int,'typed actual counts')
    driver.need(wire['budget']['controlled_wire_tokens']<=wire['budget']['controlled_token_ceiling'] and wire['budget']['wire_bytes']<=wire['budget']['controlled_wire_byte_ceiling'],'whole wrapper exceeds controlled limits')
    driver.need(wire['model_tokens'] is None and wire['budget']['provider_tokens'] is None and wire['budget']['provider_charge'] is None,'provider quantities remain unknown')
    if sidecar['original_delivery'] is not None:driver.need(sidecar['original_delivery']['model_tokens'] is None,'legacy model_tokens unchanged')


def curves(evaluation):
    groups=defaultdict(list)
    for row in evaluation['records']:groups[(row['method'],row['controlled_token_ceiling'],row['operation'])].append(row)
    result=[]
    for (method,budget,operation),rows in sorted(groups.items()):
        positives=[r for r in rows if r['file_hit'] is not None];negative=[r for r in rows if r['negative_empty'] is not None]
        result.append({'method':method,'controlled_token_ceiling':budget,'operation':operation,
            'records':len(rows),'positive_records':len(positives),'negative_records':len(negative),
            'file_hits':sum(r['file_hit'] for r in positives),'anchors_covered':sum(r['anchor_covered'] for r in positives),
            'negative_empty':sum(r['negative_empty'] for r in negative),'status_counts':dict(sorted(Counter(r['status'] for r in rows).items())),
            **{name:sum(r[name] for r in rows) for name in ('delivered_chunks','same_file_nonanchor_chunks','declared_distractor_file_chunks','unannotated_other_file_chunks','original_candidate_chunks','chunks_omitted_by_controlled_limits')},
            'controlled_wire_tokens_sum':sum(r['controlled_wire_tokens'] for r in rows),
            'controlled_wire_tokens_min':min(r['controlled_wire_tokens'] for r in rows),'controlled_wire_tokens_max':max(r['controlled_wire_tokens'] for r in rows),
            'controlled_request_projection_tokens_sum':sum(r['controlled_request_projection_tokens'] for r in rows),
            'wire_bytes_sum':sum(r['wire_bytes'] for r in rows)})
    return result


def verify(output):
    receipt=freeze.verify();config=driver.protocol();encoding,profile=driver.tokenizer()
    driver.need(same(profile,config['profile']),'actual tokenizer profile differs from prospective protocol')
    output=Path(output);driver.need(output.is_dir() and not output.is_symlink(),'ordinary measurement output directory')
    expected_files={'preregistered.json','evaluation.json'}|{f'baselines/{i:03}.json' for i in range(32)}|{f'records/{i:03}.json' for i in range(320)}
    actual=set();directories=set();total=0
    for path in output.rglob('*'):
        driver.need(not path.is_symlink(),'measurement output symlink')
        rel=path.relative_to(output).as_posix()
        if path.is_dir():directories.add(rel);continue
        driver.need(path.is_file() and path.stat().st_size<=driver.MAX_RECORD_BYTES,'ordinary bounded artifact file')
        actual.add(rel);total+=path.stat().st_size
    driver.need(actual==expected_files and directories=={'baselines','records'} and total<=driver.MAX_ARTIFACT_BYTES,'exact bounded measurement file closure')
    metadata=read(output/'preregistered.json')
    driver.need(set(metadata)=={'schema','profile','original_input_sha256','prospective_sha256','source_sha256','environment','provider_tokens','provider_charge','synthetic_test_mode','matrix_cells'},'typed metadata closure')
    driver.need(metadata['schema']=='xrai.eval.lexical-token.preregistration.v1' and same(metadata['profile'],profile) and
        same(metadata['original_input_sha256'],receipt['original_input_sha256']) and same(metadata['prospective_sha256'],receipt['prospective_sha256']) and
        same(metadata['source_sha256'],driver.source_bindings()),'actual fixed code/profile/protocol/original input binding')
    driver.need(metadata['synthetic_test_mode'] is False and type(metadata['matrix_cells']) is int and metadata['matrix_cells']==320 and
        metadata['provider_tokens'] is None and metadata['provider_charge'] is None,'actual measurement boundary, no provider quantities')
    driver.need(set(metadata['environment'])=={'repository','head_sha','run_id','run_attempt'} and all(v is None or type(v) is str for v in metadata['environment'].values()),'raw caller execution environment, authentication belongs to CI reconciler')
    queries=read(driver.ROOT/'eval/context/lexical/queries.json');matrix=read(HERE/'matrix.json')
    deliveries=driver.load_indexes(encoding,profile,config);baselines=driver.baseline_rows(deliveries,queries,config)
    for i,row in enumerate(baselines):driver.need(same(read(output/f'baselines/{i:03}.json'),row),'original immutable baseline/source/token count differs')
    expected=driver.compute_records(deliveries,queries,matrix);retained=[];seen={}
    for row in expected:
        supplied=read(output/f'records/{row["matrix"]["order"]:03}.json')
        driver.need(set(supplied)=={'matrix','search','expansion'} and same(supplied['matrix'],row['matrix']),'exact source/method/budget/repetition/order matrix')
        for operation in ('search','expansion'):validate_delivery(supplied[operation],row[operation])
        key=(row['matrix']['query_id'],row['matrix']['method'],row['matrix']['controlled_token_ceiling'])
        response={'search':supplied['search'],'expansion':supplied['expansion']}
        if key in seen:driver.need(same(seen[key],response),'deterministic repetition changed')
        seen[key]=response;retained.append(supplied)
    evaluation=driver.evaluate(retained);driver.need(same(read(output/'evaluation.json'),evaluation),'external file/anchor/distractor/rubric evaluation differs')
    driver.need(freeze.verify()==receipt,'original inputs altered by measurement/replay')
    return {'schema':'xrai.eval.lexical-token.verification.v1','verified':True,'data_only':True,'tokenizer_measured':True,
        'controlled_profile':'l4:'+profile['fingerprint_sha256'],'matrix_cells':320,'search_and_expansion_deliveries':640,'baselines':32,
        'artifact_files':len(actual),'artifact_bytes':total,'curves':curves(evaluation),
        'baseline_controlled_tokens_min':min(r['controlled_original_response_tokens'] for r in baselines),
        'baseline_controlled_tokens_max':max(r['controlled_original_response_tokens'] for r in baselines),
        'source_sha256':driver.source_bindings(),'original_input_sha256':receipt['original_input_sha256'],
        'provider_tokens':None,'provider_charge':None,'semantic_precision':None,'agent_success':None,
        'ranking_redesigned':False,'global_admission':False,'limits':evaluation['limits']}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output',type=Path);group.add_argument('--design-only',action='store_true');args=parser.parse_args()
    print(json.dumps(design() if args.design_only else verify(args.output),indent=2,sort_keys=True))
