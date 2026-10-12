//! Offline development driver. A persistent Python helper measures exact L4
//! tokens; this does not make the production binary autonomous.
use serde_json::{Value, json};
use std::io::{BufRead, BufReader, Read, Write};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, Receiver};
use std::time::{Duration, Instant};
use xrai_eval::context_spike::{Case, Limits, Meter, Store, TTL_MS};

struct PythonMeter {
    child: Child,
    replies: Receiver<Result<Value, String>>,
    profile: String,
}
impl PythonMeter {
    fn new(python: &str) -> Result<Self, String> {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let mut child = Command::new(python)
            .arg(root.join("eval/context/measure_wire.py"))
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| e.to_string())?;
        let output = child.stdout.take().ok_or("meter_stdout")?;
        let (tx, replies) = mpsc::sync_channel(1);
        std::thread::spawn(move || {
            let mut reader = BufReader::new(output);
            loop {
                let mut line = String::new();
                let read = reader.by_ref().take(8193).read_line(&mut line);
                let reply = match read {
                    Ok(0) => break,
                    Ok(n) if n > 8192 || !line.ends_with('\n') => Err("meter_reply_cap".into()),
                    Ok(_) => serde_json::from_str(&line).map_err(|e| e.to_string()),
                    Err(e) => Err(e.to_string()),
                };
                let failed = reply.is_err();
                if tx.send(reply).is_err() || failed {
                    break;
                }
            }
        });
        let mut meter = Self {
            child,
            replies,
            profile: String::new(),
        };
        let ready = meter.receive()?;
        meter.profile = ready["profile"]
            .as_str()
            .ok_or("meter_profile")?
            .to_string();
        Ok(meter)
    }
    fn receive(&mut self) -> Result<Value, String> {
        self.replies
            .recv_timeout(Duration::from_secs(5))
            .map_err(|_| "meter_deadline_or_exit".to_string())?
    }
}
impl Drop for PythonMeter {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
impl Meter for PythonMeter {
    fn profile(&self) -> &str {
        &self.profile
    }
    fn tokens(&mut self, bytes: &[u8]) -> Result<usize, String> {
        if bytes.len() > 512 * 1024 {
            return Err("meter_wire_cap".into());
        }
        let encoded = bytes.iter().map(|b| format!("{b:02x}")).collect::<String>();
        // The pipe writer runs separately so a failed helper cannot block the
        // supervisor. Kill/reap before joining on a deadline or transport error.
        let mut input = self.child.stdin.take().ok_or("meter_stdin")?;
        let (tx, rx) = mpsc::channel();
        let writer = std::thread::spawn(move || {
            let result = writeln!(input, "{encoded}").map_err(|e| e.to_string());
            let _ = tx.send(());
            (input, result)
        });
        if rx.recv_timeout(Duration::from_secs(5)).is_err() {
            let _ = self.child.kill();
            let _ = self.child.wait();
            let _ = writer.join();
            return Err("meter_write_deadline".into());
        }
        let (input, result) = writer.join().map_err(|_| "meter_writer_panic")?;
        self.child.stdin = Some(input);
        result?;
        let reply = self.receive()?;
        if reply["wire_blake3"] != xrai_eval::context_spike::hash(bytes) {
            return Err("meter_wire_hash_mismatch".into());
        }
        reply["tokens"]
            .as_u64()
            .map(|n| n as usize)
            .ok_or("meter_reply".into())
    }
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = std::env::args().collect::<Vec<_>>();
    if args.len() != 3 {
        return Err("usage: context-spike input.json python-with-L4-tokenizer".into());
    }
    let mut bytes = Vec::new();
    std::fs::File::open(&args[1])?
        .take(16 * 1024 * 1024 + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() > 16 * 1024 * 1024 {
        return Err("input_cap".into());
    }
    let case: Case = serde_json::from_slice(&bytes)?;
    let setup = Instant::now();
    let mut meter = PythonMeter::new(&args[2])?;
    let setup_us = setup.elapsed().as_micros();
    let mut store = Store::new()?;
    let initial = store.context(case.clone(), 0, &mut meter)?;
    let ids = initial
        .manifest
        .candidates
        .iter()
        .map(|c| c.id.clone())
        .collect::<Vec<_>>();
    let context_id = initial.manifest.context_id.clone();
    let expanded = if ids.is_empty() {
        None
    } else {
        Some(store.expand(
            &context_id,
            &ids,
            case.request.limits.clone(),
            1,
            &mut meter,
        )?)
    };
    // New immutable generation can publish while the old context stays retained.
    let mut newer = case.clone();
    newer.base = None;
    newer
        .head
        .files
        .entry(newer.head.root.clone())
        .and_modify(|s| s.push_str("\n// new generation\n"));
    newer.request.anchors.retain(|a| a.side == "head");
    newer.request.hunks.clear();
    let published = store.context(newer, 2, &mut meter)?;
    let after_new = if ids.is_empty() {
        None
    } else {
        Some(store.expand(
            &context_id,
            &ids,
            case.request.limits.clone(),
            3,
            &mut meter,
        )?)
    };
    let small = Limits {
        max_bytes: initial.response["budget"]["used_bytes"].as_u64().unwrap() as usize + 1024,
        max_tokens: initial.response["budget"]["used_tokens"].as_u64().unwrap() as usize + 256,
        ..case.request.limits.clone()
    };
    let insufficient = match store.expand(&context_id, &ids, small, 4, &mut meter) {
        Ok(d) => json!({"delivery":d}),
        Err(e) => json!({"error":e}),
    };
    let expired = store
        .expand(
            &context_id,
            &ids,
            case.request.limits.clone(),
            TTL_MS,
            &mut meter,
        )
        .err();
    let retention_recreated = store.context(case.clone(), TTL_MS, &mut meter)?;
    let old_handle_after_recreation = store
        .expand(
            &context_id,
            &ids,
            case.request.limits.clone(),
            TTL_MS,
            &mut meter,
        )
        .err();
    let mut controls = vec![];
    for pair in [false, true] {
        for p2 in [false, true] {
            let mut control = case.clone();
            control.request.p2 = p2;
            if !pair {
                control.base = None;
                control.request.anchors.retain(|a| a.side == "head");
                control.request.hunks.clear();
            }
            let outcome = match Store::new()?.context(control.clone(), 0, &mut meter) {
                Ok(d) => json!({"delivery":d}),
                Err(e) => json!({"error":e}),
            };
            controls.push(json!({"pair":pair,"p2":p2,"input":control,"outcome":outcome}));
        }
    }
    let mut curves = vec![];
    for tokens in [2000, 4000, 8000, 16000, 32000] {
        let mut control = case.clone();
        control.request.limits.max_tokens = tokens;
        let mut store = Store::new()?;
        let outcome = match store.context(control.clone(), 0, &mut meter) {
            Ok(d) => {
                let ids = d
                    .manifest
                    .candidates
                    .iter()
                    .map(|c| c.id.clone())
                    .collect::<Vec<_>>();
                let expansion = match store.expand(
                    &d.manifest.context_id,
                    &ids,
                    control.request.limits.clone(),
                    1,
                    &mut meter,
                ) {
                    Ok(e) => json!({"delivery":e}),
                    Err(e) => json!({"error":e}),
                };
                json!({"delivery":d,"expansion":expansion})
            }
            Err(e) => json!({"error":e}),
        };
        curves.push(json!({"max_tokens":tokens,"input":control,"outcome":outcome}));
    }
    println!(
        "{}",
        serde_json::to_string(
            &json!({"version":"xrai.context.development.v1","input":case,
        "initial":initial,"expanded":expanded,"published":published,"after_new":after_new,
        "insufficient":insufficient,"expired":expired,"retention_recreated":retention_recreated,
        "old_handle_after_recreation":old_handle_after_recreation,"controls":controls,"curves":curves,
        "meter_setup_micros":setup_us,"profile":meter.profile()})
        )?
    );
    Ok(())
}
