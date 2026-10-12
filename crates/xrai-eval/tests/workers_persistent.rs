use std::time::{Duration, Instant};
use xrai_eval::{
    parsing_spike::DIALECTS,
    worker_persistent::{PersistentPool, Request, read_frame, validate_payload},
    worker_spike::{AGGREGATE_LIMIT, direct},
};
fn executable() -> std::path::PathBuf {
    env!("CARGO_BIN_EXE_worker-persistent").into()
}
fn request(id: u64, dialect: &str, source: &str) -> Request {
    Request::new(
        id,
        dialect,
        source.as_bytes().to_vec(),
        format!("config-{id}").as_bytes(),
    )
    .unwrap()
}
fn source(dialect: &str) -> &'static str {
    match dialect {
        "rust" => "fn ready() {}",
        "python" => "def ready():\n    pass\n",
        "go" => "package ready\nfunc Ready() {}",
        _ => "function ready() {}",
    }
}
fn eventually(f: impl Fn() -> bool) {
    let deadline = Instant::now() + Duration::from_secs(2);
    while !f() {
        assert!(Instant::now() < deadline);
        std::thread::sleep(Duration::from_millis(2));
    }
}
#[test]
fn cached_seven_dialects_configs_errors_and_repeat_equal_direct() {
    let pool = PersistentPool::new(executable());
    let mut workers = std::collections::HashMap::new();
    for id in 0..42 {
        let dialect = DIALECTS[id as usize % 7];
        let text = if (14..28).contains(&id) {
            "fn ( {"
        } else {
            source(dialect)
        };
        let req = request(id, dialect, text);
        let expected = direct(&req).unwrap();
        let result = pool.submit(req, "").unwrap().wait().unwrap();
        assert_eq!(result.response, expected);
        workers.entry(result.pid).or_insert(result.incarnation);
        assert_eq!(workers[&result.pid], result.incarnation);
        assert!(result.retired.is_empty());
    }
    assert!(workers.len() <= 2);
    assert_eq!(pool.reserved(), 0);
}
#[test]
fn crash_retry_reaped_replacement_then_healthy() {
    let pool = PersistentPool::new(executable());
    let req = request(1, "rust", source("rust"));
    let mut expected = direct(&req).unwrap();
    expected.identity.attempt = 1;
    let result = pool.submit(req, "crash_once").unwrap().wait().unwrap();
    assert_eq!(result.attempts, 2);
    assert_eq!(result.retired.len(), 1);
    assert_ne!(result.retired[0], result.pid);
    assert_eq!(result.response, expected);
    let req = request(2, "rust", source("rust"));
    let expected = direct(&req).unwrap();
    assert_eq!(
        pool.submit(req, "").unwrap().wait().unwrap().response,
        expected
    );
    assert_eq!(pool.reserved(), 0);
}
#[test]
fn cancel_busy_retires_while_other_worker_progresses_and_releases() {
    let pool = PersistentPool::new(executable());
    let hung = pool
        .submit(request(1, "rust", "fn ready() {}"), "hang")
        .unwrap();
    let (pid, _) = hung.wait_started(Duration::from_secs(2)).unwrap();
    let req = request(2, "python", source("python"));
    let expected = direct(&req).unwrap();
    let healthy = pool.submit(req, "").unwrap().wait().unwrap();
    assert_ne!(healthy.pid, pid);
    assert_eq!(healthy.response, expected);
    hung.cancel();
    assert!(hung.wait().err().unwrap().contains("cancelled"));
    assert_eq!(pool.reserved(), 0);
    assert!(
        pool.submit(request(3, "rust", source("rust")), "")
            .unwrap()
            .wait()
            .is_ok()
    );
}
#[test]
fn timeout_has_no_retry_and_shutdown_unblocks_reader_and_writer() {
    let pool = PersistentPool::new(executable());
    let hung = pool
        .submit_before(
            request(1, "rust", source("rust")),
            "hang",
            "",
            Instant::now() + Duration::from_millis(200),
        )
        .unwrap();
    assert!(hung.wait().err().unwrap().contains("timeout"));
    assert_eq!(pool.reserved(), 0);
    let held = pool
        .submit(request(2, "rust", source("rust")), "hang")
        .unwrap();
    held.wait_started(Duration::from_secs(2)).unwrap();
    let start = Instant::now();
    drop(pool);
    assert!(start.elapsed() < Duration::from_secs(2));
    assert!(held.wait().err().unwrap().contains("cancelled"));
}
#[test]
fn completed_tickets_retain_cap_until_wait_or_drop() {
    let pool = PersistentPool::new(executable());
    let mut tickets = Vec::new();
    for id in 0..3 {
        let ticket = pool
            .submit(request(id, "rust", source("rust")), "")
            .unwrap();
        ticket.wait_started(Duration::from_secs(2)).unwrap();
        tickets.push(ticket);
    }
    std::thread::sleep(Duration::from_millis(100));
    let held = pool.reserved();
    assert!(held > 48 * 1024 * 1024 && held <= AGGREGATE_LIMIT);
    assert!(
        pool.submit(request(4, "rust", source("rust")), "")
            .err()
            .unwrap()
            .contains("aggregate_limit")
    );
    tickets.pop().unwrap().wait().unwrap();
    assert!(pool.reserved() < held);
    tickets.clear();
    eventually(|| pool.reserved() == 0);
}
#[test]
fn abandoned_busy_ticket_releases_and_pool_recovers() {
    let pool = PersistentPool::new(executable());
    let ticket = pool
        .submit(request(1, "rust", source("rust")), "hang")
        .unwrap();
    ticket.wait_started(Duration::from_secs(2)).unwrap();
    drop(ticket);
    eventually(|| pool.reserved() == 0);
    assert!(
        pool.submit(request(2, "rust", source("rust")), "")
            .unwrap()
            .wait()
            .is_ok()
    );
}
#[test]
fn protocol_identity_payload_and_oversized_are_definitive() {
    for fault in [
        "old_attempt",
        "wrong_incarnation",
        "wrong_payload",
        "oversized",
    ] {
        let pool = PersistentPool::new(executable());
        let ticket = pool
            .submit(request(1, "rust", source("rust")), fault)
            .unwrap();
        let old = ticket.wait_started(Duration::from_secs(2)).unwrap();
        assert!(ticket.wait().is_err(), "{fault}");
        assert_eq!(pool.reserved(), 0);
        let good = pool
            .submit(request(2, "rust", source("rust")), "")
            .unwrap()
            .wait()
            .unwrap();
        assert_ne!((good.pid, good.incarnation), old);
    }
}
#[test]
fn partial_frame_transient_once_recovers() {
    let pool = PersistentPool::new(executable());
    let outcome = pool
        .submit(request(1, "rust", source("rust")), "partial_once")
        .unwrap()
        .wait()
        .unwrap();
    assert_eq!(outcome.attempts, 2);
    assert_eq!(outcome.retired.len(), 1);
}
#[test]
fn handshake_invalid_and_death_fail_without_leak() {
    for fault in ["bad_handshake", "handshake_death", "idle_death"] {
        let pool = PersistentPool::new(executable());
        let result = pool
            .submit_before(
                request(1, "rust", source("rust")),
                "",
                fault,
                Instant::now() + Duration::from_secs(2),
            )
            .unwrap()
            .wait();
        assert!(result.is_err(), "{fault}");
        assert_eq!(pool.reserved(), 0);
    }
}
#[test]
fn result_then_death_does_not_revoke_accepted_immutable_answer() {
    let pool = PersistentPool::new(executable());
    let req = request(1, "rust", source("rust"));
    let expected = direct(&req).unwrap();
    let response = pool
        .submit(req, "after_result_death")
        .unwrap()
        .wait()
        .unwrap()
        .response;
    assert_eq!(response, expected);
    std::thread::sleep(Duration::from_millis(30));
    for id in 2..6 {
        assert!(
            pool.submit(request(id, "rust", source("rust")), "")
                .unwrap()
                .wait()
                .is_ok()
        );
    }
    assert_eq!(response, expected);
}
#[test]
fn duplicate_never_publishes_as_next_request() {
    let pool = PersistentPool::new(executable());
    let req = request(1, "rust", source("rust"));
    let expected = direct(&req).unwrap();
    assert_eq!(
        pool.submit(req, "duplicate")
            .unwrap()
            .wait()
            .unwrap()
            .response,
        expected
    );
    std::thread::sleep(Duration::from_millis(30));
    let mut rejection = 0;
    for id in 2..8 {
        let req = request(id, "rust", source("rust"));
        let expected = direct(&req).unwrap();
        match pool.submit(req, "").unwrap().wait() {
            Ok(outcome) => assert_eq!(outcome.response, expected),
            Err(error) => {
                assert!(error.contains("protocol"));
                rejection += 1;
            }
        }
    }
    assert_eq!(rejection, 1);
}
#[test]
fn codec_rejects_wrong_magic_type_and_limit_before_allocation() {
    for (magic, kind, length) in [(b"XRW1", 4, 0), (b"XRW2", 255, 0), (b"XRW2", 4, u64::MAX)] {
        let mut frame = Vec::new();
        frame.extend_from_slice(magic);
        frame.extend_from_slice(&2u16.to_le_bytes());
        frame.push(kind);
        frame.extend_from_slice(&length.to_le_bytes());
        frame.extend_from_slice(&[0; 32]);
        assert!(read_frame(&mut frame.as_slice()).is_err());
    }
}
#[test]
fn envelope_json_and_positions_cannot_disagree() {
    let req = request(1, "rust", "fn ( {\r\n");
    let original = direct(&req).unwrap();
    assert!(validate_payload(&original, &req).is_ok());
    let mut response = original.clone();
    let mut value: serde_json::Value = serde_json::from_slice(&response.payload).unwrap();
    value["node_count"] = serde_json::json!(0);
    response.payload = serde_json::to_vec(&value).unwrap();
    assert!(validate_payload(&response, &req).is_err());
    let mut response = original.clone();
    let mut value: serde_json::Value = serde_json::from_slice(&response.payload).unwrap();
    value["diagnostics"][0]["start_line"] = serde_json::json!(999);
    response.payload = serde_json::to_vec(&value).unwrap();
    assert!(validate_payload(&response, &req).is_err());
}

