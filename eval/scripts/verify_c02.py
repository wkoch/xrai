#!/usr/bin/env python3
"""C02 factual dossier reconciliation, without admitting a competitive dataset.

Only evaluator code/data are loaded. Captured upstream trees and historical logs
are inspected as bytes; no upstream command or historical probe is executed.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
SCHEMA = ROOT / 'eval/qualification/c02-state.schema.json'
REAL = ('rust', 'js')
CONTROLLED = ('python', 'go')
CONTROLLED_PROOF = ROOT / 'docs/relatorios/logs/L5-C02/ci-next-first/verification.json'
CONTROLLED_VERIFIER = ROOT / 'docs/relatorios/logs/L5-C02/reconcile_new_corpus.py'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def receipt(path, root=ROOT):
    return {'path': path, 'sha256': hashlib.sha256((root / path).read_bytes()).hexdigest()}


def bind(value, root=ROOT):
    path = root / value['path']
    require(path.resolve().is_relative_to(root.resolve()), 'C02 receipt escapes repository')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == value['sha256'], 'C02 receipt hash mismatch: ' + value['path'])
    return raw


def event_state(kind, event, root=ROOT):
    """A supplemental exercise never fills the required family-state quota."""
    role = event['role']
    require(role != 'required' or kind == 'state_config', 'C02 required event must belong to state_config')
    if event['preparation'] == 'prepared':
        require(event['descriptor'] is not None and role != 'not_applicable', 'C02 prepared event needs descriptor')
        bind(event['descriptor'], root)
    else:
        require(event['descriptor'] is None, 'C02 unprepared event claims descriptor')
    if event['execution'] == 'verified':
        require(event['preparation'] == 'prepared' and event['execution_receipt'] is not None,
                'C02 event execution needs prepared descriptor and receipt')
        result = json.loads(bind(event['execution_receipt'], root))
        require(result.get('same_process') is True and result.get('same_index') is True
                and result.get('full_B_snapshot_equal') is True, 'C02 execution lacks continuity/full B comparison')
    else:
        require(event['execution_receipt'] is None, 'C02 unexecuted event claims execution receipt')
    if role == 'not_applicable':
        require(event['preparation'] == 'not_applicable' and event['execution'] == 'not_applicable',
                'C02 not-applicable event claims progress')
    return role == 'required' and event['preparation'] != 'prepared'


def validate_state(state, kind, *, root=ROOT):
    from jsonschema import Draft202012Validator
    schema = json.loads(SCHEMA.read_bytes())
    error = next(Draft202012Validator(schema).iter_errors(state), None)
    require(error is None, 'C02 state schema: ' + (str(error) if error else ''))
    require(state['global_admission'] == {'admitted': False, 'competitive_runs_allowed': False}, 'C02 false global admission')
    blockers = []
    for dimension in ('curation', 'review', 'behavior'):
        row = state[dimension]
        if row['status'] != 'verified':
            blockers.append(dimension + '_not_verified')
        else:
            require(row['receipts'], 'C02 verified dimension without evidence: ' + dimension)
        for item in row['receipts']:
            bind(item, root)
    if event_state(kind, state['event'], root):
        blockers.append('required_event_not_prepared')
    require(state['individual_eligibility']['eligible'] == (not blockers)
            and state['individual_eligibility']['blockers'] == blockers, 'C02 individual eligibility differs from criteria')
    return not blockers


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reviewed_js_modules(case, review, relations):
    modules = case['complexity']['required_production_modules']
    paths = {a['path'] for a in review['anchors_exact_digest_and_lines_verified']}
    require(len(modules) == len(set(modules)) == 3 and set(modules) == paths,
            'C02 JS modules differ from independently reviewed production anchors')
    subsystems = {'/'.join(Path(p).parts[:2]) for p in modules}
    require(set(case['complexity']['subsystems']) == subsystems and len(subsystems) >= 2,
            'C02 JS subsystems differ from reviewed modules')
    edges = relations['relationships']
    require(all(e['from'].split('::')[0] in paths and e['to'].split('::')[0] in paths
                and e['why_required'] for e in edges), 'C02 JS relation necessity')
    require(any(a['to'].split('::')[0] == b['from'].split('::')[0]
                and a['from'].split('::')[0] != b['to'].split('::')[0]
                for a in edges for b in edges), 'C02 JS two-edge path')
    return modules, subsystems


def verify_real_cases(cases, *, root=ROOT):
    """Verify approved historical pairs and their current per-case evidence."""
    require(len(cases) == 2, 'C02 expects two historical Rust/JS dossiers')
    from collect_real_rust import verify as verify_rust
    from prepare_l5_js import prepare as verify_js
    require(root == ROOT, 'C02 source adapters operate on repository root only')
    verify_rust()
    verify_js(write=False)
    historical = root / 'docs/relatorios/logs/L5-continuacao/ci-fourth'
    module = load_module(root / 'docs/relatorios/logs/L5-continuacao/reconcile_corpus.py', 'c02_corpus_receipts')
    behavior = module.reconcile(historical, 'c48b5993550fd258f1efe5677704a59d9eb73de0', 38283109016)
    require(behavior == json.loads((historical / 'corpus-verification.json').read_bytes()), 'C02 behavioral reconciliation differs')
    rows = []
    for family, case in zip(REAL, cases):
        state = case['c02']
        kind = case['kind'] if family == 'rust' else case['type']
        expected = ('L5-Rust-RA-23422', 'Rust', 'rust-lang/rust-analyzer', 'correction', 'L5-SLOT-Rust-correction-2') if family == 'rust' else (
            'L5-JS-REACT-22239', 'TSJS', 'facebook/react', 'contract_change', 'L5-SLOT-TSJS-contract_change-2')
        require((case.get('id', case.get('case_id')), case['family'], case['repository'], kind, case['slot']) == expected,
                'C02 approved dossier identity relabeled')
        require(case.get('admitted', False) is False and case.get('competitive_runs_allowed', False) is False,
                'C02 case falsely globally admitted')
        if family == 'js':
            require(case['qualification']['admitted'] is False and case['qualification']['competitive_runs_allowed'] is False,
                    'C02 JS case falsely globally admitted')
        eligible = validate_state(state, kind, root=root)
        require(state['behavior']['receipts'] == [receipt('docs/relatorios/logs/L5-continuacao/ci-fourth/corpus-verification.json')],
                'C02 behavior must bind reconciled approved pair')
        require(state['curation']['receipts'], 'C02 missing curation evidence')
        review = json.loads(bind(state['review']['receipts'][-1], root))
        if family == 'rust':
            require(review['author'] != review['second_reader'] and review['curation_review'] == 'source_curation_supported', 'C02 Rust independent review')
            hashes = review['reviewed_artifact_hashes']
            # case.json is historical tracking, not an agent/evaluator artifact;
            # its old tracking status remains in the immutable review receipt.
            for path, digest in hashes.items():
                if path.endswith('/case.json'):
                    continue
                bind({'path': path, 'sha256': digest}, root)
            prompt = 'eval/qualification/l5-real/rust/' + case['request']['path']
            oracle = 'eval/qualification/l5-real/rust/oracles/non_exhaustive_let.rs'
            require(prompt in hashes and oracle in hashes, 'C02 Rust review does not bind input/oracle')
            modules = case['production_modules']
            edges = case['relations']
            subsystems = {m['subsystem'] for m in modules}
            paths = {m['path'] for m in modules}
            require(paths == {'crates/hir/src/diagnostics.rs', 'crates/hir-ty/src/diagnostics/expr.rs', 'crates/hir-def/src/hir.rs'}
                    and len(modules) == len(paths), 'C02 Rust necessary modules differ from reviewed scope')
            require(all(e['from'] in paths and e['to'] in paths and e['necessity'] for e in edges), 'C02 Rust relation necessity')
            require(any(a['to'] == b['from'] and a['from'] != b['to'] for a in edges for b in edges), 'C02 Rust two-edge path')
            lineage = case['change_lineage']
            case_id = case['id']
        else:
            require(review['author'] != review['second_reader'] and review['status'] == 'accepted' and review['findings'] == [], 'C02 JS independent review')
            prompt = 'eval/qualification/l5-real/js/' + case['natural_input']
            oracle = 'eval/qualification/l5-real/js/oracles/XraiExternalStoreContract-test.js'
            require(review['prompt_sha256'] == receipt(prompt)['sha256'] and review['oracle_sha256'] == receipt(oracle)['sha256'], 'C02 JS review does not bind current input/oracle')
            require(review['reference_patch_sha256'] == receipt('eval/qualification/l5-real/js/oracles/reference.patch')['sha256']
                    and review['source_relations_sha256'] == receipt('eval/qualification/l5-real/js/oracles/source-relations.json')['sha256'], 'C02 JS reviewed patch/relations mismatch')
            require(len(review['anchors_exact_digest_and_lines_verified']) >= 3, 'C02 JS necessary anchors missing')
            relations = json.loads((root / 'eval/qualification/l5-real/js/oracles/source-relations.json').read_bytes())
            modules, subsystems = reviewed_js_modules(case, review, relations)
            lineage = 'upstream:facebook/react:' + case['reference']
            case_id = case['case_id']
        require(len(modules) >= 3 and len(subsystems) >= 2, 'C02 complex requirements missing')
        rows.append({'id': case_id, 'family': case['family'], 'kind': kind,
                     'repository': case['repository'], 'change_lineage': lineage,
                     'complex': True, 'historical': True, 'multi_module': True,
                     'states': state, 'individually_eligible': eligible, 'source': 'l5_real_dossier'})
    return rows


def summarize(rows):
    require(len({r['id'] for r in rows}) == len(rows), 'C02 duplicate task ID')
    require(len({r['change_lineage'] for r in rows}) == len(rows), 'C02 duplicate task lineage')
    require(max(Counter(r['repository'] for r in rows).values(), default=0) <= 4, 'C02 repository cap')
    eligible = [r for r in rows if r['individually_eligible']]
    new = [r for r in rows if r['source'] == 'l5_real_dossier']
    return {'eligible_tasks': len(eligible), 'eligible_complex': sum(r['complex'] for r in eligible),
            'eligible_historical': sum(r['historical'] for r in eligible),
            'eligible_multi_module': sum(r['multi_module'] for r in eligible),
            'new_dossiers_behavior_verified': sum(r['states']['behavior']['status'] == 'verified' for r in new),
            'new_dossiers_curated_reviewed': sum(r['states']['curation']['status'] == 'verified'
                    and r['states']['review']['status'] == 'verified' for r in new),
            'new_dossiers_individually_eligible': sum(r['individually_eligible'] for r in new),
            'new_dossiers_required': 4, 'admitted_tasks': 0, 'competitive_runs_allowed': False,
            'required_state_events_prepared': {f: sum(r['family'] == f and r['states']['event']['role'] == 'required'
                    and r['states']['event']['preparation'] == 'prepared' for r in rows) for f in ('Rust', 'TSJS', 'Python', 'Go')},
            'conditional_projection': {'additional_tasks': max(0, 32-len(eligible)),
                'additional_complex': max(0, 16-sum(r['complex'] for r in eligible)),
                'additional_historical': max(0, 16-sum(r['historical'] for r in eligible)),
                'additional_multi_module': max(0, 20-sum(r['multi_module'] for r in eligible)),
                'new_dossiers_remaining': max(0, 4-sum(r['individually_eligible'] for r in new)),
                'admission_deficit': 32}}


def controlled_state(family, review_receipt):
    """Curated controlled dossiers remain ineligible until behavioral proof.

    Case flags/counts are intentionally not inputs to this state transition.
    Python's future supplemental exercise does not block contract eligibility.
    """
    event = {'role': 'supplemental' if family == 'python' else 'not_applicable',
             'preparation': 'not_prepared' if family == 'python' else 'not_applicable',
             'execution': 'not_executed' if family == 'python' else 'not_applicable',
             'descriptor': None, 'execution_receipt': None}
    return {'schema': 'xrai.eval.c02.state.v1',
        'curation': {'status': 'verified', 'receipts': [receipt('eval/qualification/l5-real/'+family+'/capture.json')]},
        'review': {'status': 'verified', 'receipts': [review_receipt]},
        'behavior': {'status': 'pending', 'receipts': []}, 'event': event,
        'individual_eligibility': {'eligible': False, 'blockers': ['behavior_not_verified']},
        'global_admission': {'admitted': False, 'competitive_runs_allowed': False}}


def controlled_behavior():
    """A complete verified export, not a declared case status, advances C02."""
    if not CONTROLLED_PROOF.exists():
        return None
    require(CONTROLLED_PROOF.is_file() and not CONTROLLED_PROOF.is_symlink(), 'C02 controlled proof is not a regular file')
    expected = json.loads(CONTROLLED_PROOF.read_bytes())
    verifier = load_module(CONTROLLED_VERIFIER, 'c02_controlled_export_closure')
    actual = verifier.reconcile(CONTROLLED_PROOF.parent)
    require(actual == expected, 'C02 controlled behavioral proof differs from fresh export reconciliation')
    require(actual['verified'] is True and actual['data_only'] is True and actual['admitted'] is False
            and actual['competitive_execution'] is False and actual['run_id'] == 38294106923
            and actual['code_commit'] == 'e02370ab63aaf47356f986bd2a35c20adfe848f1',
            'C02 controlled behavioral provenance/admission mismatch')
    require(set(actual['families']) == set(CONTROLLED)
            and all(r['verified'] is True for r in actual['families'].values()), 'C02 controlled behavioral family set')
    mandatory = {'docs/relatorios/logs/L5-C02/reconcile_new_corpus.py',
                 'docs/relatorios/logs/L5-C02/verify_python_export.py',
                 'docs/relatorios/logs/L5-C02/verify_go_export.py'}
    require(mandatory <= actual['sources_sha256'].keys(), 'C02 controlled proof missing verifier fingerprints')
    for path, sha in actual['sources_sha256'].items():
        bind({'path': path, 'sha256': sha})
    return actual


def verify_controlled_cases(*, include_behavior=True):
    from prepare_l5_python import prepare, MODULES, COMMIT as PY_COMMIT
    from prepare_l5_go import verify, PATHS, COMMIT as GO_COMMIT
    captures = {'python': prepare(write=False), 'go': verify()}
    behavior = controlled_behavior() if include_behavior else None
    rows = []
    for family in CONTROLLED:
        folder = ROOT / 'eval/qualification/l5-real' / family
        case = json.loads((folder / 'case.json').read_bytes())
        expected = ('L5-SLOT-PY-contract_change-2', 'Python', 'scikit-learn/scikit-learn',
                    'L5-SLOT-Python-contract_change-2') if family == 'python' else (
                    'L5-GO-GITEA-URL-QUERY-CREDENTIALS', 'Go', 'go-gitea/gitea', 'L5-SLOT-Go-contract_change-2')
        require((case.get('id', case.get('case_id')), case['family'], case['repository'], case['slot']) == expected,
                'C02 controlled dossier identity relabeled')
        require(case['qualification']['admitted'] is False and case['qualification']['competitive_runs_allowed'] is False,
                'C02 controlled case falsely admitted')
        if family == 'python':
            require(case['task_type'] == 'controlled_contract_change' and case['historical_issue'] is None
                    and case['upstream_commit'] == PY_COMMIT, 'C02 Python source/origin relabeled')
            cap = captures['python']
            modules = MODULES
            source_hashes = cap['required_modules']
            prompt, oracle = 'agent/input.md', 'oracles/probe.py'
        else:
            require(case['origin'] == 'controlled_contract_change' and case['historical_change_claimed'] is False
                    and case['base'] == GO_COMMIT, 'C02 Go source/origin relabeled')
            cap = json.loads((folder / 'capture.json').read_bytes())
            modules = PATHS
            rel = json.loads((folder / 'oracles/source-relations.json').read_bytes())
            source_hashes = {r['path']: r['sha256'] for r in rel['modules']}
            prompt, oracle = 'agent/input.md', 'oracles/xrai_url_contract_test.go'
        review_receipt = case['independent_review']['receipt']
        require(review_receipt['path'] == 'docs/relatorios/logs/L5-C02/integration/'+family+'-source-review-root.json',
                'C02 controlled independent review provenance')
        review = json.loads(bind(review_receipt))
        require(review['author'] and review['second_reader'] and review['author'] != review['second_reader']
                and review['status'] == 'accepted' and review['findings'] == [], 'C02 controlled independent review unresolved')
        hashes = review['reviewed_artifact_hashes']
        for path, sha in hashes.items():
            bind({'path': path, 'sha256': sha})
        prefix = 'eval/qualification/l5-real/'+family+'/'
        require(review['prompt_sha256'] == receipt(prefix+prompt)['sha256']
                and review['oracle_sha256'] == receipt(prefix+oracle)['sha256']
                and prefix+prompt in hashes and prefix+oracle in hashes,
                'C02 controlled review does not bind current prompt/oracle')
        require(all(prefix+p in hashes for p in ['capture.json', 'oracles/reference.patch']),
                'C02 controlled reviewed capture/reference missing')
        require(set(case['complexity']['required_production_modules']) == set(modules)
                and len(case['complexity']['required_production_modules']) == len(modules) == 3,
                'C02 controlled modules differ from reviewed production scope')
        require({a['path'] for a in review['source_anchors']} == set(modules), 'C02 controlled review anchors missing')
        for anchor in review['source_anchors']:
            # Both capture verifiers above already compared these module hashes
            # with bytes in the complete archive. Reuse that fresh proof rather
            # than decompress the entire source a second time for the review.
            require(source_hashes[anchor['path']] == anchor['sha256'], 'C02 controlled reviewed source changed')
        require(review['assessment']['three_necessary_modules_two_subsystems_two_edge_chain'] is True,
                'C02 controlled semantic necessity review missing')
        if family == 'python':
            require(set(case['complexity']['subsystems']) == {
                'composite-estimator orchestration (ColumnTransformer/FeatureUnion)',
                'configured transformer output wrapping/container concatenation'}, 'C02 Python reviewed subsystems changed')
            require(case['complexity']['necessary_edges'] == [
                {'caller': 'ColumnTransformer._call_func_on_transformers', 'callee': 'FeatureUnion.fit_transform/transform',
                 'reason': 'nested branch emits a multi-feature masked result whose mask and branch order must survive the outer composition'},
                {'caller': 'FeatureUnion._hstack', 'callee': '_get_container_adapter / MaskedArrayAdapter.hstack',
                 'reason': 'inner FeatureUnion must concatenate masks rather than numpy.hstack discarding them'}],
                'C02 Python reviewed two-edge scope changed')
        else:
            require(set(case['complexity']['subsystems']) == set(rel['subsystems']), 'C02 Go reviewed subsystems changed')
            require([(e['from'], e['to']) for e in rel['edges']] == [(modules[0], modules[1]), (modules[1], modules[2])]
                    and all(e['relation'] for e in rel['edges']), 'C02 Go reviewed two-edge scope changed')
        state = controlled_state(family, review_receipt)
        if behavior is not None:
            state['behavior'] = {'status': 'verified', 'receipts': [receipt(CONTROLLED_PROOF.relative_to(ROOT).as_posix())]}
            state['individual_eligibility'] = {'eligible': True, 'blockers': []}
        eligible = validate_state(state, 'contract_change')
        rows.append({'id': expected[0], 'family': expected[1], 'kind': 'contract_change',
                     'repository': expected[2], 'change_lineage': 'controlled:'+expected[2]+':'+cap['commit']+':'+expected[0],
                     'complex': True, 'historical': False, 'multi_module': True,
                     'states': state, 'individually_eligible': eligible, 'source': 'l5_real_dossier'})
    return rows


def reconcile():
    from verify_qualified import validate_task_rows
    pilot_path = 'eval/qualification/vertical/candidates.jsonl'
    pilots = [json.loads(line) for line in (ROOT / pilot_path).read_text().splitlines()]
    validate_task_rows(pilots)
    rows = []
    for p in pilots:
        event = {'role': 'not_applicable', 'preparation': 'not_applicable', 'execution': 'not_applicable',
                 'descriptor': None, 'execution_receipt': None}
        state = {'schema': 'xrai.eval.c02.state.v1',
            'curation': {'status': 'verified', 'receipts': [receipt(pilot_path)]},
            'review': {'status': 'verified', 'receipts': [receipt('eval/' + p['review_receipt']['evidence']['path'])]},
            'behavior': {'status': 'verified', 'receipts': [receipt('eval/' + p['probe_receipt']['evidence']['path'])]},
            'event': event, 'individual_eligibility': {'eligible': True, 'blockers': []},
            'global_admission': {'admitted': False, 'competitive_runs_allowed': False}}
        validate_state(state, p['kind'])
        rows.append({'id': p['id'], 'family': p['family'], 'kind': p['kind'], 'repository': p['repository'],
                     'change_lineage': p['change_lineage'], 'complex': p['complexity']['complex'],
                     'historical': p['origin']['class'] == 'public_change',
                     'multi_module': len(p['production_modules']) >= 2 and bool(p['relations']),
                     'states': state, 'individually_eligible': True, 'source': 'preserved_l3_pilot'})
    cases = [json.loads((ROOT / 'eval/qualification/l5-real' / f / 'case.json').read_bytes()) for f in REAL]
    rows += verify_real_cases(cases)
    rows += verify_controlled_cases()
    source_paths = [pilot_path, 'eval/sources/manifest.json', 'eval/qualification/c02-state.schema.json',
                    'eval/qualification/qualified-task.schema.json', 'eval/scripts/verify_c02.py',
                    'eval/scripts/verify_qualified.py', 'eval/scripts/prepare_l5_python.py',
                    'eval/scripts/prepare_l5_go.py'] + ['eval/qualification/l5-real/' + f + '/case.json' for f in REAL+CONTROLLED]
    if CONTROLLED_PROOF.exists():
        proof = json.loads(CONTROLLED_PROOF.read_bytes())
        source_paths += [CONTROLLED_PROOF.relative_to(ROOT).as_posix()] + list(proof['sources_sha256'])
    source_paths = list(dict.fromkeys(source_paths))
    return {'schema': 'xrai.eval.c02.factual-matrix.v1', 'data_only': True,
            'summary': summarize(rows), 'tasks': rows, 'sources': [receipt(p) for p in source_paths],
            'limits': ['Individual eligibility and conditional deficits never admit the global dataset.',
                'Four required real state cases still need selection, preparation and execution before campaigns.',
                'Supplemental Rust event is preserved, pending and not another independent task.',
                'Historical probe/curation tracking labels are superseded by separate bound current receipts, never rewritten.',
                'No upstream runtime, agent session or past native executable bytes are reexecuted by this verifier.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = reconcile()
    text = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
