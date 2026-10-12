"""Validate local result schema and replay every captured transcript."""
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from runner import replay


def verify(directory):
    validators={}
    for version, filename in [('xrai.eval.local.v1','result.schema.json'), ('xrai.eval.local.v2','result-v2.schema.json')]:
        schema=json.loads((Path(__file__).parent/filename).read_text())
        Draft202012Validator.check_schema(schema)
        validators[version]=Draft202012Validator(schema)
    rows=[]
    for path in sorted(Path(directory).glob('D0-*.json')):
        record=json.loads(path.read_text())
        validators[record['schema_version']].validate(record)
        if record['run_kind']!='scripted_retrieval':
            raise ValueError('local baseline must identify scripted retrieval')
        rows.append({'task_id':record['task_id'],'replay':replay(record)})
    if len(rows)!=20 or len({r['task_id'] for r in rows})!=20:
        raise ValueError('all 20 unique D0 transcripts required')
    return {'count':len(rows),'status':'schema_and_replay_passed','records':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('directory')
    args=parser.parse_args()
    print(json.dumps(verify(args.directory),indent=2))
