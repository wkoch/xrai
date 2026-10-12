extern crate upstream;
fn main(){let a="Friedrich Nietzsche";let b="Fran-Paul Sartre";assert!((upstream::jaro_winkler(a,b)-upstream::jaro(a,b)).abs()<1e-12);assert!((upstream::jaro(a,b)-0.452).abs()<0.001);}
