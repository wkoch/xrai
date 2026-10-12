use std::{
    io::{self, Cursor, Read},
    path::Path,
    sync::atomic::AtomicBool,
    time::{Duration, Instant},
};
use xrai_eval::{parsing_spike, worker_spike::*};
fn binary() -> &'static Path {
    Path::new(env!("CARGO_BIN_EXE_worker-spike"))
}
fn request(id: u64, dialect: &str, source: &[u8]) -> Request {
    Request::new(id, dialect, source.to_vec(), b"configuration-A").unwrap()
}
#[test]
fn roundtrip_and_direct_pool_equivalence_all_dialects() {
    let pool = Pool::new(binary().into());
    for dialect in parsing_spike::DIALECTS {
        for state in ["valid", "incomplete"] {
            let path = Path::new(env!("CARGO_MANIFEST_DIR"))
                .join(format!("tests/fixtures/parsing/{dialect}.{state}"));
            let source = std::fs::read(path).unwrap();
            let req = request(10, dialect, &source);
            let encoded = encode_request(&req).unwrap();
            assert_eq!(decode_request(&encoded).unwrap().source, source);
            let expected = direct(&req).unwrap();
            let result = pool.submit(req, "").unwrap().wait().unwrap();
            assert!(result.reaped);
            assert_eq!(result.attempts, 1);
            assert!(result.ipc_bytes > source.len());
            let actual = result.result.unwrap();
            assert_eq!(actual, expected);
            assert_eq!(
                actual.state,
                if state == "valid" {
                    State::Complete
                } else {
                    State::Partial
                }
            );
            assert_eq!(
                decode_response(&encode_response(&actual).unwrap()).unwrap(),
                actual
            );
        }
    }
    assert_eq!(pool.reserved(), 0);
}
#[test]
fn identities_spans_and_extra_bytes_refused() {
    let req = request(42, "rust", b"fn main() {}");
    let mut response = direct(&req).unwrap();
    for field in 0..6 {
        let mut bad = req.clone();
        match field {
            0 => bad.identity.request += 1,
            1 => bad.identity.attempt += 1,
            2 => bad.identity.dialect = "python".into(),
            3 => bad.identity.source_hash = [0; 32],
            4 => bad.identity.producer = [0; 32],
            _ => bad.identity.configuration = [0; 32],
        }
        assert_eq!(validate_response(&response, &bad), Err("identity".into()));
    }
    response.identity.attempt += 1;
    assert!(validate_response(&response, &req).is_err());
    response.identity = req.identity.clone();
    response.spans = vec![Span {
        start: 0,
        end: 1000,
    }];
    assert_eq!(validate_response(&response, &req), Err("span".into()));
    let mut encoded = encode_request(&req).unwrap();
    encoded.push(1);
    assert_eq!(decode_request(&encoded).unwrap_err(), "extra_bytes");
    let mut bad = req.clone();
    bad.source[0] ^= 1;
    assert_eq!(encode_request(&bad).unwrap_err(), "source_hash");
    bad = req.clone();
    bad.identity.producer = [0; 32];
    assert_eq!(encode_request(&bad).unwrap_err(), "producer");
    let different = Request::new(42, "rust", req.source, b"configuration-B").unwrap();
    assert_ne!(different.identity.configuration, req.identity.configuration);
}
#[test]
fn decoder_refuses_huge_header_before_payload_read_and_corrupt_enums() {
    struct HeaderOnly {
        header: Cursor<Vec<u8>>,
    }
    impl Read for HeaderOnly {
        fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
            assert!(
                self.header.position() < 14,
                "attempted to read oversized payload"
            );
            self.header.read(buf)
        }
    }
    let mut header = b"XRW1\x01\x00".to_vec();
    header.extend(u64::MAX.to_le_bytes());
    assert!(
        read_frame(
            &mut HeaderOnly {
                header: Cursor::new(header)
            },
            RESPONSE_LIMIT
        )
        .is_err()
    );
    let req = request(1, "rust", b"fn f() {}");
    let mut encoded = encode_response(&direct(&req).unwrap()).unwrap();
    // identity: request8+attempt4+dialect length8+rust4+hashes96
    encoded[120] = 255;
    assert_eq!(decode_response(&encoded).unwrap_err(), "state");
    let mut request_bytes = encode_request(&req).unwrap();
    request_bytes[120..128].copy_from_slice(&u64::MAX.to_le_bytes());
    assert!(decode_request(&request_bytes).is_err());
    let mut response_bytes = encode_response(&direct(&req).unwrap()).unwrap();
    response_bytes[145..153].copy_from_slice(&u64::MAX.to_le_bytes());
    assert!(decode_response(&response_bytes).is_err());
}
#[test]
fn faulty_worker_cannot_publish_and_independent_work_progresses() {
    let pool = Pool::new(binary().into());
    for fault in [
        "abort",
        "truncated",
        "wronghash",
        "wrongversion",
        "oversized",
    ] {
        let broken = pool
            .submit(request(1, "rust", b"fn broken() {}"), fault)
            .unwrap();
        let healthy = pool
            .submit(request(2, "go", b"package p\nfunc f() {}"), "")
            .unwrap();
        let healthy = healthy.wait().unwrap();
        assert!(healthy.result.is_ok());
        assert!(healthy.reaped);
        let broken = broken.wait().unwrap();
        assert!(broken.result.is_err(), "{fault}");
        assert!(broken.reaped);
        assert!(broken.attempts <= 2);
        if ["wronghash", "wrongversion", "oversized"].contains(&fault) {
            assert_eq!(broken.attempts, 1);
        }
    }
}
#[test]
fn finite_retry_in_new_process_and_stderr_capture_bounded() {
    let cancelled = AtomicBool::new(false);
    let mut req = request(1, "rust", b"fn f() {}");
    let result = supervise(
        binary(),
        req.clone(),
        "abort-once",
        Instant::now() + DEADLINE,
        &cancelled,
    );
    assert!(result.result.is_ok());
    assert_eq!(result.attempts, 2);
    assert_eq!(result.pids.len(), 2);
    assert_ne!(result.pids[0], result.pids[1]);
    assert!(result.reaped);
    req.identity.attempt = 1;
    assert_eq!(result.result.unwrap(), direct(&req).unwrap());
    let result = supervise(
        binary(),
        request(2, "rust", b"fn f() {}"),
        "stderr",
        Instant::now() + DEADLINE,
        &cancelled,
    );
    assert!(result.result.is_ok());
    assert_eq!(result.stderr.len(), 65536);
}
#[test]
fn deadlines_cancel_late_and_shutdown_are_bounded() {
    let cancelled = AtomicBool::new(false);
    let start = Instant::now();
    let result = supervise(
        binary(),
        request(1, "rust", b"fn f() {}"),
        "hang",
        start + Duration::from_millis(100),
        &cancelled,
    );
    assert_eq!(result.result.unwrap_err(), "deadline");
    assert_eq!(result.attempts, 1);
    assert!(result.reaped);
    assert!(start.elapsed() < Duration::from_secs(2));
    let pool = Pool::new(binary().into());
    let late = pool
        .submit(request(2, "rust", b"fn f() {}"), "late")
        .unwrap();
    assert!(late.wait_started(Duration::from_secs(2)).unwrap() > 0);
    late.cancel();
    let healthy = pool.submit(request(3, "rust", b"fn f() {}"), "").unwrap();
    assert!(healthy.wait().unwrap().result.is_ok());
    let result = late.wait().unwrap();
    assert_eq!(result.result.unwrap_err(), "cancelled");
    assert!(result.reaped);
    drop(pool);
}
#[test]
fn admission_overload_and_duplicate_requests_do_not_grow_memory() {
    let pool = Pool::new(binary().into());
    let mut tickets = Vec::new();
    for id in 0..3 {
        tickets.push(
            pool.submit(request(id, "rust", b"fn f() {}"), "hang")
                .unwrap(),
        );
    }
    assert_eq!(
        pool.submit(request(100, "rust", b"fn f() {}"), "")
            .unwrap_err(),
        "overload_bytes"
    );
    assert_eq!(
        pool.submit(request(0, "rust", b"fn f() {}"), "")
            .unwrap_err(),
        "duplicate_request"
    );
    assert!(pool.reserved() <= AGGREGATE_LIMIT);
    for ticket in &tickets {
        ticket.cancel();
    }
    for ticket in tickets {
        assert_eq!(ticket.wait().unwrap().result.unwrap_err(), "cancelled");
    }
    assert_eq!(pool.reserved(), 0);
    assert!(Request::new(999, "rust", vec![b' '; SOURCE_LIMIT + 1], b"").is_err());
}
#[test]
fn worker_is_given_bytes_and_does_not_reopen_source() {
    let source = b"fn exact_bytes_not_path() {}";
    let req = request(11, "rust", source);
    let result = supervise(
        binary(),
        req.clone(),
        "",
        Instant::now() + DEADLINE,
        &AtomicBool::new(false),
    );
    assert_eq!(result.result.unwrap(), direct(&req).unwrap());
    assert!(String::from_utf8(encode_request(&req).unwrap()).is_err()); // wire is binary, no path field
}

