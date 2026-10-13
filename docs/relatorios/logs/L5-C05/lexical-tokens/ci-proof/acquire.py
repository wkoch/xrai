"""Authenticated acquisition of original own C05 GitHub CI artifacts as data."""
import datetime,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path('/Users/wkoch/Projetos/xrai')
sys.path.insert(0,str(ROOT/'eval/scripts'))
import reconcile_c05_ci as c
profile,run_text,head,output=sys.argv[1:]
run_id=int(run_text);out=Path(output);out.mkdir(parents=True,exist_ok=False)
commands=[]
def acquire(endpoint,name,cap):
 command=['gh','api',endpoint];p=subprocess.run(command,capture_output=True,check=False,timeout=180)
 (out/(name+'.stderr')).write_bytes(p.stderr)
 if p.returncode:raise RuntimeError(f'GitHub API {name} failed: {p.stderr.decode()}')
 if len(p.stdout)>cap:raise RuntimeError('API payload exceeds declared bound')
 (out/name).write_bytes(p.stdout);commands.append({'command':command,'filename':name,'bytes':len(p.stdout),'sha256':c.sha(p.stdout),'received_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 return p.stdout
run=c.decode(acquire(f'repos/wkoch/xrai/actions/runs/{run_id}','run.json',4*1024*1024))
jobs=c.decode(acquire(f'repos/wkoch/xrai/actions/runs/{run_id}/jobs?per_page=100','jobs.json',4*1024*1024))
artifacts=c.decode(acquire(f'repos/wkoch/xrai/actions/runs/{run_id}/artifacts?per_page=100','artifacts.json',4*1024*1024))
selected=[a for a in artifacts['artifacts'] if a['name']==c.config(profile)['artifact']]
if len(selected)!=1:raise RuntimeError('unique expected artifact absent')
artifact_id=selected[0]['id']
c.metadata(profile,run,jobs,artifacts,run_id,head,artifact_id)
raw=acquire(f'repos/wkoch/xrai/actions/artifacts/{artifact_id}/zip','original.zip',c.MAX_ZIP_BYTES)
version=subprocess.run(['gh','--version'],capture_output=True,check=True).stdout.decode()
(out/'acquisition.json').write_text(json.dumps({'schema':'xrai.eval.authenticated-original-acquisition.v1','authenticated_client':'gh API using configured credentials; credentials never exported','gh_version':version,'profile':profile,'run_id':run_id,'head_sha':head,'artifact_id':artifact_id,'acquisition_script_sha256':c.sha(Path(__file__).read_bytes()),'commands':commands,'local_native_executed':False,'provider_calls':0},indent=2)+'\n')
(out/'acquire.py').write_bytes(Path(__file__).read_bytes())
c.safe_export(c.zip_members(raw,profile),out/'export')
proof=c.reconcile(out,profile,run_id,head,artifact_id)
(out/'reconciliation.json').write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:proof[k] for k in ['verified','profile','run_id','code_commit','artifact_id','artifact_zip_bytes','exact_zip_export_files']}))
