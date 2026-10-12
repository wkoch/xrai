from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
probes={
'D1-RS-01':('probe.rs','''extern crate upstream;
fn main() {
 let (a,b)=("a jke","jane a k");
 for (x,y) in [(a,b),(b,a)] {
  assert!((upstream::jaro(x,y)-0.6).abs()<1e-12);
  assert!((upstream::jaro_winkler(x,y)-0.6).abs()<1e-12);
  let xa:Vec<char>=x.chars().collect();let ya:Vec<char>=y.chars().collect();
  assert!((upstream::generic_jaro(&xa,&ya)-0.6).abs()<1e-12);
 }
 assert_eq!(upstream::jaro("é🦉", "é🦉"),1.0);
}
'''),
'D1-RS-02':('probe.rs','''extern crate upstream;
fn main() {assert_eq!(upstream::quote("~root"),"'~root'"); assert_eq!(upstream::join(["cat","~root"]),"cat '~root'");assert_eq!(upstream::split(&upstream::join(["cat","~root"])).unwrap(),vec!["cat","~root"]);}
'''),
'D1-TJ-01':('probe.ts','''import mitt from './src/index';
const e = mitt<{foo:string;bar?:number}>();
e.on('foo', value => {const typed:string=value;void typed;});
e.emit('foo','yes');e.emit('bar');e.emit('bar',1);
// @ts-expect-error wrong payload must be rejected
e.emit('foo',1);
// @ts-expect-error required payload cannot be omitted
e.emit('foo');
// @ts-expect-error wrong handler parameter must be rejected
e.on('foo',(n:number)=>{void n;});
e.on('*',(key,value)=>{const k:'foo'|'bar'=key;const v:string|number|undefined=value;void k;void v;});
'''),
'D1-TJ-02':('probe.js','''const assert=require('node:assert/strict'),ms=require('./index');
assert.equal(ms('-10.5h'),-37800000);assert.equal(ms('-.5h'),-1800000);assert.equal(ms('10.5h'),37800000);
'''),
'D1-PY-01':('probe.py','''from cachetools import cachedmethod
import threading
for info in [False, True]:
 for mode in ['unlocked','locked','condition']:
  mutex=threading.RLock(); cond=threading.Condition(mutex)
  opts={'info':info}
  if mode=='locked': opts['lock']=lambda s:s.mutex
  if mode=='condition': opts['condition']=lambda s:s.cond
  class C:
   def __init__(self): self.cache={};self.label='owner';self.mutex=mutex;self.cond=cond;self.calls=0
   @cachedmethod(lambda s:s.cache,key=lambda s,x:(s.label,x),**opts)
   def f(self,x): self.calls+=1;return x*2
  c=C();assert c.f.cache_key(21)==('owner',21),(mode,info)
  assert c.f(21)==42;assert c.f(21)==42;assert c.calls==1
  assert ('owner',21) in c.cache
  c.f.cache_clear();assert not c.cache
'''),
'D1-PY-02':('probe.py','''from slugify.__main__ import parse_args,slugify_params
from slugify import slugify
params=slugify_params(parse_args(['slugify','--regex-pattern','[^-a-z0-9_]+','___This is a test___']))
assert params.get('regex_pattern')=='[^-a-z0-9_]+'
assert slugify(**params)=='___this-is-a-test___'
'''),
'D1-GO-01':('oracle_test.go','''package uuid
import("testing";"time";"bytes")
func TestOracle(t *testing.T){
 old:=timeNow;defer func(){timeNow=old}();fixed:=time.Unix(1700000000,123000000);timeNow=func()time.Time{return fixed}
 a,e:=NewV7FromReader(bytes.NewReader(make([]byte,16)));if e!=nil{t.Fatal(e)}
 b,e:=NewV7FromReader(bytes.NewReader(make([]byte,16)));if e!=nil{t.Fatal(e)}
 if bytes.Compare(a[:],b[:])>=0{t.Fatal("not strictly monotonic within fixed time")}
 fixed=fixed.Add(-time.Second);c,e:=NewV7FromReader(bytes.NewReader(make([]byte,16)));if e!=nil{t.Fatal(e)}
 if bytes.Compare(b[:],c[:])>=0{t.Fatal("not monotonic after clock rollback")}
 if c.Version()!=7 || c.Variant()!=RFC4122 {t.Fatal("version or variant altered")}
}
'''),
'D1-GO-02':('oracle_test.go','''package humanize
import("testing";"math/big")
func TestOracle(t *testing.T){ for _,input:=range []string{"1000000","-1000000"} {n,_:=new(big.Int).SetString(input,10);before:=new(big.Int).Set(n);want:="1,000,000";if input[0]=='-'{want="-1,000,000"};for i:=0;i<2;i++{if got:=BigComma(n);got!=want{t.Fatal(got)};if n.Cmp(before)!=0{t.Fatal("input was mutated",input,n)}}} }
'''),
'D1-RS-07':('probe.rs','''extern crate upstream;
fn main(){let a="Friedrich Nietzsche";let b="Fran-Paul Sartre";assert!((upstream::jaro_winkler(a,b)-upstream::jaro(a,b)).abs()<1e-12);assert!((upstream::jaro(a,b)-0.452).abs()<0.001);}
'''),
'D1-TJ-07':('probe.js',"const assert=require('node:assert/strict'),ms=require('./index');assert.equal(ms('10-.5'),undefined);assert.equal(ms('-10.5'),-10.5);\n"),
'D1-PY-07':('probe.py','''import warnings,unittest.mock
from cachetools import cachedmethod
class C:
 def __init__(self):self.cache={}
 @cachedmethod(lambda self:self.cache)
 def f(self,x):return x
with warnings.catch_warnings(record=True) as recorded:
 warnings.simplefilter('always');unittest.mock.create_autospec(C,instance=True)
assert not recorded, [str(w.message) for w in recorded]
'''),
'D1-GO-07':('oracle_test.go','''package uuid
import("testing";"encoding/binary")
func TestOracle(t *testing.T){const ts uint64=0x123456789abcdef;var u UUID;binary.BigEndian.PutUint32(u[0:4],uint32(ts>>28));binary.BigEndian.PutUint16(u[4:6],uint16((ts>>12)&0xffff));binary.BigEndian.PutUint16(u[6:8],uint16(ts&0xfff)|0x6000);u[8]=0x80;if got:=uint64(u.Time());got!=ts{t.Fatalf("timestamp bits lost: %x != %x",got,ts)} }
''')}
for id,(name,code) in probes.items():
 d=R/'oracles'/id;d.mkdir(exist_ok=True);(d/name).write_text(code, encoding="utf-8", newline="\n")
 o=json.loads((d/'oracle.json').read_text(encoding="utf-8"));o['executable_probe']='oracles/'+id+'/'+name
 o['test_vectors'].append({'probe':o['executable_probe'],'expected_baseline':'fail' if o['review'] is None else 'pass','expected_reference':'pass','expected_proposed_review':'fail' if o['review'] else None})
 (d/'oracle.json').write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n', encoding="utf-8", newline="\n")
