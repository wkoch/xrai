"""Run only owned P3 typed presence-context process in disposable Linux CI."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
from run_state_event import Process
import p3_diff_native_verify as v


def collect(binary,output):
    if platform.system()!='Linux' or os.environ.get('GITHUB_ACTIONS')!='true':
        raise ValueError('owned native P3 collector restricted to disposable Linux CI')
    v.assets();binary=Path(binary).resolve(strict=True);output=Path(output)
    if binary.stat().st_size>v.MAX_FILE or not binary.read_bytes().startswith(b'\x7fELF'):
        raise ValueError('bounded owned Linux ELF required')
    output.mkdir(parents=True,exist_ok=False);(output/'inputs').mkdir();(output/'native-bin').mkdir()
    for n in v.INPUTS:shutil.copyfile(v.ASSETS/n,output/'inputs'/n);(output/'inputs'/n).chmod(0o400)
    retained=output/'native-bin/context-diff-spike';shutil.copyfile(binary,retained);retained.chmod(0o500)
    receipt={'schema':'xrai.eval.p3-diff-native-receipt.v1','source_sha256':{n:v.sha((v.ROOT/n).read_bytes()) for n in v.SOURCES},
        'input_sha256':{n:v.sha((v.ASSETS/n).read_bytes()) for n in v.INPUTS},
        'binary':{'path':'native-bin/context-diff-spike','sha256':v.sha(retained.read_bytes()),'bytes':retained.stat().st_size},
        'environment':{'github_actions':os.environ['GITHUB_ACTIONS'],'system':platform.system(),'machine':platform.machine(),
                       'github_sha':os.environ['GITHUB_SHA'],'github_run_id':os.environ['GITHUB_RUN_ID']},
        'admitted':False,'quota_event_credit':False,'competitive_runs_allowed':False,'new_eligible_dossier':False}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    process=None;fresh=None
    try:
        process=Process(retained.resolve(strict=True),output/'session')
        commands=v.commands(process.process.pid,output/'inputs')
        for request,expected in commands[:-1]:
            actual=process.call(request)
            if actual!=expected:raise ValueError('native typed reconstruction/context mismatch; transcript retained')
        process.close()
        fresh=Process(retained.resolve(strict=True),output/'rebuild')
        for request,expected in v.commands(fresh.process.pid,output/'inputs',fresh=True)[:-1]:
            actual=fresh.call(request)
            if actual!=expected:raise ValueError('independent native rebuild mismatch; transcript retained')
        fresh.close()
        if v.sha(retained.read_bytes())!=receipt['binary']['sha256']:raise ValueError('executed ELF changed')
        result=v.verify(output);(output/'verification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');return result
    finally:
        for p in [process,fresh]:
            if p and p.process.poll() is None:p.abort()

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--binary',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
    print(json.dumps(collect(a.binary,a.output),indent=2,sort_keys=True))
