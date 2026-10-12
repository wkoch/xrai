"""A→B executor against a preserved external process (development hash inventory)."""
import argparse
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import tempfile
import time

from runner import ROOT, canonical, payload, sandbox, sha
from materialize_task import apply_event, materialize


class Session:
    def __init__(self, binary, workspace):
        self.profiles = tempfile.TemporaryDirectory(prefix='xrai-incremental-profile-')
        self.command = [str(Path(binary).resolve(strict=True)), '.']
        wrapped, self.mechanism = sandbox(self.command, workspace, self.profiles.name)
        self.process = subprocess.Popen(wrapped, cwd=workspace, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        env={'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8'}, start_new_session=True)
        self.buffer = b''
        self.selector = selectors.DefaultSelector()
        for name in ['stdout','stderr']:
            pipe = getattr(self.process,name)
            os.set_blocking(pipe.fileno(),False)
            self.selector.register(pipe,selectors.EVENT_READ,name)

    def query(self, operation):
        start=time.monotonic()
        self.process.stdin.write((operation+'\n').encode())
        self.process.stdin.flush()
        errors=b''
        data=b''
        while time.monotonic()-start < 5:
            for event,_ in self.selector.select(.05):
                chunk=os.read(event.fd,65536)
                if event.data=='stderr':
                    errors+=chunk
                else:
                    self.buffer+=chunk
                if len(data)+len(self.buffer)+len(errors)>1024*1024:
                    raise RuntimeError('incremental output limit')
                if not chunk:
                    raise RuntimeError(f'probe closed stream: {errors.decode(errors="replace")}')
            while b'\n' in self.buffer:
                line,self.buffer=self.buffer.split(b'\n',1)
                data+=line+b'\n'
                if len(data)+len(errors)>1024*1024:
                    raise RuntimeError('incremental output limit')
                if line.startswith(b'END\t'):
                    pid,checkout=line.decode().split('\t')[1:]
                    sources={}
                    for row in data.splitlines():
                        if row.startswith(b'SOURCE\t'):
                            _,path,digest=row.decode().split('\t')
                            sources[path]=digest
                        elif row.startswith(b'DIAGNOSTIC\t'):
                            raise RuntimeError('unexpected inventory diagnostic '+row.decode())
                    return {'operation':operation,'pid':int(pid),'checkout_id':checkout,'sources':sources,
                            'sources_sha256':sha(canonical(sources)), 'elapsed_seconds':time.monotonic()-start,
                            'stdout':payload(data,len(data)), 'stderr':payload(errors,len(errors)),
                            'sandbox':self.mechanism}
        raise TimeoutError('incremental probe timeout')

    def close(self):
        try:
            os.killpg(self.process.pid,signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait(timeout=5)
        self.selector.close()
        for name in ['stdin','stdout','stderr']:
            getattr(self.process,name).close()
        self.profiles.cleanup()


def verify(binary,output):
    tasks=[json.loads(line) for line in (ROOT/'eval/tasks/dev.jsonl').read_text().splitlines()]
    chosen={}
    for task in tasks:
        if task['input'].get('state_changes'):
            chosen.setdefault(task['family'],task)
    receipts=[]
    for task in chosen.values():
        with tempfile.TemporaryDirectory(prefix='xrai-event-') as tmp:
            materialize(task['id'],tmp,phase='A')
            workspace=Path(tmp)/'workspace'
            original=Session(binary,workspace)
            try:
                a=original.query('INDEX')
                warm=original.query('QUERY')
                event=apply_event(task['id'],workspace)
                still_a=original.query('QUERY')
                b=original.query('UPDATE')
                query_b=original.query('QUERY')
                rebuilt=Session(binary,workspace)
                try:
                    full_b=rebuilt.query('INDEX')
                finally:
                    rebuilt.close()
                assert a['sources']==warm['sources']==still_a['sources']
                assert a['sources']!=b['sources']
                assert b['sources']==query_b['sources']==full_b['sources']
                assert len({frame['pid'] for frame in [a,warm,still_a,b,query_b]})==1
                assert len({frame['checkout_id'] for frame in [a,warm,still_a,b,query_b]})==1
                # Compare event hashes independently: parent SHA-256 vs index BLAKE3
                # comes from cold materialization plus an independent fresh process.
                with tempfile.TemporaryDirectory(prefix='xrai-event-cold-') as cold:
                    materialize(task['id'],cold)
                    cold_bytes={str(p.relative_to(Path(cold)/'workspace')):sha(p.read_bytes())
                                for p in (Path(cold)/'workspace').rglob('*') if p.is_file()}
                    b_bytes={str(p.relative_to(workspace)):sha(p.read_bytes())
                             for p in workspace.rglob('*') if p.is_file()}
                    assert b_bytes==cold_bytes
                receipts.append({'task_id':task['id'],'family':task['family'],
                                 'mode':'incremental_same_process', 'prototype':'hash_inventory_probe',
                                 'event':event, 'phases':[a,warm,still_a,b,query_b,full_b],
                                 'cold_B_comparison':'equal_source_bytes',
                                 'limitation':'inventory update; semantic retrieval/staleness and model success not measured'})
            finally:
                original.close()
    assert len(receipts)==4, 'one incremental event per family required'
    result={'schema_version':'xrai.eval.incremental.v1','events':receipts,'count':len(receipts),
            'executor_sha256':sha(Path(__file__).read_bytes()),
            'probe_binary_sha256':sha(Path(binary).read_bytes())}
    Path(output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    return {'count':len(receipts),'status':'same_process_and_rebuild_verified'}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(verify(args.binary,args.output),indent=2))
