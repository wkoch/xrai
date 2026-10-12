//! Experimental XRW2 persistent workers. XRW1 remains an independent control.
use crate::{parsing_spike as parsing, worker_spike as single};
use serde_json::{Value, json};
pub use single::{Request, Response};
use std::collections::HashMap;
use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicBool, Ordering},
    mpsc,
};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};
use tree_sitter::{Node, Parser, Query, QueryCursor, StreamingIterator};
pub type Result<T> = std::result::Result<T, String>;
const MAX_FRAME: usize = single::RESPONSE_LIMIT + 256;
const STDERR_LIMIT: usize = 64 * 1024;
const HELLO: u8 = 1;
const READY: u8 = 2;
const PARSE: u8 = 3;
const RESULT: u8 = 4;
const SHUTDOWN: u8 = 5;

/// Cap is checked before allocation, including unknown types and truncated bodies.
pub fn read_frame(reader: &mut impl Read) -> Result<(u8, [u8; 32], Vec<u8>)> {
    let mut header = [0; 47];
    reader
        .read_exact(&mut header)
        .map_err(|e| format!("transport:{e}"))?;
    if &header[..4] != b"XRW2" || header[4..6] != 2u16.to_le_bytes() {
        return Err("protocol:version".into());
    }
    if !(HELLO..=SHUTDOWN).contains(&header[6]) {
        return Err("protocol:type".into());
    }
    let size = usize::try_from(u64::from_le_bytes(header[7..15].try_into().unwrap()))
        .map_err(|_| "protocol:length")?;
    let cap = match header[6] {
        PARSE => single::SOURCE_LIMIT + 256,
        HELLO | READY => 64 * 1024,
        SHUTDOWN => 0,
        _ => MAX_FRAME,
    };
    if size > cap {
        return Err("protocol:frame_limit".into());
    }
    let incarnation = header[15..47].try_into().unwrap();
    let mut body = vec![0; size];
    reader
        .read_exact(&mut body)
        .map_err(|e| format!("transport:{e}"))?;
    Ok((header[6], incarnation, body))
}
pub fn write_frame(
    writer: &mut impl Write,
    kind: u8,
    incarnation: [u8; 32],
    body: &[u8],
) -> Result<()> {
    if !(HELLO..=SHUTDOWN).contains(&kind) || body.len() > MAX_FRAME {
        return Err("protocol:frame_limit/type".into());
    }
    writer
        .write_all(b"XRW2")
        .and_then(|()| writer.write_all(&2u16.to_le_bytes()))
        .and_then(|()| writer.write_all(&[kind]))
        .and_then(|()| writer.write_all(&(body.len() as u64).to_le_bytes()))
        .and_then(|()| writer.write_all(&incarnation))
        .and_then(|()| writer.write_all(body))
        .and_then(|()| writer.flush())
        .map_err(|e| format!("transport:{e}"))
}
fn handshake() -> Result<Vec<u8>> {
    let producers: Vec<Value> = parsing::DIALECTS
        .iter()
        .map(|dialect| Ok(json!({"dialect":dialect,"producer":single::producer(dialect)?})))
        .collect::<Result<_>>()?;
    serde_json::to_vec(&json!({"version":2,"workers":2,"queue":8,"source_limit":single::SOURCE_LIMIT,"response_limit":single::RESPONSE_LIMIT,"reserved_limit":single::AGGREGATE_LIMIT,"deadline_ms":5000,"stderr_limit":STDERR_LIMIT,"producers":producers})).map_err(|e| e.to_string())
}
fn random_incarnation() -> Result<[u8; 32]> {
    // Both supported hosts expose OS entropy here; never derive identity from PID/time.
    let mut bytes = [0; 32];
    std::fs::File::open("/dev/urandom")
        .and_then(|mut f| f.read_exact(&mut bytes))
        .map_err(|e| e.to_string())?;
    Ok(bytes)
}
fn collect(node: Node<'_>, diagnostics: &mut Vec<parsing::Diagnostic>, count: &mut usize) {
    *count += 1;
    if node.is_error() || node.is_missing() {
        diagnostics.push(parsing::Diagnostic {
            kind: if node.is_missing() {
                "missing"
            } else {
                "error"
            },
            start_byte: node.start_byte(),
            end_byte: node.end_byte(),
            start_line: node.start_position().row + 1,
            start_column_byte: node.start_position().column,
            end_line: node.end_position().row + 1,
            end_column_byte: node.end_position().column,
        });
    }
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        collect(child, diagnostics, count);
    }
}
struct CachedParser {
    parser: Parser,
    query: Query,
}
fn cached_response(
    cache: &mut HashMap<String, CachedParser>,
    request: &Request,
) -> Result<Response> {
    // Decoder validates source/configuration/producer identity before this point.
    let dialect = &request.identity.dialect;
    if !cache.contains_key(dialect) {
        let grammar = parsing::grammar(dialect).map_err(|e| e.to_string())?;
        let mut parser = Parser::new();
        parser
            .set_language(&grammar.language)
            .map_err(|e| e.to_string())?;
        let query = Query::new(&grammar.language, grammar.query).map_err(|e| e.to_string())?;
        cache.insert(dialect.clone(), CachedParser { parser, query });
    }
    let cached = cache.get_mut(dialect).unwrap();
    cached.parser.reset();
    // No old tree, ranges, edits, configuration or request state enters the next parse.
    let tree = cached
        .parser
        .parse(&request.source, None)
        .ok_or("parser:no_tree")?;
    let root = tree.root_node();
    let mut diagnostics = Vec::new();
    let mut node_count = 0;
    collect(root, &mut diagnostics, &mut node_count);
    let mut cursor = QueryCursor::new();
    let mut matches = cursor.matches(&cached.query, root, request.source.as_slice());
    let mut query_matches = 0;
    while matches.next().is_some() {
        query_matches += 1;
    }
    let parsed = parsing::Parsed {
        tree: root.to_sexp(),
        complete: !root.has_error(),
        diagnostics,
        source_bytes: request.source.len(),
        node_count,
        query_matches,
    };
    let response = Response {
        identity: request.identity.clone(),
        state: if parsed.complete {
            single::State::Complete
        } else {
            single::State::Partial
        },
        source_bytes: parsed.source_bytes as u64,
        node_count: parsed.node_count as u64,
        query_matches: parsed.query_matches as u64,
        spans: parsed
            .diagnostics
            .iter()
            .map(|d| single::Span {
                start: d.start_byte as u64,
                end: d.end_byte as u64,
            })
            .collect(),
        payload: parsed.json(dialect).into_bytes(),
    };
    drop(matches);
    drop(cursor);
    drop(tree);
    cached.parser.reset();
    validate_payload(&response, request)?;
    Ok(response)
}
/// Strict duplicated-field agreement; the bounded canonical payload is authoritative.
pub fn validate_payload(response: &Response, request: &Request) -> Result<()> {
    validate_payload_until(response, request, None)
}
fn check_deadline(deadline: Option<Instant>) -> Result<()> {
    if deadline.is_some_and(|until| Instant::now() >= until) {
        return Err("timeout".into());
    }
    Ok(())
}
fn validate_payload_until(
    response: &Response,
    request: &Request,
    deadline: Option<Instant>,
) -> Result<()> {
    check_deadline(deadline)?;
    single::validate_response(response, request)?;
    let value: Value =
        serde_json::from_slice(&response.payload).map_err(|_| "protocol:payload_json")?;
    check_deadline(deadline)?;
    let complete = match response.state {
        single::State::Complete => true,
        single::State::Partial => false,
        single::State::Error => return Err("protocol:unexpected_error_state".into()),
    };
    if value.get("dialect") != Some(&json!(request.identity.dialect))
        || value.get("complete") != Some(&json!(complete))
        || value.get("source_bytes") != Some(&json!(response.source_bytes))
        || value.get("node_count") != Some(&json!(response.node_count))
        || value.get("query_matches") != Some(&json!(response.query_matches))
        || !value.get("tree").is_some_and(Value::is_string)
    {
        return Err("protocol:payload_envelope".into());
    }
    let diagnostics = value
        .get("diagnostics")
        .and_then(Value::as_array)
        .ok_or("protocol:diagnostics")?;
    if diagnostics.len() != response.spans.len() {
        return Err("protocol:diagnostics_length".into());
    }
    let mut line_starts = vec![0];
    if !diagnostics.is_empty() {
        for (i, byte) in request.source.iter().enumerate() {
            if i % 16384 == 0 {
                check_deadline(deadline)?;
            }
            if *byte == b'\n' {
                line_starts.push(i + 1);
            }
        }
    }
    for (index, (d, s)) in diagnostics.iter().zip(&response.spans).enumerate() {
        if index % 256 == 0 {
            check_deadline(deadline)?;
        }
        if d.get("start_byte").and_then(Value::as_u64) != Some(s.start)
            || d.get("end_byte").and_then(Value::as_u64) != Some(s.end)
        {
            return Err("protocol:payload_span".into());
        }
        let start = usize::try_from(s.start).map_err(|_| "protocol:span")?;
        let end = usize::try_from(s.end).map_err(|_| "protocol:span")?;
        for (offset, line_key, column_key) in [
            (start, "start_line", "start_column_byte"),
            (end, "end_line", "end_column_byte"),
        ] {
            let line = line_starts.partition_point(|&start| start <= offset);
            let col = offset - line_starts[line - 1];
            if d.get(line_key).and_then(Value::as_u64) != Some(line as u64)
                || d.get(column_key).and_then(Value::as_u64) != Some(col as u64)
            {
                return Err("protocol:payload_position".into());
            }
        }
        if !matches!(
            d.get("kind").and_then(Value::as_str),
            Some("error" | "missing")
        ) {
            return Err("protocol:diagnostic_kind".into());
        }
    }
    if complete == !diagnostics.is_empty() {
        return Err("protocol:complete_diagnostics".into());
    }
    check_deadline(deadline)
}
/// Explicit development binary mode; fault injection is confined to this experiment.
pub fn worker(start_fault: &str) -> Result<()> {
    let mut input = std::io::stdin().lock();
    let mut output = std::io::stdout().lock();
    let (kind, zero, body) = read_frame(&mut input)?;
    if kind != HELLO || zero != [0; 32] || body != handshake()? {
        return Err("protocol:hello".into());
    }
    if start_fault == "handshake_death" {
        std::process::exit(73);
    }
    let incarnation = random_incarnation()?;
    write_frame(
        &mut output,
        READY,
        incarnation,
        if start_fault == "bad_handshake" {
            b"invalid"
        } else {
            &body
        },
    )?;
    if start_fault == "idle_death" {
        std::process::exit(74);
    }
    if matches!(
        start_fault,
        "premature_ready" | "premature_result" | "premature_valid_result"
    ) {
        // Adversarial peer reads only the header, leaving a large parent write blocked.
        let mut header = [0; 47];
        input.read_exact(&mut header).map_err(|e| e.to_string())?;
        if start_fault == "premature_ready" {
            write_frame(&mut output, READY, incarnation, &body)?;
        } else {
            let forged = if start_fault == "premature_valid_result" {
                // Known test source yields a valid response without draining any source bytes.
                single::direct(&Request::new(
                    1,
                    "rust",
                    vec![b' '; 8 * 1024 * 1024],
                    b"large",
                )?)?
            } else {
                single::direct(&Request::new(0, "rust", Vec::new(), b"forged")?)?
            };
            write_frame(
                &mut output,
                RESULT,
                incarnation,
                &single::encode_response(&forged)?,
            )?;
        }
        loop {
            thread::sleep(Duration::from_secs(1));
        }
    }
    let mut cache = HashMap::new();
    loop {
        let (kind, current, body) = read_frame(&mut input)?;
        if current != incarnation {
            return Err("protocol:incarnation".into());
        }
        if kind == SHUTDOWN && body.is_empty() {
            return Ok(());
        }
        if kind != PARSE || body.len() < 2 {
            return Err("protocol:state".into());
        }
        let fault_size = u16::from_le_bytes(body[..2].try_into().unwrap()) as usize;
        if fault_size > 64 || body.len() < 2 + fault_size {
            return Err("protocol:fault".into());
        }
        let fault = std::str::from_utf8(&body[2..2 + fault_size]).map_err(|_| "protocol:fault")?;
        let request = single::decode_request(&body[2 + fault_size..])?;
        match fault {
            "crash" => std::process::exit(75),
            "hang" => loop {
                thread::sleep(Duration::from_secs(1));
            },
            _ => {}
        }
        if fault == "stderr" {
            let chunk = [b'x'; 4096];
            for _ in 0..256 {
                std::io::stderr()
                    .write_all(&chunk)
                    .map_err(|e| e.to_string())?;
            }
        }
        let mut response = cached_response(&mut cache, &request)?;
        if fault == "old_attempt" {
            response.identity.attempt = response.identity.attempt.wrapping_add(1);
        }
        if fault == "wrong_payload" {
            response.payload = b"{}".to_vec();
        }
        let encoded = single::encode_response(&response)?;
        if fault == "oversized" {
            output
                .write_all(b"XRW2")
                .and_then(|()| output.write_all(&2u16.to_le_bytes()))
                .and_then(|()| output.write_all(&[RESULT]))
                .and_then(|()| output.write_all(&((MAX_FRAME + 1) as u64).to_le_bytes()))
                .and_then(|()| output.write_all(&incarnation))
                .and_then(|()| output.flush())
                .map_err(|e| e.to_string())?;
            continue;
        }
        if fault == "partial" {
            output
                .write_all(b"XRW2")
                .and_then(|()| output.flush())
                .map_err(|e| e.to_string())?;
            std::process::exit(76);
        }
        write_frame(
            &mut output,
            RESULT,
            if fault == "wrong_incarnation" {
                [1; 32]
            } else {
                incarnation
            },
            &encoded,
        )?;
        if fault == "duplicate" {
            write_frame(&mut output, RESULT, incarnation, &encoded)?;
        }
        if fault == "after_result_death" {
            std::process::exit(77);
        }
    }
}