#[test]
fn queue_wait_consumes_total_deadline_before_spawn() {
    let pool = Pool::new(binary().into());
    let deadline = Instant::now() + Duration::from_millis(150);
    let first = pool
        .submit_before(request(1, "rust", b"fn f() {}"), "hang", deadline)
        .unwrap();
    let second = pool
        .submit_before(request(2, "rust", b"fn f() {}"), "hang", deadline)
        .unwrap();
    first.wait_started(Duration::from_secs(1)).unwrap();
    second.wait_started(Duration::from_secs(1)).unwrap();
    let queued = pool
        .submit_before(
            request(3, "rust", b"fn f() {}"),
            "",
            deadline - Duration::from_millis(20),
        )
        .unwrap();
    let outcome = queued.wait().unwrap();
    assert_eq!(outcome.result.unwrap_err(), "deadline");
    assert_eq!(outcome.attempts, 0);
    assert!(outcome.pids.is_empty());
    assert!(first.wait().unwrap().reaped);
    assert!(second.wait().unwrap().reaped);
}
#[test]
fn simultaneous_configurations_remain_distinct() {
    let pool = Pool::new(binary().into());
    let a = Request::new(1, "rust", b"fn f() {}".to_vec(), b"A").unwrap();
    let b = Request::new(2, "rust", b"fn f() {}".to_vec(), b"B").unwrap();
    let one = pool.submit(a.clone(), "").unwrap();
    let two = pool.submit(b.clone(), "").unwrap();
    let one = one.wait().unwrap().result.unwrap();
    let two = two.wait().unwrap().result.unwrap();
    assert_eq!(one, direct(&a).unwrap());
    assert_eq!(two, direct(&b).unwrap());
    assert_ne!(one.identity.configuration, two.identity.configuration);
}

