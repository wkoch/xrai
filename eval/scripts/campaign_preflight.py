#!/usr/bin/env python3
"""Read-only factual campaign diagnostic from an owned immutable data closure.

Only project-owned Python data verifiers run. Captured upstream archives and
retained executables remain data. This entry point cannot dispatch a provider,
admit D1, or reinterpret ready/admitted caller flags as evidence.
"""
from dataclasses import dataclass
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'xrai.eval.campaign-preflight.v1'
BASE_SCOPES = ('eval', 'crates/xrai-eval/harness', 'crates/xrai-eval/src',
               'docs/relatorios/logs/L3', 'docs/relatorios/logs/L5-C02',
               'docs/relatorios/logs/L5-continuacao', 'docs/relatorios/logs/L5-C03/native-proof')
BASE_FILES = ('Cargo.lock', 'rust-toolchain.toml')
MAX_FILES = 8192
MAX_BYTES = 384 * 1024 * 1024
MAX_FILE_BYTES = 128 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'duplicate key: ' + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + value)))


def relative_path(name):
    require(type(name) is str and name and not name.startswith('/') and '\\' not in name and ':' not in name and
            all(piece not in ('', '.', '..') for piece in name.split('/')), 'snapshot path alias/escape')
    return name


def closure_paths(root):
    """Bounded verifier/data superset, plus progress-referenced native bundles."""
    root = Path(root).resolve()
    scopes = set(BASE_SCOPES)
    progress = root / 'eval/qualification/state-progress-v2.json'
    if progress.exists():
        def visit(value):
            if type(value) is dict:
                name = value.get('path')
                if type(name) is str:
                    relative_path(name)
                    if name.startswith('docs/relatorios/logs/'):
                        scopes.add(str(Path(name).parent))
                for child in value.values():
                    visit(child)
            elif type(value) is list:
                for child in value:
                    visit(child)
        visit(decode(progress.read_bytes()))
    paths = set()
    for scope in sorted(scopes):
        directory = root / relative_path(scope)
        require(directory.is_dir() and not directory.is_symlink(), 'snapshot scope unavailable/symlink: ' + scope)
        for path in directory.rglob('*'):
            relative = path.relative_to(root).as_posix()
            if '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            require(not path.is_symlink(), 'snapshot symlink: ' + relative)
            if path.is_dir():
                continue
            require(path.is_file(), 'snapshot nonregular file: ' + relative)
            paths.add(relative)
    paths.update(BASE_FILES)
    require(len(paths) <= MAX_FILES, 'snapshot file count bound')
    return tuple(sorted(paths))


@dataclass(frozen=True)
class CampaignSnapshot:
    root: Path
    entries: tuple

    def __post_init__(self):
        require(type(self.entries) is tuple and self.entries == tuple(sorted(self.entries)), 'sorted immutable snapshot entries')
        require(all(type(pair) is tuple and len(pair) == 2 and type(pair[1]) is bytes for pair in self.entries), 'snapshot owns immutable bytes')
        require(len({name for name, _ in self.entries}) == len(self.entries), 'unique snapshot paths')
        for name, raw in self.entries:
            relative_path(name)
            require(len(raw) <= MAX_FILE_BYTES, 'snapshot per-file limit')
        require(len(self.entries) <= MAX_FILES and sum(len(raw) for _, raw in self.entries) <= MAX_BYTES, 'snapshot total limits')

    @classmethod
    def capture(cls, *, root=ROOT):
        root = Path(root).resolve()
        names = closure_paths(root)
        entries, total = [], 0
        for name in names:
            path = root / name
            require(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_FILE_BYTES, 'bounded regular capture: ' + name)
            raw = path.read_bytes()
            total += len(raw)
            require(total <= MAX_BYTES, 'snapshot total byte bound')
            entries.append((name, raw))
        result = cls(root, tuple(entries))
        result.assert_current()
        return result

    @property
    def manifest(self):
        return {'schema': VERSION, 'intent': 'campaign_d1',
                'scope': 'owned-immutable-data-diagnostic-only',
                'files': {name: {'sha256': sha(raw), 'bytes': len(raw)} for name, raw in self.entries}}

    @property
    def fingerprint(self):
        return sha(canonical(self.manifest))

    def assert_current(self, *, current=None):
        if current is not None:
            observed = current()
            require(type(observed) is dict and all(type(k) is str and type(v) is bytes for k, v in observed.items()),
                    'current callback requires named actual bytes, never readiness flags')
            require(tuple(sorted(observed.items())) == self.entries, 'current captured bytes changed')
            return
        require(closure_paths(self.root) == tuple(name for name, _ in self.entries), 'snapshot file closure changed')
        for name, raw in self.entries:
            path = self.root / name
            require(path.is_file() and not path.is_symlink() and path.read_bytes() == raw, 'snapshot source changed: ' + name)

    def materialize(self, destination):
        destination = Path(destination)
        require(not destination.exists(), 'private snapshot destination must be fresh')
        destination.mkdir()
        for name, raw in self.entries:
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o400)