type Frame = (u8, [u8; 32], Vec<u8>);
struct Session {
    child: Child,
    input: Option<ChildStdin>,
    frames: Option<mpsc::Receiver<Result<Frame>>>,
    reader: Option<JoinHandle<()>>,
    stderr: Option<JoinHandle<()>>,
    incarnation: [u8; 32],
    reaped: bool,
}
impl Session {
    fn start(
        executable: &PathBuf,
        start_fault: &str,
        deadline: Instant,
        cancel: &AtomicBool,
        stop: &AtomicBool,
    ) -> Result<Self> {
        let mut child = Command::new(executable)
            .args(["worker", start_fault])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("transport:{e}"))?;
        let input = child.stdin.take();
        let mut output = child.stdout.take().unwrap();
        let mut error = child.stderr.take().unwrap();
        let (sender, frames) = mpsc::sync_channel(1);
        let reader = thread::spawn(move || {
            loop {
                let result = read_frame(&mut output);
                let terminal = result.is_err();
                if sender.send(result).is_err() || terminal {
                    break;
                }
            }
        });
        let stderr = thread::spawn(move || {
            let mut buffer = [0; 4096];
            let mut retained = Vec::new();
            while let Ok(n) = error.read(&mut buffer) {
                if n == 0 {
                    break;
                }
                let keep = n.min(STDERR_LIMIT.saturating_sub(retained.len()));
                retained.extend_from_slice(&buffer[..keep]);
            }
        });
        let mut session = Self {
            child,
            input,
            frames: Some(frames),
            reader: Some(reader),
            stderr: Some(stderr),
            incarnation: [0; 32],
            reaped: false,
        };
        write_frame(
            session.input.as_mut().unwrap(),
            HELLO,
            [0; 32],
            &handshake()?,
        )?;
        let (kind, incarnation, body) = session.receive(deadline, cancel, stop)?;
        if kind != READY || incarnation == [0; 32] || body != handshake()? {
            return Err("protocol:ready".into());
        }
        session.incarnation = incarnation;
        Ok(session)
    }
    fn receive(
        &mut self,
        deadline: Instant,
        cancel: &AtomicBool,
        stop: &AtomicBool,
    ) -> Result<Frame> {
        loop {
            if cancel.load(Ordering::Acquire) || stop.load(Ordering::Acquire) {
                return Err("cancelled".into());
            }
            let remaining = deadline
                .checked_duration_since(Instant::now())
                .ok_or("timeout")?;
            match self
                .frames
                .as_ref()
                .unwrap()
                .recv_timeout(remaining.min(Duration::from_millis(10)))
            {
                Ok(result) => return result,
                Err(mpsc::RecvTimeoutError::Disconnected) => return Err("transport:closed".into()),
                Err(mpsc::RecvTimeoutError::Timeout) => {}
            }
        }
    }
    fn parse(
        &mut self,
        request: &Request,
        fault: &str,
        deadline: Instant,
        cancel: &AtomicBool,
        stop: &AtomicBool,
    ) -> Result<Response> {
        if self.child.try_wait().map_err(|e| e.to_string())?.is_some() {
            return Err("transport:idle_death".into());
        }
        match self.frames.as_ref().unwrap().try_recv() {
            Ok(Ok(_)) => return Err("protocol:unsolicited/duplicate".into()),
            Ok(Err(e)) => return Err(e),
            Err(mpsc::TryRecvError::Disconnected) => return Err("transport:idle_closed".into()),
            Err(mpsc::TryRecvError::Empty) => {}
        }
        let encoded = single::encode_request(request)?;
        let mut body = Vec::with_capacity(encoded.len() + fault.len() + 2);
        body.extend_from_slice(&(fault.len() as u16).to_le_bytes());
        body.extend_from_slice(fault.as_bytes());
        body.extend_from_slice(&encoded);
        // Completion of the pipe writer is supervised independently from Result.
        // A peer can emit a premature frame while refusing to drain request bytes.
        let mut input = self.input.take().unwrap();
        let incarnation = self.incarnation;
        let (sent_tx, sent_rx) = mpsc::channel();
        let writer = thread::spawn(move || {
            let result = write_frame(&mut input, PARSE, incarnation, &body);
            let _ = sent_tx.send((input, result));
        });
        let validated =
            self.receive(deadline, cancel, stop)
                .and_then(|(kind, incarnation, body)| {
                    if kind != RESULT || incarnation != self.incarnation {
                        return Err("protocol:result/identity".into());
                    }
                    let response =
                        single::decode_response(&body).map_err(|e| format!("protocol:{e}"))?;
                    validate_payload_until(&response, request, Some(deadline)).map_err(|e| {
                        if e == "timeout" {
                            e
                        } else {
                            format!("protocol:{e}")
                        }
                    })?;
                    Ok(response)
                });
        if let Err(error) = validated {
            let retirement = self.retire();
            let _ = writer.join();
            retirement?;
            return Err(error);
        }
        let response = validated?;
        let completion = loop {
            if cancel.load(Ordering::Acquire) || stop.load(Ordering::Acquire) {
                break Err("cancelled".into());
            }
            let Some(remaining) = deadline.checked_duration_since(Instant::now()) else {
                break Err("timeout".into());
            };
            match sent_rx.recv_timeout(remaining.min(Duration::from_millis(10))) {
                Ok(completion) => break Ok(completion),
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    break Err("transport:writer_closed".into());
                }
                Err(mpsc::RecvTimeoutError::Timeout) => {}
            }
        };
        match completion {
            Ok((input, result)) => {
                self.input = Some(input);
                writer.join().map_err(|_| "transport:writer_panic")?;
                result?;
            }
            Err(error) => {
                let retirement = self.retire();
                let _ = writer.join();
                retirement?;
                return Err(error);
            }
        }
        if cancel.load(Ordering::Acquire) || stop.load(Ordering::Acquire) {
            return Err("cancelled".into());
        }
        check_deadline(Some(deadline))?;
        Ok(response)
    }

    fn retire(&mut self) -> Result<()> {
        if !self.reaped {
            let _ = self.child.kill();
            self.child.wait().map_err(|e| format!("reap_failed:{e}"))?;
            self.reaped = true;
        }
        self.input.take();
        self.frames.take();
        if let Some(reader) = self.reader.take() {
            let _ = reader.join();
        }
        if let Some(stderr) = self.stderr.take() {
            let _ = stderr.join();
        }
        Ok(())
    }
}
impl Drop for Session {
    fn drop(&mut self) {
        if !self.reaped {
            if let Some(input) = self.input.as_mut() {
                let _ = write_frame(input, SHUTDOWN, self.incarnation, &[]);
            }
            let deadline = Instant::now() + Duration::from_millis(100);
            while Instant::now() < deadline {
                if matches!(self.child.try_wait(), Ok(Some(_))) {
                    self.reaped = true;
                    break;
                }
                thread::sleep(Duration::from_millis(2));
            }
        }
        let _ = self.retire();
    }
}

