package uuid
import("testing";"encoding/binary")
func TestOracle(t *testing.T){const ts uint64=0x123456789abcdef;var u UUID;binary.BigEndian.PutUint32(u[0:4],uint32(ts>>28));binary.BigEndian.PutUint16(u[4:6],uint16((ts>>12)&0xffff));binary.BigEndian.PutUint16(u[6:8],uint16(ts&0xfff)|0x6000);u[8]=0x80;if got:=uint64(u.Time());got!=ts{t.Fatalf("timestamp bits lost: %x != %x",got,ts)} }
