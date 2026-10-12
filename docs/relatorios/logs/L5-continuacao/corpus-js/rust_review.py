#!/usr/bin/env python3
"""Independent source-only audit of the real Rust dossier. No upstream execution."""
from pathlib import Path, PurePosixPath
import difflib
import hashlib
import json
import re
import tarfile

ROOT=Path(__file__).resolve().parents[5]
CASE=ROOT/'eval/qualification/l5-real/rust'
CORE={'hir','hir-def','hir-ty','ide-diagnostics'}

def sha(b):
    return hashlib.sha256(b).hexdigest()

def main():
    case=json.loads((CASE/'case.json').read_text())
    commit=json.loads((ROOT/'docs/relatorios/logs/L5-continuacao/corpus-rust/commit-reference.json').read_text())
    pull=json.loads((ROOT/'docs/relatorios/logs/L5-continuacao/corpus-rust/pr-23422.json').read_text())
    assert commit['sha']==case['reference']['commit']==pull['merge_commit_sha']
    assert commit['parents'][0]['sha']==case['baseline']['commit']
    assert pull['merged'] is True
    proofs={}
    for side in ['baseline','reference']:
        archive=CASE/case[side]['archive']
        files=lines=0
        with tarfile.open(archive) as tree:
            root='rust-analyzer-'+case[side]['commit']
            assert {m.name.split('/',1)[0] for m in tree.getmembers()}=={root}
            mit=tree.extractfile(tree.getmember(root+'/LICENSE-MIT')).read()
            apache=tree.extractfile(tree.getmember(root+'/LICENSE-APACHE')).read()
            assert b'Permission is hereby granted' in mit and b'Apache License' in apache
            for m in tree.getmembers():
                if not m.isfile():continue
                p=PurePosixPath(m.name.split('/',1)[-1]);parts=p.parts
                if len(parts)<4 or parts[0]!='crates' or parts[1] not in CORE or parts[2]!='src' or p.suffix!='.rs':continue
                if any(x in {'tests','test','test_data','fixtures','generated','testutils'} for x in parts) or any(x in p.name.lower() for x in ['test','fixture','generated']):continue
                data=tree.extractfile(m).read().decode()
                if re.search(r'(?i)generated (code|file)|do not edit|automatically generated',data[:2000]):continue
                cut=re.search(r'#\[\s*(?:cfg\([^\]]*\btest\b|test\b)',data,re.S)
                if cut:data=data[:cut.start()]
                block=False;count=0
                for line in data.splitlines():
                    s=line.strip()
                    if block:
                        if '*/' in s:block=False
                        continue
                    if s.startswith('/*'):block='*/' not in s;continue
                    if s and not s.startswith(('//','*','*/')):count+=1
                if count:files+=1;lines+=count
        assert lines>=50000
        proofs[side]={'archive_sha256':sha(archive.read_bytes()),'root_commit_verified':True,
            'core_crates':sorted(CORE),'core_source_files':files,'core_nonempty_comment_filtered_prefix_lines':lines,
            'method':'independent four-crate src-only prefix count, broader test cfg and comment-block filtering; source-only operational floor check, not exact lexical LOC',
            'license_mit_sha256':sha(mit),'license_apache_sha256':sha(apache)}
    path='crates/hir-ty/src/diagnostics/expr.rs'
    b=(CASE/'captures/baseline'/path).read_text();h=(CASE/'captures/reference'/path).read_text()
    patch=''.join(difflib.unified_diff(b.splitlines(keepends=True),h.splitlines(keepends=True),fromfile='a/'+path,tofile='b/'+path))
    assert patch==(CASE/'oracles/reference.patch').read_text()
    for side in ['baseline','reference']:
        handler=(CASE/'captures'/side/'crates/ide-diagnostics/src/handlers/non_exhaustive_let.rs').read_bytes()
        hidden=(CASE/'oracles/non_exhaustive_let.rs').read_bytes()
        assert handler.split(b'#[cfg(test)]',1)[0]==hidden.split(b'#[cfg(test)]',1)[0]
    assert b'regression_23336_1' in hidden and b'regression_23336_2' in hidden
    request=json.loads((CASE/'request.json').read_text())['prompt']
    assert all(term not in request for term in ['types_of_subpatterns_do_match','walk_child_pats','crates/hir','reference.patch'])
    collector=ROOT/'eval/scripts/collect_real_rust.py'
    hardened=all(marker in collector.read_text() for marker in ['captured public parent/head mismatch','archive commit root mismatch','evaluator patch/probe fingerprint mismatch','hidden probe modifies production code','production reference patch differs from captured delta'])
    paths=[collector]+[p for p in CASE.rglob('*') if p.is_file()]
    return {'schema_version':'xrai.eval.dossier.second-reader.source.v1','case_id':case['id'],
        'author':'/root/corpus_rust','second_reader':'/root/corpus_js','review_script_sha256':sha(Path(__file__).read_bytes()),
        'review_scope':'origin/parent, full archives, licenses, independent production-floor sample, three necessary modules/two source edges, request naturalness, hidden production-prefix and exact reference delta',
        'source_evidence':proofs,
        'relationship_assessment':'HIR diagnostics dispatches BodyValidationDiagnostic.collect; hir-ty validates let and retains inference errors; its nested mismatch walk calls hir-def Pat.walk_child_pats over tuple/or/bind/ref shapes. Needed to reject malformed nested shapes before usefulness analysis while preserving genuine type errors, rather than disabling diagnostics.',
        'natural_input_assessment':'public issue reproducer and desired diagnostic continuation, no solution symbol/path or oracle injected',
        'oracle_assessment':'reference production prefix of hidden handler equals both captured sides; upstream annotation assertions and two added public regressions, independent of xrai/parser output. Runtime not executed in this review.',
        'findings':[{'id':'RUST-VERIFY-01','severity':'resolved' if hardened else 'verification_gap','description':'Parent/root hardened commit/root/public-parent binding, hidden-probe and patch digests, hidden production-prefix equality and exact patch delta after this review. Independent source checks above agree with the current artifacts; root source was read directly following changed graph metadata.' if hardened else 'Collector requires commit/root/public-parent and evaluator probe/patch cross-binding; current artifacts pass the independent source audit.'}],
        'curation_review':'source_curation_supported' if hardened else 'source_curation_supported_with_verifier_gap','behavioral_probes':'pending_disposable_Linux_receipts',
        'incremental_event':'pending_same_index_process_A_B_rebuild','admitted':False,'competitive_runs_allowed':False,
        'reviewed_artifact_hashes':{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(paths)}}

if __name__=='__main__':
    print(json.dumps(main(),indent=2))
