package uuid
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
