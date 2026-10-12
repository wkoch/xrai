//! L3-03 experimental bounded byte-only parsing IPC. No product runtime is exposed.
use crate::parsing_spike;
use std::{
    collections::BTreeSet,
    io::{self, Read, Write},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, AtomicU32, AtomicUsize, Ordering},
        mpsc,
    },
    thread,
    time::{Duration, Instant},
};

pub const SOURCE_LIMIT: usize = 8 * 1024 * 1024;
pub const RESPONSE_LIMIT: usize = 16 * 1024 * 1024;
pub const AGGREGATE_LIMIT: usize = 64 * 1024 * 1024;
pub const WORKERS: usize = 2;
pub const QUEUE: usize = 8;
pub const DEADLINE: Duration = Duration::from_secs(5);
const STDERR_LIMIT: usize = 64 * 1024;
const MAGIC: &[u8; 4] = b"XRW1";
const VERSION: u16 = 1;
type Result<T> = std::result::Result<T, String>;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Identity {
    pub request: u64,
    pub attempt: u32,
    pub dialect: String,
    pub source_hash: [u8; 32],
    pub producer: [u8; 32],
    pub configuration: [u8; 32],
}
#[derive(Clone, Debug)]
pub struct Request {
    pub identity: Identity,
    pub source: Vec<u8>,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Span {
    pub start: u64,
    pub end: u64,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum State {
    Complete,
    Partial,
    Error,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Response {
    pub identity: Identity,
    pub state: State,
    pub source_bytes: u64,
    pub node_count: u64,
    pub query_matches: u64,
    pub spans: Vec<Span>,
    pub payload: Vec<u8>,
}
impl Request {
    pub fn new(request: u64, dialect: &str, source: Vec<u8>, configuration: &[u8]) -> Result<Self> {
        if source.len() > SOURCE_LIMIT {
            return Err("source_limit".into());
        }
        let producer = producer(dialect)?;
        Ok(Self {
            identity: Identity {
                request,
                attempt: 0,
                dialect: dialect.into(),
                source_hash: *blake3::hash(&source).as_bytes(),
                producer,
                configuration: *blake3::hash(configuration).as_bytes(),
            },
            source,
        })
    }
}
pub fn producer(dialect: &str) -> Result<[u8; 32]> {
    let grammar = parsing_spike::grammar(dialect).map_err(|e| e.to_string())?;
    let mut hash = blake3::Hasher::new();
    for value in [
        "tree-sitter=0.27.1",
        grammar.crate_name,
        grammar.version,
        grammar.node_types,
        grammar.query,
        include_str!("../parsing-provenance.json"),
    ] {
        hash.update(&(value.len() as u64).to_le_bytes());
        hash.update(value.as_bytes());
    }
    hash.update(&(grammar.language.abi_version() as u64).to_le_bytes());
    Ok(*hash.finalize().as_bytes())
}
fn number(out: &mut Vec<u8>, n: u64) {
    out.extend(n.to_le_bytes());
}
fn bytes(out: &mut Vec<u8>, value: &[u8]) {
    number(out, value.len() as u64);
    out.extend(value);
}
fn identity(out: &mut Vec<u8>, value: &Identity) {
    number(out, value.request);
    out.extend(value.attempt.to_le_bytes());
    bytes(out, value.dialect.as_bytes());
    out.extend(value.source_hash);
    out.extend(value.producer);
    out.extend(value.configuration);
}
struct Decoder<'a> {
    bytes: &'a [u8],
    position: usize,
}
impl<'a> Decoder<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8]> {
        let end = self.position.checked_add(n).ok_or("overflow")?;
        let value = self.bytes.get(self.position..end).ok_or("truncated")?;
        self.position = end;
        Ok(value)
    }
    fn u64(&mut self) -> Result<u64> {
        Ok(u64::from_le_bytes(
            self.take(8)?.try_into().map_err(|_| "u64")?,
        ))
    }
    fn blob(&mut self, max: usize) -> Result<&'a [u8]> {
        let n = usize::try_from(self.u64()?).map_err(|_| "overflow")?;
        if n > max {
            return Err("length_limit".into());
        }
        self.take(n)
    }
    fn identity(&mut self) -> Result<Identity> {
        Ok(Identity {
            request: self.u64()?,
            attempt: u32::from_le_bytes(self.take(4)?.try_into().map_err(|_| "u32")?),
            dialect: std::str::from_utf8(self.blob(32)?)
                .map_err(|_| "dialect_utf8")?
                .into(),
            source_hash: self.take(32)?.try_into().map_err(|_| "hash")?,
            producer: self.take(32)?.try_into().map_err(|_| "producer")?,
            configuration: self.take(32)?.try_into().map_err(|_| "configuration")?,
        })
    }
    fn finish(self) -> Result<()> {
        if self.position == self.bytes.len() {
            Ok(())
        } else {
            Err("extra_bytes".into())
        }
    }
}
pub fn encode_request(request: &Request) -> Result<Vec<u8>> {
    validate_request(request)?;
    let mut out = Vec::new();
    identity(&mut out, &request.identity);
    bytes(&mut out, &request.source);
    Ok(out)
}
pub fn decode_request(frame: &[u8]) -> Result<Request> {
    if frame.len() > SOURCE_LIMIT + 256 {
        return Err("frame_limit".into());
    }
    let mut d = Decoder {
        bytes: frame,
        position: 0,
    };
    let identity = d.identity()?;
    let source = d.blob(SOURCE_LIMIT)?.to_vec();
    d.finish()?;
    let request = Request { identity, source };
    validate_request(&request)?;
    Ok(request)
}
fn validate_request(request: &Request) -> Result<()> {
    if request.source.len() > SOURCE_LIMIT {
        return Err("source_limit".into());
    }
    if request.identity.source_hash != *blake3::hash(&request.source).as_bytes() {
        return Err("source_hash".into());
    }
    if request.identity.producer != producer(&request.identity.dialect)? {
        return Err("producer".into());
    }
    Ok(())
}
pub fn encode_response(response: &Response) -> Result<Vec<u8>> {
    let size = 8usize
        .checked_add(4)
        .and_then(|n| n.checked_add(8 + response.identity.dialect.len()))
        .and_then(|n| n.checked_add(96 + 1 + 24 + 8 + 8))
        .and_then(|n| {
            response
                .spans
                .len()
                .checked_mul(16)
                .and_then(|spans| n.checked_add(spans))
        })
        .and_then(|n| n.checked_add(response.payload.len()))
        .ok_or("overflow")?;
    if size > RESPONSE_LIMIT {
        return Err("response_limit".into());
    }
    let mut out = Vec::new();
    identity(&mut out, &response.identity);
    out.push(match response.state {
        State::Complete => 0,
        State::Partial => 1,
        State::Error => 2,
    });
    number(&mut out, response.source_bytes);
    number(&mut out, response.node_count);
    number(&mut out, response.query_matches);
    number(&mut out, response.spans.len() as u64);
    for span in &response.spans {
        number(&mut out, span.start);
        number(&mut out, span.end);
    }
    bytes(&mut out, &response.payload);
    if out.len() > RESPONSE_LIMIT {
        return Err("response_limit".into());
    }
    Ok(out)
}
pub fn decode_response(frame: &[u8]) -> Result<Response> {
    if frame.len() > RESPONSE_LIMIT {
        return Err("frame_limit".into());
    }
    let mut d = Decoder {
        bytes: frame,
        position: 0,
    };
    let identity = d.identity()?;
    let state = match d.take(1)?[0] {
        0 => State::Complete,
        1 => State::Partial,
        2 => State::Error,
        _ => return Err("state".into()),
    };
    let source_bytes = d.u64()?;
    let node_count = d.u64()?;
    let query_matches = d.u64()?;
    let count = usize::try_from(d.u64()?).map_err(|_| "overflow")?;
    if count > RESPONSE_LIMIT / 16
        || count.checked_mul(16).ok_or("overflow")? > frame.len().saturating_sub(d.position)
    {
        return Err("spans_length".into());
    }
    let mut spans = Vec::with_capacity(count);
    for _ in 0..count {
        spans.push(Span {
            start: d.u64()?,
            end: d.u64()?,
        });
    }
    let payload = d.blob(RESPONSE_LIMIT)?.to_vec();
    d.finish()?;
    Ok(Response {
        identity,
        state,
        source_bytes,
        node_count,
        query_matches,
        spans,
        payload,
    })
}
pub fn write_frame(writer: &mut impl Write, payload: &[u8], max: usize) -> Result<()> {
    if payload.len() > max {
        return Err("frame_limit".into());
    }
    writer
        .write_all(MAGIC)
        .and_then(|()| writer.write_all(&VERSION.to_le_bytes()))
        .and_then(|()| writer.write_all(&(payload.len() as u64).to_le_bytes()))
        .and_then(|()| writer.write_all(payload))
        .and_then(|()| writer.flush())
        .map_err(|e| e.to_string())
}
pub fn read_frame(reader: &mut impl Read, max: usize) -> Result<Vec<u8>> {
    let mut header = [0; 14];
    reader
        .read_exact(&mut header)
        .map_err(|e| format!("transport:{:?}:{e}", e.kind()))?;
    if &header[..4] != MAGIC {
        return Err("magic".into());
    }
    if u16::from_le_bytes(header[4..6].try_into().map_err(|_| "version")?) != VERSION {
        return Err("version".into());
    }
    let length = usize::try_from(u64::from_le_bytes(
        header[6..].try_into().map_err(|_| "length")?,
    ))
    .map_err(|_| "overflow")?;
    if length > max {
        return Err("frame_limit".into());
    }
    let mut payload = vec![0; length];
    reader
        .read_exact(&mut payload)
        .map_err(|e| format!("transport:{:?}:{e}", e.kind()))?;
    Ok(payload)
}
pub fn direct(request: &Request) -> Result<Response> {
    validate_request(request)?;
    match parsing_spike::parse(&request.identity.dialect, &request.source) {
        Ok(parsed) => Ok(Response {
            identity: request.identity.clone(),
            state: if parsed.complete {
                State::Complete
            } else {
                State::Partial
            },
            source_bytes: parsed.source_bytes as u64,
            node_count: parsed.node_count as u64,
            query_matches: parsed.query_matches as u64,
            spans: parsed
                .diagnostics
                .iter()
                .map(|d| Span {
                    start: d.start_byte as u64,
                    end: d.end_byte as u64,
                })
                .collect(),
            payload: parsed.json(&request.identity.dialect).into_bytes(),
        }),
        Err(error) => Ok(Response {
            identity: request.identity.clone(),
            state: State::Error,
            source_bytes: request.source.len() as u64,
            node_count: 0,
            query_matches: 0,
            spans: Vec::new(),
            payload: error.to_string().into_bytes(),
        }),
    }
}
pub fn validate_response(response: &Response, request: &Request) -> Result<()> {
    if response.identity != request.identity {
        return Err("identity".into());
    }
    if response.source_bytes != request.source.len() as u64 {
        return Err("source_length".into());
    }
    if response
        .spans
        .iter()
        .any(|s| s.start > s.end || s.end > response.source_bytes)
    {
        return Err("span".into());
    }
    Ok(())
}
/// Fault injection exists only in this development executable.
pub fn worker(fault: &str) -> Result<()> {
    let frame = read_frame(&mut io::stdin().lock(), SOURCE_LIMIT + 256)?;
    let request = decode_request(&frame)?;
    match fault {
        "abort" => std::process::abort(),
        "hang" => loop {
            thread::park();
        },
        "truncated" => {
            io::stdout().write_all(b"XRW").map_err(|e| e.to_string())?;
            return Ok(());
        }
        "oversized" => {
            let mut h = Vec::from(*MAGIC);
            h.extend(VERSION.to_le_bytes());
            h.extend(u64::MAX.to_le_bytes());
            io::stdout().write_all(&h).map_err(|e| e.to_string())?;
            return Ok(());
        }
        "wrongversion" => {
            io::stdout()
                .write_all(b"XRW1\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00")
                .map_err(|e| e.to_string())?;
            return Ok(());
        }
        "stderr" => {
            let block = [b'!'; 4096];
            for _ in 0..100 {
                io::stderr().write_all(&block).map_err(|e| e.to_string())?;
            }
        }
        "" | "wronghash" | "late" | "abort-once" | "exit-failure" => (),
        _ => return Err("unknown_fault".into()),
    }
    if fault == "abort-once" && request.identity.attempt == 0 {
        std::process::abort();
    }
    if fault == "late" {
        thread::sleep(Duration::from_secs(10));
    }
    let mut response = direct(&request)?;
    if fault == "wronghash" {
        response.identity.source_hash = [0; 32];
    }
    write_frame(
        &mut io::stdout().lock(),
        &encode_response(&response)?,
        RESPONSE_LIMIT,
    )?;
    if fault == "exit-failure" {
        Err("injected failure after valid response".into())
    } else {
        Ok(())
    }
}

