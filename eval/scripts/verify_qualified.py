#!/usr/bin/env python3
"""Fail-closed ADR021 admission gate. Never substitute the development seed."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ('Rust', 'TSJS', 'Python', 'Go')
STRATA = {'correction': 2, 'contract_change': 2, 'state_config': 2, 'review': 1, 'control': 1}


def require(value, message):
    if not value:
        raise ValueError(message)


def artifact(root, receipt):
    path = root / receipt['path']
    require(path.resolve().is_relative_to(root.resolve()), 'artifact escapes evaluator root')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == receipt['sha256'], 'artifact fingerprint')
    return path


def validate(rows, *, root=ROOT, check_artifacts=True):
    require(len(rows) == 32, 'qualified admission requires exactly 32 primary tasks')
    require(len({r['id'] for r in rows}) == 32, 'duplicate qualified ID')
    require(len({r['change_lineage'] for r in rows}) == 32, 'duplicate change lineage')
    require(max(Counter(r['repository'] for r in rows).values()) <= 4, 'repository exceeds four primary tasks')
    required = {'id', 'version', 'dataset', 'family', 'kind', 'language', 'repository',
                'change_lineage', 'derived_from', 'origin', 'input', 'production_modules',
                'relations', 'complexity', 'snapshot_proof', 'oracle_receipt', 'review_receipt'}
    for row in rows:
        require(required <= row.keys(), 'missing qualified task fields')
        require(row['dataset'] == 'qualified' and row['version'] >= 1 and row['id'].startswith('Q1-'), 'seed cannot be promoted by default')
        require(row['family'] in FAMILIES and row['kind'] in STRATA, 'unknown stratum')
        require(row['change_lineage'] and isinstance(row['derived_from'], list), 'missing lineage')
        modules = row['production_modules']
        require(len({m['path'] for m in modules}) == len(modules), 'duplicate production module')
        require(all(m['subsystem'] and m['necessity'] for m in modules), 'production module requires semantic necessity')
        paths = {m['path'] for m in modules}
        require(all(e['from'] in paths and e['to'] in paths and e['from'] != e['to'] and e['reason'] for e in row['relations']), 'relation must connect necessary production modules')
        proof = row['snapshot_proof']
        require(len(proof['commit']) == 40 and all(c in '0123456789abcdef' for c in proof['commit']), 'full immutable source commit')
        require(proof['complete_checkout'] is True and proof['license_files'] and proof['measurement_method'] and proof['exclusions'], 'complete licensed checkout and explicit measurement required')
        require(proof['production_files'] >= len(modules) and proof['production_nonempty_lines'] >= 0, 'invalid production measurement')
        require(row['origin']['class'] in ('public_change', 'controlled_real_use', 'control'), 'unknown problem provenance')
        require(row['origin']['url'] and row['origin']['motivation'], 'missing attributable problem provenance')
        require((row['kind'] == 'control') == (row['origin']['class'] == 'control'), 'control provenance mismatch')
        require(row['input']['prompt'] and row['input']['snapshot'], 'missing natural prompt/source snapshot')
        review = row['review_receipt']
        require(review['author'] != review['second_reader'] and review['author'] and review['second_reader'], 'independent second reader required')
        require(review['status'] == 'accepted' and isinstance(review['findings'], list) and isinstance(review['corrections'], list), 'review receipt unresolved')
        oracle = row['oracle_receipt']
        prompt_hash = hashlib.sha256(row['input']['prompt'].encode()).hexdigest()
        require(review['prompt_sha256'] == prompt_hash and review['oracle_sha256'] == oracle['sha256'], 'review hashes do not bind prompt/oracle')
        if check_artifacts:
            artifact(root, proof['archive'])
            artifact(root, oracle)
            artifact(root, review['evidence'])
        if row['kind'] in ('correction', 'contract_change'):
            probe = row['probe_receipt']
            require(1 <= probe['baseline']['exit_code'] <= 125 and probe['reference']['exit_code'] == 0 and probe['regression']['exit_code'] == 0, 'independent behavioral probe and regression evidence required; missing tool/signal is not a behavioral failure')
            require(all(probe[k]['command'] and probe[k]['environment'] for k in ('baseline', 'reference', 'regression')), 'probe command/environment not pinned')
            if check_artifacts:
                artifact(root, probe['evidence'])
        if row['kind'] == 'review':
            require(row['review_oracle']['blind_adjudication'] is True and row['review_oracle']['unexpected_findings_require_reproduction'] is True and row['review_oracle']['defects'], 'review needs blind adjudication and reproducible defects')
        if row['kind'] == 'state_config':
            require(row['configuration_oracle']['facts'] and row['configuration_oracle']['alternate_valid_evidence_allowed'] is True, 'configuration factual rubric missing')
        if row['complexity']['complex']:
            require(len(modules) >= 3 and len({m['subsystem'] for m in modules}) >= 2, 'complex task needs three modules/two subsystems')
            edges = row['relations']
            require(any(a['to'] == b['from'] and a['from'] != b['to'] for a in edges for b in edges), 'complex task needs a two-relation path')
            require(proof['production_nonempty_lines'] >= 50000 or proof['production_files'] >= 500, 'complex project below production size floor')
    for family in FAMILIES:
        subset = [r for r in rows if r['family'] == family]
        require(Counter(r['kind'] for r in subset) == STRATA, family + ' strata')
        repos = Counter(r['repository'] for r in subset)
        require(len(repos) >= 2 and max(repos.values()) <= 4, family + ' repository balance')
        complex_rows = [r for r in subset if r['complexity']['complex']]
        complex_repos = Counter(r['repository'] for r in complex_rows)
        require(len(complex_rows) >= 4 and len(complex_repos) >= 2 and all(n >= 2 for n in complex_repos.values()), family + ' complex coverage')
        require(sum(r['origin']['class'] == 'public_change' for r in subset) >= 4, family + ' public provenance floor')
        events = [r for r in subset if r.get('incremental_event')]
        require(events, family + ' incremental event missing')
        for row in events:
            event = row['incremental_event']
            require(event['sequence'] == ['materialize_A', 'start_index_A', 'warm_query', 'apply_B', 'same_index_query', 'oracle_B', 'full_rebuild_B'] and event['same_process_required'] is True, 'cold checkout is not incremental')
            require(row['input'].get('state_changes') and event['oracle_B'] and event['full_rebuild_comparison'], 'incremental event/oracle specification missing')
    tsjs = [r for r in rows if r['family'] == 'TSJS']
    require(sum(r['language'] == 'TypeScript' for r in tsjs) >= 2 and sum(r['language'] == 'JavaScript' for r in tsjs) >= 2, 'TS and JS floors')
    require(sum(r['kind'] != 'control' and len(r['production_modules']) >= 2 and bool(r['relations']) for r in rows) >= 20, 'twenty noncontrols need related production modules')
    require(sum(r['origin']['class'] == 'controlled_real_use' for r in rows) <= 12, 'controlled origin ceiling')
    return {'primary_tasks': 32, 'complex_tasks': sum(r['complexity']['complex'] for r in rows), 'gate': 'admitted', 'semantic_review_required': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'tasks/challenge-qualified.jsonl')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        rows = [json.loads(line) for line in args.dataset.read_text(encoding='utf-8').splitlines() if line.strip()]
        result = {'status': 'passed', 'summary': validate(rows)}
    except (ValueError, KeyError, OSError, TypeError) as error:
        result = {'status': 'not_admitted', 'error': str(error), 'competitive_runs_allowed': False}
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
    return result['status'] != 'passed'


if __name__ == '__main__':
    sys.exit(main())