def _recompute(snapshot, rows):
    """Only owned verifier imports, in a private copy made from captured bytes."""
    require(snapshot.root == ROOT.resolve(), 'factual worker accepts only the configured owned project root')
    with tempfile.TemporaryDirectory(prefix='xrai-campaign-owned-data-') as temp:
        safe, scratch = Path(temp) / 'root', Path(temp) / 'scratch'
        snapshot.materialize(safe)
        scratch.mkdir()
        row_file = Path(temp) / 'rows.json'
        row_file.write_bytes(canonical(rows))
        command = [sys.executable, str(safe / 'eval/scripts/campaign_preflight.py'),
                   '--snapshot-worker', str(row_file)]
        environment = {'PATH': os.defpath, 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(scratch)}
        result = subprocess.run(command, cwd=safe, env=environment, capture_output=True, timeout=240)
        require(result.returncode == 0 and not result.stderr, 'owned factual recomposition failed: ' + result.stderr.decode(errors='replace')[:2000])
        return decode(result.stdout)


def preflight(snapshot, *, rows=None, current=None):
    require(type(snapshot) is CampaignSnapshot, 'owned factual snapshot required')
    snapshot.assert_current()
    if current is not None:
        snapshot.assert_current(current=current)
    if rows is None:
        captured = dict(snapshot.entries)
        raw = captured['eval/tasks/challenge-qualified.jsonl']
        rows = [decode(line) for line in raw.splitlines() if line]
    require(type(rows) is list and all(type(row) is dict for row in rows), 'explicit admission task rows')
    rows = decode(canonical(rows))
    recomposed = _recompute(snapshot, rows)
    snapshot.assert_current()
    if current is not None:
        snapshot.assert_current(current=current)
    require(set(recomposed) == {'facts', 'admission'}, 'factual worker output fields')
    facts = recomposed['facts']
    require(facts['verified'] is True and facts['data_only'] is True, 'facts must be recomposed')
    summary = facts['progress']['summary']
    reasons = {}
    if not facts['allocation']['allocation_globally_satisfactory']:
        reasons['allocation'] = f"multimodule projection {summary['multi_module_planning_projection']}/{summary['multi_module_planning_required']}; compensation pending"
    if summary['admitted_tasks'] != summary['primary_tasks_required']:
        reasons['corpus'] = f"global admitted {summary['admitted_tasks']}/{summary['primary_tasks_required']}; individual eligible {summary['individual_eligible_tasks']}"
    if summary['new_state_dossiers_individually_eligible'] < 4:
        reasons['state_dossiers'] = f"individually eligible state dossiers {summary['new_state_dossiers_individually_eligible']}/4"
    if summary['required_events_operationally_proven'] < 4:
        reasons['events'] = f"operational required events {summary['required_events_operationally_proven']}/4; families {summary['required_event_by_family']}"
    if recomposed['admission']['accepted'] is not True:
        reasons['admission'] = recomposed['admission']['reason']
    reasons.update(provider='paid provider adapter unavailable', authorization='paid authorization absent',
                   budget='concrete paid currency/window/ceiling unavailable',
                   containment='real provider/resource containment profile unavailable')
    return {'schema': VERSION, 'intent': 'campaign_d1', 'snapshot_sha256': snapshot.fingerprint,
            'admission_rows_sha256': sha(canonical(rows)), 'accepted': False,
            'factual_summary': summary, 'fact_reconciliation_sha256': sha(canonical(facts)),
            'dimensions': reasons, 'admission': recomposed['admission'],
            'snapshot_manifest': snapshot.manifest, 'external_calls': 0,
            'paid_provider_enabled': False, 'campaign_scoring_enabled': False,
            'limits': ['Diagnostic uses owned frozen bytes; upstream/native binaries remain data.',
                       'Local API snapshots are internally reconciled; original authenticated acquisition is a prerequisite, not a cryptographic signature.',
                       'This entry point cannot grant D1 or a paid resource even if corpus facts later change.',
                       'No tokenizer execution, performance claim or task eligibility inferred from state protocol proof.']}


def _worker(rows_file):
    import verify_state_assignment as allocation
    rows = decode(Path(rows_file).read_bytes())
    facts = allocation.verify()
    try:
        admitted = allocation.admission(rows)
        admission = {'accepted': True, 'result': admitted}
    except (ValueError, KeyError, TypeError) as error:
        admission = {'accepted': False, 'reason': str(error)}
    return {'facts': facts, 'admission': admission}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--intent', choices=['campaign_d1'], default='campaign_d1')
    parser.add_argument('--rows', type=Path)
    parser.add_argument('--snapshot-worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.snapshot_worker:
        print(json.dumps(_worker(args.snapshot_worker), sort_keys=True))
        return 0
    rows = decode(args.rows.read_bytes()) if args.rows else None
    snapshot = CampaignSnapshot.capture()
    print(json.dumps(preflight(snapshot, rows=rows), indent=2, sort_keys=True))
    return 1  # Expected diagnostic refusal, never a provider dispatch.


if __name__ == '__main__':
    raise SystemExit(main())
