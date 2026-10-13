//! Prospective byte-presence P3 extension. No raw diff parser or semantic claims.
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};
use std::io::{BufRead, Read, Write};
use std::sync::Arc;
const FRAME: usize = 4 * 1024 * 1024;
const SCHEMA: &str = "xrai.eval.p3-diff-native.v1";
fn hash(raw: &[u8]) -> String {
    blake3::hash(raw).to_hex().to_string()
}
fn identity(v: &impl Serialize) -> String {
    hash(&serde_json::to_vec(v).expect("owned serialization"))
}
fn producer() -> String {
    hash(
        &[
            include_bytes!("context-diff-spike.rs").as_slice(),
            include_bytes!("../../../../Cargo.lock").as_slice(),
            include_bytes!("../../../../rust-toolchain.toml").as_slice(),
        ]
        .concat(),
    )
}
fn hex(b: &[u8]) -> String {
    b.iter().map(|n| format!("{n:02x}")).collect()
}
fn unhex(s: &str) -> Result<Vec<u8>, String> {
    if !s.len().is_multiple_of(2)
        || s.len() > 16 * 1024 * 1024
        || !s
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err("hex".into());
    }
    s.as_bytes()
        .as_chunks::<2>()
        .0
        .iter()
        .map(|p| {
            u8::from_str_radix(std::str::from_utf8(p).map_err(|_| "hex")?, 16)
                .map_err(|_| "hex".into())
        })
        .collect()
}
fn path(p: &str) -> bool {
    !p.is_empty()
        && p.len() <= 4096
        && !p.starts_with('/')
        && !p.contains(['\\', ':'])
        && p.split('/').all(|x| !["", ".", ".."].contains(&x))
        && !p.chars().any(|c| c <= ' ' || c == '\x7f')
}
fn files(m: &BTreeMap<String, String>) -> Result<BTreeMap<String, Vec<u8>>, String> {
    if m.len() > 128 {
        return Err("file_limit".into());
    }
    let mut size = 0usize;
    let mut out = BTreeMap::new();
    for (p, s) in m {
        if !path(p) {
            return Err("path".into());
        }
        let b = unhex(s)?;
        size += b.len();
        if b.len() > 8 * 1024 * 1024 || size > 32 * 1024 * 1024 {
            return Err("source_limit".into());
        }
        std::str::from_utf8(&b).map_err(|_| "utf8")?;
        out.insert(p.clone(), b);
    }
    Ok(out)
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Hunk {
    base_span: [usize; 2],
    head_span: [usize; 2],
    removed_hex: String,
    replacement_hex: String,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Change {
    path: String,
    kind: String,
    base_present: bool,
    head_present: bool,
    hunks: Vec<Hunk>,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Intake {
    raw_diff_hex: String,
    decoder_profile: String,
    decoder_source_sha256: String,
    diff_sha256: String,
    #[serde(deserialize_with = "unique_map")]
    base: BTreeMap<String, String>,
    #[serde(deserialize_with = "unique_map")]
    head: BTreeMap<String, String>,
    changes: Vec<Change>,
}
fn unique_map<'de, D: serde::Deserializer<'de>>(
    d: D,
) -> Result<BTreeMap<String, String>, D::Error> {
    struct Unique;
    impl<'de> serde::de::Visitor<'de> for Unique {
        type Value = BTreeMap<String, String>;
        fn expecting(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            f.write_str("unique bounded captured file map")
        }
        fn visit_map<A: serde::de::MapAccess<'de>>(
            self,
            mut a: A,
        ) -> Result<Self::Value, A::Error> {
            let mut out = BTreeMap::new();
            while let Some((p, bytes)) = a.next_entry::<String, String>()? {
                if out.len() >= 128 || out.insert(p, bytes).is_some() {
                    return Err(serde::de::Error::custom(
                        "duplicate or excessive captured file",
                    ));
                }
            }
            Ok(out)
        }
    }
    d.deserialize_map(Unique)
}
#[derive(Deserialize)]
#[serde(tag = "operation", rename_all = "snake_case", deny_unknown_fields)]
enum Request {
    Open {
        intake: Intake,
        intake_sha256: String,
        budget_bytes: usize,
    },
    Expand {
        context_id: String,
        handles: Vec<String>,
        budget_bytes: usize,
    },
    Close,
}
#[derive(Clone)]
struct Evidence {
    metadata: Value,
    raw: Arc<Vec<u8>>,
}
struct Context {
    id: String,
    manifest: Value,
    evidence: Vec<Evidence>,
}
fn prepare(i: Intake, incarnation: u64, intake_sha256: String) -> Result<Context, String> {
    if i.diff_sha256.len() != 64
        || !i
            .diff_sha256
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err("diff_identity".into());
    }
    if intake_sha256.len() != 64
        || !intake_sha256
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Err("intake_sha_identity".into());
    }
    let raw_diff = unhex(&i.raw_diff_hex)?;
    if raw_diff.len() > 2 * 1024 * 1024
        || i.decoder_profile != "captured-unified-diff-v1"
        || i.decoder_source_sha256.len() != 64
    {
        return Err("decoder_provenance".into());
    }
    let base = files(&i.base)?;
    let head = files(&i.head)?;
    let mut rebuilt = base.clone();
    let mut seen = BTreeSet::new();
    let mut n = 0usize;
    if i.changes.len() > 128 {
        return Err("change_limit".into());
    }
    for c in &i.changes {
        if !path(&c.path) || !seen.insert(c.path.clone()) {
            return Err("duplicate_path".into());
        }
        if (c.base_present, c.head_present)
            != match c.kind.as_str() {
                "create" => (false, true),
                "delete" => (true, false),
                "modify" => (true, true),
                _ => return Err("kind".into()),
            }
            || base.contains_key(&c.path) != c.base_present
            || head.contains_key(&c.path) != c.head_present
        {
            return Err("presence".into());
        }
        if c.hunks.is_empty() {
            return Err("hunks".into());
        }
        let source = base.get(&c.path).map(Vec::as_slice).unwrap_or(&[]);
        let destination = head.get(&c.path).map(Vec::as_slice).unwrap_or(&[]);
        let mut out = Vec::new();
        let mut pos = 0usize;
        for h in &c.hunks {
            n += 1;
            let [s, e] = h.base_span;
            let [a, b] = h.head_span;
            if n > 4096 || s < pos || s > e || e > source.len() || a > b || b > destination.len() {
                return Err("span".into());
            }
            let removed = unhex(&h.removed_hex)?;
            let replacement = unhex(&h.replacement_hex)?;
            if source[s..e] != removed || destination[a..b] != replacement {
                return Err("hunk_bytes".into());
            }
            for (bytes, start, end) in [(source, s, e), (destination, a, b)] {
                let text = std::str::from_utf8(bytes).map_err(|_| "utf8")?;
                if !text.is_char_boundary(start) || !text.is_char_boundary(end) {
                    return Err("utf8_span".into());
                }
            }
            out.extend_from_slice(&source[pos..s]);
            if out.len() != a {
                return Err("head_location".into());
            }
            out.extend_from_slice(&replacement);
            if out.len() != b {
                return Err("head_location".into());
            }
            pos = e;
        }
        out.extend_from_slice(&source[pos..]);
        if out != destination {
            return Err("file_reconstruction".into());
        }
        if c.head_present {
            rebuilt.insert(c.path.clone(), out);
        } else {
            rebuilt.remove(&c.path);
        }
    }
    if rebuilt != head {
        return Err("integral_head".into());
    }
    let base_id = identity(&i.base);
    let head_id = identity(&i.head);
    let intake_id = identity(&i);
    let id = identity(&json!({"intake":intake_id,"incarnation":incarnation,"producer":producer()}));
    let mut evidence = Vec::new();
    let mut obligations = Vec::new();
    for c in &i.changes {
        for (side, present, m, snapshot) in [
            ("base", c.base_present, &base, &base_id),
            ("head", c.head_present, &head, &head_id),
        ] {
            obligations.push(json!({"path":c.path,"side":side,"kind":"file_presence","present":present,"snapshot_id":snapshot,"proof":"integral_typed_reconstruction"}));
            if !present {
                continue;
            }
            let raw = Arc::new(m.get(&c.path).ok_or("presence")?.clone());
            for (ordinal, h) in c.hunks.iter().enumerate() {
                let span = if side == "base" {
                    h.base_span
                } else {
                    h.head_span
                };
                let metadata = json!({"path":c.path,"side":side,"kind":"changed_source_bytes","present":true,"snapshot_id":snapshot,"source_hash":hash(raw.as_slice()),"source_bytes":raw.len(),"span":span,"hunk_ordinal":ordinal,"semantic_state":"unknown"});
                let handle = identity(&json!({"context_id":id,"evidence":metadata}));
                let mut metadata = metadata;
                metadata["handle"] = json!(handle);
                obligations.push(json!({"path":c.path,"side":side,"kind":"changed_source_bytes","span":span,"evidence_handle":handle,"snapshot_id":snapshot}));
                evidence.push(Evidence {
                    metadata,
                    raw: raw.clone(),
                });
            }
        }
    }
    let manifest = json!({"context_id":id,"intake_id":intake_id,"intake_identity_algorithms":{"intake_id":"BLAKE3","intake_sha256":"SHA-256"},"intake_sha256":intake_sha256,"intake_sha256_checked_natively":false,"diff_sha256":i.diff_sha256,"raw_diff_hex":i.raw_diff_hex,"raw_diff_blake3":hash(&raw_diff),"decoder_profile":i.decoder_profile,"decoder_source_sha256":i.decoder_source_sha256,"base_snapshot_id":base_id,"head_snapshot_id":head_id,"integral_head_verified":true,"obligations":obligations,"evidence":evidence.iter().map(|e| &e.metadata).collect::<Vec<_>>(),"semantic_support":"unknown","raw_diff_decoded_natively":false});
    Ok(Context {
        id,
        manifest,
        evidence,
    })
}
fn envelope(operation: &str, result: Value, status: &str) -> Value {
    json!({"status":status,"schema":SCHEMA,"pid":std::process::id(),"producer":producer(),"operation":operation,"result":result,"wire_bytes":0,"model_tokens":null,"controlled_tokens":null,"meter":"canonical_response_utf8_bytes_excluding_newline"})
}
fn stabilize(mut v: Value) -> Result<Value, String> {
    for _ in 0..16 {
        let n = serde_json::to_vec(&v).map_err(|_| "wire")?.len();
        if v["wire_bytes"] == json!(n) {
            return Ok(v);
        }
        v["wire_bytes"] = json!(n);
    }
    Err("wire_counter".into())
}
fn failure(op: &str, code: &str) -> Value {
    stabilize(envelope(op, json!({"code":code}), "error")).expect("bounded error")
}
fn deliver(
    c: &Context,
    handles: &[String],
    expanded: bool,
    budget: usize,
) -> Result<Value, String> {
    if budget > 1024 * 1024 {
        return Err("budget_limit".into());
    }
    let op = if expanded { "expand" } else { "open" };
    let mut items = Vec::new();
    let mut omitted = Vec::new();
    let selected: Vec<_> = c
        .evidence
        .iter()
        .filter(|e| {
            handles.contains(
                &e.metadata["handle"]
                    .as_str()
                    .unwrap_or_default()
                    .to_string(),
            )
        })
        .collect();
    let materialized_bytes: usize = selected
        .iter()
        .map(|e| {
            if expanded {
                e.raw.len()
            } else {
                let span: [usize; 2] =
                    serde_json::from_value(e.metadata["span"].clone()).unwrap_or([0, 0]);
                span[1] - span[0]
            }
        })
        .sum();
    if selected.len() > 128 || materialized_bytes > FRAME / 2 {
        return Err("selection_work_limit".into());
    }
    for e in &selected {
        let span = if expanded {
            [0, e.raw.len()]
        } else {
            serde_json::from_value(e.metadata["span"].clone()).map_err(|_| "span")?
        };
        let mut item = e.metadata.clone();
        item["delivered_span"] = json!(span);
        item["content_hex"] = json!(hex(&e.raw[span[0]..span[1]]));
        items.push(item);
    }
    loop {
        let wire = stabilize(envelope(
            op,
            json!({"context_id":c.id,"manifest":c.manifest,"requested_handles":handles,"expanded":expanded,"items":items,"omitted":omitted,"budget_bytes":budget,"complete":omitted.is_empty()}),
            "ok",
        ))?;
        if wire["wire_bytes"].as_u64().ok_or("wire")? as usize <= budget {
            return Ok(wire);
        }
        if let Some(last) = items.pop() {
            omitted.insert(0,json!({"handle":last["handle"],"reason":"whole_wire_byte_budget","identified":true}));
        } else {
            return Err("metadata_budget_floor".into());
        }
    }
}
fn main() {
    let stdin = std::io::stdin();
    let mut reader = stdin.lock();
    let mut stdout = std::io::stdout().lock();
    let mut current: Option<Context> = None;
    let mut incarnation = 0u64;
    for ordinal in 0..512 {
        let mut raw = Vec::new();
        let result = reader
            .by_ref()
            .take((FRAME + 1) as u64)
            .read_until(b'\n', &mut raw);
        if result.is_err() || raw.is_empty() {
            break;
        }
        let mut close = false;
        let wire = if raw.len() > FRAME || !raw.ends_with(b"\n") {
            failure("invalid", "frame")
        } else {
            match serde_json::from_slice::<Request>(&raw) {
                Err(_) => failure("invalid", "request"),
                Ok(Request::Close) => {
                    close = true;
                    stabilize(envelope("close", json!({"closed":true}), "ok")).expect("close")
                }
                Ok(Request::Open {
                    intake,
                    intake_sha256,
                    budget_bytes,
                }) => match prepare(intake, incarnation + 1, intake_sha256) {
                    Err(e) => failure("open", &e),
                    Ok(next) => {
                        let handles = next
                            .evidence
                            .iter()
                            .map(|e| {
                                e.metadata["handle"]
                                    .as_str()
                                    .unwrap_or_default()
                                    .to_string()
                            })
                            .collect::<Vec<_>>();
                        match deliver(&next, &handles, false, budget_bytes) {
                            Err(e) => failure("open", &e),
                            Ok(wire) => {
                                incarnation += 1;
                                current = Some(next);
                                wire
                            }
                        }
                    }
                },
                Ok(Request::Expand {
                    context_id,
                    handles,
                    budget_bytes,
                }) => match &current {
                    None => failure("expand", "no_context"),
                    Some(c) => {
                        let unique: BTreeSet<_> = handles.iter().collect();
                        if c.id != context_id {
                            failure("expand", "stale_context")
                        } else if handles.len() > 8192
                            || unique.len() != handles.len()
                            || handles.iter().any(|h| {
                                !c.evidence.iter().any(|e| e.metadata["handle"] == json!(h))
                            })
                        {
                            failure("expand", "foreign_or_duplicate_handle")
                        } else {
                            deliver(c, &handles, true, budget_bytes)
                                .unwrap_or_else(|e| failure("expand", &e))
                        }
                    }
                },
            }
        };
        if serde_json::to_writer(&mut stdout, &wire).is_err()
            || stdout.write_all(b"\n").is_err()
            || stdout.flush().is_err()
        {
            break;
        }
        if close || ordinal == 511 || raw.len() > FRAME {
            break;
        }
    }
}
