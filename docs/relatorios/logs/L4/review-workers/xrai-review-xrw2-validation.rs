use std::time::Instant;
use xrai_eval::worker_persistent::{Request,Response,validate_payload};
use xrai_eval::worker_spike::{State,Span};
fn main(){
 let length=1024*1024;
 let req=Request::new(1,"rust",vec![b'a';length],b"review").unwrap();
 let diagnostic=serde_json::json!({"kind":"missing","start_byte":length,"end_byte":length,"start_line":1,"end_line":1,"start_column_byte":length,"end_column_byte":length});
 let payload=serde_json::to_vec(&serde_json::json!({"dialect":"rust","complete":false,"source_bytes":length,"node_count":2000,"query_matches":0,"tree":"(source_file)","diagnostics":vec![diagnostic;2000]})).unwrap();
 let response=Response{identity:req.identity.clone(),state:State::Partial,source_bytes:length as u64,node_count:2000,query_matches:0,spans:(0..2000).map(|_|Span{start:length as u64,end:length as u64}).collect(),payload};
 println!("source_bytes={} diagnostics={} payload_bytes={}",length,2000,response.payload.len());
 let start=Instant::now(); println!("result={:?} elapsed={:?}",validate_payload(&response,&req),start.elapsed());
}
