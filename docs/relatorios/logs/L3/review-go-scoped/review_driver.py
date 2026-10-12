import sys,json,pathlib,os,tempfile,hashlib
root=pathlib.Path('/Users/wkoch/Projetos/xrai');sys.path.insert(0,str(root/'eval/scripts'))
import run_vertical_probes as runner
out=root/'docs/relatorios/logs/L3/review-go-scoped';out.mkdir(exist_ok=False)
cache=pathlib.Path('/private/tmp/xrai-l3-corpus');checkout=pathlib.Path(tempfile.mkdtemp(prefix='xrai-review-go-scoped-'))
case=next(c for c in json.loads((root/'eval/qualification/vertical/selection.json').read_text())['cases'] if c['key']=='prometheus')
manifest=json.loads((root/'eval/sources/manifest.json').read_text())
probe=json.loads((root/'eval/qualification/vertical/oracles/prometheus/probe.json').read_text())
source=runner.materialize_base(case,checkout,manifest)
hidden=runner.hidden_files('prometheus',checkout)
env=dict(os.environ);env.update(GOMODCACHE=str(cache/'gomodcache'),GOCACHE=str(checkout/'gocache'),GOTOOLCHAIN='local',GOMAXPROCS='2',GOFLAGS='-mod=readonly',GOPROXY='off',GOSUMDB='off')
go='/opt/homebrew/bin/go'
version,text=runner.run_process([go,'version'],checkout,env,out,'tool-go');assert runner.succeeded(version) and text.startswith('go version go1.27.2 ')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bind={'reviewer':'/root/l3_containment','schema_version':'xrai.eval.independent.scoped-patch.v1','competitive_runs_allowed':False,'runner_sha256':sha(root/'eval/scripts/run_vertical_probes.py'),'review_script_sha256':sha(pathlib.Path(__file__)),'source':source,'checkout':str(checkout),'hidden_inputs':hidden,'initial_module_sha256':{n:sha(checkout/n) for n in probe['source_fingerprints']['base']},'phases':[]}
assert bind['initial_module_sha256']==probe['source_fingerprints']['base']
(out/'case.json').write_text(json.dumps(bind,indent=2)+'\n')
command=[go,'test','-mod=readonly','-p','2','./storage/remote','-run','^TestCalculateDesiredShardsDetail$','-count=1','-v']
record,text=runner.run_process(command,checkout,env,out,'baseline')
bind['phases'].append({'phase':'baseline','probe':record,'classification':runner.verdict('prometheus','baseline',record,text)})
(out/'case.json').write_text(json.dumps(bind,indent=2)+'\n')
assert bind['phases'][-1]['classification']=='baseline_regression_reproduced'
patch=root/'eval/qualification/vertical/oracles/prometheus/reference.patch'
record,text=runner.run_process(['/usr/bin/patch','-p1','-i',str(patch)],checkout,env,out,'apply-scoped-patch');assert runner.succeeded(record)
after={n:sha(checkout/n) for n in probe['source_fingerprints']['base']}
assert after['storage/remote/queue_manager.go']==probe['source_fingerprints']['reference']['storage/remote/queue_manager.go']
assert after['storage/remote/write.go']==probe['source_fingerprints']['base']['storage/remote/write.go']
bind['scoped_patch']={'path':str(patch),'sha256':sha(patch),'receipt':record,'module_sha256_after':after,'only_queue_manager_changed':True,'upstream_write_go_wal_change_excluded':True}
command=[go,'test','-mod=readonly','-p','2','./storage/remote','-run','^TestCalculateDesiredShards','-count=1','-v']
record,text=runner.run_process(command,checkout,env,out,'scoped-reference')
bind['phases'].append({'phase':'scoped_reference','probe':record,'classification':runner.verdict('prometheus','reference',record,text)})
bind['status']='verified' if bind['phases'][-1]['classification']=='reference_pass' else 'failed'
bind['lock_sha256']={n:sha(checkout/n) for n in ['go.mod','go.sum']}
(out/'case.json').write_text(json.dumps(bind,indent=2)+'\n')
print(bind['status'],checkout,flush=True)
sys.exit(0 if bind['status']=='verified' else 1)
