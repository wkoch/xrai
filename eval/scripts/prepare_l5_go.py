#!/usr/bin/env python3
"""Capture/verify pinned Gitea data. Never import or execute captured source."""
import argparse
import difflib
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT=Path(__file__).resolve().parents[2]
CASE=ROOT/'eval/qualification/l5-real/go'
COMMIT='8eefa1f6dedf2488db2c9e12c916e8e51f673160'
ARCHIVE_SHA='3cd918c96a563db6a64e8c9717d556097240de799f9f0948ba50060e6143c190'
EXCLUDE={'tests','test','testdata','fixtures','docs','doc','examples','vendor','vendored','node_modules','build','dist','generated','.git','assets'}
PATHS=['services/convert/repository.go','models/repo/repo.go','modules/util/url.go']

def sha(data): return hashlib.sha256(data).hexdigest()
def canonical(data): return json.dumps(data,sort_keys=True,separators=(',',':')).encode()
def source_tree(archive):
    seen={}
    with tarfile.open(archive) as tree:
        for member in tree:
            p=PurePosixPath(member.name)
            if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!='gitea-'+COMMIT:
                raise ValueError('unsafe or unpinned source member')
            if member.isdir(): continue
            name=str(PurePosixPath(*p.parts[1:]))
            if not member.isfile() or len(p.parts)<2 or name in seen:
                raise ValueError('nonregular or duplicate source member')
            seen[name]=(tree.extractfile(member).read(),member.mode&0o777)
    return seen

def production(path,blob):
    p=PurePosixPath(path)
    if p.suffix!='.go': return 'not_go_source'
    if any(x.lower() in EXCLUDE for x in p.parts): return 'excluded_directory'
    if p.name.endswith('_test.go'): return 'test_filename'
    if any(x in blob[:2048].lower() for x in [b'code generated',b'do not edit',b'@generated',b'automatically generated']):return 'generated_marker'
    return None

def inventory(tree):
    rows=[]
    for name,(data,mode) in sorted(tree.items()):
        reason=production(name,data)
        rows.append({'path':name,'bytes':len(data),'sha256':sha(data),'mode':mode,'production_nonempty_lines':0 if reason else sum(bool(x.strip()) for x in data.splitlines()),'exclusion':reason})
    return {'method':'xrai.production.go.conservative-path-marker.v1','comments_included':True,'exclusions':sorted(EXCLUDE),'file_count':len(rows),'source_bytes':sum(x['bytes'] for x in rows),'production_files':sum(x['production_nonempty_lines']>0 for x in rows),'production_nonempty_lines':sum(x['production_nonempty_lines'] for x in rows),'files':rows}

def reference(base):
    old=b'\tu.User = nil\n\treturn u.String(), nil\n'
    new=b'''\tu.User = nil
\tquery, err := url.ParseQuery(u.RawQuery)
\tif err != nil {
\t\treturn "", err
\t}
\tchanged := false
\tfor key := range query {
\t\tswitch strings.ToLower(key) {
\t\tcase "token", "access_token", "password":
\t\t\tquery.Del(key)
\t\t\tchanged = true
\t\t}
\t}
\tif changed {
\t\tu.RawQuery = query.Encode()
\t}
\treturn u.String(), nil
'''
    if base.count(old)!=1: raise ValueError('reference anchor changed')
    return base.replace(old,new)

def patch(base,ref):
    return ''.join(difflib.unified_diff(base.decode().splitlines(keepends=True),ref.decode().splitlines(keepends=True),fromfile='a/modules/util/url.go',tofile='b/modules/util/url.go')).encode()

