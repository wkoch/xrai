const ts=require(process.cwd()+'/built/local/typescript.js');
const fs=require('node:fs'), os=require('node:os'), path=require('node:path'), assert=require('node:assert/strict');
const d=fs.mkdtempSync(path.join(os.tmpdir(),'xrai-ts-oracle-'));
try {
 const p=path.join(d,'case.ts');
 const source="type Thing = {id: string; label: string}; const things: Thing[] = []; function find(id: string): undefined | Thing { return things.find(t => t.id === id); } declare function fun(t: Thing): void; fun({id: 'foo', ...find('foo') ?? {label: 'Foo'}});";
 fs.writeFileSync(p,source);
 function codes(s){fs.writeFileSync(p,s); const program=ts.createProgram([p],{strict:true,noEmit:true,types:[],target:ts.ScriptTarget.ES2020});return ts.getPreEmitDiagnostics(program).map(d=>d.code);}
 const result=codes(source);console.log(JSON.stringify({compiler_version:ts.version,diagnostics:result}));assert.deepEqual(result,[],'nullable union spread must not claim id always overwritten');
 const positive=codes("declare const u: {x:number,y:number}|{x:number,z:number}; const result={x:1,...u};");assert.deepEqual(positive,[2783],'required property present in every alternative must still error');
 const optional=codes("declare const u: {b?:number,a:string}|{a:string,c:boolean}; const result={b:42,...u};");assert.deepEqual(optional,[],'optional or absent property is not guaranteed override');
 console.log('3 behavioral checks passed');
} finally {fs.rmSync(d,{recursive:true,force:true});}
