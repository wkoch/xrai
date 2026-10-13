"""Authenticated GitHub proof acquisition; retained native files are data only."""
import datetime,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path('/Users/wkoch/Projetos/xrai');sys.path.insert(0,str(ROOT/'eval/scripts'))
import reconcile_real_resources_ci as c
run_id=int(sys.argv[1]); out=Path(sys.argv[2]);assert run_id>0 and not out.exists();out.mkdir(parents=True)
def api(path):
    p=subprocess.run(['gh','api',path],capture_output=True,timeout=120)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    return p.stdout
for name,path in [('run',f'repos/wkoch/xrai/actions/runs/{run_id}'),('jobs',f'repos/wkoch/xrai/actions/runs/{run_id}/jobs?per_page=100'),('artifacts',f'repos/wkoch/xrai/actions/runs/{run_id}/artifacts?per_page=100')]:
    raw=api(path);(out/(name+'.json')).write_bytes(raw)
run=json.loads((out/'run.json').read_bytes());artifacts=json.loads((out/'artifacts.json').read_bytes());ids={};acquired={}
assert run['status']=='completed'
for host in ['x86_64-unknown-linux-gnu','aarch64-apple-darwin']:
    selected=[a for a in artifacts['artifacts'] if a['name']=='c04-real-resources-'+host]
    assert len(selected)==1 and selected[0]['size_in_bytes']<=c.MAX_ZIP_BYTES
    a=selected[0]; ids[host]=a['id']; d=out/host;d.mkdir();raw=api(f'repos/wkoch/xrai/actions/artifacts/{a["id"]}/zip')
    assert len(raw)<=c.MAX_ZIP_BYTES
    (d/'original.zip').write_bytes(raw)
    acquired[host]={'artifact_id':a['id'],'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    if run['conclusion']=='success':c.safe_export(c.zip_members(raw),d/'export')
(out/'acquisition.json').write_text(json.dumps({'schema':'xrai.authenticated-ci-acquisition.v1','authenticated_tool':'gh api repos/wkoch/xrai','run_id':run_id,'head':run['head_sha'],'attempt':run['run_attempt'],'acquired_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'artifacts':acquired,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'retained_binaries_executed':False},indent=2)+'\n')
if run['conclusion']=='success':
    result=c.reconcile(out,run_id,run['head_sha'],ids,run['run_attempt'])
    (out/'reconciliation.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
else:
    p=subprocess.run(['gh','run','view',str(run_id),'--log-failed'],capture_output=True,timeout=120)
    (out/'failed-job.log').write_bytes(p.stdout+p.stderr)
print(json.dumps({'run_id':run_id,'conclusion':run['conclusion'],'artifacts':acquired,'reconciled':run['conclusion']=='success'}))
