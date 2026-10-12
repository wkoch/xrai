#!/usr/bin/env python3
"""Verify four reviewed vertical dossiers without opening the 32-task gate."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import tarfile

from verify_qualified import ROOT, FAMILIES, require, validate_task_rows


def validate_vertical(rows, *, root=ROOT, check_artifacts=True):
    require(Counter(r.get('family') for r in rows) == Counter(FAMILIES),
            'vertical increment requires exactly one case per family')
    validate_task_rows(rows, root=root, check_artifacts=check_artifacts)
    return {'status': 'vertical_evidence_verified', 'candidate_tasks': 4,
            'competitive_runs_allowed': False,
            'remaining_global_gate': 'exactly 32 tasks and all ADR021 matrix floors'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path,
                        default=ROOT / 'qualification/vertical/candidates.jsonl')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        rows = [json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
        result = validate_vertical(rows)
        code = 0
    except (ValueError, KeyError, OSError, TypeError, tarfile.TarError) as error:
        result = {'status': 'vertical_evidence_incomplete', 'error': str(error),
                  'competitive_runs_allowed': False}
        code = 1
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end='')
    return code


if __name__ == '__main__':
    sys.exit(main())
