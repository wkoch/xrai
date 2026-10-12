#!/usr/bin/env python3
"""Portable append-only evidence collector for this R3 delivery."""
import datetime,hashlib,json,platform,subprocess,sys,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
OUT=Path(os.environ.get("XRAI_R3_OUTPUT_DIR",Path(__file__).resolve().parent));OUT.mkdir(parents=True,exist_ok=True)
label=sys.argv[1];command=sys.argv[2:]
assert label.replace('-','').replace('_','').isalnum() and command
receipt=OUT/(label+'.receipt.json');assert not receipt.exists()
started=datetime.datetime.now(datetime.UTC).isoformat();begin=time.monotonic()
r=subprocess.run(command,cwd=ROOT,capture_output=True)
stdout=OUT/(label+'.stdout');stderr=OUT/(label+'.stderr')
stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
sources=['crates/xrai-eval/src/semantics_spike.rs','crates/xrai-eval/src/semantics_spike/r3.rs','crates/xrai-eval/src/bin/semantics-spike.rs','crates/xrai-eval/tests/semantics_spike.rs','eval/scripts/verify_semantics.py']
receipt.write_text(json.dumps({'command':command,'started':started,'elapsed_seconds':time.monotonic()-begin,'exit':r.returncode,'platform':platform.platform(),'machine':platform.machine(),'stdout':stdout.name,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr':stderr.name,'stderr_sha256':hashlib.sha256(r.stderr).hexdigest(),'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}},indent=2)+'\n')
print(json.dumps({'label':label,'exit':r.returncode}))
sys.exit(r.returncode)
