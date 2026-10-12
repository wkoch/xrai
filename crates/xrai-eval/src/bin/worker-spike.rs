use std::{path::Path, time::Instant};
use xrai_eval::{
    parsing_spike::json_string,
    worker_spike::{self, DEADLINE, Pool, Request},
};
fn stats(values: &[f64]) -> (f64, f64) {
    let mut sorted = values.to_vec();
    sorted.sort_by(f64::total_cmp);
    (
        sorted[sorted.len() / 2],
        sorted[(sorted.len() * 95).div_ceil(100).saturating_sub(1)],
    )
}
fn demonstrate() -> Result<(), String> {
    let executable = std::env::current_exe().map_err(|e| e.to_string())?;
    let pool = Pool::new(executable.clone());
    let large = format!("{}\nfn large() {{}}", "// 0123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789\n".repeat(11000)).into_bytes();
    let inputs = [
        ("small", b"fn small() {}".to_vec()),
        ("large-comments", large),
        ("incomplete", b"fn unfinished( {".to_vec()),
    ];
    let mut rows = Vec::new();
    for (kind, source) in inputs {
        let request = Request::new(1, "rust", source, b"l3-workers-fixed-v1")?;
        let expected = worker_spike::direct(&request)?;
        let mut direct_times = Vec::new();
        let mut serialization = Vec::new();
        let mut pooled_times = Vec::new();
        let mut ipc_bytes = 0;
        let mut verification = Vec::new();
        let direct_start = Instant::now();
        for _ in 0..6 {
            let start = Instant::now();
            let parsed = worker_spike::direct(&request)?;
            direct_times.push(start.elapsed().as_secs_f64() * 1000.0);
            if parsed != expected {
                return Err("direct_equivalence".into());
            }
        }
        let direct_seconds = direct_start.elapsed().as_secs_f64();
        for _ in 0..6 {
            let start = Instant::now();
            let encoded = worker_spike::encode_request(&request)?;
            worker_spike::decode_request(&encoded)?;
            let encoded = worker_spike::encode_response(&expected)?;
            worker_spike::decode_response(&encoded)?;
            serialization.push(start.elapsed().as_secs_f64() * 1000.0);
        }
        let pool_start = Instant::now();
        for iteration in 0..3 {
            let mut tickets = Vec::new();
            for slot in 0..2 {
                let mut req = request.clone();
                req.identity.request = (iteration * 2 + slot + 10) as u64;
                let start = Instant::now();
                tickets.push((start, pool.submit(req.clone(), "")?, req));
            }
            for (start, ticket, req) in tickets {
                let outcome = ticket.wait()?;
                if !outcome.reaped {
                    return Err("not_reaped".into());
                }
                ipc_bytes += outcome.ipc_bytes;
                let result = outcome.result?;
                pooled_times.push(start.elapsed().as_secs_f64() * 1000.0);
                verification.push((result, req));
            }
        }
        let pool_seconds = pool_start.elapsed().as_secs_f64();
        for (result, req) in verification {
            if result != worker_spike::direct(&req)? {
                return Err("pool_equivalence".into());
            }
        }
        let (dp50, dp95) = stats(&direct_times);
        let (pp50, pp95) = stats(&pooled_times);
        let (sp50, sp95) = stats(&serialization);
        rows.push(format!("{{\"kind\":{},\"source_bytes\":{},\"source_blake3\":{},\"producer\":{},\"configuration\":{},\"repetitions\":6,\"direct_p50_ms\":{dp50},\"direct_p95_ms\":{dp95},\"pool_p50_ms_including_spawn\":{pp50},\"pool_p95_ms_including_spawn\":{pp95},\"codec_p50_ms\":{sp50},\"codec_p95_ms\":{sp95},\"direct_files_per_second\":{},\"pool_files_per_second_including_spawn\":{},\"ipc_bytes\":{ipc_bytes},\"logical_equivalence\":true,\"direct_samples_ms\":{:?},\"pool_samples_ms\":{:?},\"codec_samples_ms\":{:?}}}",json_string(kind),request.source.len(),json_string(blake3::Hash::from(request.identity.source_hash).to_hex().as_ref()),json_string(blake3::Hash::from(request.identity.producer).to_hex().as_ref()),json_string(blake3::Hash::from(request.identity.configuration).to_hex().as_ref()),6.0/direct_seconds,6.0/pool_seconds,direct_times,pooled_times,serialization));
    }
    let start = Instant::now();
    let outcome = worker_spike::supervise(
        Path::new(&executable),
        Request::new(
            99,
            "rust",
            b"fn startup() {}".to_vec(),
            b"l3-workers-fixed-v1",
        )?,
        "",
        Instant::now() + DEADLINE,
        &std::sync::atomic::AtomicBool::new(false),
    );
    outcome.result?;
    let startup = start.elapsed().as_secs_f64() * 1000.0;
    println!(
        "{{\"schema\":\"l3-worker-proof-v1\",\"version\":{},\"build_debug_assertions\":{},\"os\":{},\"arch\":{},\"workers\":2,\"queue\":8,\"source_limit\":8388608,\"response_limit\":16777216,\"aggregate_limit\":67108864,\"attempt_deadline_ms\":5000,\"retry_limit\":1,\"startup_parse_roundtrip_ms\":{startup},\"worker_lifecycle\":\"new process per attempt, reaped before acceptance\",\"cpu_seconds\":null,\"rss_aggregate_bytes\":null,\"resources_status\":\"not yet measured; payload reservation is not RSS cap\",\"cases\":[{}]}}",
        json_string(env!("CARGO_PKG_VERSION")),
        cfg!(debug_assertions),
        json_string(std::env::consts::OS),
        json_string(std::env::consts::ARCH),
        rows.join(",")
    );
    // Drop waits for finite in-flight deadlines and reaps successful attempts too.
    drop(pool);
    Ok(())
}
fn main() {
    let args: Vec<_> = std::env::args().skip(1).collect();
    let result = if args.len() == 2 && args[0] == "worker" {
        worker_spike::worker(&args[1])
    } else if args == ["demonstrate"] {
        demonstrate()
    } else {
        Err("usage: worker-spike worker <development fault or empty> | demonstrate".into())
    };
    if let Err(error) = result {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
