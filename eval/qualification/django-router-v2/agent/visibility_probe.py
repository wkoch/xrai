"""Owned tool-view probe; not an agent/model success measurement."""
import json
from pathlib import Path
import sys


def main():
    attacks = ['/private/oracle.json', '/private/reference.json', '/private/physical_oracle.py',
               '/checkout/../private/oracle.json', '/public/../private/oracle.json',
               '/workspace/private/oracle.json', '/proc/1/root/workspace/private/oracle.json',
               '/public/private-link', '/checkout/graft/INDEX.md', '/checkout/.git/config',
               '/checkout/eval/qualification/django-router-v2/evaluator/oracle.json']
    rows = []
    for name in attacks:
        try:
            content = Path(name).read_bytes()
            rows.append({'path': name, 'readable': True, 'bytes': len(content)})
        except (OSError, ValueError):
            rows.append({'path': name, 'readable': False})
    public = {name: Path(name).is_file() for name in ['/checkout/django/db/utils.py',
                                                    '/public/input.md', '/public/policy.py',
                                                    '/public/deployment.json']}
    try:
        Path('/checkout/xrai-write-attack').write_text('forbidden')
        readonly = False
    except OSError:
        readonly = True
    result = {'schema': 'xrai.eval.django-router.agent-view.v2', 'attacks': rows,
              'public_readable': public, 'checkout_readonly': readonly,
              'private_reads_denied': all(not r['readable'] for r in rows),
              'framework_imported': False, 'model_called': False}
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    if not result['private_reads_denied'] or not readonly or not all(public.values()):
        sys.exit(1)


if __name__ == '__main__':
    main()
