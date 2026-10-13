"""Execute three frozen presence events in disposable CI, using only owned Rust."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
from run_state_event import Process, successful
from verify_presence_event import SOURCES, PROFILE, verify, sha, ROOT
import prepare_state_events


def collect(binary, output, folder):
    if platform.system()!='Linux' or os.environ.get('GITHUB_ACTIONS')!='true':
        raise ValueError('owned native collection restricted to disposable Linux CI')
    prepare_state_events.verify()
    assets=ROOT/'eval/qualification/state-events'/folder
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    frozen=output/'inputs';frozen.mkdir()
    for name in ['descriptor.json','a.json','b.json','queries.json','oracle.json']:shutil.copyfile(assets/name,frozen/name)
    retained=output/'native-bin/source-presence-session';retained.parent.mkdir();shutil.copyfile(binary,retained);retained.chmod(0o500)
    retained=retained.resolve(strict=True)
    d,a,b,queries=[json.loads((frozen/n).read_bytes())for n in ['descriptor.json','a.json','b.json','queries.json']]
    m={'schema':'xrai.eval.c04.source-presence.receipt.v1','family':d['family'],'task_id':d['task_id'],'slot_id':d['slot_id'],
       'descriptor_sha256':sha((frozen/'descriptor.json').read_bytes()),
       'input_sha256':{n:sha((frozen/n).read_bytes())for n in ['a.json','b.json','queries.json','oracle.json']},
       'source_sha256':{n:sha((ROOT/n).read_bytes())for n in SOURCES},
       'binary':{'path':'native-bin/source-presence-session','sha256':sha(retained.read_bytes()),'bytes':retained.stat().st_size},
       'environment':{'platform':platform.platform(),'machine':platform.machine(),'github_sha':os.environ['GITHUB_SHA'],'github_run_id':os.environ['GITHUB_RUN_ID']},
       'scope':PROFILE,'strategy':'conservative_full_rebuild','normalization':[],'admitted':False,'competitive_runs_allowed':False}
    (output/'receipt.json').write_text(json.dumps(m,indent=2)+'\n')
    live,fresh=None,None
    try:
        live=Process(retained,output/'incremental');opened=successful(live.call({'operation':'open','input':a}))
        successful(live.call({'operation':'snapshot'}))
        qr=[{'operation':'query',**{k:q[k]for k in ['kind','path']}}for q in queries]
        for q in qr:successful(live.call(q))
        rejected=live.call({'operation':'update','expected_snapshot':'intentionally-stale-revision','input':b})
        if rejected['status']!='error':raise ValueError('stale revision accepted')
        successful(live.call({'operation':'snapshot'}))
        successful(live.call({'operation':'update','expected_snapshot':opened['snapshot_id'],'input':b}))
        successful(live.call({'operation':'snapshot'}))
        for q in qr:successful(live.call(q))
        live.close()
        fresh=Process(retained,output/'rebuild');successful(fresh.call({'operation':'open','input':b}));successful(fresh.call({'operation':'snapshot'}))
        for q in qr:successful(fresh.call(q))
        fresh.close()
        if sha(retained.read_bytes())!=m['binary']['sha256']:raise ValueError('consumed binary changed')
        result=verify(output);(output/'verification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        return result
    finally:
        if live:live.abort()
        if fresh:fresh.abort()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();binary=args.binary.resolve(strict=True);args.output.mkdir(parents=True,exist_ok=False)
    results={folder:collect(binary,args.output/folder,folder)for folder in ['js','python','go']}
    print(json.dumps({'schema':'xrai.eval.c04.presence-batch.v1','events':results,'admitted':False,'competitive_runs_allowed':False},indent=2,sort_keys=True))