#[test]
fn completed_cancel_is_checked_at_transfer_and_releases_reservation() {
    let pool = PersistentPool::new(executable());
    let ticket = pool.submit(request(1, "rust", source("rust")), "").unwrap();
    ticket.wait_started(Duration::from_secs(2)).unwrap();
    std::thread::sleep(Duration::from_millis(100));
    assert!(pool.reserved() > 0);
    ticket.cancel();
    assert!(ticket.wait().err().unwrap().contains("cancelled"));
    assert_eq!(pool.reserved(), 0);
}
#[test]
fn retry_attempt_overflow_is_definitive_without_panicking() {
    let pool = PersistentPool::new(executable());
    let mut req = request(1, "rust", source("rust"));
    req.identity.attempt = u32::MAX;
    assert!(
        pool.submit(req, "crash_once")
            .unwrap()
            .wait()
            .err()
            .unwrap()
            .contains("attempt_overflow")
    );
    assert_eq!(pool.reserved(), 0);
}

#[test]
fn stderr_above_retention_limit_is_drained_without_backpressure_deadlock() {
    let pool = PersistentPool::new(executable());
    let req = request(1, "rust", source("rust"));
    let expected = direct(&req).unwrap();
    assert_eq!(
        pool.submit(req, "stderr").unwrap().wait().unwrap().response,
        expected
    );
    assert_eq!(pool.reserved(), 0);
}
#[test]
fn caller_cannot_extend_reference_deadline() {
    let pool = PersistentPool::new(executable());
    let start = Instant::now();
    let ticket = pool
        .submit_before(
            request(1, "rust", source("rust")),
            "hang",
            "",
            start + Duration::from_secs(3600),
        )
        .unwrap();
    assert!(ticket.wait().err().unwrap().contains("timeout"));
    assert!(start.elapsed() < Duration::from_secs(7));
    assert_eq!(pool.reserved(), 0);
}

