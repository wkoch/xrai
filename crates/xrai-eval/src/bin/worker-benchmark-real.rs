//! Frozen real-source measurement experiment. No upstream source is executed.
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet, HashMap},
    io::Read,
    path::PathBuf,
    sync::{Arc, Barrier, atomic::AtomicBool},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tree_sitter::{Node, Parser, Query, QueryCursor, StreamingIterator};
use xrai_eval::{
    parsing_spike as parsing,
    worker_persistent::{self, PersistentPool},
    worker_spike::{self as single, Request, Response},
};
type Result<T> = std::result::Result<T, String>;
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    mode: String,
    phase: String,
    worker: PathBuf,
    concurrency: usize,
    control_directory: PathBuf,
    requests: Vec<Item>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Item {
    key: String,
    source_id: String,
    dialect: String,
    source: PathBuf,
    source_blake3: String,
    configuration: String,
    warmup: bool,
}
struct Captured {
    bytes: Vec<u8>,
    read_ns: u128,
    path: PathBuf,
    dialect: String,
    hash: String,
}
struct CachedParser {
    parser: Parser,
    query: Query,
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
fn cached_response(
    cache: &mut HashMap<String, CachedParser>,
    request: &Request,
) -> Result<(Response, u128)> {
    // Equivalent to frozen XRW2 cached_response: validate each request, cache only
    // parser/query by dialect, reset twice and never pass an old tree or edits.
    single::encode_request(request)?;
    let compilation = Instant::now();
    let mut compile_ns = 0;
    let dialect = &request.identity.dialect;
    if !cache.contains_key(dialect) {
        let grammar = parsing::grammar(dialect).map_err(|e| e.to_string())?;
        let mut parser = Parser::new();
        parser
            .set_language(&grammar.language)
            .map_err(|e| e.to_string())?;
        let query = Query::new(&grammar.language, grammar.query).map_err(|e| e.to_string())?;
        cache.insert(dialect.clone(), CachedParser { parser, query });
        compile_ns = compilation.elapsed().as_nanos();
    }
    let cached = cache.get_mut(dialect).expect("cache inserted");
    cached.parser.reset();
    let tree = cached
        .parser
        .parse(&request.source, None)
        .ok_or("parser:no_tree")?;
    let root = tree.root_node();
    let mut diagnostics = vec![];
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
    worker_persistent::validate_payload(&response, request)?;
    Ok((response, compile_ns))
}
fn epoch_ns() -> Result<u128> {
    Ok(SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_nanos())
}
fn gate(directory: &std::path::Path, name: &str) -> Result<u128> {
    let timestamp = epoch_ns()?;
    std::fs::write(
        directory.join(format!("{name}.ready")),
        timestamp.to_string(),
    )
    .map_err(|e| e.to_string())?;
    let deadline = Instant::now() + Duration::from_secs(30);
    while !directory.join(format!("{name}.start")).exists() {
        if Instant::now() > deadline {
            return Err("synchronized idle baseline acknowledgement timed out".into());
        }
        thread::sleep(Duration::from_millis(5));
    }
    Ok(timestamp)
}
fn encoded(mut response: Response) -> Result<Vec<u8>> {
    // Correlation is validated before this single operational normalization.
    response.identity.request = 0;
    single::encode_response(&response)
}
fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
struct Lane<'a> {
    input: &'a Input,
    captured: &'a BTreeMap<String, Captured>,
    pool: Option<&'a PersistentPool>,
    start: Instant,
    references: &'a PathBuf,
}
impl Lane<'_> {
    fn execute(
        &self,
        id: usize,
        item: &Item,
        lane: usize,
        cache: &mut HashMap<String, CachedParser>,
        seen: &mut BTreeSet<u32>,
    ) -> Result<Value> {
        let start = Instant::now();
        let captured = self.captured.get(&item.source_id).ok_or("source missing")?;
        let request = Request::new(
            id as u64,
            &item.dialect,
            captured.bytes.clone(),
            item.configuration.as_bytes(),
        )?;
        let request_ready = start.elapsed().as_nanos();
        let encode_start = Instant::now();
        let request_bytes = single::encode_request(&request)?.len();
        let encode_request_ns = encode_start.elapsed().as_nanos();
        let dispatch = Instant::now();
        let mut pid = std::process::id();
        let mut incarnation = None;
        let mut attempts = 1;
        let mut ipc_bytes = None;
        let mut stderr_bytes = None;
        let mut compile_ns = None;
        let response = match self.input.mode.as_str() {
            "direct" => single::direct(&request)?,
            "direct_cached" => {
                let (response, compilation) = cached_response(cache, &request)?;
                compile_ns = Some(compilation);
                response
            }
            "xrw1" => {
                let outcome = single::supervise(
                    &self.input.worker,
                    request.clone(),
                    "",
                    Instant::now() + single::DEADLINE,
                    &AtomicBool::new(false),
                );
                if !outcome.reaped {
                    return Err("unreaped XRW1 worker".into());
                }
                pid = *outcome.pids.last().ok_or("missing XRW1 PID")?;
                attempts = outcome.attempts;
                ipc_bytes = Some(outcome.ipc_bytes);
                stderr_bytes = Some(outcome.stderr.len());
                outcome.result?
            }
            "xrw2" => {
                let outcome = self
                    .pool
                    .ok_or("pool missing")?
                    .submit(request.clone(), "")?
                    .wait()?;
                pid = outcome.pid;
                incarnation = Some(hex(&outcome.incarnation));
                attempts = outcome.attempts;
                outcome.response
            }
            _ => return Err("mode".into()),
        };
        let dispatch_ns = dispatch.elapsed().as_nanos();
        single::validate_response(&response, &request)?;
        worker_persistent::validate_payload(&response, &request)?;
        let response_start = Instant::now();
        let canonical = encoded(response)?;
        let encode_response_ns = response_start.elapsed().as_nanos();
        let fingerprint = blake3::hash(&canonical).to_hex().to_string();
        if self.input.phase == "equivalence" {
            let path = self.references.join(format!("{id}.response"));
            std::fs::write(path, &canonical).map_err(|e| e.to_string())?;
        }
        let elapsed = start.elapsed().as_nanos();
        Ok(
            json!({"request":id,"lane":lane,"key":item.key,"source_id":item.source_id,"warmup":item.warmup,
            "pid":pid,"incarnation":incarnation,"first_seen_by_lane":seen.insert(pid),"attempts":attempts,
            "source_read_ns":captured.read_ns,"request_prepare_ns":request_ready,"encode_request_ns":encode_request_ns,
            "dispatch_ns":dispatch_ns,"compile_ns":compile_ns,"encode_response_ns":encode_response_ns,
            "end_to_end_ns":elapsed,"completed_from_session_start_ns":self.start.elapsed().as_nanos(),
            "request_bytes":request_bytes,"response_bytes":canonical.len(),"response_blake3":fingerprint,
            "ipc_bytes":ipc_bytes,"stderr_captured_bytes":stderr_bytes,
            "inner_queue_ns":null,"inner_codec_ns":null,"inner_roundtrip_ns":null,
            "unavailable_components_reason":"Existing controls expose only outer dispatch; XRW2 IPC/stderr and inner timing are not instrumented"}),
        )
    }
}
fn run(input: Input) -> Result<Value> {
    if !["direct", "direct_cached", "xrw1", "xrw2"].contains(&input.mode.as_str())
        || !["equivalence", "measurement"].contains(&input.phase.as_str())
        || ![1, 2].contains(&input.concurrency)
        || input.requests.is_empty()
        || input.requests.len() > 6000
    {
        return Err("frozen input mode/phase/bound required".into());
    }
    let start = Instant::now();
    std::fs::create_dir_all(&input.control_directory).map_err(|e| e.to_string())?;
    let references = input.control_directory.join("references");
    if input.phase == "equivalence" {
        std::fs::create_dir(&references).map_err(|e| e.to_string())?;
    }
    let mut captured: BTreeMap<String, Captured> = BTreeMap::new();
    for item in &input.requests {
        if let Some(previous) = captured.get(&item.source_id) {
            if previous.path != item.source
                || previous.dialect != item.dialect
                || previous.hash != item.source_blake3
            {
                return Err("conflicting repeated captured source descriptor".into());
            }
            continue;
        }
        let read = Instant::now();
        let bytes = std::fs::read(&item.source).map_err(|e| e.to_string())?;
        if bytes.len() > single::SOURCE_LIMIT
            || blake3::hash(&bytes).to_hex().to_string() != item.source_blake3
        {
            return Err("captured consumed source mismatch".into());
        }
        captured.insert(
            item.source_id.clone(),
            Captured {
                bytes,
                read_ns: read.elapsed().as_nanos(),
                path: item.source.clone(),
                dialect: item.dialect.clone(),
                hash: item.source_blake3.clone(),
            },
        );
    }
    let capture_ns = start.elapsed().as_nanos();
    let setup = Instant::now();
    let pool = (input.mode == "xrw2").then(|| PersistentPool::new(input.worker.clone()));
    let setup_ns = setup.elapsed().as_nanos();
    let idle_epoch_ns = gate(&input.control_directory, "idle")?;
    let ready = Arc::new(Barrier::new(input.concurrency + 1));
    let begin = Arc::new(Barrier::new(input.concurrency + 1));
    let lane = Lane {
        input: &input,
        captured: &captured,
        pool: pool.as_ref(),
        start,
        references: &references,
    };
    let samples: Vec<Value> =
        thread::scope(|scope| -> Result<Vec<Value>> {
            let mut handles = vec![];
            for worker in 0..input.concurrency {
                let lane = &lane;
                let ready = ready.clone();
                let begin = begin.clone();
                handles.push(scope.spawn(move || -> Result<Vec<Value>> {
                    let mut cache = HashMap::new();
                    let mut seen = BTreeSet::new();
                    let mut rows = vec![];
                    let mut failure = None;
                    for (id, item) in
                        lane.input.requests.iter().enumerate().filter(|(id, item)| {
                            item.warmup && id % lane.input.concurrency == worker
                        })
                    {
                        match lane.execute(id, item, worker, &mut cache, &mut seen) {
                            Ok(row) => rows.push(row),
                            Err(error) => {
                                failure = Some(error);
                                break;
                            }
                        }
                    }
                    ready.wait();
                    begin.wait();
                    if let Some(error) = failure {
                        return Err(error);
                    }
                    for (id, item) in
                        lane.input.requests.iter().enumerate().filter(|(id, item)| {
                            !item.warmup && id % lane.input.concurrency == worker
                        })
                    {
                        rows.push(lane.execute(id, item, worker, &mut cache, &mut seen)?);
                    }
                    Ok(rows)
                }));
            }
            ready.wait();
            let acknowledgement = gate(&input.control_directory, "warm_idle");
            begin.wait();
            acknowledgement?;
            let mut rows = vec![];
            for handle in handles {
                rows.extend(handle.join().map_err(|_| "lane panic")??);
            }
            Ok(rows)
        })?;
    let mut samples = samples;
    samples.sort_by_key(|row| row["request"].as_u64().unwrap_or(u64::MAX));
    let reserved_at_shutdown = pool.as_ref().map_or(0, PersistentPool::reserved);
    if reserved_at_shutdown != 0 {
        return Err("reserved tickets remain at shutdown".into());
    }
    let shutdown = Instant::now();
    drop(pool);
    let shutdown_ns = shutdown.elapsed().as_nanos();
    Ok(
        json!({"schema_version":"xrai.eval.resources.real-native-session.v1","mode":input.mode,"phase":input.phase,
        "concurrency":input.concurrency,"parent_pid":std::process::id(),"capture_ns":capture_ns,"setup_ns":setup_ns,
        "idle_epoch_ns":idle_epoch_ns,"shutdown_ns":shutdown_ns,"reserved_at_shutdown":reserved_at_shutdown,
        "samples":samples,"elapsed_ns":start.elapsed().as_nanos(),"cache_policy":"XRW2 dialect-only parser/query; reset before/after; no old tree/edit/source/response cache",
        "operational_response_normalization":["identity.request"],"upstream_executed":false}),
    )
}
fn producer_design() -> Result<Value> {
    let mut records = vec![];
    for dialect in parsing::DIALECTS {
        let grammar = parsing::grammar(dialect).map_err(|e| e.to_string())?;
        records.push(json!({"dialect":dialect,"crate":grammar.crate_name,"version":grammar.version,
            "node_types":grammar.node_types,"query":grammar.query,"abi":grammar.language.abi_version(),
            "producer":hex(&single::producer(dialect)?)}));
    }
    Ok(
        json!({"schema_version":"xrai.eval.resources.real-producers.v1","tree_sitter":"0.27.1",
        "provenance":include_str!("../../parsing-provenance.json"),"grammars":records}),
    )
}
fn main() {
    let result = (|| {
        let arguments: Vec<String> = std::env::args().skip(1).collect();
        if arguments == ["--producers"] {
            return producer_design();
        }
        if !arguments.is_empty() {
            return Err("unexpected argument".into());
        }
        let mut bytes = vec![];
        std::io::stdin()
            .take(8 * 1024 * 1024 + 1)
            .read_to_end(&mut bytes)
            .map_err(|e| e.to_string())?;
        if bytes.len() > 8 * 1024 * 1024 {
            return Err("input limit".to_string());
        }
        let input: Input = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
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
