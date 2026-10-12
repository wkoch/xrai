use std::collections::BTreeMap;
use std::time::{Duration, Instant};
use xrai_eval::{
    parsing_spike::DIALECTS,
    worker_persistent::{PersistentPool, Request, worker},
    worker_spike::direct,
};
fn demonstrate() -> Result<(), String> {
    let executable = std::env::current_exe().map_err(|e| e.to_string())?;
    let pool = PersistentPool::new(executable);
    let mut rows = Vec::new();
    let mut seen = BTreeMap::new();
    for id in 0..28 {
        let dialect = DIALECTS[id as usize % 7];
        let text = if (7..14).contains(&id) {
            "fn ( {"
        } else {
            match dialect {
                "rust" => "fn ready() {}",
                "python" => "def ready():\n    pass\n",
                "go" => "package ready\nfunc Ready() {}",
                _ => "function ready() {}",
            }
        };
        let request = Request::new(
            id,
            dialect,
            text.as_bytes().to_vec(),
            format!("config-{id}").as_bytes(),
        )?;
        let expected = direct(&request)?;
        let start = Instant::now();
        let result = pool.submit(request, "")?.wait()?;
        if result.response != expected {
            return Err("direct_equivalence".into());
        }
        let incarnation = blake3::Hash::from(result.incarnation).to_hex().to_string();
        let cold = seen.insert(result.pid, incarnation.clone()).is_none();
        rows.push(serde_json::json!({"request":id,"dialect":dialect,"pid":result.pid,"incarnation":incarnation,"first_for_process":cold,"end_to_end_ns":start.elapsed().as_nanos(),"direct_equal":true,"configuration":result.response.identity.configuration,"payload_blake3":blake3::hash(&result.response.payload).to_hex().to_string()}));
    }
    let request = Request::new(100, "rust", b"fn ready() {}".to_vec(), b"replacement")?;
    let ticket = pool.submit(request, "crash_once")?;
    let (before_pid, before_incarnation) = ticket.wait_started(Duration::from_secs(2))?;
    let replacement = ticket.wait()?;
    if replacement.attempts != 2
        || !replacement.retired.contains(&before_pid)
        || before_pid == replacement.pid
        || before_incarnation == replacement.incarnation
    {
        return Err("replacement".into());
    }
    let next = Request::new(101, "rust", b"fn ready() {}".to_vec(), b"healthy-after")?;
    let expected = direct(&next)?;
    let healthy = pool.submit(next, "")?.wait()?;
    if healthy.response != expected {
        return Err("after_failure".into());
    }
    let held = pool.submit(
        Request::new(102, "rust", b"fn ready() {}".to_vec(), b"held")?,
        "",
    )?;
    held.wait_started(Duration::from_secs(2))?;
    std::thread::sleep(Duration::from_millis(30));
    let held_reserved = pool.reserved();
    held.wait()?;
    let released = pool.reserved();
    let shutdown = Instant::now();
    drop(pool);
    println!(
        "{}",
        serde_json::json!({"schema":"xrai.eval.workers.persistent.smoke.v1","protocol":"XRW2","status":"first_functional_increment","worker_limit":2,"direct_equivalent":rows.len()+1,"healthy_workers":seen,"samples":rows,"failure":{"before_pid":before_pid,"before_incarnation":blake3::Hash::from(before_incarnation).to_hex().to_string(),"replacement_pid":replacement.pid,"replacement_incarnation":blake3::Hash::from(replacement.incarnation).to_hex().to_string(),"attempts":replacement.attempts,"retired_reaped":replacement.retired,"healthy_after_failure":true},"reservation":{"held_ticket_bytes":held_reserved,"after_transfer_bytes":released},"shutdown_ns":shutdown.elapsed().as_nanos(),"cpu_user_seconds":null,"cpu_system_seconds":null,"sampled_peak_sum_rss":null,"resource_gap":"Functional smoke only; exit CPU counters and simultaneous RSS observer not implemented in this increment.","latency_scope":"Exploratory end-to-end samples; first-for-process includes handshake, later requests reuse parser/query; no statistical comparison or OS cold cache claim."})
    );
    Ok(())
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let result = match args.get(1).map(String::as_str) {
        Some("worker") => worker(args.get(2).map(String::as_str).unwrap_or("")),
        Some("demonstrate") => demonstrate(),
        _ => Err("usage: worker-persistent worker [development-start-fault] | demonstrate".into()),
    };
    if let Err(error) = result {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