#[test]
fn premature_frame_with_blocked_large_writer_is_rejected_and_reaped_in_deadline() {
    for fault in ["premature_ready", "premature_result"] {
        let pool = PersistentPool::new(executable());
        let large_source = vec![b' '; 8 * 1024 * 1024];
        let start = Instant::now();
        let ticket = pool
            .submit_before(
                Request::new(1, "rust", large_source, b"large").unwrap(),
                "",
                fault,
                start + Duration::from_secs(2),
            )
            .unwrap();
        ticket.wait_started(Duration::from_secs(2)).unwrap();
        let other = request(2, "python", source("python"));
        let expected = direct(&other).unwrap();
        assert_eq!(
            pool.submit(other, "").unwrap().wait().unwrap().response,
            expected
        );
        assert!(ticket.wait().err().unwrap().contains("protocol"));
        assert!(start.elapsed() < Duration::from_secs(3), "{fault}");
        assert_eq!(pool.reserved(), 0);
        let shutdown = Instant::now();
        drop(pool);
        assert!(shutdown.elapsed() < Duration::from_secs(2));
    }
}

#[test]
fn valid_result_without_draining_large_write_still_obeys_timeout_and_cancel() {
    for cancel in [false, true] {
        let pool = PersistentPool::new(executable());
        let req = Request::new(1, "rust", vec![b' '; 8 * 1024 * 1024], b"large").unwrap();
        let start = Instant::now();
        let ticket = pool
            .submit_before(
                req,
                "",
                "premature_valid_result",
                start + Duration::from_secs(2),
            )
            .unwrap();
        ticket.wait_started(Duration::from_secs(2)).unwrap();
        if cancel {
            std::thread::sleep(Duration::from_millis(300));
            ticket.cancel();
        }
        let error = ticket.wait().err().unwrap();
        assert!(
            error.contains(if cancel { "cancelled" } else { "timeout" }),
            "{error}"
        );
        assert!(start.elapsed() < Duration::from_secs(3));
        assert_eq!(pool.reserved(), 0);
    }
}
#[test]
fn dense_diagnostic_positions_validate_with_linear_source_scan() {
    let req = request(1, "rust", &"fn ready() { let x = ; }\r\n".repeat(2048));
    let response = direct(&req).unwrap();
    assert!(response.spans.len() >= 2048);
    let start = Instant::now();
    assert!(validate_payload(&response, &req).is_ok());
    assert!(start.elapsed() < Duration::from_secs(2));
}
