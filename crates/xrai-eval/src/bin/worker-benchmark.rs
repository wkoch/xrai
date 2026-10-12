//! Experimental measurement driver. The observer and reference replay run elsewhere.
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    collections::BTreeSet,
    io::Read,
    path::PathBuf,
    sync::atomic::AtomicBool,
    time::{Duration, Instant},
};
use xrai_eval::{
    worker_persistent::PersistentPool,
    worker_spike::{self, Request, Response},
};

#[derive(Deserialize)]
struct Input {
    mode: String,
    worker: PathBuf,
    requests: Vec<Item>,
    idle_ms: u64,
    hold_ms: u64,
}
#[derive(Deserialize)]
struct Item {
    key: String,
    dialect: String,
    source: PathBuf,
    configuration: String,
    warmup: bool,
}

fn fingerprint(mut response: Response) -> Result<String, String> {
    // Compare every response field, checking request correlation before normalizing only its id.
    response.identity.request = 0;
    Ok(blake3::hash(&worker_spike::encode_response(&response)?)
        .to_hex()
        .to_string())
}
fn run(input: Input) -> Result<Value, String> {
    if !["direct", "xrw1", "xrw2"].contains(&input.mode.as_str()) {
        return Err("mode".into());
    }
    let pool = (input.mode == "xrw2").then(|| PersistentPool::new(input.worker.clone()));
    std::thread::sleep(Duration::from_millis(input.idle_ms));
    let mut seen = BTreeSet::new();
    let mut rows = Vec::new();
    for (id, item) in input.requests.iter().enumerate() {
        let source = std::fs::read(&item.source).map_err(|e| e.to_string())?;
        let request = Request::new(
            id as u64,
            &item.dialect,
            source,
            item.configuration.as_bytes(),
        )?;
        let source_hash = blake3::hash(&request.source).to_hex().to_string();
        let source_bytes = request.source.len();
        let producer = blake3::Hash::from(request.identity.producer)
            .to_hex()
            .to_string();
        let configuration = blake3::Hash::from(request.identity.configuration)
            .to_hex()
            .to_string();
        let start = Instant::now();
        let mut pid = std::process::id();
        let mut incarnation = None;
        let mut attempts = 1;
        let mut ipc_bytes = None;
        let mut stderr_bytes = None;
        let response = match input.mode.as_str() {
            "direct" => worker_spike::direct(&request)?,
            "xrw1" => {
                let out = worker_spike::supervise(
                    &input.worker,
                    request.clone(),
                    "",
                    Instant::now() + worker_spike::DEADLINE,
                    &AtomicBool::new(false),
                );
                if !out.reaped {
                    return Err("not_reaped".into());
                }
                pid = *out.pids.last().ok_or("pid")?;
                attempts = out.attempts;
                ipc_bytes = Some(out.ipc_bytes);
                stderr_bytes = Some(out.stderr.len());
                out.result?
            }
            "xrw2" => {
                let out = pool.as_ref().unwrap().submit(request.clone(), "")?.wait()?;
                pid = out.pid;
                incarnation = Some(blake3::Hash::from(out.incarnation).to_hex().to_string());
                attempts = out.attempts;
                out.response
            }
            _ => unreachable!(),
        };
        let elapsed = start.elapsed().as_nanos();
        if response.identity != request.identity {
            return Err("correlation".into());
        }
        let first_for_process = seen.insert(pid);
        rows.push(json!({"key":item.key,"request":id,"dialect":item.dialect,"warmup":item.warmup,"source_bytes":source_bytes,"source_blake3":source_hash,"producer":producer,"configuration":configuration,"end_to_end_ns":elapsed,"pid":pid,"incarnation":incarnation,"first_for_process":first_for_process,"attempts":attempts,"ipc_bytes":ipc_bytes,"stderr_captured_bytes":stderr_bytes,"response_blake3":fingerprint(response)?}));
    }
    let mut retention = Value::Null;
    if let Some(pool) = pool.as_ref() {
        let request = Request::new(
            u64::MAX,
            "rust",
            b"fn held() {}".to_vec(),
            b"retention-calibration",
        )?;
        let expected = worker_spike::direct(&request)?;
        let ticket = pool.submit(request, "")?;
        ticket.wait_started(Duration::from_secs(2))?;
        std::thread::sleep(Duration::from_millis(input.hold_ms));
        let held = pool.reserved();
        if ticket.wait()?.response != expected {
            return Err("held_equivalence".into());
        }
        let released = pool.reserved();
        if held == 0 || released != 0 {
            return Err("retention_accounting".into());
        }
        retention = json!({"hold_ms":input.hold_ms,"held_ticket_reserved_bytes":held,"after_transfer_reserved_bytes":released,"full_direct_equal":true,"ownership":"External consumer allocations cease to be covered after transfer"});
    }
    let shutdown = Instant::now();
    drop(pool);
    Ok(
        json!({"schema":"xrai.eval.worker.session.v1","mode":input.mode,"parent_pid":std::process::id(),"samples":rows,"retention":retention,"shutdown_ns":shutdown.elapsed().as_nanos(),"concurrency":1,"component_timing_gap":"Only end-to-end timing exposed; queue/codec/roundtrip split unavailable","ipc_gap":"XRW2 counters unavailable; XRW1 stderr is captured bytes, not observed total"}),
    )
}
fn main() {
    let result = (|| {
        let mut source = String::new();
        std::io::stdin()
            .read_to_string(&mut source)
            .map_err(|e| e.to_string())?;
        let input = serde_json::from_str(&source).map_err(|e| e.to_string())?;
        run(input)
    })();
    match result {
        Ok(value) => println!("{value}"),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
}
