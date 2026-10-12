//! Experimental C03 session. Captured source is parsed, never executed.
use serde::Deserialize;
use serde_json::{Value, json};
use std::io::{BufRead, Write};
use xrai_eval::semantics_spike::{Index, Input, Snapshot};

const MAX_LINE: usize = 8 * 1024 * 1024;

#[derive(Deserialize)]
#[serde(tag = "operation", rename_all = "snake_case", deny_unknown_fields)]
enum Request {
    Open {
        input: Input,
    },
    Snapshot,
    Query {
        module: String,
        path: String,
        namespace: String,
    },
    Update {
        expected_snapshot: String,
        input: Input,
    },
    Close,
}

struct Session {
    id: String,
    index: Index,
}

fn envelope(session: &Session, operation: &str, result: Value) -> Value {
    json!({"schema":"xrai.eval.c03.rust-session.v1", "operation": operation,
           "session_id": session.id, "pid": std::process::id(),
           "generation": session.index.generation,
           "snapshot_id": session.index.current.snapshot_id, "result": result})
}

fn query(snapshot: &Snapshot, module: &str, path: &str, namespace: &str) -> Value {
    let resolution = snapshot.resolve(module, path, namespace);
    let target = resolution.target_id.as_ref().and_then(|id| {
        snapshot.declarations.iter().find(|d| &d.id == id).map(|d| {
            if d.module.is_empty() {
                format!("{}:{}", d.evidence.path, d.name)
            } else {
                format!("{}:{}::{}", d.evidence.path, d.module, d.name)
            }
        })
    });
    json!({"module":module,"path":path,"namespace":namespace,
           "resolution":resolution,"target":target})
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut session: Option<Session> = None;
    let mut opened = false;
    let stdin = std::io::stdin();
    let mut reader = stdin.lock();
    let stdout = std::io::stdout();
    let mut writer = stdout.lock();
    loop {
        // read_until is bounded manually; no arbitrary unbounded line allocation.
        let mut line = Vec::new();
        loop {
            let buffer = reader.fill_buf()?;
            if buffer.is_empty() {
                break;
            }
            let count = buffer
                .iter()
                .position(|b| *b == b'\n')
                .map_or(buffer.len(), |p| p + 1);
            if line.len() + count > MAX_LINE {
                return Err("request exceeds byte limit".into());
            }
            line.extend_from_slice(&buffer[..count]);
            reader.consume(count);
            if line.last() == Some(&b'\n') {
                break;
            }
        }
        if line.is_empty() {
            break;
        }
        let request = serde_json::from_slice::<Request>(&line);
        let mut close = false;
        let response: Result<Value, String> = match request {
            Err(error) => Err(format!("invalid request: {error}")),
            Ok(Request::Open { input }) => {
                if opened {
                    Err("this process cannot reopen or replace its index".into())
                } else {
                    match Index::new(input) {
                        Err(error) => Err(error),
                        Ok(index) => {
                            let now = std::time::SystemTime::now()
                                .duration_since(std::time::UNIX_EPOCH)?;
                            let id = blake3::hash(
                                format!(
                                    "{}:{}:{}",
                                    std::process::id(),
                                    now.as_nanos(),
                                    index.current.snapshot_id
                                )
                                .as_bytes(),
                            )
                            .to_hex()
                            .to_string();
                            session = Some(Session { id, index });
                            opened = true;
                            Ok(envelope(
                                session.as_ref().ok_or("session absent")?,
                                "open",
                                json!({"strategy":"conservative_full_rebuild", "complete_snapshot":true}),
                            ))
                        }
                    }
                }
            }
            Ok(Request::Snapshot) => session
                .as_ref()
                .map(|s| envelope(s, "snapshot", json!(s.index.current)))
                .ok_or_else(|| "session is not open".into()),
            Ok(Request::Query {
                module,
                path,
                namespace,
            }) => session
                .as_ref()
                .map(|s| {
                    envelope(
                        s,
                        "query",
                        query(&s.index.current, &module, &path, &namespace),
                    )
                })
                .ok_or_else(|| "session is not open".into()),
            Ok(Request::Update {
                expected_snapshot,
                input,
            }) => match session.as_mut() {
                None => Err("session is not open".into()),
                Some(s) if s.index.current.snapshot_id != expected_snapshot => {
                    Err("expected snapshot mismatch; previous snapshot preserved".into())
                }
                Some(s) => match s.index.update(input) {
                    Err(error) => Err(format!(
                        "update rejected; previous snapshot preserved: {error}"
                    )),
                    Ok(_) => Ok(envelope(
                        s,
                        "update",
                        json!({"strategy":"conservative_full_rebuild", "complete_snapshot":true}),
                    )),
                },
            },
            Ok(Request::Close) => {
                close = true;
                session
                    .as_ref()
                    .map(|s| envelope(s, "close", json!({"closed":true})))
                    .ok_or_else(|| "session is not open".into())
            }
        };
        let value = match response {
            Ok(value) => json!({"status":"ok", "response":value}),
            Err(error) => json!({"status":"error", "diagnostic":error,
                "session_id":session.as_ref().map(|s| &s.id),
                "snapshot_id":session.as_ref().map(|s| &s.index.current.snapshot_id),
                "generation":session.as_ref().map(|s| s.index.generation)}),
        };
        serde_json::to_writer(&mut writer, &value)?;
        writer.write_all(b"\n")?;
        writer.flush()?;
        if close {
            return Ok(());
        }
    }
    if opened {
        return Err("EOF without explicit close".into());
    }
    Ok(())
}
