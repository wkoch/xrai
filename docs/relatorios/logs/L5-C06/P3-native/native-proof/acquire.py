"""Authenticated original C06 CI archive acquisition; owned Python replay only."""
import datetime,json,stat,subprocess,sys,zipfile,io
from pathlib import Path
ROOT=Path('/Users/wkoch/Projetos/xrai');sys.path.insert(0,str(ROOT/'eval/scripts'))
import reconcile_c06_p3_ci as c
run_id=int(sys.argv[1]);head=sys.argv[2];out=Path(sys.argv[3]);mode=sys.argv[4] if len(sys.argv)>4 else 'success'
c.need(mode in ('success','failure'),'known acquisition mode');out.mkdir(parents=True,exist_ok=False)
commands=[]
def acquire(endpoint,name,cap):
 cmd=['gh','api',endpoint];p=subprocess.run(cmd,capture_output=True,timeout=180,check=False);(out/(name+'.stderr')).write_bytes(p.stderr)
 c.need(p.returncode==0,'authenticated gh API failed');c.need(len(p.stdout)<=cap,'bounded API payload');(out/name).write_bytes(p.stdout)
 commands.append({'command':cmd,'filename':name,'bytes':len(p.stdout),'sha256':c.sha(p.stdout),'received_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()});return p.stdout
run=c.decode(acquire(f'repos/wkoch/xrai/actions/runs/{run_id}','run.json',4*1024*1024));jobs=c.decode(acquire(f'repos/wkoch/xrai/actions/runs/{run_id}/jobs?per_page=100','jobs.json',4*1024*1024));artifacts=c.decode(acquire(f'repos/wkoch/xrai/actions/runs/{run_id}/artifacts?per_page=100','artifacts.json',4*1024*1024))
a=[x for x in artifacts['artifacts'] if x['name']==c.CONFIG['artifact']];c.need(len(a)==1,'exact expected artifact');a=a[0]
c.need(run['id']==run_id and run['head_sha']==head and run['path']==c.CONFIG['workflow'] and run['run_attempt']==1 and run['status']=='completed' and run['conclusion']==mode,'exact completed requested head/run/outcome')
raw=acquire(f'repos/wkoch/xrai/actions/artifacts/{a["id"]}/zip','original.zip',c.MAX_ZIP_BYTES);c.need(c.sha(raw)==a['digest'][7:] and len(raw)==a['size_in_bytes'],'original archive API digest/size')
if mode=='success':
 c.metadata(run,jobs,artifacts,run_id,head,a['id']);members=c.zip_members(raw)
else:
 members={};total=0;allowed=c.TOP|{'event/'+name for name in c.EVENT}
 with zipfile.ZipFile(io.BytesIO(raw)) as archive:
  c.need(len(archive.infolist())<=1024,'partial ZIP member cap')
  for entry in archive.infolist():
   c.need(not entry.is_dir() and entry.filename in allowed and entry.filename not in members and not entry.flag_bits&1 and stat.S_IFMT(entry.external_attr>>16) in (0,stat.S_IFREG),'bounded known regular partial member')
   c.need(0<=entry.file_size<=32*1024*1024,'partial member cap');total+=entry.file_size;c.need(total<=128*1024*1024,'partial expansion cap');data=archive.read(entry);c.need(len(data)==entry.file_size,'partial actual member bytes');members[entry.filename]=data
c.safe_export(members,out/'export');(out/'acquire.py').write_bytes(Path(__file__).read_bytes())
(out/'acquisition.json').write_text(json.dumps({'schema':'xrai.eval.c06.authenticated-original-acquisition.v1','client':'authenticated gh API; credentials never exported','run_id':run_id,'head_sha':head,'artifact_id':a['id'],'outcome':mode,'exact_acquired_files':len(members),'acquisition_script_sha256':c.sha(Path(__file__).read_bytes()),'commands':commands,'local_native_executed':False,'provider_calls':0,'failure_not_successful_acceptance':mode=='failure'},indent=2)+'\n')
if mode=='success':
 proof=c.reconcile(out,run_id,head,a['id']);(out/'reconciliation.json').write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n');print(json.dumps({k:proof[k] for k in ['verified','run_id','artifact_id','artifact_zip_bytes','exact_zip_export_files']}))
else:print(json.dumps({'preserved_failed_run':run_id,'artifact_id':a['id'],'files':len(members),'artifact_zip_sha256':c.sha(raw)}))