#[test]
fn shutdown_with_inflight_failure_reaps_child() {
    let pool = Pool::new(binary().into());
    let ticket = pool
        .submit_before(
            request(70, "rust", b"fn f() {}"),
            "hang",
            Instant::now() + Duration::from_millis(150),
        )
        .unwrap();
    let pid = ticket.wait_started(Duration::from_secs(1)).unwrap();
    let start = Instant::now();
    drop(pool);
    assert!(start.elapsed() < Duration::from_secs(2));
    let outcome = ticket.wait().unwrap();
    assert!(outcome.reaped);
    assert_eq!(outcome.pids, vec![pid]);
    assert_eq!(outcome.result.unwrap_err(), "deadline");
}

#[test]
fn valid_frame_requires_successful_exit_and_roundtrips_repeat() {
    let cancelled = AtomicBool::new(false);
    let outcome = supervise(
        binary(),
        request(900, "rust", b"fn f() {}"),
        "exit-failure",
        Instant::now() + DEADLINE,
        &cancelled,
    );
    assert_eq!(outcome.result.unwrap_err(), "worker_exit");
    assert_eq!(outcome.attempts, 2);
    assert!(outcome.reaped);
    let pool = Pool::new(binary().into());
    for id in 0..32 {
        let req = request(id, "rust", b"fn f() {}");
        let result = pool.submit(req.clone(), "").unwrap().wait().unwrap();
        assert_eq!(result.attempts, 1);
        assert_eq!(result.result.unwrap(), direct(&req).unwrap());
        assert!(result.reaped);
    }
}

#[test]
fn executable_path_with_spaces_roundtrips_real_worker() {
    struct TemporaryCopy(std::path::PathBuf);
    impl Drop for TemporaryCopy {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }
    let unique = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let directory = std::env::temp_dir().join(format!(
        "xrai worker path with spaces {} {unique}",
        std::process::id()
    ));
    std::fs::create_dir(&directory).unwrap();
    let temporary = TemporaryCopy(directory);
    let copied = temporary.0.join("worker spike copied executable");
    std::fs::copy(binary(), &copied).unwrap();
    assert!(copied.to_str().unwrap().contains(' '));
    let req = request(80, "rust", b"fn worker_with_spaces() {}");
    let outcome = supervise(
        &copied,
        req.clone(),
        "",
        Instant::now() + DEADLINE,
        &AtomicBool::new(false),
    );
    assert_eq!(outcome.attempts, 1);
    assert_eq!(outcome.pids.len(), 1);
    assert!(outcome.reaped);
    assert_eq!(outcome.result.unwrap(), direct(&req).unwrap());
}
