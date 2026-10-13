//! Experimental bounded JSONL owner for the unchanged captured ESM resolver.
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::io::{BufRead, Write};
use xrai_eval::tsjs_semantics::{Input, Snapshot, build};

const SCHEMA: &str = "xrai.eval.tsjs-semantic-session.v1";
const FRAME_LIMIT: usize = 8 * 1024 * 1024;
const RESPONSE_LIMIT: usize = 16 * 1024 * 1024;
const OPERATIONS: u64 = 64;

fn hash(bytes: &[u8]) -> String {
    blake3::hash(bytes).to_hex().to_string()
}

fn producer() -> String {
    hash(
        &[
            include_bytes!("tsjs-semantic-session.rs").as_slice(),
            include_bytes!("../tsjs_semantics.rs").as_slice(),
            include_bytes!("../../../../Cargo.lock").as_slice(),
            include_bytes!("../../../../rust-toolchain.toml").as_slice(),
        ]
        .concat(),
    )
}

#[derive(Default, Serialize)]
struct Counters {
    requests: u64,
    build_attempts: u64,
    successful_builds: u64,
    queries: u64,
    failed_updates: u64,
}

struct Index {
    current: Snapshot,
    generation: u64,
    session_id: String,
    producer: String,
}

impl Index {
    fn envelope(&self, operation: &str, result: Value, counters: &Counters) -> Value {
        json!({"status":"ok","response":{"schema":SCHEMA,"session_id":self.session_id,
            "pid":std::process::id(),"generation":self.generation,
            "snapshot_id":self.current.snapshot_id,"session_producer_fingerprint":self.producer,
            "operation":operation,"counters":counters,"result":result}})
    }
}

#[derive(Deserialize)]
#[serde(tag = "operation", rename_all = "snake_case", deny_unknown_fields)]
enum Request {
    Open {
        input: Input,
    },
    Snapshot,
    Query {
        path: String,
        offset: usize,
    },
    Update {
        expected_snapshot: String,
        input: Input,
    },
    Close,
}

struct BoundedOutput(Vec<u8>);
impl Write for BoundedOutput {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        if self.0.len() + bytes.len() > RESPONSE_LIMIT - 1 {
            return Err(std::io::Error::other("response frame limit"));
        }
        self.0.extend_from_slice(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut index: Option<Index> = None;
    let mut counters = Counters::default();
    let mut reader = std::io::stdin().lock();
    let mut writer = std::io::stdout().lock();
    loop {
        let mut line = Vec::new();
        loop {
            let chunk = reader.fill_buf()?;
            if chunk.is_empty() {
                break;
            }
            let count = chunk
                .iter()
                .position(|b| *b == b'\n')
                .map_or(chunk.len(), |p| p + 1);
            if line.len() + count > FRAME_LIMIT {
                return Err("request frame limit".into());
            }
            line.extend_from_slice(&chunk[..count]);
            reader.consume(count);
            if line.last() == Some(&b'\n') {
                break;
            }
        }
        if line.is_empty() {
            break;
        }
        if line.last() != Some(&b'\n') {
            return Err("incomplete request frame".into());
        }
        counters.requests += 1;
        if counters.requests > OPERATIONS {
            return Err("operation limit".into());
        }
        let mut close = false;
        let outcome: Result<Value, String> = match serde_json::from_slice::<Request>(&line) {
            Err(error) => Err(format!("invalid request: {error}")),
            Ok(Request::Open { input }) if index.is_none() => {
                counters.build_attempts += 1;
                build(input).map(|current| {
                    let now = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default();
                    let session_id = hash(
                        format!(
                            "{}:{}:{}",
                            std::process::id(),
                            now.as_nanos(),
                            current.snapshot_id
                        )
                        .as_bytes(),
                    );
                    counters.successful_builds += 1;
                    index = Some(Index {
                        current,
                        generation: 1,
                        session_id,
                        producer: producer(),
                    });
                    index.as_ref().expect("just opened").envelope(
                        "open",
                        json!({"strategy":"conservative_full_semantic_rebuild"}),
                        &counters,
                    )
                })
            }
            Ok(Request::Open { .. }) => Err("index cannot be reopened".into()),
            Ok(Request::Snapshot) => index
                .as_ref()
                .map(|i| i.envelope("snapshot", json!(i.current), &counters))
                .ok_or("index is not open".into()),
            Ok(Request::Query { path, offset }) => match index.as_ref() {
                Some(i)
                    if i.current.input.files.get(&path).is_some_and(|source| {
                        offset < source.source.len() && source.source.is_char_boundary(offset)
                    }) =>
                {
                    counters.queries += 1;
                    Ok(i.envelope(
                        "query",
                        json!({"kind":"lexical_reference","path":path,"offset":offset,
                            "reference":i.current.lookup(&path,offset)}),
                        &counters,
                    ))
                }
                _ => {
                    Err("query path/UTF-8 offset outside captured source or index not open".into())
                }
            },
            Ok(Request::Update {
                expected_snapshot,
                input,
            }) => match index.as_mut() {
                Some(i) if i.current.snapshot_id == expected_snapshot => {
                    counters.build_attempts += 1;
                    match build(input) {
                        Ok(next) => {
                            i.current = next;
                            i.generation += 1;
                            counters.successful_builds += 1;
                            Ok(i.envelope(
                                "update",
                                json!({"strategy":"conservative_full_semantic_rebuild"}),
                                &counters,
                            ))
                        }
                        Err(error) => {
                            counters.failed_updates += 1;
                            Err(format!(
                                "update build failed; previous snapshot preserved: {error}"
                            ))
                        }
                    }
                }
                Some(_) => {
                    counters.failed_updates += 1;
                    Err("expected snapshot mismatch; previous snapshot preserved".into())
                }
                None => Err("index is not open".into()),
            },
            Ok(Request::Close) => {
                close = true;
                index
                    .as_ref()
                    .map(|i| i.envelope("close", json!({"closed":true}), &counters))
                    .ok_or("index is not open".into())
            }
        };
        let response = outcome.unwrap_or_else(|diagnostic| {
            json!({"status":"error","diagnostic":diagnostic,
                "schema":SCHEMA,"pid":std::process::id(),"counters":counters,
                "session_id":index.as_ref().map(|i|&i.session_id),
                "session_producer_fingerprint":index.as_ref().map(|i|&i.producer),
                "snapshot_id":index.as_ref().map(|i|&i.current.snapshot_id),
                "generation":index.as_ref().map(|i|i.generation)})
        });
        let mut encoded = BoundedOutput(Vec::new());
        serde_json::to_writer(&mut encoded, &response)?;
        encoded.0.push(b'\n');
        writer.write_all(&encoded.0)?;
        writer.flush()?;
        if close {
            return Ok(());
        }
    }
    if index.is_some() {
        return Err("EOF without explicit close".into());
    }
    Ok(())
}