#[derive(Debug)]
pub struct Outcome {
    pub result: Result<Response>,
    pub attempts: u32,
    pub pids: Vec<u32>,
    pub stderr: Vec<u8>,
    pub ipc_bytes: usize,
    pub elapsed: Duration,
    pub reaped: bool,
}
struct Counted<T> {
    inner: T,
    count: Arc<AtomicUsize>,
}
impl<T: Read> Read for Counted<T> {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        let n = self.inner.read(buffer)?;
        self.count.fetch_add(n, Ordering::Relaxed);
        Ok(n)
    }
}
impl<T: Write> Write for Counted<T> {
    fn write(&mut self, buffer: &[u8]) -> io::Result<usize> {
        let n = self.inner.write(buffer)?;
        self.count.fetch_add(n, Ordering::Relaxed);
        Ok(n)
    }
    fn flush(&mut self) -> io::Result<()> {
        self.inner.flush()
    }
}
fn attempt(
    executable: &Path,
    request: &Request,
    fault: &str,
    deadline: Instant,
    cancelled: &AtomicBool,
    running: Option<&AtomicU32>,
) -> (Result<Response>, u32, Vec<u8>, usize, bool) {
    let payload = match encode_request(request) {
        Ok(p) => p,
        Err(e) => return (Err(e), 0, Vec::new(), 0, true),
    };
    let mut child = match Command::new(executable)
        .args(["worker", fault])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => return (Err(format!("spawn:{e}")), 0, Vec::new(), 0, true),
    };
    let pid = child.id();
    if let Some(running) = running {
        running.store(pid, Ordering::Release);
    }
    let input_count = Arc::new(AtomicUsize::new(0));
    let output_count = Arc::new(AtomicUsize::new(0));
    let mut input = Counted {
        inner: child.stdin.take().expect("piped stdin"),
        count: input_count.clone(),
    };
    let mut output = Counted {
        inner: child.stdout.take().expect("piped stdout"),
        count: output_count.clone(),
    };
    let mut stderr = child.stderr.take().expect("piped stderr");
    let writer = thread::spawn(move || write_frame(&mut input, &payload, SOURCE_LIMIT + 256));
    let (tx, rx) = mpsc::sync_channel(1);
    let reader = thread::spawn(move || {
        let result = read_frame(&mut output, RESPONSE_LIMIT).and_then(|frame| {
            // One response, then EOF: trailing transport bytes are rejected too.
            let mut extra = [0];
            if output.read(&mut extra).map_err(|e| e.to_string())? != 0 {
                return Err("extra_bytes".into());
            }
            let bytes = frame.len() + 14;
            decode_response(&frame).map(|r| (r, bytes))
        });
        let _ = tx.send(result);
    });
    let drain = thread::spawn(move || {
        let mut kept = Vec::new();
        let mut buffer = [0; 4096];
        while let Ok(n) = stderr.read(&mut buffer) {
            if n == 0 {
                break;
            }
            let room = STDERR_LIMIT.saturating_sub(kept.len());
            kept.extend(&buffer[..n.min(room)]);
        }
        kept
    });
    let result = loop {
        if cancelled.load(Ordering::Acquire) {
            break Err("cancelled".into());
        }
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            break Err("deadline".into());
        }
        match rx.recv_timeout(remaining.min(Duration::from_millis(10))) {
            Ok(result) => break result,
            Err(mpsc::RecvTimeoutError::Timeout) => (),
            Err(mpsc::RecvTimeoutError::Disconnected) => break Err("pipe".into()),
        }
    };
    // A valid frame followed by EOF can precede waitable exit by a scheduling
    // instant. Do not turn that successful response into SIGKILL ourselves.
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break Ok(status),
            Ok(None)
                if result.is_ok()
                    && !cancelled.load(Ordering::Acquire)
                    && Instant::now() < deadline =>
            {
                thread::sleep(Duration::from_millis(1));
            }
            _ => {
                let _ = child.kill();
                break child.wait();
            }
        }
    };
    let reaped = status.is_ok();
    let successful = status.is_ok_and(|s| s.success());
    let _ = writer.join();
    let _ = reader.join();
    let stderr = drain.join().unwrap_or_default();
    let result = if cancelled.load(Ordering::Acquire) {
        Err("cancelled".into())
    } else if Instant::now() >= deadline {
        Err("deadline".into())
    } else {
        result
    };
    let (result, _decoded_bytes) = match result {
        Ok((response, n)) => (
            if successful {
                validate_response(&response, request).map(|()| response)
            } else {
                Err("worker_exit".into())
            },
            n,
        ),
        Err(e) => (Err(e), 0),
    };
    let ipc = input_count.load(Ordering::Relaxed) + output_count.load(Ordering::Relaxed);
    (result, pid, stderr, ipc, reaped)
}
pub fn supervise(
    executable: &Path,
    request: Request,
    fault: &str,
    deadline: Instant,
    cancelled: &AtomicBool,
) -> Outcome {
    supervise_active(executable, request, fault, deadline, cancelled, None)
}
fn supervise_active(
    executable: &Path,
    mut request: Request,
    fault: &str,
    deadline: Instant,
    cancelled: &AtomicBool,
    running: Option<&AtomicU32>,
) -> Outcome {
    let start = Instant::now();
    let deadline = deadline.min(start + DEADLINE);
    let mut outcome = Outcome {
        result: Err("deadline".into()),
        attempts: 0,
        pids: Vec::new(),
        stderr: Vec::new(),
        ipc_bytes: 0,
        elapsed: Duration::ZERO,
        reaped: true,
    };
    if let Err(error) = validate_request(&request) {
        outcome.result = Err(error);
        return outcome;
    }
    for attempt_id in 0..=1 {
        if cancelled.load(Ordering::Acquire) {
            outcome.result = Err("cancelled".into());
            break;
        }
        if Instant::now() >= deadline {
            break;
        }
        request.identity.attempt = attempt_id;
        let (result, pid, stderr, bytes, reaped) = attempt(
            executable,
            &request,
            fault,
            deadline.min(Instant::now() + DEADLINE),
            cancelled,
            running,
        );
        outcome.attempts += 1;
        if pid != 0 {
            outcome.pids.push(pid);
        }
        outcome.stderr = stderr;
        outcome.ipc_bytes += bytes;
        outcome.reaped &= reaped;
        let retry = matches!(&result, Err(e) if e.starts_with("transport:") || e == "worker_exit");
        outcome.result = result;
        if !retry {
            break;
        }
    }
    outcome.elapsed = start.elapsed();
    outcome
}
struct Job {
    request: Request,
    fault: String,
    deadline: Instant,
    cancelled: Arc<AtomicBool>,
    running: Arc<AtomicU32>,
    sender: mpsc::SyncSender<Outcome>,
    reservation: usize,
}
struct Accounting {
    reserved: usize,
    active: BTreeSet<u64>,
}
#[derive(Debug)]
pub struct Ticket {
    pub id: u64,
    cancelled: Arc<AtomicBool>,
    running: Arc<AtomicU32>,
    receiver: mpsc::Receiver<Outcome>,
}
impl Ticket {
    pub fn wait_started(&self, timeout: Duration) -> Result<u32> {
        let deadline = Instant::now() + timeout;
        loop {
            let pid = self.running.load(Ordering::Acquire);
            if pid != 0 {
                return Ok(pid);
            }
            if Instant::now() >= deadline {
                return Err("start_deadline".into());
            }
            thread::sleep(Duration::from_millis(1));
        }
    }
    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::Release);
    }
    pub fn wait(self) -> Result<Outcome> {
        let mut outcome = self
            .receiver
            .recv_timeout(DEADLINE + Duration::from_secs(1))
            .map_err(|e| e.to_string())?;
        if self.cancelled.load(Ordering::Acquire) {
            outcome.result = Err("cancelled".into());
        }
        Ok(outcome)
    }
}
impl Drop for Ticket {
    fn drop(&mut self) {
        self.cancel();
    }
}
pub struct Pool {
    sender: Option<mpsc::SyncSender<Job>>,
    threads: Vec<thread::JoinHandle<()>>,
    accounting: Arc<Mutex<Accounting>>,
}
impl Pool {
    pub fn new(executable: PathBuf) -> Self {
        let (sender, receiver) = mpsc::sync_channel::<Job>(QUEUE);
        let receiver = Arc::new(Mutex::new(receiver));
        let accounting = Arc::new(Mutex::new(Accounting {
            reserved: 0,
            active: BTreeSet::new(),
        }));
        let mut threads = Vec::new();
        for _ in 0..WORKERS {
            let receiver = receiver.clone();
            let accounting = accounting.clone();
            let executable = executable.clone();
            threads.push(thread::spawn(move || {
                loop {
                    let job = match receiver.lock().expect("queue lock").recv() {
                        Ok(job) => job,
                        Err(_) => break,
                    };
                    let id = job.request.identity.request;
                    let outcome = supervise_active(
                        &executable,
                        job.request,
                        &job.fault,
                        job.deadline,
                        &job.cancelled,
                        Some(&job.running),
                    );
                    let mut count = accounting.lock().expect("accounting lock");
                    count.reserved -= job.reservation;
                    count.active.remove(&id);
                    drop(count);
                    let _ = job.sender.send(outcome);
                }
            }));
        }
        Self {
            sender: Some(sender),
            threads,
            accounting,
        }
    }
    pub fn submit(&self, request: Request, fault: &str) -> Result<Ticket> {
        self.submit_before(request, fault, Instant::now() + DEADLINE)
    }
    /// A caller may tighten the total admission deadline, never extend the fixed cap.
    pub fn submit_before(
        &self,
        request: Request,
        fault: &str,
        deadline: Instant,
    ) -> Result<Ticket> {
        let deadline = deadline.min(Instant::now() + DEADLINE);
        validate_request(&request)?;
        let reservation = request
            .source
            .len()
            .checked_add(RESPONSE_LIMIT)
            .ok_or("overflow")?;
        let mut count = self.accounting.lock().map_err(|_| "accounting")?;
        if count.active.contains(&request.identity.request) {
            return Err("duplicate_request".into());
        }
        if count.reserved.checked_add(reservation).ok_or("overflow")? > AGGREGATE_LIMIT {
            return Err("overload_bytes".into());
        }
        count.reserved += reservation;
        count.active.insert(request.identity.request);
        let id = request.identity.request;
        let running = Arc::new(AtomicU32::new(0));
        let cancelled = Arc::new(AtomicBool::new(false));
        let (sender, receiver) = mpsc::sync_channel(1);
        let job = Job {
            request,
            fault: fault.into(),
            deadline,
            cancelled: cancelled.clone(),
            running: running.clone(),
            sender,
            reservation,
        };
        if self
            .sender
            .as_ref()
            .ok_or("shutdown")?
            .try_send(job)
            .is_err()
        {
            count.reserved -= reservation;
            count.active.remove(&id);
            return Err("overload_queue".into());
        }
        Ok(Ticket {
            id,
            cancelled,
            running,
            receiver,
        })
    }
    pub fn reserved(&self) -> usize {
        self.accounting.lock().expect("accounting").reserved
    }
}
impl Drop for Pool {
    fn drop(&mut self) {
        self.sender.take();
        for thread in self.threads.drain(..) {
            let _ = thread.join();
        }
    }
}
