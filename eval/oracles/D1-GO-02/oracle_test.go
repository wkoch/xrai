package humanize
import("testing";"math/big")
func TestOracle(t *testing.T){ for _,input:=range []string{"1000000","-1000000"} {n,_:=new(big.Int).SetString(input,10);before:=new(big.Int).Set(n);want:="1,000,000";if input[0]=='-'{want="-1,000,000"};for i:=0;i<2;i++{if got:=BigComma(n);got!=want{t.Fatal(got)};if n.Cmp(before)!=0{t.Fatal("input was mutated",input,n)}}} }
