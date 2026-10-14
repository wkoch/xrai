#!/usr/bin/env python3
"""Recompute owned complete receipts; never import or run captured Django."""
import argparse
import math
from pathlib import Path
import sys
from django_router_physical import BOUND, CASE, FREEZE_SHA, ROOT, lock, prepared, stream, validate_result
from django_router_verify import canonical, decode, read_owned, require, sha


def verify(output):
    output = output.resolve()
    freeze, data, files = prepared()
    expected_members = {'runtime-before.json', 'freeze-before.json', 'setup-lock-before.json', 'pair.json'}
    expected_members |= {p + suffix for p in ('agent', 'a', 'b', 'controls')
                         for suffix in ('-harness.json', '-report.json', '.stdout', '.stderr')}
    require({str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()} == expected_members,
            'exact physical proof file closure')
    raw = {name: read_owned(output, name, 16 * BOUND if name == 'runtime-before.json' else BOUND)
           for name in expected_members}
    require(raw['freeze-before.json'] == (CASE / 'freeze.json').read_bytes() and
            raw['setup-lock-before.json'] == (CASE / 'setup.lock.json').read_bytes(), 'before-execution frozen inputs')
    boot = decode(raw['runtime-before.json'])
    require(boot['before_upstream_execution'] is True and boot['framework_imported_during_setup'] is False and
            boot['no_site_packages_inherited'] is True, 'pre-execution runtime closure')
    require(boot['python_version'] == lock()['python'] and boot['setup_lock_sha256'] == sha(raw['setup-lock-before.json']) and
            boot['executor_source_sha256'] == sha((ROOT / 'eval/scripts/django_router_physical.py').read_bytes()) and
            boot['oracle_source_sha256'] == sha((CASE / 'evaluator/physical_oracle.py').read_bytes()), 'runtime/producer binding')
    require(boot['source_files'] == {name: {'bytes': len(value), 'sha256': sha(value)} for name, value in files.items()},
            'runtime source full archive closure')
    require(len(boot['wheels']) == 2 and all({k: row[k] for k in item} == item
            for row, item in zip(boot['wheels'], lock()['packages'])), 'dependency pins')
    require(all(row['downloaded_package_executed'] is False and row['licenses'] for row in boot['wheels']), 'wheel licenses/setup phase')
    require(boot['runtime_files'] and boot['dependency_files'] and boot['dynamic_libraries'] and boot['sqlite_libraries'] and
            boot['system_licenses'], 'inventories/licenses cannot be omitted')
    for section in ('runtime_files', 'dependency_files', 'dynamic_libraries', 'sqlite_libraries'):
        for name, row in boot[section].items():
            require(type(row['bytes']) is int and row['bytes'] >= 0 and len(row['sha256']) == 64,
                    'runtime inventory typed fingerprint')
    require(all(name.startswith('/usr/') or name.startswith('/opt/') for name in boot['dynamic_libraries']), 'system dependency path scope')
    origins = {name: {'path': '/checkout/' + name.replace('.', '/') + '.py',
                     'sha256': sha(files[name.replace('.', '/') + '.py'])}
               for name in ('django.db.migrations.operations.models', 'django.db.migrations.operations.base',
                            'django.db.utils', 'django.db.models.options')}
    origins['policy'] = {'path': '/public/policy.py', 'sha256': sha((CASE / 'agent/policy.py').read_bytes())}
    oracle = decode((CASE / 'evaluator/oracle.json').read_bytes())
    sys.path.insert(0, str(ROOT / 'crates/xrai-eval/harness'))
    from supervisor import verify_receipt, confirmed_receipt
    phases = []
    for phase in ('agent', 'a', 'b', 'controls'):
        turn = decode(raw[phase + '-harness.json'])
        verify_receipt(turn)
        require(confirmed_receipt(turn) and turn['eligible_for_agent_run'] and turn['execution_status'] == 'ok' and
                type(turn['exit_code']) is int and turn['exit_code'] == 0, 'actual domain success/teardown')
        require(type(turn['elapsed_seconds']) in (int, float) and math.isfinite(turn['elapsed_seconds']) and
                0 <= turn['elapsed_seconds'] <= 62, 'actual domain time')
        require(turn['phase'] == 'django-v2-' + phase, 'domain phase')
        from django_router_physical import command
        require(turn['command'] == command(phase), 'exact bounded command and view')
        stdout, stderr = stream(turn, 'stdout'), stream(turn, 'stderr')
        require(stdout == raw[phase + '.stdout'] and stderr == raw[phase + '.stderr'], 'raw stream binding')
        report = decode(stdout)
        require(canonical(report) == canonical(decode(raw[phase + '-report.json'])), 'complete report binding')
        if phase == 'agent':
            require(report['private_reads_denied'] is True and report['checkout_readonly'] is True and
                    report['framework_imported'] is False and report['model_called'] is False,
                    'agent probe scope')
            require(len(report['attacks']) == 11 and len({r['path'] for r in report['attacks']}) == 11 and
                    all(r['readable'] is False for r in report['attacks']) and
                    all(report['public_readable'].values()), 'effective visibility attacks')
            result = {'visibility_verified': True, 'private_reads_attempted': len(report['attacks'])}
        else:
            require(report['sqlite_version'] == boot['sqlite_version'], 'actual SQLite runtime binding')
            result = validate_result(report, phase, oracle, origins)
        phases.append({'phase': phase, 'result': result, 'domain_id': turn['domain_id'],
                       'teardown_confirmed': True, 'stdout_sha256': sha(stdout), 'stderr_sha256': sha(stderr)})
    pair = decode(raw['pair.json'])
    elapsed = pair['elapsed_batch_seconds']
    require(type(elapsed) in (int, float) and math.isfinite(elapsed) and 0 <= elapsed <= 300, 'batch ceiling')
    expected = {'schema': 'xrai.eval.django-router.physical-pair.v2', 'freeze_sha256': FREEZE_SHA,
                'phases': phases, 'source_runtime_dependencies_unchanged': True,
                'physical_cells': 12, 'physical_controls': 4, 'oracle_executed': True,
                'baseline_requirement_satisfied': False, 'reference_requirement_satisfied': True,
                'model_veto_observed_before_router': True, 'public_agent_visibility_verified': True,
                'elapsed_batch_seconds': elapsed, 'phase_policy': lock()['phase_policy'],
                'multimodule': False, 'projection': 19, 'individual_eligible': False,
                'qualified': False, 'admitted': False, 'provider_used': False}
    require(canonical(pair) == canonical(expected), 'complete derived pair, no promotion')
    require(len({p['domain_id'] for p in phases}) == 4, 'fresh domain identities')
    return {'verified': True, 'freeze_sha256': FREEZE_SHA, 'original_event_files': len(raw),
            'physical_cells': 12, 'physical_controls': 4, 'fresh_domains': 4,
            'oracle_executed': True, 'baseline_requirement_satisfied': False,
            'reference_requirement_satisfied': True, 'qualified': False, 'admitted': False,
            'multimodule': False, 'projection': 19, 'provider_used': False}


def main():
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output), indent=2))


if __name__ == '__main__':
    main()
