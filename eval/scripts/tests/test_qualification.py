"""Admission mutations and real phase A/B materialization without model sessions."""
import copy
import hashlib
import json
import io
from pathlib import Path
import sys
import tempfile
import tarfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from materialize_task import ROOT, apply_event, materialize, tasks
from verify_qualified import FAMILIES, validate


def synthetic_rows():
    rows = []
    kinds = ['correction', 'correction', 'contract_change', 'contract_change', 'state_config', 'state_config', 'review', 'control']
    receipt = {'path': 'synthetic', 'sha256': 'a' * 64}
    for family in FAMILIES:
        for index, kind in enumerate(kinds):
            prompt = 'Natural symptom for unit fixture only'
            modules = [{'path': f'm{n}.py', 'subsystem': str(n % 2), 'necessity': 'fixture dependency'} for n in range(3)]
            row = {'id': f'Q1-{family}-{index}', 'version': 1, 'dataset': 'qualified', 'family': family, 'kind': kind,
                   'language': 'JavaScript' if family == 'TSJS' and index < 4 else 'TypeScript' if family == 'TSJS' else family,
                   'repository': family + str(index // 4), 'change_lineage': family + str(index), 'derived_from': [],
                   'origin': {'class': 'public_change' if index < 4 else 'control' if kind == 'control' else 'controlled_real_use', 'url': 'https://example.invalid/fixture', 'motivation': 'unit test'},
                   'input': {'prompt': prompt, 'snapshot': 'fixture'}, 'production_modules': modules,
                   'relations': [{'from': 'm0.py', 'to': 'm1.py', 'reason': 'calls'}, {'from': 'm1.py', 'to': 'm2.py', 'reason': 'uses'}],
                   'complexity': {'complex': index in (0, 1, 4, 5)},
                   'snapshot_proof': {'commit': 'a' * 40, 'complete_checkout': True, 'license_files': ['LICENSE'], 'measurement_method': 'fixture', 'exclusions': ['tests'], 'production_files': 500, 'production_nonempty_lines': 50000, 'archive': receipt},
                   'oracle_receipt': receipt,
                   'review_receipt': {'author': 'author', 'second_reader': 'reader', 'status': 'accepted', 'findings': [], 'corrections': [], 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'oracle_sha256': receipt['sha256'], 'evidence': receipt}}
            if kind in ('correction', 'contract_change'):
                row['probe_receipt'] = {k: {'exit_code': int(k == 'baseline'), 'command': ['fixture'], 'environment': {'version': 'fixture'}} for k in ('baseline', 'reference', 'regression')}
                row['probe_receipt']['evidence'] = receipt
            if kind == 'review':
                row['review_oracle'] = {'blind_adjudication': True, 'unexpected_findings_require_reproduction': True, 'defects': ['fixture']}
            if kind == 'state_config':
                row['configuration_oracle'] = {'facts': ['fixture'], 'alternate_valid_evidence_allowed': True}
            if index == 4:
                row['input']['state_changes'] = [{'kind': 'write', 'path': 'fixture', 'content': 'fixture'}]
                row['incremental_event'] = {'sequence': ['materialize_A', 'start_index_A', 'warm_query', 'apply_B', 'same_index_query', 'oracle_B', 'full_rebuild_B'], 'same_process_required': True, 'oracle_B': receipt, 'full_rebuild_comparison': ['fixture']}
            rows.append(row)
    return rows


def synthetic_artifacts(root):
    """Complete temporary fake sources for gate tests only, never corpus tasks."""
    rows = synthetic_rows()
    data = b'fixture evidence only'
    (root / 'synthetic').write_bytes(data)
    evidence = {'path': 'synthetic', 'sha256': hashlib.sha256(data).hexdigest()}
    sources = root / 'sources'
    sources.mkdir()
    archive = sources / 'synthetic.tar.gz'
    entries = []
    with tarfile.open(archive, 'w:gz') as tree:
        for name in ['LICENSE'] + [f'm{i}.py' for i in range(500)]:
            content = b'fixture license' if name == 'LICENSE' else b'x = 1\n' * 100
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tree.addfile(info, io.BytesIO(content))
            entries.append({'path': name, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
    archive_receipt = {'path': 'sources/synthetic.tar.gz', 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
    manifest = {'snapshots': {}}
    for row in rows:
        key = row['repository'] + '@' + row['snapshot_proof']['commit']
        row['input']['snapshot'] = key
        row['snapshot_proof'].update(archive=archive_receipt, measurement_method='xrai.production.path-marker.v1')
        manifest['snapshots'][key] = {'repository': row['repository'], 'commit': row['snapshot_proof']['commit'], 'archive': archive_receipt['path'], 'sha256': archive_receipt['sha256'], 'license_files': ['LICENSE'], 'file_count': len(entries), 'files': entries}
        row['oracle_receipt'] = evidence
        row['review_receipt'].update(evidence=evidence, oracle_sha256=evidence['sha256'])
        if 'probe_receipt' in row:
            row['probe_receipt']['evidence'] = evidence
        if 'incremental_event' in row:
            row['incremental_event']['oracle_B'] = evidence
    (sources / 'manifest.json').write_text(json.dumps(manifest))
    return rows


class AdmissionTests(unittest.TestCase):
    def test_empty_and_seed_fail_closed(self):
        for rows in ([], tasks('seed')):
            with self.assertRaises(ValueError):
                validate(rows, check_artifacts=False)

    def test_complete_synthetic_shape(self):
        # These rows never leave this unit test or count as qualified tasks.
        self.assertEqual(validate(synthetic_rows(), check_artifacts=False)['primary_tasks'], 32)

    def test_schema_types_language_and_incremental_oracle_both_modes(self):
        mutations = [lambda r: r[0].update(language='Go'),
                     lambda r: r[0].update(version=True),
                     lambda r: r[0].update(version='1'),
                     lambda r: r[0]['complexity'].update(complex='yes'),
                     lambda r: r[0]['snapshot_proof'].update(production_files=True),
                     lambda r: r[0]['review_receipt'].update(findings='accepted'),
                     lambda r: r[4]['incremental_event'].update(oracle_B={'path':'/outside/does-not-exist', 'sha256':'bad'}),
                     lambda r: r[4]['incremental_event'].update(oracle_B={'path':'../outside', 'sha256':'a'*64}),
                     lambda r: r[7]['complexity'].update(complex=True)]
        for check_artifacts in (False, True):
            for index, mutate in enumerate(mutations):
                with self.subTest(artifacts=check_artifacts, mutation=index), tempfile.TemporaryDirectory() as tmp:
                    rows = synthetic_artifacts(Path(tmp)) if check_artifacts else synthetic_rows()
                    mutate(rows)
                    with self.assertRaises(ValueError):
                        validate(rows, root=Path(tmp), check_artifacts=check_artifacts)

    def test_real_mode_binds_snapshots_sources_measurements_and_event_oracle(self):
        mutations = [lambda r: r[0]['input'].update(snapshot='unknown'),
                     lambda r: r[0]['snapshot_proof'].update(commit='b'*40),
                     lambda r: r[0]['production_modules'][0].update(path='absent.py'),
                     lambda r: r[0]['snapshot_proof'].update(production_nonempty_lines=50001),
                     lambda r: r[4]['incremental_event'].update(oracle_B={'path':'missing', 'sha256':'a'*64}),
                     lambda r: r[4]['incremental_event'].update(oracle_B={'path':'synthetic', 'sha256':'a'*64})]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = synthetic_artifacts(root)
            self.assertEqual(validate(original, root=root)['primary_tasks'], 32)
            for index, mutate in enumerate(mutations):
                with self.subTest(mutation=index):
                    rows = copy.deepcopy(original)
                    mutate(rows)
                    with self.assertRaises(ValueError):
                        validate(rows, root=root)

    def test_mutations_reject_false_admission(self):
        mutations = [lambda r: r.pop(), lambda r: r[0].update(dataset='D1'),
                     lambda r: r[1].update(change_lineage=r[0]['change_lineage']),
                     lambda r: r[0]['snapshot_proof'].update(production_files=499, production_nonempty_lines=49999),
                     lambda r: r[0]['review_receipt'].update(second_reader='author'),
                     lambda r: r[0]['review_receipt'].update(prompt_sha256='bad'),
                     lambda r: r[0].update(relations=[]),
                     lambda r: r[0]['probe_receipt']['baseline'].update(exit_code=0),
                     lambda r: r[0]['probe_receipt']['baseline'].update(exit_code=127),
                     lambda r: r[4].pop('incremental_event'),
                     lambda r: r[6]['review_oracle'].update(unexpected_findings_require_reproduction=False),
                     lambda r: r[4]['incremental_event'].update(same_process_required=False)]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                rows = copy.deepcopy(synthetic_rows())
                mutate(rows)
                with self.assertRaises(ValueError):
                    validate(rows, check_artifacts=False)

    def test_qualified_and_supplementary_are_explicit_empty(self):
        self.assertEqual(tasks('qualified'), [])
        self.assertEqual(tasks('supplementary'), [])
        self.assertEqual(len(tasks()), 52)

    def test_phase_A_event_B_matches_cold_checkout_each_family(self):
        for family in FAMILIES:
            task = next(t for t in tasks() if t['family'] == family and t['input'].get('state_changes'))
            with self.subTest(family=family), tempfile.TemporaryDirectory() as temp:
                a, b = Path(temp) / 'a', Path(temp) / 'b'
                materialize(task['id'], a, phase='A')
                request = json.loads((a / 'request.json').read_text())
                self.assertNotIn('state_changes', request)
                workspace = a / 'workspace'
                identity = workspace.stat().st_ino
                receipt = apply_event(task['id'], workspace)
                self.assertEqual(identity, workspace.stat().st_ino)
                self.assertTrue(receipt['events'])
                for operation, event in zip(task['input']['state_changes'], receipt['events']):
                    if operation.get('preserve_mtime') and event['before_mtime_ns'] is not None:
                        self.assertEqual(event['before_mtime_ns'], event['after_mtime_ns'])
                materialize(task['id'], b)
                content = lambda root: {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                self.assertEqual(content(workspace), content(b / 'workspace'))

    def test_event_refuses_agent_symlink_escape(self):
        task = next(t for t in tasks() if t['input'].get('state_changes'))
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / 'task'
            materialize(task['id'], dest, phase='A')
            operation = task['input']['state_changes'][0]
            target = dest / 'workspace' / operation['path']
            target.unlink(missing_ok=True)
            outside = Path(temp) / 'outside'
            outside.write_text('must survive')
            target.symlink_to(outside)
            with self.assertRaises(ValueError):
                apply_event(task['id'], dest / 'workspace')
            self.assertEqual(outside.read_text(), 'must survive')

    def test_event_refuses_hardlink_and_parent_symlink_escape(self):
        task = next(t for t in tasks() if any('/' in o['path'] and o['kind'] == 'write' for o in t['input'].get('state_changes', [])))
        operation = next(o for o in task['input']['state_changes'] if '/' in o['path'] and o['kind'] == 'write')
        for link_kind in ('hardlink', 'parent_symlink'):
            with self.subTest(link_kind=link_kind), tempfile.TemporaryDirectory() as temp:
                dest = Path(temp) / 'task'
                materialize(task['id'], dest, phase='A')
                outside = Path(temp) / 'outside'
                outside.mkdir()
                target = dest / 'workspace' / operation['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                external = outside / target.name
                external.write_text('must survive')
                if link_kind == 'hardlink':
                    target.unlink(missing_ok=True)
                    target.hardlink_to(external)
                else:
                    import shutil
                    shutil.rmtree(target.parent)
                    target.parent.symlink_to(outside, target_is_directory=True)
                with self.assertRaises(ValueError):
                    apply_event(task['id'], dest / 'workspace')
                self.assertEqual(external.read_text(), 'must survive')


if __name__ == '__main__':
    unittest.main()
