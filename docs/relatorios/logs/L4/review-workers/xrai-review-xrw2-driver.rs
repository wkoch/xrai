use std::time::{Duration,Instant};
use xrai_eval::worker_persistent::{PersistentPool,Request};
fn main(){
 let pool=PersistentPool::new("/private/tmp/xrai-review-xrw2-peer.py".into());
 let req=Request::new(1,"rust",vec![b'a';8*1024*1024],b"review").unwrap();
 let start=Instant::now();
 let ticket=pool.submit_before(req,"","",start+Duration::from_millis(500)).unwrap();
 println!("started={:?}",ticket.wait_started(Duration::from_secs(2)));
 println!("result={:?} elapsed={:?}",ticket.wait().map(|_|()),start.elapsed());
}
