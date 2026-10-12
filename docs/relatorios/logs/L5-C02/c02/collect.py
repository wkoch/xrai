"""Local evidence collector; exit status stays the check's exit status."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / 'docs/relatorios/logs/L5-C02/c02'
OUT.mkdir(parents=True, exist_ok=True)
label, *command = sys.argv[1:]
destination = OUT / (label + '.json')
if destination.exists():
    raise SystemExit('existing evidence is immutable: choose a new label')
before = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
started = time.monotonic()
result = subprocess.run(command, cwd=ROOT, env=os.environ.copy(), capture_output=True)
receipt = {
    'command': command, 'base_commit': before,
    'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'platform': platform.platform(), 'machine': platform.machine(),
    'elapsed_seconds': time.monotonic() - started, 'exit_code': result.returncode,
    'stdout': result.stdout.decode('utf8', 'replace'),
    'stderr': result.stderr.decode('utf8', 'replace'),
    'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
    'stderr_sha256': hashlib.sha256(result.stderr).hexdigest(),
}
destination.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({key: receipt[key] for key in ('command', 'exit_code', 'elapsed_seconds')}))
if len(result.stdout) > 2500 and result.stdout.lstrip().startswith(b'{'):
    print(json.dumps({'stdout_bytes': len(result.stdout),
                      'stdout_sha256': receipt['stdout_sha256']}))
    print(receipt['stderr'][-2500:])
else:
    print((receipt['stdout'] + receipt['stderr'])[-2500:])
sys.exit(result.returncode)
