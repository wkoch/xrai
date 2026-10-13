"""Read-only complete consumer receipt and public guarded replay verification."""
from pathlib import Path
import argparse
import io
import stat
import zipfile
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'crates/xrai-eval/harness'))
from guarded_smoke import (owned,decode,canonical,sha,require,exact,source_hashes,frozen,
    verify_record,VERSION,MAX_MANIFEST,MAX_RECORD_BYTES,MAX_OUTPUT,DESIGN)


def verify_members(members):
    require(type(members) is dict and set(members)=={'receipt.json'}|{f'case-{n:02}.json' for n in range(10)},'exact output closure; incidents/extra files refused')
    require(all(type(raw) is bytes and 0<len(raw)<=MAX_RECORD_BYTES for raw in members.values()) and sum(map(len,members.values()))<=MAX_OUTPUT,'bounded actual artifact members')
    receipt=decode(members['receipt.json'])
    require(members['receipt.json']==canonical(receipt),'canonical receipt')
    require(type(receipt) is dict and set(receipt)=={'schema_version','freeze_sha256','source_hashes','records','provider_calls','agent_runs','campaign_scoring_enabled','provider_charge','provider_usage','model_tokens'} and receipt['schema_version']==VERSION,'exact consumer receipt')
    require(receipt['freeze_sha256']==sha(owned(DESIGN/'freeze.json',MAX_MANIFEST)) and exact(receipt['source_hashes'],source_hashes()),'frozen input/current consumer method closure')
    scenarios,_=frozen()
    require(type(receipt['records']) is list and len(receipt['records'])==10,'complete ten scenario receipts')
    result=[];total=0
    for n,(entry,scenario) in enumerate(zip(receipt['records'],scenarios)):
        require(type(entry) is dict and set(entry)=={'path','sha256','bytes','scenario_id'} and entry['path']==f'case-{n:02}.json' and entry['scenario_id']==scenario['scenario_id'],'exact ordered record identity')
        raw=members[entry['path']];total+=len(raw)
        require(total<=MAX_OUTPUT and type(entry['bytes']) is int and len(raw)==entry['bytes'] and sha(raw)==entry['sha256'],'actual record hash/byte ceiling')
        record=decode(raw,MAX_RECORD_BYTES)
        require(raw==canonical(record) and exact(record['scenario'],scenario),'canonical exact frozen consumer artifact')
        result.append(verify_record(record))
    require(all(type(receipt[k]) is int and receipt[k]==0 for k in ('provider_calls','agent_runs')) and receipt['campaign_scoring_enabled'] is False and all(receipt[k] is None for k in ('provider_charge','provider_usage','model_tokens')),'fake-only unknown provider/tokens')
    return {'schema_version':'xrai.eval.guarded-smoke-verification.v3','verified':True,'records':result,'source_files':22,'source_bytes':54032,'provider_calls':0,'agent_runs':0,'campaign_scoring_enabled':False,'provider_charge':None,'provider_usage':None,'model_tokens':None}


def verify(output):
    output=Path(output)
    expected={'receipt.json'}|{f'case-{n:02}.json' for n in range(10)}
    require(output.is_dir() and not output.is_symlink() and {p.name for p in output.iterdir()}==expected,'exact ordinary output closure')
    return verify_members({name:owned(output/name,MAX_RECORD_BYTES) for name in expected})


def verify_archive(path):
    raw=owned(path,MAX_OUTPUT)
    members={}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries=archive.infolist()
        expected={'receipt.json'}|{f'case-{n:02}.json' for n in range(10)}
        require(len(entries)==11 and {entry.filename for entry in entries}==expected,'exact unique normalized ZIP closure')
        require(sum(entry.file_size for entry in entries)<=MAX_OUTPUT,'declared expanded ZIP byte bound')
        for entry in entries:
            mode=entry.external_attr>>16
            require(not entry.is_dir() and not entry.flag_bits&1 and stat.S_IFMT(mode) in (0,stat.S_IFREG) and 0<entry.file_size<=MAX_RECORD_BYTES,'ordinary unencrypted bounded ZIP member')
            with archive.open(entry) as stream: data=stream.read(MAX_RECORD_BYTES+1)
            require(len(data)==entry.file_size,'actual expanded member byte bound/CRC')
            members[entry.filename]=data
    return verify_members(members)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output',type=Path)
    group.add_argument('--archive',type=Path)
    args=parser.parse_args()
    try:print(canonical(verify_archive(args.archive) if args.archive else verify(args.output)).decode())
    except (ValueError,KeyError,TypeError,OSError,zipfile.BadZipFile) as error:
        print(str(error),file=sys.stderr);raise SystemExit(1)
