"""Collect only the owned captured ESM semantic session in disposable Linux CI."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
from run_state_event import Process, successful
import verify_tsjs_semantic_session as v


def collect(binary, output):
    if platform.system() != 'Linux' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('owned native collection restricted to disposable Linux CI')
    v.assets()
    binary, output = Path(binary).resolve(strict=True), Path(output)
    if binary.stat().st_size > v.MAX_MEMBER or not binary.read_bytes().startswith(b'\x7fELF'):
        raise ValueError('bounded owned Linux ELF required')
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / 'inputs'; frozen.mkdir()
    for name in v.INPUTS:
        shutil.copyfile(v.ASSETS / name, frozen / name)
        (frozen / name).chmod(0o400)
    retained = output / 'native-bin/tsjs-semantic-session'
    retained.parent.mkdir()
    shutil.copyfile(binary, retained); retained.chmod(0o500)
    retained = retained.resolve(strict=True)
    m = {'schema':'xrai.eval.tsjs-semantic-session-receipt.v1',
         'source_sha256':{n:v.sha((v.ROOT / n).read_bytes()) for n in v.SOURCES},
         'input_sha256':{n:v.sha((frozen / n).read_bytes()) for n in v.INPUTS},
         'binary':{'path':'native-bin/tsjs-semantic-session','sha256':v.sha(retained.read_bytes()),'bytes':retained.stat().st_size},
         'environment':{'platform':platform.platform(),'machine':platform.machine(),
                        'github_sha':os.environ['GITHUB_SHA'],'github_run_id':os.environ['GITHUB_RUN_ID']},
         'scope':v.PROFILE,'strategy':v.STRATEGY,'normalization':[],'admitted':False,
         'competitive_runs_allowed':False,'quota_event_credit':False,'new_eligible_dossier':False,
         'native_process_helper_frame_bytes':v.FRAME}
    (output / 'receipt.json').write_text(json.dumps(m,indent=2) + '\n')
    a,b,invalid,p = [v.decode((frozen / name).read_bytes()) for name in
                     ['input-a.json','input-b.json','input-invalid.json','protocol.json']]
    live, fresh = None, None
    try:
        live = Process(retained, output / 'incremental')
        opened = successful(live.call({'operation':'open','input':a}))
        expected = v.requests(a,b,invalid,opened['snapshot_id'],p['queries'])
        for request in expected[1:-1]:
            response = live.call(request)
            refused = request['operation'] == 'update' and (
                request['expected_snapshot'] == 'intentionally-stale-revision' or
                request['input']['configuration']['module'] != 'esm')
            if refused:
                if response['status'] != 'error':
                    raise ValueError('frozen stale/configuration update accepted')
            else:
                successful(response)
        live.close()
        fresh = Process(retained, output / 'rebuild')
        for request in v.requests(a,b,invalid,opened['snapshot_id'],p['queries'],fresh=True)[:-1]:
            successful(fresh.call(request))
        fresh.close()
        if v.sha(retained.read_bytes()) != m['binary']['sha256']:
            raise ValueError('executed retained native bytes changed')
        for name, digest in m['source_sha256'].items():
            if v.sha((v.ROOT / name).read_bytes()) != digest:
                raise ValueError('consumed source/verifier changed during trial')
        result = v.verify(output)
        (output / 'verification.json').write_text(json.dumps(result,indent=2,sort_keys=True) + '\n')
        return result
    finally:
        for process in [live,fresh]:
            if process and process.process.poll() is None:
                process.abort()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.binary,args.output),indent=2,sort_keys=True))
