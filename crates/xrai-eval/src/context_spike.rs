//! ADR027 development-only context selection. Captures and manifests are immutable;
//! evaluator labels never enter this typed boundary. No analyzed program executes.
use crate::semantics_spike::{self, Input, Snapshot};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};
use std::io::Read;
use std::time::Instant;
use tree_sitter::{Node, Parser};

pub mod validated_diff;
use validated_diff::{Presence, ValidatedDiff};

pub const RULES: &str = "p3-rust-obligations-v1";
pub const MAX_CONTEXTS: usize = 2;
pub const MAX_RETAINED_BYTES: usize = 8 * 1024 * 1024;
pub const TTL_MS: u64 = 60_000;
pub const MAX_EXPANSIONS: usize = 4;
pub const RETENTION_POLICY: &str = "p3-memory-contexts2-serialized8MiB-ttl60000-attempts4-v1";
const COUNTER_ITERATIONS: usize = 16;
pub fn hash(bytes: &[u8]) -> String {
    blake3::hash(bytes).to_hex().to_string()
}
fn id(prefix: &str, value: &impl Serialize) -> String {
    format!(
        "{prefix}_{}",
        hash(&serde_json::to_vec(value).expect("typed serialization"))
    )
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Limits {
    pub max_bytes: usize,
    pub max_tokens: usize,
    pub max_candidates: usize,
    pub max_files: usize,
    pub max_source_bytes: usize,
    pub deadline_ms: u64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Anchor {
    pub side: String,
    pub path: String,
    pub start: usize,
    pub end: usize,
    pub lookup: Option<Lookup>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Lookup {
    pub module: String,
    pub path: String,
    pub namespace: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Hunk {
    pub path: String,
    pub base_start: usize,
    pub base_end: usize,
    pub head_start: usize,
    pub head_end: usize,
    pub removed: String,
    pub added: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub intent: String,
    pub description: String,
    pub anchors: Vec<Anchor>,
    pub hunks: Vec<Hunk>,
    pub p2: bool,
    pub limits: Limits,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Case {
    #[serde(deserialize_with = "strict_optional_input")]
    pub base: Option<Input>,
    #[serde(deserialize_with = "strict_input")]
    pub head: Input,
    pub request: Request,
}
fn checked_input<E: serde::de::Error>(value: Value) -> Result<Input, E> {
    let keys = ["files", "root", "edition", "configuration", "rules"];
    if !value
        .as_object()
        .is_some_and(|m| m.keys().all(|k| keys.contains(&k.as_str())))
    {
        return Err(E::custom("unknown capture field"));
    }
    serde_json::from_value(value).map_err(E::custom)
}
fn strict_input<'de, D: serde::Deserializer<'de>>(d: D) -> Result<Input, D::Error> {
    checked_input(Value::deserialize(d)?)
}
fn strict_optional_input<'de, D: serde::Deserializer<'de>>(
    d: D,
) -> Result<Option<Input>, D::Error> {
    let value = Value::deserialize(d)?;
    if value.is_null() {
        Ok(None)
    } else {
        checked_input(value).map(Some)
    }
}

/// Implementations return the fixed L4 profile name/fingerprint. Exact counts
/// are requested for the entire compact envelope, including these counters.
pub trait Meter {
    fn profile(&self) -> &str;
    fn tokens(&mut self, bytes: &[u8]) -> Result<usize, String>;
}
#[derive(Clone, Debug, Serialize)]
pub struct Candidate {
    pub id: String,
    pub snapshot_id: String,
    pub file_id: String,
    pub path: String,
    pub source_hash: String,
    pub minimum: [usize; 2],
    pub container: [usize; 2],
    pub full: [usize; 2],
    pub reason: String,
    pub state: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub presence: Option<String>,
}
#[derive(Clone, Debug, Serialize)]
pub struct Obligation {
    pub id: String,
    pub snapshot_id: String,
    pub required: bool,
    pub state: String,
    pub reason: String,
    pub item_ids: Vec<String>,
    pub minimum_view: String,
    pub minimum_span: Option<Value>,
}
#[derive(Clone, Debug, Serialize)]
pub struct Manifest {
    pub context_id: String,
    pub selection_fingerprint: String,
    pub retention_epoch: String,
    pub incarnation: u64,
    pub retention_policy: String,
    pub snapshots: Vec<Value>,
    pub request: Value,
    pub normalized_request: Request,
    pub rules_version: String,
    pub selector_fingerprint: String,
    pub candidates: Vec<Candidate>,
    pub resolutions: Vec<Value>,
    pub obligations: Vec<Obligation>,
    pub selected: BTreeMap<String, [usize; 2]>,
    pub gaps: Vec<String>,
    pub created_ms: u64,
    pub expires_ms: u64,
    pub retained_bytes: usize,
}
/// A captured revision is independent of optional Rust IR. Historical outputs
/// retain their exact Snapshot projection; prospective profiles expose IR absence.
#[derive(Clone)]
pub struct RetainedRevision {
    pub snapshot_id: String,
    pub configuration_id: String,
    pub configuration_fingerprint: String,
    pub producer_fingerprint: String,
    pub input: Input,
    pub ir: Option<Snapshot>,
    capture: Option<validated_diff::RevisionInput>,
}
impl Serialize for RetainedRevision {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        if self.capture.is_none() {
            return self.ir.as_ref().expect("legacy IR").serialize(serializer);
        }
        json!({"snapshot_id":self.snapshot_id,"configuration_id":self.configuration_id,
            "configuration_fingerprint":self.configuration_fingerprint,"producer_fingerprint":self.producer_fingerprint,
            "capture":self.capture,"input":self.input,"ir":self.ir}).serialize(serializer)
    }
}
impl RetainedRevision {
    fn legacy(ir: Snapshot) -> Self {
        Self {
            snapshot_id: ir.snapshot_id.clone(),
            configuration_id: ir.configuration_id.clone(),
            configuration_fingerprint: ir.configuration_fingerprint.clone(),
            producer_fingerprint: ir.producer_fingerprint.clone(),
            input: ir.input.clone(),
            ir: Some(ir),
            capture: None,
        }
    }
    fn validated(revision: &validated_diff::Revision) -> Result<Self, String> {
        let ir = if revision.dto.frontend == "rust" {
            Some(semantics_spike::build(revision.input.clone())?)
        } else {
            None
        };
        let producer_fingerprint = hash(
            &[
                include_bytes!("context_spike.rs").as_slice(),
                include_bytes!("context_spike/validated_diff.rs").as_slice(),
            ]
            .concat(),
        );
        let configuration_fingerprint = hash(
            &serde_json::to_vec(&(
                &revision.dto.frontend,
                &revision.input.edition,
                &revision.input.configuration,
                &revision.input.rules,
            ))
            .map_err(|e| e.to_string())?,
        );
        Ok(Self {
            snapshot_id: id(
                "snap",
                &(&revision.dto.capture_blake3, &producer_fingerprint),
            ),
            configuration_id: format!("cfg_{configuration_fingerprint}"),
            configuration_fingerprint,
            producer_fingerprint,
            input: revision.input.clone(),
            ir,
            capture: Some(revision.dto.clone()),
        })
    }
}
#[derive(Clone)]
struct Saved {
    manifest: Manifest,
    snapshots: Vec<RetainedRevision>,
    request: Request,
    expansions: usize,
}
pub struct Store {
    contexts: BTreeMap<String, Saved>,
    pub published: Option<String>,
    epoch: String,
    next_incarnation: u64,
}
#[derive(Serialize)]
pub struct Delivery {
    pub request: Value,
    pub response: Value,
    pub manifest: Manifest,
    pub snapshots: Vec<RetainedRevision>,
    pub wire_hex: String,
    pub wire_blake3: String,
    pub meter_calls: usize,
    pub meter_elapsed_micros: u128,
}
fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
fn descriptor(s: &RetainedRevision, generation: usize) -> Value {
    json!({"snapshot_id":s.snapshot_id,"workspace_id":"ws_context","worktree_id":"wt_context",
    "generation":generation,"input_kind":"captured_blobs","configuration_id":s.configuration_id,
    "configuration_fingerprint":{"algorithm":"blake3","hex":s.configuration_fingerprint},
    "producer_fingerprint":{"algorithm":"blake3","hex":s.producer_fingerprint},
    "captured_at":"2026-10-12T00:00:00Z"})
}
fn wire_request(
    req: &Request,
    snapshots: &[Value],
    operation: &str,
    context: Option<(&str, &[String])>,
    profile: &str,
) -> Value {
    let head = snapshots.last().expect("head");
    let mut params = json!({"intent":req.intent,"description":req.description,"anchors":[]});
    if snapshots.len() == 2 {
        params["base"] = snapshots[0]["snapshot_id"].clone();
        params["head"] = head["snapshot_id"].clone();
    }
    if let Some((cid, ids)) = context {
        params = json!({"context_id":cid,"item_ids":ids});
    }
    json!({"schema_version":3,"request_id":id("request", &(req,operation,context)),
    "workspace_id":"ws_context","worktree_id":"wt_context","operation":operation,
    "consistency":{"mode":"snapshot","scope":{"kind":"workspace"},"revision":{"kind":"fixed","snapshot_id":head["snapshot_id"]}},
    "limits":{"max_bytes":req.limits.max_bytes,"max_tokens":req.limits.max_tokens,"tokenizer":profile,
    "deadline_ms":req.limits.deadline_ms,"max_candidates":req.limits.max_candidates,"max_files":req.limits.max_files,
    "max_source_bytes":req.limits.max_source_bytes,"max_expansions":MAX_EXPANSIONS},"params":params})
}
fn valid_span(source: &str, start: usize, end: usize) -> bool {
    start <= end
        && end <= source.len()
        && source.is_char_boundary(start)
        && source.is_char_boundary(end)
}
fn container(node: Node<'_>, start: usize, end: usize) -> Option<[usize; 2]> {
    if node.start_byte() > start || node.end_byte() < end {
        return None;
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        if let Some(span) = container(child, start, end) {
            return Some(span);
        }
    }
    [
        "function_item",
        "struct_item",
        "impl_item",
        "enum_item",
        "mod_item",
    ]
    .contains(&node.kind())
    .then_some([node.start_byte(), node.end_byte()])
}
fn window(source: &str, start: usize, end: usize) -> [usize; 2] {
    let a = source[..start].rfind('\n').map_or(0, |i| i + 1);
    let b = source[end..]
        .find('\n')
        .map_or(source.len(), |i| end + i + 1);
    [a, b]
}
fn add_candidate(
    s: &RetainedRevision,
    path: &str,
    start: usize,
    end: usize,
    reason: &str,
    state: &str,
) -> Result<Candidate, String> {
    let source = s.input.files.get(path).ok_or("source_unavailable")?;
    if !valid_span(source, start, end) {
        return Err("invalid_request:source_span".into());
    }
    let container_span = if s.ir.is_some() {
        let mut parser = Parser::new();
        parser
            .set_language(&tree_sitter_rust::LANGUAGE.into())
            .map_err(|e| e.to_string())?;
        let tree = parser.parse(source, None).ok_or("parse_unavailable")?;
        container(tree.root_node(), start, end).unwrap_or([start, end])
    } else {
        window(source, start, end)
    };
    Ok(Candidate {
        id: id("item", &(&s.snapshot_id, path, start, end)),
        snapshot_id: s.snapshot_id.clone(),
        file_id: format!("fi_{}", hash(path.as_bytes())),
        path: path.into(),
        source_hash: hash(source.as_bytes()),
        minimum: window(source, start, end),
        container: container_span,
        full: [0, source.len()],
        reason: reason.into(),
        state: state.into(),
        presence: None,
    })
}
fn obligation(c: &Candidate) -> Obligation {
    Obligation {
        id: id("item_obligation", &c.id),
        snapshot_id: c.snapshot_id.clone(),
        required: true,
        state: "omitted_budget".into(),
        reason: c.reason.clone(),
        item_ids: vec![c.id.clone()],
        minimum_view: if c.presence.is_some() {
            "presence"
        } else {
            "excerpt"
        }
        .into(),
        minimum_span: if c.presence.is_some() {
            None
        } else {
            Some(json!({"start":c.minimum[0],"end":c.minimum[1]}))
        },
    }
}
fn prepare(case: Case, now_ms: u64, profile: &str) -> Result<Saved, String> {
    prepare_with(case, now_ms, profile, None)
}
fn prepare_with(
    case: Case,
    now_ms: u64,
    profile: &str,
    validated: Option<&ValidatedDiff>,
) -> Result<Saved, String> {
    let req = case.request;
    if !["locate", "understand", "fix", "review", "impact"].contains(&req.intent.as_str())
        || req.limits.max_candidates == 0
        || req.limits.max_files == 0
        || req.limits.max_source_bytes == 0
        || req.limits.deadline_ms == 0
        || req.description.len() > 8192
        || req.anchors.len() + req.hunks.len() > 128
    {
        return Err("invalid_request".into());
    }
    if req.limits.max_bytes < 1024 || req.limits.max_tokens < 256 {
        return Err("budget_below_envelope".into());
    }
    let started = Instant::now();
    let mut inputs = case.base.into_iter().collect::<Vec<_>>();
    inputs.push(case.head);
    let retained_bytes = inputs
        .iter()
        .flat_map(|i| i.files.values())
        .map(String::len)
        .sum::<usize>();
    if retained_bytes > MAX_RETAINED_BYTES {
        return Err("retention_capacity".into());
    }
    if inputs.iter().map(|i| i.files.len()).sum::<usize>() > req.limits.max_files
        || retained_bytes > req.limits.max_source_bytes
    {
        return Err("work_limit:input_capture".into());
    }
    let mut snapshots = vec![];
    for (index, input) in inputs.into_iter().enumerate() {
        if input.files.keys().any(|p| {
            p.is_empty()
                || p.starts_with('/')
                || p.contains('\0')
                || p.split('/').any(|part| part == "..")
        }) {
            return Err("invalid_request:native_path".into());
        }
        if input.files.len() > req.limits.max_files
            || input.files.values().map(String::len).sum::<usize>() > req.limits.max_source_bytes
        {
            return Err("work_limit:input_capture".into());
        }
        snapshots.push(if let Some(diff) = validated {
            RetainedRevision::validated(if index == 0 { &diff.base } else { &diff.head })?
        } else {
            RetainedRevision::legacy(semantics_spike::build(input)?)
        });
        if started.elapsed().as_millis() >= u128::from(req.limits.deadline_ms) {
            return Err("work_limit:deadline".into());
        }
    }
    if snapshots.len() == 2 && snapshots[0].snapshot_id == snapshots[1].snapshot_id {
        return Err("invalid_request:identical_revisions".into());
    }
    let head = snapshots.last().expect("head");
    let mut candidates = BTreeMap::new();
    let mut gaps = BTreeSet::new();
    let mut anchors = req.anchors.clone();
    let mut unavailable = vec![];
    let mut resolutions = vec![];
    for h in req.hunks.iter().filter(|_| validated.is_none()) {
        if snapshots.len() != 2 {
            return Err("invalid_request:diff_without_base".into());
        }
        for (s, start, end, content, side) in [
            (&snapshots[0], h.base_start, h.base_end, &h.removed, "base"),
            (head, h.head_start, h.head_end, &h.added, "head"),
        ] {
            let source = s
                .input
                .files
                .get(&h.path)
                .ok_or("invalid_request:diff_path")?;
            if !valid_span(source, start, end) || &source[start..end] != content {
                return Err("invalid_request:diff_content".into());
            }
            if start != end {
                anchors.push(Anchor {
                    side: side.into(),
                    path: h.path.clone(),
                    start,
                    end,
                    lookup: None,
                });
            }
        }
    }
    for path in req
        .hunks
        .iter()
        .filter(|_| validated.is_none())
        .map(|h| &h.path)
        .collect::<BTreeSet<_>>()
    {
        let base = &snapshots[0].input.files[path];
        let changed = &head.input.files[path];
        let mut hunks = req
            .hunks
            .iter()
            .filter(|h| &h.path == path)
            .collect::<Vec<_>>();
        hunks.sort_by_key(|h| h.base_start);
        let mut cursor = 0;
        let mut rebuilt = String::new();
        for h in hunks {
            if h.base_start < cursor {
                return Err("invalid_request:diff_overlap".into());
            }
            rebuilt.push_str(&base[cursor..h.base_start]);
            if rebuilt.len() != h.head_start {
                return Err("invalid_request:diff_range".into());
            }
            rebuilt.push_str(&h.added);
            if rebuilt.len() != h.head_end {
                return Err("invalid_request:diff_range".into());
            }
            cursor = h.base_end;
        }
        rebuilt.push_str(&base[cursor..]);
        if &rebuilt != changed {
            return Err("invalid_request:diff_inconsistent".into());
        }
    }
    for a in &anchors {
        if candidates.len() >= req.limits.max_candidates {
            gaps.insert("max_candidates".into());
            break;
        }
        let s = match a.side.as_str() {
            "head" => head,
            "base" if snapshots.len() == 2 => &snapshots[0],
            _ => return Err("anchor_revision_mismatch".into()),
        };
        if !s.input.files.contains_key(&a.path) {
            gaps.insert("source_unavailable".to_string());
            unavailable.push(Obligation {
                id: id(
                    "item_obligation",
                    &(&s.snapshot_id, &a.path, a.start, a.end),
                ),
                snapshot_id: s.snapshot_id.clone(),
                required: true,
                state: "unavailable".into(),
                reason: "source_unavailable".into(),
                item_ids: vec![],
                minimum_view: "excerpt".into(),
                minimum_span: None,
            });
            continue;
        }
        let mut c = add_candidate(s, &a.path, a.start, a.end, "anchor_or_hunk", "syntactic")?;
        if req.intent == "understand" {
            c.minimum = c.container;
        }
        candidates.insert(c.id.clone(), c);
        if let Some(lookup) = &a.lookup {
            if req.p2 {
                let ir = s.ir.as_ref().ok_or("p2_unavailable:bytes_capture")?;
                let r = if s.input.rules == crate::semantics_spike::RULES_R3 {
                    ir.resolve_at(
                        &lookup.module,
                        &lookup.path,
                        &lookup.namespace,
                        &a.path,
                        a.start,
                    )
                } else {
                    ir.resolve(&lookup.module, &lookup.path, &lookup.namespace)
                };
                resolutions.push(json!({"snapshot_id":s.snapshot_id,"lookup":lookup,
                    "occurrence":{"path":a.path,"start":a.start,"end":a.end},"result":r}));
                if r.state == "resolved" {
                    if let Some(d) = ir
                        .declarations
                        .iter()
                        .find(|d| Some(&d.id) == r.target_id.as_ref())
                    {
                        let e = &d.evidence;
                        let mut c = add_candidate(
                            s,
                            &e.path,
                            e.start,
                            e.end,
                            "resolved_definition",
                            "resolved",
                        )?;
                        if req.intent != "locate" {
                            c.minimum = c.container;
                        }
                        candidates.insert(c.id.clone(), c);
                        for reference in &ir.references {
                            if candidates.len() >= req.limits.max_candidates {
                                gaps.insert("max_candidates".into());
                                break;
                            }
                            if reference.resolution.state == "resolved"
                                && reference.resolution.target_id == r.target_id
                            {
                                let e = &reference.evidence;
                                let c = add_candidate(
                                    s,
                                    &e.path,
                                    e.start,
                                    e.end,
                                    "demonstrated_consumer",
                                    "resolved",
                                )?;
                                candidates.insert(c.id.clone(), c);
                            }
                        }
                    }
                } else {
                    gaps.insert(format!("{}:{}", r.state, r.reason));
                }
            } else {
                gaps.insert("p2_disabled_lexical_anchor_only".into());
            }
        }
        if started.elapsed().as_millis() >= u128::from(req.limits.deadline_ms) {
            return Err("work_limit:deadline".into());
        }
    }
    if let Some(diff) = validated {
        // A query can be derived from a removed BASE occurrence. Its HEAD
        // comparison is explicitly not an occurrence; never fabricate one.
        if req.p2 {
            for anchor in &req.anchors {
                if anchor.side != "base" {
                    continue;
                }
                let Some(lookup) = &anchor.lookup else {
                    continue;
                };
                if !diff.hunks.iter().any(|h| {
                    h.path == anchor.path
                        && h.base_start <= anchor.start
                        && anchor.end <= h.base_end
                        && !h.removed.is_empty()
                }) {
                    continue;
                }
                let ir = head.ir.as_ref().ok_or("p2_unavailable:bytes_capture")?;
                let result = ir.resolve(&lookup.module, &lookup.path, &lookup.namespace);
                if result.state != "resolved" {
                    gaps.insert(format!("{}:{}", result.state, result.reason));
                }
                resolutions.push(json!({"snapshot_id":head.snapshot_id,"lookup":lookup,"occurrence":null,"query_origin":{"kind":"removed_base_occurrence","snapshot_id":snapshots[0].snapshot_id,"path":anchor.path,"start":anchor.start,"end":anchor.end},"result":result}));
            }
        }
        for change in &diff.changes {
            for (side, s, revision) in [
                ("base", &snapshots[0], &diff.base),
                ("head", head, &diff.head),
            ] {
                let presence = &revision.dto.files[&change.path];
                let state = match presence {
                    Presence::Absent => Some("absent"),
                    Presence::Present { .. }
                        if !s
                            .input
                            .files
                            .get(&change.path)
                            .is_some_and(|source| !source.is_empty()) =>
                    {
                        Some("present_empty")
                    }
                    _ => None,
                };
                if let Some(state) = state {
                    if candidates.len() >= req.limits.max_candidates {
                        gaps.insert("max_candidates".into());
                        continue;
                    }
                    let c = Candidate {
                        id: id(
                            "item_presence",
                            &(&s.snapshot_id, &change.path, side, state),
                        ),
                        snapshot_id: s.snapshot_id.clone(),
                        file_id: format!("fi_{}", hash(change.path.as_bytes())),
                        path: change.path.clone(),
                        source_hash: s
                            .input
                            .files
                            .get(&change.path)
                            .map(|source| hash(source.as_bytes()))
                            .unwrap_or_default(),
                        minimum: [0, 0],
                        container: [0, 0],
                        full: [0, 0],
                        reason: format!("diff_{side}_presence"),
                        state: "captured_presence".into(),
                        presence: Some(state.into()),
                    };
                    candidates.insert(c.id.clone(), c);
                }
            }
        }
        if snapshots.iter().any(|s| s.ir.is_none()) {
            gaps.insert("ir_absent:captured_bytes_only".into());
        }
    }
    if anchors.is_empty() {
        gaps.insert("not_assessed:no_anchors_lexical_search_unimplemented".into());
    }
    if snapshots.iter().any(|s| s.ir.is_some()) {
        gaps.insert("bounded_rust_r1_r2_not_all_callers".into());
    }
    let mut candidates = candidates.into_values().collect::<Vec<_>>();
    candidates.sort_by(|a, b| {
        (&a.snapshot_id, &a.path, a.minimum, a.id.as_str()).cmp(&(
            &b.snapshot_id,
            &b.path,
            b.minimum,
            b.id.as_str(),
        ))
    });
    if candidates.len() > req.limits.max_candidates {
        candidates.truncate(req.limits.max_candidates);
        gaps.insert("max_candidates".into());
    }
    let descriptions = snapshots
        .iter()
        .enumerate()
        .map(|(i, s)| descriptor(s, i + 1))
        .collect::<Vec<_>>();
    let q = wire_request(&req, &descriptions, "context", None, profile);
    let selector_fingerprint = hash(include_str!("context_spike.rs").as_bytes());
    let context_id = id(
        "ctx",
        &(RULES, &selector_fingerprint, &q, &candidates, &gaps),
    );
    let mut obligations = candidates.iter().map(obligation).collect::<Vec<_>>();
    obligations.extend(unavailable);
    let manifest = Manifest {
        selection_fingerprint: context_id.clone(),
        context_id,
        retention_epoch: String::new(),
        incarnation: 0,
        retention_policy: RETENTION_POLICY.into(),
        snapshots: descriptions,
        request: q,
        normalized_request: req.clone(),
        rules_version: RULES.into(),
        selector_fingerprint,
        obligations,
        candidates,
        resolutions,
        selected: BTreeMap::new(),
        gaps: gaps.into_iter().collect(),
        created_ms: now_ms,
        expires_ms: now_ms.saturating_add(TTL_MS),
        retained_bytes,
    };
    let mut saved = Saved {
        manifest,
        snapshots,
        request: req,
        expansions: 0,
    };
    account_retention(&mut saved)?;
    Ok(saved)
}
fn account_retention(saved: &mut Saved) -> Result<(), String> {
    for _ in 0..8 {
        let size = serde_json::to_vec(&saved.snapshots)
            .map_err(|e| e.to_string())?
            .len()
            + serde_json::to_vec(&saved.manifest)
                .map_err(|e| e.to_string())?
                .len()
            + serde_json::to_vec(&saved.request)
                .map_err(|e| e.to_string())?
                .len();
        if size > MAX_RETAINED_BYTES {
            return Err("retention_capacity".into());
        }
        if saved.manifest.retained_bytes == size {
            return Ok(());
        }
        saved.manifest.retained_bytes = size;
    }
    Err("retention_accounting_unstable".into())
}

fn inventory(n: usize) -> Value {
    json!({"scope":{"kind":"workspace"},"denominator":"eligible_files","processed":0,"partial":n,
    "excluded":0,"failed":0,"stale":0,"capability_absent":0,"eligible":n,"discovered":n})
}
fn relations() -> Value {
    json!({"denominator":"not_available","recognized":null,"resolved":null,"candidates":null,"unknown":null,"external":null})
}
fn item(saved: &Saved, c: &Candidate, span: [usize; 2]) -> Value {
    let s = saved
        .snapshots
        .iter()
        .find(|s| s.snapshot_id == c.snapshot_id)
        .expect("retained revision");
    if let Some(presence) = &c.presence {
        return json!({"id":c.id,"kind":"presence","view":"presence","file_id":c.file_id,"snapshot_id":c.snapshot_id,"presence":presence,"span":null,"content":null,"source_hash":if presence=="absent" {Value::Null}else{json!({"algorithm":"blake3","hex":c.source_hash})},"producer_id":format!("prod_{}",s.producer_fingerprint),"configuration_id":s.configuration_id,"reason":c.reason});
    }
    let source = &s.input.files[&c.path];
    json!({"id":c.id,"kind":"source","view":"source","file_id":c.file_id,"snapshot_id":c.snapshot_id,
    "source_hash":{"algorithm":"blake3","hex":c.source_hash},"byte_length":source.len(),
    "span":{"start":span[0],"end":span[1]},"content":&source[span[0]..span[1]],
    "producer_id":format!("prod_{}",s.producer_fingerprint),"configuration_id":s.configuration_id,"reason":c.reason})
}
fn envelope(
    saved: &Saved,
    q: &Value,
    selected: &BTreeMap<String, [usize; 2]>,
    obligations: &[Obligation],
) -> Value {
    let m = &saved.manifest;
    let head = m.snapshots.last().expect("head");
    let mut items: Vec<Value> = vec![];
    for c in &m.candidates {
        if let Some(span) = selected.get(&c.id) {
            if let Some(existing) = items.iter_mut().find(|i| {
                i["kind"] == "source"
                    && c.presence.is_none()
                    && i["snapshot_id"] == c.snapshot_id
                    && i["file_id"] == c.file_id
                    && i["span"]["start"].as_u64().unwrap() <= span[1] as u64
                    && i["span"]["end"].as_u64().unwrap() >= span[0] as u64
            }) {
                let merged = [
                    span[0].min(existing["span"]["start"].as_u64().unwrap() as usize),
                    span[1].max(existing["span"]["end"].as_u64().unwrap() as usize),
                ];
                let original_id = existing["id"].clone();
                *existing = item(saved, c, merged);
                existing["id"] = original_id;
            } else {
                items.push(item(saved, c, *span));
            }
        }
    }
    let omitted = obligations
        .iter()
        .filter(|o| o.state == "omitted_budget")
        .collect::<Vec<_>>();
    let included = obligations
        .iter()
        .filter(|o| o.state == "satisfied")
        .count();
    let status = if !omitted.is_empty() {
        "insufficient_budget"
    } else if !m.gaps.is_empty() {
        "partial"
    } else {
        "ok"
    };
    let producers = saved.snapshots.iter().map(|s|json!({"producer_id":format!("prod_{}",s.producer_fingerprint),
        "name":"rust-r1-r2-p3","version":RULES,"fingerprint":{"algorithm":"blake3","hex":s.producer_fingerprint},
        "frontend":"rust","grammar_version":"0.24.2","method":"syntactic"})).collect::<Vec<_>>();
    let mut unique = BTreeSet::new();
    let producers = producers
        .into_iter()
        .filter(|p| unique.insert(p["producer_id"].to_string()))
        .collect::<Vec<_>>();
    let gap = saved.snapshots.iter().flat_map(|s|s.input.files.keys()).next().map(|path|json!({"code":"bounded_context_spike","file_id":format!("fi_{}",hash(path.as_bytes())),"span":null}));
    let query = json!({"completeness":"partial","scope":{"kind":"workspace"},"gaps":gap.into_iter().collect::<Vec<_>>()});
    let parts = saved
        .snapshots
        .iter()
        .map(|s| {
            json!({"snapshot_id":s.snapshot_id,"inventory":inventory(s.input.files.len()),
        "relations":relations(),"query":query})
        })
        .collect::<Vec<_>>();
    let files = saved.snapshots.iter().flat_map(|s|s.input.files.keys().map(|path|json!({"snapshot_id":s.snapshot_id,
        "file_id":format!("fi_{}",hash(path.as_bytes())),"state":"partial","tree_valid":Value::Null,
        "symbol_count":s.ir.as_ref().map(|ir|ir.declarations.iter().filter(|d|&d.evidence.path==path).count()),"reason":if s.ir.is_some(){"bounded_r1_r2"}else{"captured_bytes:ir_absent"},"gaps":[{"start":0,"end":s.input.files[path].len()}]}))).collect::<Vec<_>>();
    let mut result = json!({"schema_version":3,"request_id":q["request_id"],"workspace_id":"ws_context","worktree_id":"wt_context","status":status,
    "snapshot":head,"comparison":if m.snapshots.len()==2 {json!({"base":m.snapshots[0],"head":head})}else{Value::Null},
    "index":{"availability":"ready"},"support":{"status":"experimental","capability":"context.experimental","languages":["rust"],
    "scope":{"kind":"workspace"},"limits":m.gaps,"producers":producers},
    "freshness":{"mode":"snapshot","validated_scope":{"kind":"workspace"},"validated_at":null,"validation_complete":false,
    "atomicity":"captured_blobs","gaps":[]},
    "coverage":{"inventory":inventory(saved.snapshots.iter().map(|s|s.input.files.len()).sum()),"files":files,"relations":relations(),"query":query,"by_snapshot":parts},
    "sufficiency":{"state":if !omitted.is_empty(){"insufficient_budget"}else if included<obligations.len(){"incomplete"}else{"satisfied"},"identified":obligations.len(),"included":included},
    "budget":{"requested_bytes":q["limits"]["max_bytes"],"used_bytes":0,"requested_tokens":q["limits"]["max_tokens"],"used_tokens":0,
    "counting":"exact","tokenizer":q["limits"]["tokenizer"],"counting_scope":"domain_envelope"},
    "items":items,"assertions":[],"candidates":[],"unknowns":[],
    "omissions":omitted.iter().map(|o|json!({"id":o.id,"required":true,"reason":"budget",
    "minimum_additional_bytes":0,"description":o.reason})).collect::<Vec<_>>(),"diagnostics":[],
    "next":if omitted.is_empty(){json!([])}else{json!([{"operation":"expand","context_id":m.context_id,
        "item_ids":omitted.iter().flat_map(|o|o.item_ids.clone()).collect::<Vec<_>>(),"reason":"identified_content_omitted"}])},
    "error":null,"context_id":m.context_id,"obligation_receipts":obligations.iter().map(|o|json!({"id":o.id,"state":o.state,"reason":o.reason,"item_ids":o.item_ids})).collect::<Vec<_>>()});
    if saved.snapshots.iter().any(|s| s.capture.is_some()) {
        result["profile"] = json!(validated_diff::PROFILE);
        result["support"]["languages"] = json!(
            saved
                .snapshots
                .iter()
                .filter_map(|s| s.capture.as_ref().map(|c| c.frontend.clone()))
                .collect::<BTreeSet<_>>()
        );
        result["support"]["producers"] = json!(saved.snapshots.iter().map(|s|json!({"producer_id":format!("prod_{}",s.producer_fingerprint),"fingerprint":{"algorithm":"blake3","hex":s.producer_fingerprint},"frontend":s.capture.as_ref().unwrap().frontend,"method":if s.ir.is_some(){"rust_structural_optional_p2"}else{"captured_bytes"}})).collect::<Vec<_>>());
        result["capture_binding"] = json!(saved.snapshots.iter().enumerate().map(|(i,s)|json!({"side":if i==0{"base"}else{"head"},"snapshot_id":s.snapshot_id,"external_revision":s.capture.as_ref().unwrap().external_revision,"external_revision_is_provenance_only":true,"capture_blake3":s.capture.as_ref().unwrap().capture_blake3,"ir_present":s.ir.is_some(),"p2_enabled":saved.request.p2})).collect::<Vec<_>>());
        result["resolutions"] = json!(m.resolutions);
        result["unknowns"] = json!(
            m.resolutions
                .iter()
                .filter(|r| r["result"]["state"] != "resolved")
                .collect::<Vec<_>>()
        );
        result["retained_candidates"] = json!(m.candidates);
        result["retained_obligations"] = json!(obligations);
        result["diagnostics"] = json!(m.gaps);
    }
    result
}
/// Bounded fixed point, including digit boundaries and token interactions.
pub fn stabilize(
    value: &mut Value,
    meter: &mut impl Meter,
) -> Result<(Vec<u8>, usize, u128), String> {
    let start = Instant::now();
    let mut seen = BTreeSet::new();
    for n in 1..=COUNTER_ITERATIONS {
        let wire = serde_json::to_vec(value).map_err(|e| e.to_string())?;
        let tokens = meter.tokens(&wire)?;
        if value["budget"]["used_bytes"] == wire.len() && value["budget"]["used_tokens"] == tokens {
            return Ok((wire, n, start.elapsed().as_micros()));
        }
        if !seen.insert((wire.len(), tokens)) {
            return Err("counter_cycle".into());
        }
        value["budget"]["used_bytes"] = json!(wire.len());
        value["budget"]["used_tokens"] = json!(tokens);
    }
    Err("counter_iterations_exhausted".into())
}
fn select(
    mut saved: Saved,
    q: Value,
    ids: Option<&[String]>,
    meter: &mut impl Meter,
) -> Result<(Saved, Delivery), String> {
    let started = Instant::now();
    let mut selected = BTreeMap::new();
    let mut obligations = saved.manifest.obligations.clone();
    for o in &mut obligations {
        if ids.is_some_and(|ids| !o.item_ids.iter().any(|id| ids.contains(id))) {
            o.state = "not_assessed".into();
            o.reason = "not_requested_in_expansion".into();
            continue;
        }
        if o.state != "unavailable" {
            o.state = "omitted_budget".into();
        }
    }
    let mut meter_calls = 0;
    let mut meter_elapsed = 0;
    let mut base = envelope(&saved, &q, &selected, &obligations);
    let (wire, calls, elapsed) = stabilize(&mut base, meter)?;
    meter_calls += calls;
    meter_elapsed += elapsed;
    if started.elapsed().as_millis() >= u128::from(saved.request.limits.deadline_ms) {
        return Err("work_limit:deadline".into());
    }
    if wire.len() > saved.request.limits.max_bytes
        || base["budget"]["used_tokens"].as_u64().unwrap() > saved.request.limits.max_tokens as u64
    {
        return Err("budget_below_envelope".into());
    }
    let candidates = saved.manifest.candidates.clone();
    for c in &candidates {
        if ids.is_some_and(|ids| !ids.contains(&c.id)) {
            continue;
        }
        let alternatives = if ids.is_some() {
            vec![c.full, c.container]
        } else {
            vec![c.minimum]
        };
        for span in alternatives {
            if ids.is_some()
                && saved
                    .manifest
                    .selected
                    .get(&c.id)
                    .is_some_and(|old| span[1] - span[0] <= old[1] - old[0] && *old != c.full)
            {
                continue;
            }
            let mut trial_selected = selected.clone();
            trial_selected.insert(c.id.clone(), span);
            let mut trial_obligations = obligations.clone();
            for o in &mut trial_obligations {
                if o.item_ids.contains(&c.id) {
                    o.state = "satisfied".into();
                }
            }
            let mut trial = envelope(&saved, &q, &trial_selected, &trial_obligations);
            let (wire, calls, elapsed) = stabilize(&mut trial, meter)?;
            meter_calls += calls;
            meter_elapsed += elapsed;
            if started.elapsed().as_millis() >= u128::from(saved.request.limits.deadline_ms) {
                return Err("work_limit:deadline".into());
            }
            if wire.len() <= saved.request.limits.max_bytes
                && trial["budget"]["used_tokens"].as_u64().unwrap()
                    <= saved.request.limits.max_tokens as u64
            {
                selected = trial_selected;
                obligations = trial_obligations;
                break;
            }
        }
    }
    let mut response = envelope(&saved, &q, &selected, &obligations);
    let (wire, calls, elapsed) = stabilize(&mut response, meter)?;
    meter_calls += calls;
    meter_elapsed += elapsed;
    if started.elapsed().as_millis() >= u128::from(saved.request.limits.deadline_ms) {
        return Err("work_limit:deadline".into());
    }
    if wire.len() > saved.request.limits.max_bytes
        || response["budget"]["used_tokens"].as_u64().unwrap()
            > saved.request.limits.max_tokens as u64
    {
        return Err("budget_limit".into());
    }
    if ids.is_none() {
        saved.manifest.selected = selected;
        saved.manifest.obligations = obligations;
        account_retention(&mut saved)?;
        if started.elapsed().as_millis() >= u128::from(saved.request.limits.deadline_ms) {
            return Err("work_limit:deadline".into());
        }
    }
    let delivery = Delivery {
        request: q,
        response,
        manifest: saved.manifest.clone(),
        snapshots: saved.snapshots.clone(),
        wire_hex: hex(&wire),
        wire_blake3: hash(&wire),
        meter_calls,
        meter_elapsed_micros: meter_elapsed,
    };
    Ok((saved, delivery))
}
impl Store {
    /// Linux/macOS experimental retention domain. Entropy failure is explicit;
    /// no predictable fallback can resurrect a handle in a replacement Store.
    pub fn new() -> Result<Self, String> {
        let mut epoch = [0; 32];
        std::fs::File::open("/dev/urandom")
            .and_then(|mut file| file.read_exact(&mut epoch))
            .map_err(|e| format!("retention_epoch_unavailable:{e}"))?;
        Ok(Self {
            contexts: BTreeMap::new(),
            published: None,
            epoch: hex(&epoch),
            next_incarnation: 0,
        })
    }
    fn expire(&mut self, now_ms: u64) {
        self.contexts.retain(|_, s| now_ms < s.manifest.expires_ms);
    }
    pub fn context(
        &mut self,
        case: Case,
        now_ms: u64,
        meter: &mut impl Meter,
    ) -> Result<Delivery, String> {
        let started = Instant::now();
        let deadline_ms = case.request.limits.deadline_ms;
        self.expire(now_ms);
        let saved = prepare(case, now_ms, meter.profile())?;
        self.publish_prepared(saved, now_ms, meter, started, deadline_ms)
    }
    pub fn context_validated(
        &mut self,
        diff: ValidatedDiff,
        mut request: Request,
        now_ms: u64,
        meter: &mut impl Meter,
    ) -> Result<Delivery, String> {
        let started = Instant::now();
        let deadline_ms = request.limits.deadline_ms;
        self.expire(now_ms);
        if !request.hunks.is_empty() {
            return Err("invalid_request:caller_hunks_for_validated_diff".into());
        }
        if diff.head.dto.frontend == "bytes" && request.p2 {
            return Err("p2_unavailable:bytes_capture".into());
        }
        for anchor in &request.anchors {
            let revision = match anchor.side.as_str() {
                "base" => &diff.base,
                "head" => &diff.head,
                _ => return Err("anchor_revision_mismatch".into()),
            };
            let source = revision
                .input
                .files
                .get(&anchor.path)
                .ok_or("invalid_request:anchor_presence")?;
            if !valid_span(source, anchor.start, anchor.end) || anchor.start == anchor.end {
                return Err("invalid_request:source_span".into());
            }
            if let Some(lookup) = &anchor.lookup {
                if &source[anchor.start..anchor.end]
                    != lookup.path.rsplit("::").next().unwrap_or("")
                {
                    return Err("invalid_request:lookup_occurrence".into());
                }
            }
        }
        request.anchors.extend(diff.anchors.clone());
        request.hunks = diff.hunks.clone();
        let case = Case {
            base: Some(diff.base.input.clone()),
            head: diff.head.input.clone(),
            request,
        };
        let saved = prepare_with(case, now_ms, meter.profile(), Some(&diff))?;
        self.publish_prepared(saved, now_ms, meter, started, deadline_ms)
    }
    fn publish_prepared(
        &mut self,
        mut saved: Saved,
        _now_ms: u64,
        meter: &mut impl Meter,
        started: Instant,
        deadline_ms: u64,
    ) -> Result<Delivery, String> {
        let live = self
            .contexts
            .values()
            .find(|s| s.manifest.selection_fingerprint == saved.manifest.selection_fingerprint)
            .cloned();
        let reuse = live.is_some();
        if let Some(old) = live {
            saved = old;
        } else {
            self.next_incarnation = self
                .next_incarnation
                .checked_add(1)
                .ok_or("context_incarnation_overflow")?;
            saved.manifest.retention_epoch = self.epoch.clone();
            saved.manifest.incarnation = self.next_incarnation;
            saved.manifest.context_id = id(
                "ctx",
                &(
                    &saved.manifest.selection_fingerprint,
                    &saved.manifest.retention_epoch,
                    saved.manifest.incarnation,
                    saved.manifest.created_ms,
                    saved.manifest.expires_ms,
                    &saved.manifest.retention_policy,
                ),
            );
        }
        let remaining = deadline_ms.saturating_sub(started.elapsed().as_millis() as u64);
        if remaining == 0 {
            return Err("work_limit:deadline".into());
        }
        let q = saved.manifest.request.clone();
        let mut view = saved;
        view.request.limits.deadline_ms = remaining;
        let (mut saved, mut delivery) = select(view, q, None, meter)?;
        if started.elapsed().as_millis() >= u128::from(deadline_ms) {
            return Err("work_limit:deadline".into());
        }
        saved.request.limits.deadline_ms = deadline_ms;
        account_retention(&mut saved)?;
        if started.elapsed().as_millis() >= u128::from(deadline_ms) {
            return Err("work_limit:deadline".into());
        }
        delivery.manifest = saved.manifest.clone();
        let cid = saved.manifest.context_id.clone();
        if reuse {
            delivery.manifest = self.contexts[&cid].manifest.clone();
            return Ok(delivery);
        }
        // Plan every eviction without mutating live contexts. All errors/deadline
        // checks happen before the infallible commit; failure B leaves valid A.
        self.commit_publication(cid, saved, || {
            if started.elapsed().as_millis() >= u128::from(deadline_ms) {
                Err("work_limit:deadline".into())
            } else {
                Ok(())
            }
        })?;
        Ok(delivery)
    }
    fn commit_publication(
        &mut self,
        cid: String,
        saved: Saved,
        admission: impl FnOnce() -> Result<(), String>,
    ) -> Result<(), String> {
        let victims = self.publication_victims(&saved)?;
        admission()?;
        for victim in victims {
            self.contexts.remove(&victim);
        }
        self.published = Some(saved.snapshots.last().expect("head").snapshot_id.clone());
        self.contexts.insert(cid, saved);
        Ok(())
    }
    fn publication_victims(&self, saved: &Saved) -> Result<Vec<String>, String> {
        let mut ordered = self.contexts.iter().collect::<Vec<_>>();
        ordered.sort_by_key(|(_, s)| (s.manifest.created_ms, s.manifest.incarnation));
        let mut count = ordered.len();
        let mut bytes = ordered
            .iter()
            .map(|(_, s)| s.manifest.retained_bytes)
            .sum::<usize>();
        let mut victims = vec![];
        for (id, s) in ordered {
            if count < MAX_CONTEXTS && bytes + saved.manifest.retained_bytes <= MAX_RETAINED_BYTES {
                break;
            }
            victims.push(id.clone());
            count -= 1;
            bytes -= s.manifest.retained_bytes;
        }
        if count >= MAX_CONTEXTS || bytes + saved.manifest.retained_bytes > MAX_RETAINED_BYTES {
            return Err("retention_capacity".into());
        }
        Ok(victims)
    }
    pub fn expand(
        &mut self,
        context_id: &str,
        item_ids: &[String],
        limits: Limits,
        now_ms: u64,
        meter: &mut impl Meter,
    ) -> Result<Delivery, String> {
        let started = Instant::now();
        let deadline_ms = limits.deadline_ms;
        self.expire(now_ms);
        let saved = self.contexts.get_mut(context_id).ok_or("context_expired")?;
        if limits.deadline_ms == 0
            || limits.max_candidates == 0
            || limits.max_files == 0
            || limits.max_source_bytes == 0
            || item_ids.len() > limits.max_candidates
        {
            return Err("invalid_request:limits".into());
        }
        if saved.expansions >= MAX_EXPANSIONS {
            return Err("expansion_limit".into());
        }
        let unique = item_ids.iter().collect::<BTreeSet<_>>();
        if item_ids.is_empty()
            || unique.len() != item_ids.len()
            || item_ids
                .iter()
                .any(|id| !saved.manifest.candidates.iter().any(|c| &c.id == id))
        {
            return Err("invalid_request:item_ids".into());
        }
        if meter.profile()
            != saved.manifest.request["limits"]["tokenizer"]
                .as_str()
                .unwrap()
        {
            return Err("measurement_profile_mismatch".into());
        }
        let requested = saved
            .manifest
            .candidates
            .iter()
            .filter(|c| item_ids.contains(&c.id))
            .collect::<Vec<_>>();
        let files = requested
            .iter()
            .map(|c| (&c.snapshot_id, &c.file_id))
            .collect::<BTreeSet<_>>();
        let bytes = files
            .iter()
            .map(|(snapshot, file)| {
                requested
                    .iter()
                    .find(|c| &c.snapshot_id == *snapshot && &c.file_id == *file)
                    .unwrap()
                    .full[1]
            })
            .sum::<usize>();
        if files.len() > limits.max_files || bytes > limits.max_source_bytes {
            return Err("work_limit:expansion_sources".into());
        }
        // An admitted attempt spends technical work even when its meter,
        // counters, deadline or payload budget fail. Cheap validation above
        // consumes no expansion slot.
        saved.expansions += 1;
        let mut view = saved.clone();
        view.request.limits = limits;
        let q = wire_request(
            &view.request,
            &view.manifest.snapshots,
            "expand",
            Some((context_id, item_ids)),
            meter.profile(),
        );
        let remaining = deadline_ms.saturating_sub(started.elapsed().as_millis() as u64);
        if remaining == 0 {
            return Err("work_limit:deadline".into());
        }
        view.request.limits.deadline_ms = remaining;
        let (_, delivery) = select(view, q, Some(item_ids), meter)?;
        if started.elapsed().as_millis() >= u128::from(deadline_ms) {
            return Err("work_limit:deadline".into());
        }
        Ok(delivery)
    }
    pub fn release_snapshot(&mut self, snapshot_id: &str) {
        self.contexts.retain(|_, s| {
            !s.snapshots
                .iter()
                .any(|snapshot| snapshot.snapshot_id == snapshot_id)
        });
    }
    /// Evaluator-only diagnostics; does not search or reread a checkout.
    pub fn inspect(&mut self, context_id: &str, now_ms: u64) -> Result<Value, String> {
        self.expire(now_ms);
        let saved = self.contexts.get(context_id).ok_or("context_expired")?;
        Ok(
            json!({"manifest":saved.manifest,"snapshots":saved.snapshots,"expansions":saved.expansions}),
        )
    }
    pub fn instance_id(&self) -> &str {
        &self.epoch
    }
    pub fn retained_contexts(&self) -> usize {
        self.contexts.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    struct Bytes;
    impl Meter for Bytes {
        fn profile(&self) -> &str {
            "test-only-byte-meter"
        }
        fn tokens(&mut self, b: &[u8]) -> Result<usize, String> {
            Ok(b.len())
        }
    }
    fn input(source: &str) -> Input {
        Input {
            files: BTreeMap::from([("src/lib.rs".into(), source.into())]),
            root: "src/lib.rs".into(),
            edition: "2024".into(),
            configuration: BTreeMap::new(),
            rules: "rust-r1-r2-v1".into(),
        }
    }
    fn limits() -> Limits {
        Limits {
            max_bytes: 131072,
            max_tokens: 131072,
            max_candidates: 32,
            max_files: 8,
            max_source_bytes: 1048576,
            deadline_ms: 30000,
        }
    }
    fn case(source: &str) -> Case {
        Case {
            base: None,
            head: input(source),
            request: Request {
                intent: "review".into(),
                description: "development".into(),
                anchors: vec![Anchor {
                    side: "head".into(),
                    path: "src/lib.rs".into(),
                    start: 7,
                    end: 11,
                    lookup: None,
                }],
                hunks: vec![],
                p2: true,
                limits: limits(),
            },
        }
    }
    fn removed() -> Case {
        serde_json::from_str(include_str!(
            "../../../eval/context/removed-consumer-input.json"
        ))
        .unwrap()
    }
    #[test]
    fn base_consumer_and_definition_use_ir_without_promotion() {
        let mut store = Store::new().unwrap();
        let d = store.context(removed(), 0, &mut Bytes).unwrap();
        assert!(
            d.manifest
                .candidates
                .iter()
                .any(|c| c.reason == "demonstrated_consumer"
                    && c.state == "resolved"
                    && c.snapshot_id == d.snapshots[0].snapshot_id)
        );
        assert!(d.response["assertions"].as_array().unwrap().is_empty());
        assert_eq!(d.response["comparison"]["head"], d.response["snapshot"]);
        assert!(d.response["coverage"]["query"]["completeness"] == "partial");
    }
    #[test]
    fn immutable_expansion_does_not_migrate_when_new_snapshot_publishes() {
        let mut store = Store::new().unwrap();
        let d = store.context(removed(), 0, &mut Bytes).unwrap();
        let original = serde_json::to_value(&d.manifest).unwrap();
        let cid = &d.manifest.context_id;
        let ids = d
            .manifest
            .candidates
            .iter()
            .map(|c| c.id.clone())
            .collect::<Vec<_>>();
        let expanded = store.expand(cid, &ids, limits(), 1, &mut Bytes).unwrap();
        store
            .context(case("pub fn newer() {}\n"), 2, &mut Bytes)
            .unwrap();
        let after = store.expand(cid, &ids, limits(), 3, &mut Bytes).unwrap();
        assert_eq!(expanded.response, after.response);
        assert_eq!(serde_json::to_value(&after.manifest).unwrap(), original);
        assert_ne!(
            store.published.as_ref().unwrap(),
            d.snapshots.last().unwrap().snapshot_id.as_str()
        );
    }
    #[test]
    fn central_hunk_is_not_prefix_and_wrong_diff_is_rejected() {
        let c: Case = serde_json::from_str(include_str!(
            "../../../eval/context/central-hunk-input.json"
        ))
        .unwrap();
        let d = Store::new()
            .unwrap()
            .context(c.clone(), 0, &mut Bytes)
            .unwrap();
        assert!(
            d.response["items"]
                .as_array()
                .unwrap()
                .iter()
                .any(|i| i["content"].as_str().unwrap().contains("corrected_call"))
        );
        assert!(d.manifest.candidates.iter().all(|i| i.minimum[0] > 1000));
        let mut invalid = c;
        invalid.request.hunks[0].added = "incorrect_text".into();
        assert_eq!(
            Store::new()
                .unwrap()
                .context(invalid, 0, &mut Bytes)
                .err()
                .unwrap(),
            "invalid_request:diff_content"
        );
    }
    #[test]
    fn valid_changed_slice_but_wrong_unchanged_region_is_invalid_diff() {
        let mut c: Case = serde_json::from_str(include_str!(
            "../../../eval/context/central-hunk-input.json"
        ))
        .unwrap();
        c.head
            .files
            .get_mut("src/lib.rs")
            .unwrap()
            .push_str("// undeclared change\n");
        assert_eq!(
            Store::new()
                .unwrap()
                .context(c, 0, &mut Bytes)
                .err()
                .unwrap(),
            "invalid_request:diff_inconsistent"
        );
    }
    #[test]
    fn identified_content_does_not_fit_bytes_or_tokens() {
        let source = format!("pub fn long() {{ /* {} */ }}\n", "x".repeat(12000));
        for token_limit in [false, true] {
            let mut c = case(&source);
            if token_limit {
                c.request.limits.max_tokens = 6500;
            } else {
                c.request.limits.max_bytes = 6500;
            }
            let d = Store::new().unwrap().context(c, 0, &mut Bytes).unwrap();
            assert_eq!(d.response["status"], "insufficient_budget");
            assert_eq!(d.response["sufficiency"]["included"], 0);
            assert!(d.response["budget"]["used_bytes"].as_u64().unwrap() <= 6500);
            assert_eq!(d.manifest.obligations[0].state, "omitted_budget");
        }
    }
    #[test]
    fn expansion_that_cannot_grow_reports_insufficient() {
        let source = format!("pub fn long() {{\n{}\n}}\n", "    // filler\n".repeat(1000));
        let c = case(&source);
        let mut store = Store::new().unwrap();
        let d = store.context(c, 0, &mut Bytes).unwrap();
        let ids = d
            .manifest
            .candidates
            .iter()
            .map(|c| c.id.clone())
            .collect::<Vec<_>>();
        let small = Limits {
            max_bytes: 6500,
            max_tokens: 6500,
            ..limits()
        };
        let expanded = store
            .expand(&d.manifest.context_id, &ids, small, 1, &mut Bytes)
            .unwrap();
        assert_eq!(expanded.response["status"], "insufficient_budget");
        assert_eq!(
            expanded.response["obligation_receipts"][0]["state"],
            "omitted_budget"
        );
        assert_eq!(
            serde_json::to_value(&expanded.manifest).unwrap(),
            serde_json::to_value(&d.manifest).unwrap()
        );
    }
    #[test]
    fn ttl_release_and_pressure_end_whole_context() {
        for expiry in ["ttl", "release", "pressure"] {
            let mut store = Store::new().unwrap();
            let d = store.context(removed(), 0, &mut Bytes).unwrap();
            let now = if expiry == "ttl" { TTL_MS } else { 3 };
            if expiry == "release" {
                store.release_snapshot(&d.snapshots[0].snapshot_id);
            }
            if expiry == "pressure" {
                store
                    .context(case("pub fn second() {}\n"), 1, &mut Bytes)
                    .unwrap();
                store
                    .context(case("pub fn third() {}\n"), 2, &mut Bytes)
                    .unwrap();
                assert_eq!(store.retained_contexts(), 2);
            }
            assert_eq!(
                store
                    .expand(
                        &d.manifest.context_id,
                        &[d.manifest.candidates[0].id.clone()],
                        limits(),
                        now,
                        &mut Bytes
                    )
                    .err()
                    .unwrap(),
                "context_expired"
            );
        }
    }
    #[test]
    fn foreign_duplicate_ids_and_expansion_cap_are_refused() {
        let mut store = Store::new().unwrap();
        let d = store
            .context(case("pub fn test() {}\n"), 0, &mut Bytes)
            .unwrap();
        let cid = &d.manifest.context_id;
        let id = d.manifest.candidates[0].id.clone();
        for ids in [
            vec!["item_foreign".into()],
            vec![id.clone(), id.clone()],
            vec![],
        ] {
            assert_eq!(
                store
                    .expand(cid, &ids, limits(), 1, &mut Bytes)
                    .err()
                    .unwrap(),
                "invalid_request:item_ids"
            );
        }
        for n in 0..MAX_EXPANSIONS {
            store
                .expand(
                    cid,
                    std::slice::from_ref(&id),
                    limits(),
                    n as u64 + 1,
                    &mut Bytes,
                )
                .unwrap();
        }
        assert_eq!(
            store
                .expand(cid, &[id], limits(), 9, &mut Bytes)
                .err()
                .unwrap(),
            "expansion_limit"
        );
    }
    #[test]
    fn deterministic_wire_counts_and_profile_binding() {
        let c = case("pub fn test() { /* café 漢字 <|endoftext|> */ }\r\n");
        let a = Store::new()
            .unwrap()
            .context(c.clone(), 0, &mut Bytes)
            .unwrap();
        let b = Store::new().unwrap().context(c, 4, &mut Bytes).unwrap();
        let mut normalized_a = a.response.clone();
        let mut normalized_b = b.response.clone();
        normalized_a["context_id"] = json!("ctx_normalized");
        normalized_b["context_id"] = json!("ctx_normalized");
        assert_eq!(normalized_a, normalized_b);
        assert_ne!(a.manifest.retention_epoch, b.manifest.retention_epoch);
        assert_eq!(
            a.manifest.selection_fingerprint,
            b.manifest.selection_fingerprint
        );
        assert_ne!(a.wire_hex, b.wire_hex);
        assert_eq!(
            a.wire_hex.len() / 2,
            a.response["budget"]["used_bytes"].as_u64().unwrap() as usize
        );
        assert_eq!(
            a.response["budget"]["used_tokens"],
            a.response["budget"]["used_bytes"]
        );
        assert_eq!(
            a.manifest.selector_fingerprint,
            hash(include_str!("context_spike.rs").as_bytes())
        );
    }
    #[test]
    fn absent_source_is_unavailable_not_budget() {
        let mut c = case("pub fn test() {}\n");
        c.request.anchors[0].path = "src/absent.rs".into();
        let d = Store::new().unwrap().context(c, 0, &mut Bytes).unwrap();
        assert_eq!(d.response["status"], "partial");
        assert_eq!(d.manifest.obligations[0].state, "unavailable");
        assert_eq!(d.response["sufficiency"]["state"], "incomplete");
    }
    #[test]
    fn absent_base_and_work_limits_do_not_fallback() {
        let mut c = case("pub fn test() {}\n");
        c.request.anchors[0].side = "base".into();
        assert_eq!(
            Store::new()
                .unwrap()
                .context(c, 0, &mut Bytes)
                .err()
                .unwrap(),
            "anchor_revision_mismatch"
        );
        let mut c = removed();
        c.request.limits.max_files = 1;
        assert_eq!(
            Store::new()
                .unwrap()
                .context(c, 0, &mut Bytes)
                .err()
                .unwrap(),
            "work_limit:input_capture"
        );
        let mut c = removed();
        c.request.limits.max_source_bytes = 1;
        assert_eq!(
            Store::new()
                .unwrap()
                .context(c, 0, &mut Bytes)
                .err()
                .unwrap(),
            "work_limit:input_capture"
        );
    }
    #[test]
    fn unknown_lookup_is_retained_without_global_fallback() {
        let mut c = case("pub fn test() {}\n");
        c.request.anchors[0].lookup = Some(Lookup {
            module: "".into(),
            path: "missing".into(),
            namespace: "value".into(),
        });
        let d = Store::new().unwrap().context(c, 0, &mut Bytes).unwrap();
        assert!(d.manifest.gaps.iter().any(|g| g.starts_with("unknown:")));
        assert!(!d.manifest.candidates.iter().any(|c| c.state == "resolved"));
        assert!(d.response["assertions"].as_array().unwrap().is_empty());
    }
    #[test]
    fn opaque_evaluator_fields_cannot_enter_typed_boundary() {
        let mut value = serde_json::to_value(case("pub fn test() {}\n")).unwrap();
        value["labels"] = json!({"answer":"yes"});
        assert!(serde_json::from_value::<Case>(value).is_err());
        let mut value = serde_json::to_value(case("pub fn test() {}\n")).unwrap();
        value["head"]["expected_target"] = json!("secret");
        assert!(serde_json::from_value::<Case>(value).is_err());
    }
    #[test]
    fn expansion_work_limits_are_checked_before_materializing() {
        let mut store = Store::new().unwrap();
        let d = store.context(removed(), 0, &mut Bytes).unwrap();
        let ids = d
            .manifest
            .candidates
            .iter()
            .map(|c| c.id.clone())
            .collect::<Vec<_>>();
        for constrained in [
            Limits {
                max_files: 1,
                ..limits()
            },
            Limits {
                max_source_bytes: 1,
                ..limits()
            },
        ] {
            assert_eq!(
                store
                    .expand(&d.manifest.context_id, &ids, constrained, 1, &mut Bytes)
                    .err()
                    .unwrap(),
                "work_limit:expansion_sources"
            );
        }
    }
    #[test]
    fn deadline_checked_after_final_meter_and_empty_selection() {
        struct Slow;
        impl Meter for Slow {
            fn profile(&self) -> &str {
                "test-only-byte-meter"
            }
            fn tokens(&mut self, b: &[u8]) -> Result<usize, String> {
                std::thread::sleep(std::time::Duration::from_millis(10));
                Ok(b.len())
            }
        }
        let mut c = case("pub fn test() {}\n");
        c.request.anchors.clear();
        c.request.limits.deadline_ms = 5;
        assert_eq!(
            Store::new()
                .unwrap()
                .context(c, 0, &mut Slow)
                .err()
                .unwrap(),
            "work_limit:deadline"
        );
        let mut store = Store::new().unwrap();
        let d = store
            .context(case("pub fn test() {}\n"), 0, &mut Bytes)
            .unwrap();
        assert_eq!(
            store
                .expand(
                    &d.manifest.context_id,
                    &[d.manifest.candidates[0].id.clone()],
                    Limits {
                        deadline_ms: 5,
                        ..limits()
                    },
                    1,
                    &mut Slow
                )
                .err()
                .unwrap(),
            "work_limit:deadline"
        );
    }
    #[test]
    fn candidate_cap_has_gap_and_unknown_evidence_preserves_state() {
        let mut c = removed();
        c.request.limits.max_candidates = 1;
        let d = Store::new().unwrap().context(c, 0, &mut Bytes).unwrap();
        assert_eq!(d.manifest.candidates.len(), 1);
        assert!(d.manifest.gaps.iter().any(|g| g == "max_candidates"));
        let mut c = case("pub fn test() {}\n");
        c.request.anchors[0].lookup = Some(Lookup {
            module: "".into(),
            path: "missing".into(),
            namespace: "value".into(),
        });
        let d = Store::new().unwrap().context(c, 0, &mut Bytes).unwrap();
        assert_eq!(d.manifest.resolutions[0]["result"]["state"], "unknown");
        assert!(d.manifest.resolutions[0]["result"]["target_id"].is_null());
    }
    #[test]
    fn failed_admitted_expansions_consume_attempt_cap() {
        struct Fails {
            calls: usize,
        }
        impl Meter for Fails {
            fn profile(&self) -> &str {
                "test-only-byte-meter"
            }
            fn tokens(&mut self, _: &[u8]) -> Result<usize, String> {
                self.calls += 1;
                Err("measurement_failed".into())
            }
        }
        let mut store = Store::new().unwrap();
        let d = store
            .context(case("pub fn test() {}\n"), 0, &mut Bytes)
            .unwrap();
        let ids = vec![d.manifest.candidates[0].id.clone()];
        let mut meter = Fails { calls: 0 };
        for n in 0..MAX_EXPANSIONS {
            assert_eq!(
                store
                    .expand(
                        &d.manifest.context_id,
                        &ids,
                        limits(),
                        n as u64 + 1,
                        &mut meter
                    )
                    .err()
                    .unwrap(),
                "measurement_failed"
            );
        }
        assert_eq!(meter.calls, MAX_EXPANSIONS);
        assert_eq!(
            store
                .expand(&d.manifest.context_id, &ids, limits(), 9, &mut meter)
                .err()
                .unwrap(),
            "expansion_limit"
        );
        assert_eq!(meter.calls, MAX_EXPANSIONS);
    }
    #[test]
    fn ended_context_handle_never_resurrects_when_same_input_is_recreated() {
        for ended in ["ttl", "eviction", "release"] {
            let c = case("pub fn test() {}\n");
            let mut store = Store::new().unwrap();
            let first = store.context(c.clone(), 0, &mut Bytes).unwrap();
            let now = if ended == "ttl" { TTL_MS } else { 0 };
            if ended == "eviction" {
                store
                    .context(case("pub fn second() {}\n"), 0, &mut Bytes)
                    .unwrap();
                store
                    .context(case("pub fn third() {}\n"), 0, &mut Bytes)
                    .unwrap();
            }
            if ended == "release" {
                store.release_snapshot(&first.snapshots[0].snapshot_id);
            }
            let recreated = store.context(c, now, &mut Bytes).unwrap();
            assert_ne!(
                first.manifest.context_id, recreated.manifest.context_id,
                "{ended}"
            );
            assert_eq!(
                store
                    .expand(
                        &first.manifest.context_id,
                        &[first.manifest.candidates[0].id.clone()],
                        limits(),
                        now,
                        &mut Bytes
                    )
                    .err()
                    .unwrap(),
                "context_expired"
            );
        }
    }
    #[test]
    fn replacement_store_and_live_reuse_preserve_retention_domain_and_cap() {
        let c = case("pub fn test() {}\n");
        let mut store = Store::new().unwrap();
        let first = store.context(c.clone(), 0, &mut Bytes).unwrap();
        let ids = vec![first.manifest.candidates[0].id.clone()];
        for n in 0..MAX_EXPANSIONS {
            store
                .expand(
                    &first.manifest.context_id,
                    &ids,
                    limits(),
                    n as u64 + 1,
                    &mut Bytes,
                )
                .unwrap();
        }
        let reused = store.context(c.clone(), TTL_MS - 1, &mut Bytes).unwrap();
        assert_eq!(first.manifest.context_id, reused.manifest.context_id);
        assert_eq!(first.manifest.expires_ms, reused.manifest.expires_ms);
        assert_eq!(
            store
                .expand(
                    &first.manifest.context_id,
                    &ids,
                    limits(),
                    TTL_MS - 1,
                    &mut Bytes
                )
                .err()
                .unwrap(),
            "expansion_limit"
        );
        let mut replacement = Store::new().unwrap();
        let new = replacement.context(c, 0, &mut Bytes).unwrap();
        assert_ne!(first.manifest.context_id, new.manifest.context_id);
        assert_ne!(first.manifest.retention_epoch, new.manifest.retention_epoch);
        assert_eq!(
            replacement
                .expand(&first.manifest.context_id, &ids, limits(), 0, &mut Bytes)
                .err()
                .unwrap(),
            "context_expired"
        );
        assert_ne!(
            first.manifest.context_id,
            store
                .context(case("pub fn test() {}\n"), TTL_MS, &mut Bytes)
                .unwrap()
                .manifest
                .context_id
        );
    }
    #[test]
    fn incarnation_overflow_fails_closed() {
        let mut store = Store::new().unwrap();
        store.next_incarnation = u64::MAX;
        assert_eq!(
            store
                .context(case("pub fn test() {}\n"), 0, &mut Bytes)
                .err()
                .unwrap(),
            "context_incarnation_overflow"
        );
        assert_eq!(store.retained_contexts(), 0);
    }
    #[test]
    fn byte_digit_boundaries_and_counter_cycles_are_bounded() {
        for n in [8, 88, 988, 9988] {
            let mut value =
                json!({"budget":{"used_bytes":0,"used_tokens":0},"content":"x".repeat(n)});
            let (wire, iterations, _) = stabilize(&mut value, &mut Bytes).unwrap();
            assert!(iterations <= COUNTER_ITERATIONS);
            assert_eq!(
                wire.len(),
                value["budget"]["used_bytes"].as_u64().unwrap() as usize
            );
        }
        struct Cycle;
        impl Meter for Cycle {
            fn profile(&self) -> &str {
                "cycle"
            }
            fn tokens(&mut self, b: &[u8]) -> Result<usize, String> {
                let v: Value = serde_json::from_slice(b).unwrap();
                Ok(if v["budget"]["used_tokens"] == 1 {
                    2
                } else {
                    1
                })
            }
        }
        let mut v = json!({"budget":{"used_bytes":0,"used_tokens":0}});
        assert_eq!(
            stabilize(&mut v, &mut Cycle).err().unwrap(),
            "counter_cycle"
        );
    }
}

#[cfg(test)]
mod bridge_tests {
    use super::*;
    use validated_diff::{Change, DiffInput, Edit, RevisionInput};
    struct Bytes;
    impl Meter for Bytes {
        fn profile(&self) -> &str {
            "bridge-functional-bytes-unmeasured-model-tokens"
        }
        fn tokens(&mut self, bytes: &[u8]) -> Result<usize, String> {
            Ok(bytes.len())
        }
    }
    fn limits() -> Limits {
        Limits {
            max_bytes: 131072,
            max_tokens: 131072,
            max_candidates: 64,
            max_files: 16,
            max_source_bytes: 1048576,
            deadline_ms: 30000,
        }
    }
    fn request() -> Request {
        Request {
            intent: "review".into(),
            description: "public controlled diff".into(),
            anchors: vec![],
            hunks: vec![],
            p2: false,
            limits: limits(),
        }
    }
    fn revision(id: &str, frontend: &str, path: &str, source: Option<&str>) -> RevisionInput {
        let mut r = RevisionInput {
            external_revision: id.into(),
            frontend: frontend.into(),
            root: path.into(),
            edition: if frontend == "rust" { "2021" } else { "none" }.into(),
            configuration: BTreeMap::from([
                ("target".into(), "not_evaluated".into()),
                ("features".into(), "not_evaluated".into()),
            ]),
            rules: if frontend == "rust" {
                semantics_spike::RULES
            } else {
                "captured-bytes-v1"
            }
            .into(),
            files: BTreeMap::from([(
                path.into(),
                source
                    .map(|s| Presence::Present {
                        bytes_hex: hex(s.as_bytes()),
                    })
                    .unwrap_or(Presence::Absent),
            )]),
            capture_blake3: String::new(),
        };
        r.capture_blake3 = r.identity();
        r
    }
    fn change(frontend: &str, path: &str, a: Option<&str>, b: Option<&str>) -> DiffInput {
        let base = revision("captured-A", frontend, path, a);
        let head = revision("captured-B", frontend, path, b);
        DiffInput {
            base,
            head,
            changes: vec![Change {
                path: path.into(),
                kind: match (a, b) {
                    (None, Some(_)) => "create",
                    (Some(_), None) => "delete",
                    _ => "modify",
                }
                .into(),
                hunks: vec![Edit {
                    base_span: [0, a.map_or(0, str::len)],
                    head_span: [0, b.map_or(0, str::len)],
                    removed_hex: hex(a.unwrap_or("").as_bytes()),
                    replacement_hex: hex(b.unwrap_or("").as_bytes()),
                }],
            }],
        }
    }
    #[test]
    fn bytes_presence_create_delete_empty_without_rust_ir() {
        for (a, b) in [
            (None, Some("")),
            (Some(""), None),
            (None, Some("export const α=1;\r\n")),
            (Some("export const α=1;\r\n"), None),
            (Some("a\n"), Some("b\n")),
        ] {
            let mut store = Store::new().unwrap();
            let diff = ValidatedDiff::try_from(change("bytes", "src/a.jsx", a, b)).unwrap();
            let delivery = store
                .context_validated(diff, request(), 0, &mut Bytes)
                .unwrap();
            assert!(delivery.snapshots.iter().all(|s| s.ir.is_none()));
            assert_eq!(delivery.response["support"]["languages"], json!(["bytes"]));
            assert!(
                delivery.response["resolutions"]
                    .as_array()
                    .unwrap()
                    .is_empty()
            );
            assert!(
                delivery.response["items"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .filter(|i| i["kind"] == "presence")
                    .all(|i| i["span"].is_null() && i["content"].is_null())
            );
            assert!(
                delivery
                    .manifest
                    .obligations
                    .iter()
                    .all(|o| o.state == "satisfied")
            );
            for c in &delivery.manifest.candidates {
                let expanded = store
                    .expand(
                        &delivery.manifest.context_id,
                        std::slice::from_ref(&c.id),
                        limits(),
                        1,
                        &mut Bytes,
                    )
                    .unwrap();
                assert_eq!(expanded.response["items"][0]["snapshot_id"], c.snapshot_id);
                if let Some(presence) = &c.presence {
                    assert_eq!(expanded.response["items"][0]["presence"], *presence);
                }
            }
        }
    }
    #[test]
    fn byte_p2_and_foreign_hunks_refused_preserving_live_context() {
        let mut store = Store::new().unwrap();
        let raw = change("bytes", "src/a.jsx", Some("a\n"), Some("b\n"));
        let a = store
            .context_validated(
                ValidatedDiff::try_from(raw.clone()).unwrap(),
                request(),
                0,
                &mut Bytes,
            )
            .unwrap();
        let mut req = request();
        req.p2 = true;
        assert!(
            store
                .context_validated(
                    ValidatedDiff::try_from(raw.clone()).unwrap(),
                    req,
                    1,
                    &mut Bytes
                )
                .is_err()
        );
        let mut req = request();
        req.hunks = vec![Hunk {
            path: "wrong".into(),
            base_start: 0,
            base_end: 0,
            head_start: 0,
            head_end: 0,
            removed: String::new(),
            added: String::new(),
        }];
        assert!(
            store
                .context_validated(ValidatedDiff::try_from(raw).unwrap(), req, 1, &mut Bytes)
                .is_err()
        );
        assert!(store.inspect(&a.manifest.context_id, 2).is_ok());
    }
    #[test]
    fn pressure_deadline_gate_is_atomic_and_ttl_is_separate() {
        let mut store = Store::new().unwrap();
        let a = store
            .context_validated(
                ValidatedDiff::try_from(change("bytes", "a.jsx", Some("a"), Some("b"))).unwrap(),
                request(),
                0,
                &mut Bytes,
            )
            .unwrap();
        let b = store
            .context_validated(
                ValidatedDiff::try_from(change("bytes", "b.jsx", Some("a"), Some("b"))).unwrap(),
                request(),
                1,
                &mut Bytes,
            )
            .unwrap();
        let valid = store.contexts[&b.manifest.context_id].clone();
        let mut failing = valid.clone();
        failing.manifest.context_id = "ctx_new".into();
        failing.manifest.retained_bytes = MAX_RETAINED_BYTES;
        let victims = store.publication_victims(&failing).unwrap();
        assert_eq!(victims.len(), 2);
        let before = serde_json::to_value((
            &store.contexts[&a.manifest.context_id].manifest,
            &store.contexts[&b.manifest.context_id].manifest,
            &store.published,
        ))
        .unwrap();
        assert_eq!(
            store
                .commit_publication("ctx_new".into(), failing, || Err(
                    "work_limit:deadline".into()
                ))
                .unwrap_err(),
            "work_limit:deadline"
        );
        assert_eq!(
            serde_json::to_value((
                &store.contexts[&a.manifest.context_id].manifest,
                &store.contexts[&b.manifest.context_id].manifest,
                &store.published
            ))
            .unwrap(),
            before
        );
        let mut failing = valid;
        failing.manifest.retained_bytes = MAX_RETAINED_BYTES + 1;
        assert!(
            store
                .commit_publication("ctx_new".into(), failing, || Ok(()))
                .is_err()
        );
        assert!(
            store
                .expand(
                    &a.manifest.context_id,
                    &[a.manifest.candidates[0].id.clone()],
                    limits(),
                    2,
                    &mut Bytes
                )
                .is_ok()
        );
        assert!(store.inspect(&a.manifest.context_id, TTL_MS).is_err());
        assert!(store.inspect(&b.manifest.context_id, TTL_MS).is_ok());
    }
    #[test]
    fn valid_update_and_failed_budget_keep_retained_source() {
        let mut store = Store::new().unwrap();
        let a = store
            .context_validated(
                ValidatedDiff::try_from(change("bytes", "a.jsx", Some("a\n"), Some("b\n")))
                    .unwrap(),
                request(),
                0,
                &mut Bytes,
            )
            .unwrap();
        let b = store
            .context_validated(
                ValidatedDiff::try_from(change("bytes", "a.jsx", Some("a\n"), Some("c\n")))
                    .unwrap(),
                request(),
                1,
                &mut Bytes,
            )
            .unwrap();
        assert_ne!(a.manifest.context_id, b.manifest.context_id);
        let mut req = request();
        req.limits.max_bytes = 1024;
        assert!(
            store
                .context_validated(
                    ValidatedDiff::try_from(change("bytes", "a.jsx", Some("a\n"), Some("d\n")))
                        .unwrap(),
                    req,
                    2,
                    &mut Bytes
                )
                .is_err()
        );
        let old = store
            .expand(
                &a.manifest.context_id,
                &[a.manifest.candidates[0].id.clone()],
                limits(),
                3,
                &mut Bytes,
            )
            .unwrap();
        assert_eq!(
            old.response["items"][0]["content"],
            a.response["items"][0]["content"]
        );
        assert_eq!(
            store.published.as_deref(),
            Some(b.snapshots[1].snapshot_id.as_str())
        );
    }
    #[test]
    fn tokio_removed_declaration_base_expansion_and_head_query_are_distinct() {
        let captured: Value = serde_json::from_str(include_str!(
            "../../../eval/semantics/tokio-development.json"
        ))
        .unwrap();
        assert_eq!(
            captured["upstream_commit"],
            "2fb5757a97a94b3173f8fdd7b6280423b63da6e6"
        );
        let path = "tokio/src/io/uring/utils.rs";
        let source = captured["cases"][0]["files"][path].as_str().unwrap();
        let start = source.find("pub(crate) fn cstr").unwrap();
        let head = &source[..start];
        let mut dto = change("rust", path, Some(source), Some(head));
        dto.changes[0].hunks = vec![Edit {
            base_span: [start, source.len()],
            head_span: [start, start],
            removed_hex: hex(source[start..].as_bytes()),
            replacement_hex: String::new(),
        }];
        let mut req = request();
        req.p2 = true;
        for (name, needle, namespace) in [
            ("cstr", "fn cstr", "value"),
            ("ArcFd", "type ArcFd", "type"),
            ("UringFd", "trait UringFd", "type"),
            ("OwnedFd", "OwnedFd", "type"),
        ] {
            for (side, content) in [("base", source), ("head", head)] {
                if let Some(index) = content.find(needle) {
                    let at = index + needle.len() - name.len();
                    req.anchors.push(Anchor {
                        side: side.into(),
                        path: path.into(),
                        start: at,
                        end: at + name.len(),
                        lookup: Some(Lookup {
                            module: String::new(),
                            path: name.into(),
                            namespace: namespace.into(),
                        }),
                    });
                }
            }
        }
        let diff = ValidatedDiff::try_from(dto).unwrap();
        let mut store = Store::new().unwrap();
        let d = store
            .context_validated(diff.clone(), req.clone(), 0, &mut Bytes)
            .unwrap();
        for r in &d.manifest.resolutions {
            let name = r["lookup"]["path"].as_str().unwrap();
            let is_head = r["snapshot_id"] == d.snapshots[1].snapshot_id;
            assert_eq!(
                r["result"]["state"],
                if name == "OwnedFd" || name == "cstr" && is_head {
                    "unknown"
                } else {
                    "resolved"
                }
            );
            if name == "cstr" && is_head {
                assert!(r["occurrence"].is_null());
                assert_eq!(r["query_origin"]["kind"], "removed_base_occurrence");
            }
        }
        let declaration = d
            .manifest
            .candidates
            .iter()
            .find(|c| {
                c.reason == "resolved_definition"
                    && c.snapshot_id == d.snapshots[0].snapshot_id
                    && c.minimum[0] >= start
            })
            .unwrap();
        let expanded = store
            .expand(
                &d.manifest.context_id,
                std::slice::from_ref(&declaration.id),
                limits(),
                1,
                &mut Bytes,
            )
            .unwrap();
        assert_eq!(expanded.response["items"][0]["content"], source);
        // Freeze operational identity mapping explicitly; fresh build uses no
        // persisted IR/candidates, then compare every semantic artifact field.
        let mut fresh = Store::new().unwrap();
        fresh.epoch = store.epoch.clone();
        let rebuilt = fresh.context_validated(diff, req, 0, &mut Bytes).unwrap();
        assert_eq!(
            serde_json::to_value((
                &d.request,
                &d.response,
                &d.manifest,
                &d.snapshots,
                &d.wire_hex,
                &d.wire_blake3
            ))
            .unwrap(),
            serde_json::to_value((
                &rebuilt.request,
                &rebuilt.response,
                &rebuilt.manifest,
                &rebuilt.snapshots,
                &rebuilt.wire_hex,
                &rebuilt.wire_blake3
            ))
            .unwrap()
        );
    }
}
