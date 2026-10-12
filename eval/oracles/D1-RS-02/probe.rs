extern crate upstream;
fn main() {assert_eq!(upstream::quote("~root"),"'~root'"); assert_eq!(upstream::join(["cat","~root"]),"cat '~root'");assert_eq!(upstream::split(&upstream::join(["cat","~root"])).unwrap(),vec!["cat","~root"]);}