def capture():
    tree=source_tree(CASE/'sources/base.tar.gz'); inv=inventory(tree)
    (CASE/'sources/base-inventory.json.gz').write_bytes(gzip.compress(canonical(inv),mtime=0))
    (CASE/'LICENSE.gitea').write_bytes(tree['LICENSE'][0])
    for p in ['go.mod','go.sum']:
        (CASE/'setup'/p).write_bytes(tree[p][0])
    base=tree['modules/util/url.go'][0];ref=reference(base)
    (CASE/'oracles/reference-url.go').write_bytes(ref)
    (CASE/'oracles/reference.patch').write_bytes(patch(base,ref))
    anchors=[]
    for path,needles in [('services/convert/repository.go',['func innerToRepo(', 'OriginalURL:                   repo.SanitizedOriginalURL(),']),('models/repo/repo.go',['func (repo *Repository) SanitizedOriginalURL()', 'util.SanitizeURL(repo.OriginalURL)']),('modules/util/url.go',['func SanitizeURL(s string)', 'u.User = nil'])]:
        data=tree[path][0];ls=data.decode().splitlines();spans=[]
        for needle in needles:
            hits=[i for i,l in enumerate(ls) if needle in l]
            if len(hits)!=1:raise ValueError('ambiguous anchor '+needle)
            i=hits[0];spans.append({'needle':needle,'line':i+1,'excerpt':'\n'.join(ls[max(0,i-2):i+4])})
        anchors.append({'path':path,'sha256':sha(data),'anchors':spans})
    rel={'source_commit':COMMIT,'modules':anchors,'subsystems':['services/convert','models/repo','modules/util'],'edges':[{'from':PATHS[0],'to':PATHS[1],'relation':'innerToRepo builds public API Repository.OriginalURL from Repository.SanitizedOriginalURL'}, {'from':PATHS[1],'to':PATHS[2],'relation':'SanitizedOriginalURL delegates nonempty OriginalURL to util.SanitizeURL'}],'necessity':'The contract concerns public API original_url: converter chooses exposed field, repository model chooses sanitizer, utility handles decoded query names. Probe exercises all three modules; only utility requires patch.','review':'author source inspection; independent reader pending'}
    (CASE/'oracles/source-relations.json').write_text(json.dumps(rel,indent=2)+'\n')
    receipt={'repository':'go-gitea/gitea','commit':COMMIT,'version':'v1.22.6','origin':'controlled_contract_change','historical_change_claimed':False,'archive_url':'https://codeload.github.com/go-gitea/gitea/tar.gz/'+COMMIT,'archive_sha256':sha((CASE/'sources/base.tar.gz').read_bytes()),'archive_bytes':(CASE/'sources/base.tar.gz').stat().st_size,'inventory_sha256':sha((CASE/'sources/base-inventory.json.gz').read_bytes()),'production_floor':{k:inv[k] for k in ['method','comments_included','production_files','production_nonempty_lines']},'license_spdx':'MIT','license_sha256':sha(tree['LICENSE'][0]),'setup':{p:sha(tree[p][0]) for p in ['go.mod','go.sum']},'toolchain':'go1.22.12','behavioral_execution':'not_run','admitted':False,'competitive_runs_allowed':False}
    (CASE/'capture.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

def verify():
    case=json.loads((CASE/'case.json').read_text());cap=json.loads((CASE/'capture.json').read_text())
    tree=source_tree(CASE/'sources/base.tar.gz');inv=inventory(tree)
    if case['base']!=COMMIT or cap['commit']!=COMMIT or case['origin']!='controlled_contract_change' or cap['historical_change_claimed'] is not False:raise ValueError('origin or source pin mismatch')
    if sha((CASE/'sources/base.tar.gz').read_bytes())!=ARCHIVE_SHA or cap['archive_sha256']!=ARCHIVE_SHA:raise ValueError('source digest mismatch')
    if json.loads(gzip.decompress((CASE/'sources/base-inventory.json.gz').read_bytes()))!=inv:raise ValueError('full source inventory mismatch')
    floor={k:inv[k] for k in ['method','comments_included','production_files','production_nonempty_lines']}
    if cap['production_floor']!=floor or case['production_floor']!={**floor,'eligible':True}:raise ValueError('production floor receipt mismatch')
    if sha((CASE/'sources/base-inventory.json.gz').read_bytes())!=cap['inventory_sha256']:raise ValueError('inventory export digest mismatch')
    if inv['production_files']<500 and inv['production_nonempty_lines']<50000:raise ValueError('production floor not met')
    if (CASE/'LICENSE.gitea').read_bytes()!=tree['LICENSE'][0] or b'Permission is hereby granted, free of charge' not in tree['LICENSE'][0]:raise ValueError('license mismatch')
    for path in ['go.mod','go.sum']:
        if (CASE/'setup'/path).read_bytes()!=tree[path][0] or sha(tree[path][0])!=cap['setup'][path]:raise ValueError('setup mismatch')
    base=tree['modules/util/url.go'][0];ref=reference(base)
    if (CASE/'oracles/reference-url.go').read_bytes()!=ref or (CASE/'oracles/reference.patch').read_bytes()!=patch(base,ref):raise ValueError('reference delta mismatch')
    for p,row in case['artifacts'].items():
        data=(CASE/p).read_bytes()
        if sha(data)!=row['sha256'] or len(data)!=row['bytes']:raise ValueError('frozen artifact mismatch '+p)
    rel=json.loads((CASE/'oracles/source-relations.json').read_text())
    if [x['path'] for x in rel['modules']]!=PATHS or len(rel['edges'])!=2:raise ValueError('relation set mismatch')
    for row in rel['modules']:
        data=tree[row['path']][0]
        if sha(data)!=row['sha256']:raise ValueError('relation digest mismatch')
        ls=data.decode().splitlines()
        for span in row['anchors']:
            i=span['line']-1
            if span['excerpt']!='\n'.join(ls[max(0,i-2):i+4]):raise ValueError('relation excerpt mismatch')
            if span['needle'] not in ls[span['line']-1]:raise ValueError('relation anchor mismatch')
    if case['qualification']['admitted'] or case['qualification']['competitive_runs_allowed']:raise ValueError('curated dossier cannot self-admit')
    return {'verified':True,'source_commit':COMMIT,'complete_source_files':inv['file_count'],'production_files':inv['production_files'],'production_nonempty_lines':inv['production_nonempty_lines'],'controlled_contract_change':True,'behavioral_probe':'not inferred from data verification','admitted':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['capture','verify']);a=p.parse_args();print(json.dumps(capture() if a.action=='capture' else verify(),indent=2))
if __name__=='__main__':main()
