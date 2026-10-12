from pathlib import Path
import json, hashlib, re
root=Path('docs/relatorios/logs/L3'); run=json.loads((root/'ci-native-run.json').read_text()); assert run['conclusion']=='success' and run['headSha']=='21e9279a7502ed398e3b1d8321495142376e78af' and len(run['jobs'])==3 and all(j['conclusion']=='success' for j in run['jobs'])
rows=[]
for p in sorted((root/'ci-native').glob('native-*')):
 env=json.loads((p/'environment.json').read_text()); w=json.loads((p/'workers.json').read_text()); fs=json.loads((p/'filesystem.json').read_text()); pack=json.loads((p/'packaging.json').read_text()); inc=json.loads((p/'incremental.json').read_text()); tests=(p/'workspace-tests.log').read_text(); harness=(p/'harness-tests.log').read_text()
 assert len(w['cases'])==3 and all(c['logical_equivalence'] and c['repetitions']==6 and len(c['pool_samples_ms'])==6 and len(c['direct_samples_ms'])==6 for c in w['cases'])
 assert w['cpu_seconds'] is None and w['rss_aggregate_bytes'] is None and w['workers']==2 and w['source_limit']==8388608 and w['aggregate_limit']==67108864
 assert fs['read_limit_bytes']==8388608 and fs['native_filename_valid_control_passed'] and fs['permission_denial_supported'] and 'not-atomic-snapshot' in fs['consistency_model']
 assert len(pack['fixtures'])==14 and all(f['exit_code']==(0 if f['state']=='valid' else 2) and f['parsed']['complete']==(f['state']=='valid') for f in pack['fixtures']) and all(pack['isolation_negative_probes'].values()) and pack['paid_campaign_executed'] is False
 assert inc['count']==4 and all(e['original_child_cleanup']['status']==e['rebuild_child_cleanup']['status']=='child_reaped' for e in inc['events'])
 assert all(len({f['pid'] for f in e['phases'][:5]})==1 and e['phases'][3]['sources']==e['phases'][5]['sources'] for e in inc['events'])
 assert '13 passed; 0 failed' in tests and '14 passed; 0 failed' in tests
 anchored=21 if env['system']=='Linux' else 20; assert f'{anchored} passed; 0 failed' in tests
 assert 'Ran 31 tests' in harness and ('OK (skipped=1)' if env['system']=='Linux' else 'OK (skipped=5)') in harness
 rows.append({'host':p.name,'environment':env,'filesystem_tests':anchored+14,'filesystem_resolution':fs['capture_resolution'],'workers_tests':13,'worker_equivalent_roundtrips':18,'incremental_events':4,'packaging_fixtures':14,'negative_packaging_probes':pack['isolation_negative_probes'],'harness_tests':31,'harness_skips':1 if env['system']=='Linux' else 5,'literal_macos_15_0_proved':False,'worker_cpu_rss_proved':False})
print(json.dumps({'status':'native_receipts_verified','code_commit':run['headSha'],'run_url':run['url'],'hosts':rows,'competitive_runs_allowed':False},indent=2))
