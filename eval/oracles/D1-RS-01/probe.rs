extern crate upstream;
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
