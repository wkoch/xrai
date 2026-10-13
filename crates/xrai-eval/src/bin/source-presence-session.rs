//! Experimental captured-source inventory only; never parses or executes source.
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::io::{BufRead, Write};

const PROFILE: &str = "captured-source-presence-v1";
const SCHEMA: &str = "xrai.eval.c04.source-presence.session.v1";

#[derive(Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Input {
    configuration: BTreeMap<String, String>,
    files: BTreeMap<String, String>,
}

#[derive(Serialize)]
struct Snapshot {
    schema: &'static str,
    snapshot_id: String,
    configuration_id: String,
    producer_fingerprint: String,
    input: Input,
    files: BTreeMap<String, Value>,
    coverage: BTreeMap<String, Value>,
    unknowns: Vec<Value>,
    diagnostics: Vec<String>,
}

fn hash(bytes: &[u8]) -> String {
    blake3::hash(bytes).to_hex().to_string()
}

fn path_valid(path: &str) -> bool {
    !path.is_empty()
        && !path.starts_with('/')
        && !path.contains(['\\', ':', '\0'])
        && path.split('/').all(|p| !["", ".", ".."].contains(&p))
}

fn build(input: Input) -> Result<Snapshot, String> {
    if input.configuration != BTreeMap::from([("profile".into(), PROFILE.into())]) {
        return Err("unsupported source-presence configuration".into());
    }
    if input.files.len() > 2048
        || input.files.values().map(String::len).sum::<usize>() > 4 * 1024 * 1024
        || input.files.keys().any(|p| !path_valid(p))
    {
        return Err("captured source paths/size outside profile".into());
    }
    let producer_fingerprint = hash(
        &[
            include_bytes!("source-presence-session.rs").as_slice(),
            include_bytes!("../../../../Cargo.lock").as_slice(),
            include_bytes!("../../../../rust-toolchain.toml").as_slice(),
            PROFILE.as_bytes(),
        ]
        .concat(),
    );
    let configuration_id = format!(
        "presence-cfg_{}",
        hash(&serde_json::to_vec(&input.configuration).map_err(|e| e.to_string())?)
    );
    let snapshot_id = format!(
        "presence-snap_{}",
        hash(&serde_json::to_vec(&(&input, &producer_fingerprint)).map_err(|e| e.to_string())?)
    );
    let mut files = BTreeMap::new();
    let mut coverage = BTreeMap::new();
    for (path, source) in &input.files {
        files.insert(
            path.clone(),
            json!({"file_id":format!("presence-file_{}",hash(path.as_bytes())),
            "source_hash":hash(source.as_bytes()),"byte_length":source.len(),
            "parse_state":"unknown","semantic_state":"unknown"}),
        );
        coverage.insert(
            path.clone(),
            json!({"source_capture":"complete_for_declared_bytes",
            "parse":"not_evaluated","semantics":"not_evaluated"}),
        );
    }
    Ok(Snapshot {
        schema: "xrai.eval.c04.source-presence.snapshot.v1",
        snapshot_id,
        configuration_id,
        producer_fingerprint,
        input,
        files,
        coverage,
        unknowns: vec![
            json!({"dimension":"parse","reason":"source_presence_profile_only"}),
            json!({"dimension":"semantics","reason":"source_presence_profile_only"}),
        ],
        diagnostics: vec![
            "Absence is limited to captured sources; no whole-program absence claim.".into(),
        ],
    })
}

struct Index {
    current: Snapshot,
    generation: u64,
    session_id: String,
}

impl Index {
    fn envelope(&self, operation: &str, result: Value) -> Value {
        json!({"status":"ok","response":{"schema":SCHEMA,"session_id":self.session_id,
            "pid":std::process::id(),"generation":self.generation,
            "snapshot_id":self.current.snapshot_id,"operation":operation,"result":result}})
    }

    fn query(&self, path: &str) -> Value {
        let file = self.current.files.get(path);
        json!({"kind":"source_presence","path":path,"available":file.is_some(),
            "source_hash":file.map(|f| f["source_hash"].clone()),
            "evidence":file.map(|f| json!({"file_id":f["file_id"],"path":path,
                "snapshot_id":self.current.snapshot_id,"source_hash":f["source_hash"],
                "start":0,"end":f["byte_length"]})),
            "dependencies":[format!("{}:{}:{}:{path}",self.current.snapshot_id,
                self.current.configuration_id,if file.is_some(){"captured"}else{"absent_in_capture"})],
            "coverage":"captured_sources_only","parse_state":"unknown","semantic_state":"unknown",
            "diagnostics":["No parsing or semantic resolution performed."]})
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
        kind: String,
        path: String,
    },
    Update {
        expected_snapshot: String,
        input: Input,
    },
    Close,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut index: Option<Index> = None;
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
            if line.len() + count > 8 * 1024 * 1024 {
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
        let mut close = false;
        let outcome: Result<Value, String> = match serde_json::from_slice::<Request>(&line) {
            Err(e) => Err(format!("invalid request: {e}")),
            Ok(Request::Open { input }) if index.is_none() => build(input).map(|current| {
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
                index = Some(Index {
                    current,
                    generation: 1,
                    session_id,
                });
                index
                    .as_ref()
                    .expect("just opened")
                    .envelope("open", json!({"strategy":"conservative_full_rebuild"}))
            }),
            Ok(Request::Open { .. }) => Err("index cannot be reopened".into()),
            Ok(Request::Snapshot) => index
                .as_ref()
                .map(|i| i.envelope("snapshot", json!(i.current)))
                .ok_or("index is not open".into()),
            Ok(Request::Query { kind, path }) => match index.as_ref() {
                Some(i) if kind == "source_presence" && path_valid(&path) => {
                    Ok(i.envelope("query", i.query(&path)))
                }
                _ => Err("unsupported query or index not open".into()),
            },
            Ok(Request::Update {
                expected_snapshot,
                input,
            }) => match index.as_mut() {
                Some(i) if i.current.snapshot_id == expected_snapshot => build(input).map(|next| {
                    i.current = next;
                    i.generation += 1;
                    i.envelope("update", json!({"strategy":"conservative_full_rebuild"}))
                }),
                Some(_) => Err("expected snapshot mismatch; previous snapshot preserved".into()),
                None => Err("index is not open".into()),
            },
            Ok(Request::Close) => {
                close = true;
                index
                    .as_ref()
                    .map(|i| i.envelope("close", json!({"closed":true})))
                    .ok_or("index is not open".into())
            }
        };
        let response = outcome.unwrap_or_else(|diagnostic|json!({"status":"error","diagnostic":diagnostic,
            "session_id":index.as_ref().map(|i|&i.session_id),
            "snapshot_id":index.as_ref().map(|i|&i.current.snapshot_id),"generation":index.as_ref().map(|i|i.generation)}));
        serde_json::to_writer(&mut writer, &response)?;
        writer.write_all(b"\n")?;
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
