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
    source_paths = [pilot_path, 'eval/sources/manifest.json', 'eval/qualification/c02-state.schema.json',
                    'eval/qualification/qualified-task.schema.json', 'eval/scripts/verify_c02.py',
                    'eval/scripts/verify_qualified.py'] + ['eval/qualification/l5-real/' + f + '/case.json' for f in REAL]
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