struct Reservation {
    bytes: usize,
    account: Arc<Mutex<usize>>,
}
impl Drop for Reservation {
    fn drop(&mut self) {
        let mut used = self.account.lock().unwrap();
        *used -= self.bytes;
    }
}
pub struct Outcome {
    pub response: Response,
    pub pid: u32,
    pub incarnation: [u8; 32],
    pub attempts: u32,
    pub retired: Vec<u32>,
}
struct Delivered {
    result: Result<Outcome>,
    _reservation: Reservation,
}
struct Job {
    request: Request,
    fault: String,
    start_fault: String,
    deadline: Instant,
    cancel: Arc<AtomicBool>,
    started: mpsc::Sender<(u32, [u8; 32])>,
    reply: mpsc::Sender<Delivered>,
    reservation: Reservation,
}
pub struct Ticket {
    reply: mpsc::Receiver<Delivered>,
    started: mpsc::Receiver<(u32, [u8; 32])>,
    cancel: Arc<AtomicBool>,
}
impl Ticket {
    pub fn wait_started(&self, timeout: Duration) -> Result<(u32, [u8; 32])> {
        self.started
            .recv_timeout(timeout)
            .map_err(|e| e.to_string())
    }
    pub fn cancel(&self) {
        self.cancel.store(true, Ordering::Release);
    }
    /// Transfer response ownership to the caller: cap stops covering that external allocation.
    pub fn wait(self) -> Result<Outcome> {
        let delivered = self.reply.recv().map_err(|e| e.to_string())?;
        if self.cancel.load(Ordering::Acquire) {
            return Err("cancelled".into());
        }
        delivered.result
    }
}
impl Drop for Ticket {
    fn drop(&mut self) {
        self.cancel();
    }
}
pub struct PersistentPool {
    sender: Option<mpsc::SyncSender<Job>>,
    threads: Vec<JoinHandle<()>>,
    account: Arc<Mutex<usize>>,
    stop: Arc<AtomicBool>,
}
impl PersistentPool {
    pub fn new(executable: PathBuf) -> Self {
        let (sender, receiver) = mpsc::sync_channel::<Job>(single::QUEUE);
        let receiver = Arc::new(Mutex::new(receiver));
        let account = Arc::new(Mutex::new(0));
        let stop = Arc::new(AtomicBool::new(false));
        let mut threads = Vec::new();
        for _ in 0..single::WORKERS {
            let receiver = receiver.clone();
            let executable = executable.clone();
            let stop = stop.clone();
            threads.push(thread::spawn(move || {
                let mut session: Option<Session> = None;
                let mut idle_error = None;
                loop {
                    let job = match receiver
                        .lock()
                        .unwrap()
                        .recv_timeout(Duration::from_millis(10))
                    {
                        Ok(job) => job,
                        Err(mpsc::RecvTimeoutError::Disconnected) => break,
                        Err(mpsc::RecvTimeoutError::Timeout) => {
                            if let Some(s) = session.as_mut() {
                                let health = match s.frames.as_ref().unwrap().try_recv() {
                                    Ok(Ok(_)) => Some("protocol:unsolicited/duplicate".to_string()),
                                    Ok(Err(e)) => Some(e),
                                    Err(mpsc::TryRecvError::Disconnected) => {
                                        Some("transport:idle_closed".into())
                                    }
                                    Err(mpsc::TryRecvError::Empty) => match s.child.try_wait() {
                                        Ok(Some(_)) => Some("transport:idle_death".into()),
                                        Err(e) => Some(format!("reap_failed:{e}")),
                                        Ok(None) => None,
                                    },
                                };
                                if let Some(error) = health {
                                    let retirement = s.retire();
                                    idle_error = if let Err(e) = retirement {
                                        Some(e)
                                    } else if error.starts_with("protocol:") {
                                        Some(error)
                                    } else {
                                        None
                                    };
                                    session = None;
                                }
                            }
                            continue;
                        }
                    };
                    let mut request = job.request;
                    let mut retired = Vec::new();
                    let mut attempts = 0;
                    let result = loop {
                        if let Some(error) = idle_error.take() {
                            break Err(error);
                        }
                        if job.cancel.load(Ordering::Acquire) || stop.load(Ordering::Acquire) {
                            break Err("cancelled".into());
                        }
                        if Instant::now() >= job.deadline {
                            break Err("timeout".into());
                        }
                        attempts += 1;
                        if session.is_none() {
                            match Session::start(
                                &executable,
                                &job.start_fault,
                                job.deadline,
                                &job.cancel,
                                &stop,
                            ) {
                                Ok(s) => session = Some(s),
                                Err(e) => {
                                    if attempts < 2 && e.starts_with("transport:") {
                                        match request.identity.attempt.checked_add(1) {
                                            Some(next) => request.identity.attempt = next,
                                            None => break Err("protocol:attempt_overflow".into()),
                                        }
                                        continue;
                                    }
                                    break Err(e);
                                }
                            }
                        }
                        let s = session.as_mut().unwrap();
                        let pid = s.child.id();
                        let incarnation = s.incarnation;
                        let _ = job.started.send((pid, incarnation));
                        let fault = if attempts > 1
                            && matches!(job.fault.as_str(), "crash_once" | "partial_once")
                        {
                            ""
                        } else {
                            match job.fault.as_str() {
                                "crash_once" => "crash",
                                "partial_once" => "partial",
                                other => other,
                            }
                        };
                        match s.parse(&request, fault, job.deadline, &job.cancel, &stop) {
                            Ok(response) => {
                                break Ok(Outcome {
                                    response,
                                    pid,
                                    incarnation,
                                    attempts,
                                    retired,
                                });
                            }
                            Err(e) => {
                                if let Err(error) = s.retire() {
                                    break Err(error);
                                }
                                retired.push(pid);
                                session = None;
                                if attempts < 2
                                    && e.starts_with("transport:")
                                    && Instant::now() < job.deadline
                                {
                                    match request.identity.attempt.checked_add(1) {
                                        Some(next) => request.identity.attempt = next,
                                        None => break Err("protocol:attempt_overflow".into()),
                                    }
                                    continue;
                                }
                                break Err(e);
                            }
                        }
                    };
                    if result.is_err()
                        && let Some(mut s) = session.take()
                    {
                        let _ = s.retire();
                    }
                    let _ = job.reply.send(Delivered {
                        result,
                        _reservation: job.reservation,
                    });
                }
            }));
        }
        Self {
            sender: Some(sender),
            threads,
            account,
            stop,
        }
    }
    pub fn submit(&self, request: Request, fault: &str) -> Result<Ticket> {
        self.submit_before(request, fault, "", Instant::now() + single::DEADLINE)
    }
    /// Development-only startup fault and deadline controls; ordinary caller uses submit.
    pub fn submit_before(
        &self,
        request: Request,
        fault: &str,
        start_fault: &str,
        deadline: Instant,
    ) -> Result<Ticket> {
        let deadline = deadline.min(Instant::now() + single::DEADLINE);
        if fault.len() > 64 {
            return Err("fault_limit".into());
        }
        single::encode_request(&request)?;
        if self.stop.load(Ordering::Acquire) {
            return Err("closed".into());
        }
        let bytes = request.source.len() + single::RESPONSE_LIMIT + 256 + STDERR_LIMIT;
        let mut used = self.account.lock().unwrap();
        if *used + bytes > single::AGGREGATE_LIMIT {
            return Err("aggregate_limit".into());
        }
        *used += bytes;
        drop(used);
        let reservation = Reservation {
            bytes,
            account: self.account.clone(),
        };
        let cancel = Arc::new(AtomicBool::new(false));
        let (reply, rx) = mpsc::channel();
        let (started, sx) = mpsc::channel();
        self.sender
            .as_ref()
            .ok_or("closed")?
            .try_send(Job {
                request,
                fault: fault.into(),
                start_fault: start_fault.into(),
                deadline,
                cancel: cancel.clone(),
                started,
                reply,
                reservation,
            })
            .map_err(|e| {
                match e {
                    mpsc::TrySendError::Full(_) => "queue_full",
                    mpsc::TrySendError::Disconnected(_) => "closed",
                }
                .to_string()
            })?;
        Ok(Ticket {
            reply: rx,
            started: sx,
            cancel,
        })
    }
    pub fn reserved(&self) -> usize {
        *self.account.lock().unwrap()
    }
}
impl Drop for PersistentPool {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Release);
        self.sender.take();
        for handle in self.threads.drain(..) {
            let _ = handle.join();
        }
    }
}
