"""Execute only the owned Store session in disposable Linux CI; preserve all frames."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import store_bridge_verify as v


def helper():
    path=v.ROOT/'crates/xrai-eval/harness/store_process_protocol.py'
    spec=importlib.util.spec_from_file_location('_c07_owned_store_process',path);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

class Peer:
    def __init__(self,process):self.process=process
    def call(self,request):
        if request['operation']=='close':return self.process.close(request['command_id'])
        return self.process.call(request)

def collect(binary,output):
    if platform.system()!='Linux' or os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Store native collector restricted to disposable Linux CI')
    _,cases=v.assets();binary=Path(binary).resolve(strict=True);output=Path(output)
    if binary.stat().st_size>v.MAX_FILE or not binary.read_bytes().startswith(b'\x7fELF'):raise ValueError('bounded owned Linux ELF required')
    output.mkdir(parents=True,exist_ok=False);(output/'inputs').mkdir();(output/'native-bin').mkdir();(output/'rebuild').mkdir()
    for name in v.INPUTS:shutil.copyfile(v.ASSETS/name,output/'inputs'/name);(output/'inputs'/name).chmod(0o400)
    retained=output/'native-bin/context-store-session';shutil.copyfile(binary,retained);retained.chmod(0o500);executable=str(retained.resolve(strict=True))
    receipt={'profile':'xrai.eval.store-bridge-receipt.v1','source_sha256':{p:v.sha((v.ROOT/p).read_bytes()) for p in v.SOURCES},'input_sha256':{p:v.sha((v.ASSETS/p).read_bytes()) for p in v.INPUTS},'binary':{'path':'native-bin/context-store-session','sha256':v.sha(retained.read_bytes()),'bytes':retained.stat().st_size},'executed_binary':executable,'environment':{'github_actions':os.environ['GITHUB_ACTIONS'],'system':platform.system(),'machine':platform.machine(),'github_sha':os.environ['GITHUB_SHA'],'github_run_id':os.environ['GITHUB_RUN_ID']},'admitted':False,'provider_used':False,'model_tokens':None}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    module=helper();processes=[]
    def run(path,selected,*,fresh=None):
        process=module.SessionProcess([executable]);processes.append(process)
        try:return v.run_plan(Peer(process),selected,fresh=fresh)[0]
        finally:
            if process.record()['active']:process.abort()
            path.write_text(json.dumps(process.record(),indent=2,sort_keys=True)+'\n')
    samples=run(output/'session.json',cases)
    for case in cases:run(output/'rebuild'/(case['id']+'.json'),[case],fresh=samples[case['id']])
    v.need(v.sha(retained.read_bytes())==receipt['binary']['sha256'],'executed ELF changed')
    result=v.verify(output);(output/'verification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True,type=Path);p.add_argument('--output',required=True,type=Path);args=p.parse_args();print(json.dumps(collect(args.binary,args.output),indent=2,sort_keys=True))
