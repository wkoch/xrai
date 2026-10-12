//! ADR025 development-only Rust R1/R2 module environment. No analyzed code executes.
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use tree_sitter::{Node, Parser};

pub const RULES: &str = "rust-r1-r2-v1";
pub const RULES_R3: &str = "rust-r3-v1";
mod r3;
pub use r3::{Binding, Condition};
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Input {
    pub files: BTreeMap<String, String>,
    pub root: String,
    pub edition: String,
    pub configuration: BTreeMap<String, String>,
    pub rules: String,
}
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Evidence {
    pub file_id: String,
    pub snapshot_id: String,
    pub path: String,
    pub source_hash: String,
    pub start: usize,
    pub end: usize,
}
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Declaration {
    pub id: String,
    pub name: String,
    pub module: String,
    pub namespace: String,
    pub kind: String,
    pub visibility: String,
    pub evidence: Evidence,
}
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Import {
    pub module: String,
    pub alias: String,
    pub path: String,
    pub visibility: String,
    pub evidence: Evidence,
}
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Gap {
    pub module: String,
    pub reason: String,
    pub evidence: Option<Evidence>,
}
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Resolution {
    pub state: String,
    pub target_id: Option<String>,
    pub candidate_ids: Vec<String>,
    pub reason: String,
    pub method: String,
    pub evidence: Vec<Evidence>,
    pub dependencies: Vec<String>,
}
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Scope {
    pub local_id: usize,
    pub kind: String,
    pub module_owner: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parent_scope_local_id: Option<usize>,
    pub evidence: Evidence,
}
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Reference {
    pub occurrence_id: String,
    pub scope_local_id: usize,
    pub module: String,
    pub path: String,
    pub namespace: String,
    pub role: String,
    pub evidence: Evidence,
    pub resolution: Resolution,
}
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Module {
    pub name: String,
    pub parent: String,
    pub visibility: String,
    pub file: String,
    pub directory: String,
    pub evidence: Evidence,
}
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Snapshot {
    pub snapshot_id: String,
    pub configuration_id: String,
    pub configuration_fingerprint: String,
    pub producer_fingerprint: String,
    pub input: Input,
    pub declarations: Vec<Declaration>,
    pub imports: Vec<Import>,
    pub modules: BTreeMap<String, Module>,
    pub gaps: Vec<Gap>,
    pub references: Vec<Reference>,
    pub scopes: Vec<Scope>,
    pub coverage: BTreeMap<String, String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub bindings: Vec<Binding>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub conditions: Vec<Condition>,
}
fn hash(bytes: &[u8]) -> String {
    blake3::hash(bytes).to_hex().to_string()
}
fn qualify(module: &str, name: &str) -> String {
    if module.is_empty() {
        name.into()
    } else {
        format!("{module}::{name}")
    }
}
fn descendant(module: &str, ancestor: &str) -> bool {
    ancestor.is_empty() || module == ancestor || module.starts_with(&format!("{ancestor}::"))
}
fn text<'a>(node: Node<'_>, source: &'a str) -> &'a str {
    &source[node.byte_range()]
}
fn children(node: Node<'_>) -> Vec<Node<'_>> {
    let mut cursor = node.walk();
    node.named_children(&mut cursor).collect()
}
fn visibility(node: Node<'_>, source: &str) -> String {
    children(node)
        .iter()
        .find(|n| n.kind() == "visibility_modifier")
        .map_or("private".into(), |n| text(*n, source).replace(' ', ""))
}
fn permitted(visibility: &str, owner: &str, requester: &str) -> bool {
    visibility == "pub"
        || visibility == "pub(crate)"
        || (visibility == "private" && descendant(requester, owner))
}
fn unknown(reason: &str, dependencies: Vec<String>) -> Resolution {
    Resolution {
        state: "unknown".into(),
        target_id: None,
        candidate_ids: vec![],
        reason: reason.into(),
        method: "semantic_resolution".into(),
        evidence: vec![],
        dependencies,
    }
}
impl Snapshot {
    fn evidence(&self, file: &str, start: usize, end: usize) -> Evidence {
        let source = &self.input.files[file];
        Evidence {
            file_id: format!("fi_{}", hash(file.as_bytes())),
            snapshot_id: self.snapshot_id.clone(),
            path: file.into(),
            source_hash: hash(source.as_bytes()),
            start,
            end,
        }
    }
    fn gap(&mut self, module: &str, reason: &str, evidence: Option<Evidence>) {
        self.gaps.push(Gap {
            module: module.into(),
            reason: reason.into(),
            evidence,
        });
    }
    fn ancestors_gap(&self, module: &str) -> Option<&Gap> {
        self.gaps
            .iter()
            .find(|g| g.reason != "r3_lexical_form_not_supported" && descendant(module, &g.module))
    }
    pub fn resolve(&self, module: &str, path: &str, namespace: &str) -> Resolution {
        let mut visiting = BTreeSet::new();
        self.lookup(module, module, path, namespace, &mut visiting, 0)
    }
    fn lookup(
        &self,
        origin: &str,
        requester: &str,
        path: &str,
        namespace: &str,
        visiting: &mut BTreeSet<String>,
        depth: usize,
    ) -> Resolution {
        let dep = format!(
            "{}:{}:{origin}:{namespace}:{path}:{}:{}",
            self.snapshot_id, self.configuration_id, self.producer_fingerprint, RULES
        );
        if depth > 128 {
            return unknown("work_limit", vec![dep]);
        }
        if !["type", "value"].contains(&namespace) {
            return unknown("namespace_not_supported", vec![dep]);
        }
        if let Some(gap) = self.ancestors_gap(origin) {
            return unknown(&gap.reason, vec![dep]);
        }
        if !self.modules.contains_key(origin) {
            return unknown("module_absent", vec![dep]);
        }
        let key = format!("{origin}:{requester}:{namespace}:{path}");
        if !visiting.insert(key.clone()) {
            return unknown("import_cycle", vec![dep]);
        }
        let mut parts: Vec<&str> = path.split("::").collect();
        let mut current = origin.to_string();
        if parts.first() == Some(&"crate") {
            current.clear();
            parts.remove(0);
        } else if parts.first() == Some(&"self") {
            parts.remove(0);
        }
        while parts.first() == Some(&"super") {
            if current.is_empty() {
                visiting.remove(&key);
                return unknown("super_outside_root", vec![dep]);
            }
            current = self.modules[&current].parent.clone();
            parts.remove(0);
        }
        let Some(last) = parts.last().copied() else {
            visiting.remove(&key);
            return unknown("empty_path", vec![dep]);
        };
        let mut prefix_evidence = vec![];
        for part in &parts[..parts.len() - 1] {
            if let Some(gap) = self.ancestors_gap(&current) {
                visiting.remove(&key);
                return unknown(&gap.reason, vec![dep]);
            }
            let next = qualify(&current, part);
            if self
                .declarations
                .iter()
                .any(|d| d.module == current && d.name == *part && d.namespace == "type")
            {
                visiting.remove(&key);
                return unknown("module_type_namespace_conflict", vec![dep]);
            }
            if let Some(m) = self.modules.get(&next) {
                if !permitted(&m.visibility, &current, requester) {
                    visiting.remove(&key);
                    return unknown("visibility_denied", vec![dep]);
                }
                prefix_evidence.push(m.evidence.clone());
                current = next;
            } else {
                visiting.remove(&key);
                return unknown("module_or_external_not_captured", vec![dep]);
            }
        }
        if let Some(gap) = self.ancestors_gap(&current) {
            visiting.remove(&key);
            return unknown(&gap.reason, vec![dep]);
        }
        let mut matches = vec![];
        let mut blocked = None;
        for d in &self.declarations {
            if d.module == current && d.name == last && d.namespace == namespace {
                if permitted(&d.visibility, &current, requester) {
                    matches.push((d.id.clone(), vec![d.evidence.clone()], vec![]));
                } else {
                    blocked = Some("visibility_denied".to_string());
                }
            }
        }
        for import in &self.imports {
            if import.module == current && import.alias == last {
                if !permitted(&import.visibility, &current, requester) {
                    blocked = Some("visibility_denied".into());
                    continue;
                }
                let result = self.lookup(
                    &current,
                    &current,
                    &import.path,
                    namespace,
                    visiting,
                    depth + 1,
                );
                if let Some(target) = result.target_id {
                    let declaration = self
                        .declarations
                        .iter()
                        .find(|d| d.id == target)
                        .expect("local target");
                    if (import.visibility == "pub" && declaration.visibility != "pub")
                        || (import.visibility == "pub(crate)"
                            && declaration.visibility == "private")
                    {
                        blocked = Some("reexport_visibility_widening_not_proven".into());
                        continue;
                    }
                    let mut evidence = vec![import.evidence.clone()];
                    evidence.extend(result.evidence);
                    matches.push((target, evidence, result.dependencies));
                } else {
                    blocked = Some(result.reason);
                }
            }
        }
        visiting.remove(&key);
        if let Some(reason) = blocked {
            return unknown(&reason, vec![dep]);
        }
        if matches.is_empty() {
            return unknown("name_absent_or_external_not_captured", vec![dep]);
        }
        let binding_count = matches.len();
        // Even duplicate imports to one destination are an invalid/ambiguous binding environment.
        let mut evidence = prefix_evidence;
        let mut dependencies = vec![dep];
        let mut ids = vec![];
        for (id, ev, deps) in matches {
            ids.push(id);
            evidence.extend(ev);
            dependencies.extend(deps);
        }
        ids.sort();
        ids.dedup();
        dependencies.sort();
        dependencies.dedup();
        if ids.len() == 1 && binding_count > 1 {
            return unknown("duplicate_binding", dependencies);
        }
        let state = if ids.len() == 1 {
            "resolved"
        } else {
            "candidate"
        };
        Resolution {
            state: state.into(),
            target_id: (state == "resolved").then(|| ids[0].clone()),
            candidate_ids: if state == "candidate" { ids } else { vec![] },
            reason: if state == "resolved" {
                "unique_demonstrated"
            } else {
                "lookup_ambiguous"
            }
            .into(),
            method: "semantic_resolution".into(),
            evidence,
            dependencies,
        }
    }
}

pub fn build(input: Input) -> Result<Snapshot, String> {
    for path in input.files.keys() {
        if path.starts_with('/')
            || path.contains('\0')
            || path.split('/').any(|s| s == ".." || s.is_empty())
        {
            return Err("invalid captured relative path".into());
        }
    }
    if !input.files.contains_key(&input.root) {
        return Err("captured root absent".into());
    }
    let configuration_fingerprint = hash(
        &serde_json::to_vec(&(&input.edition, &input.configuration)).map_err(|e| e.to_string())?,
    );
    let parser_producer = crate::worker_spike::producer("rust")?;
    let producer_fingerprint = hash(
        &serde_json::to_vec(&(
            parser_producer,
            RULES,
            &input.rules,
            include_str!("semantics_spike.rs"),
            include_str!("semantics_spike/r3.rs"),
        ))
        .map_err(|e| e.to_string())?,
    );
    let snapshot_id = format!(
        "snap_{}",
        hash(&serde_json::to_vec(&(&input, &producer_fingerprint)).map_err(|e| e.to_string())?)
    );
    let mut snapshot = Snapshot {
        snapshot_id,
        configuration_id: format!("cfg_{configuration_fingerprint}"),
        configuration_fingerprint,
        producer_fingerprint,
        input,
        declarations: vec![],
        imports: vec![],
        modules: BTreeMap::new(),
        gaps: vec![],
        references: vec![],
        scopes: vec![],
        coverage: BTreeMap::new(),
        bindings: vec![],
        conditions: vec![],
    };
    let root = snapshot.input.root.clone();
    let directory = root.rsplit_once('/').map_or("", |(d, _)| d).to_string();
    snapshot.modules.insert(
        "".into(),
        Module {
            name: "".into(),
            parent: "".into(),
            visibility: "pub".into(),
            file: root.clone(),
            directory,
            evidence: snapshot.evidence(&root, 0, snapshot.input.files[&root].len()),
        },
    );
    if !["2021", "2024"].contains(&snapshot.input.edition.as_str()) {
        snapshot.gap("", "edition_not_supported", None);
    }
    if ![RULES, RULES_R3].contains(&snapshot.input.rules.as_str()) {
        snapshot.gap("", "resolver_rules_not_supported", None);
    }
    let mut visited = BTreeSet::new();
    load_file(&mut snapshot, "", &root, &mut visited)?;
    snapshot.declarations.sort_by(|a, b| a.id.cmp(&b.id));
    snapshot
        .imports
        .sort_by(|a, b| (&a.module, &a.alias, &a.path).cmp(&(&b.module, &b.alias, &b.path)));
    snapshot
        .gaps
        .sort_by(|a, b| (&a.module, &a.reason).cmp(&(&b.module, &b.reason)));
    for i in 0..snapshot.references.len() {
        if snapshot.references[i].resolution.reason == "pending" {
            let r = &snapshot.references[i];
            let mut result = if snapshot.input.rules == RULES_R3 {
                snapshot.resolve_at(
                    &r.module,
                    &r.path,
                    &r.namespace,
                    &r.evidence.path,
                    r.evidence.start,
                )
            } else {
                snapshot.resolve(&r.module, &r.path, &r.namespace)
            };
            if !result.evidence.contains(&r.evidence) {
                result.evidence.insert(0, r.evidence.clone());
            }
            snapshot.references[i].resolution = result;
        }
    }
    for path in snapshot.input.files.keys() {
        snapshot.coverage.insert(
            path.clone(),
            if visited.contains(path) {
                "parsed"
            } else {
                "not_in_module_graph"
            }
            .into(),
        );
    }
    Ok(snapshot)
}
fn load_file(
    snapshot: &mut Snapshot,
    module: &str,
    file: &str,
    visited: &mut BTreeSet<String>,
) -> Result<(), String> {
    if !visited.insert(file.into()) {
        snapshot.gap(module, "module_file_cycle", None);
        return Ok(());
    }
    let source = snapshot.input.files[file].clone();
    let mut parser = Parser::new();
    parser
        .set_language(
            &crate::parsing_spike::grammar("rust")
                .map_err(|e| e.to_string())?
                .language,
        )
        .map_err(|e| e.to_string())?;
    let tree = parser
        .parse(source.as_bytes(), None)
        .ok_or("parse_failed")?;
    if tree.root_node().has_error() {
        snapshot.gap(
            module,
            "parse_partial",
            Some(snapshot.evidence(file, 0, source.len())),
        );
    }
    extract_items(snapshot, module, file, tree.root_node(), &source, visited)
}
fn extract_items(
    snapshot: &mut Snapshot,
    module: &str,
    file: &str,
    node: Node<'_>,
    source: &str,
    visited: &mut BTreeSet<String>,
) -> Result<(), String> {
    let mut cfg_active = true;
    for item in children(node) {
        if snapshot.input.rules == RULES_R3
            && item.kind() == "attribute_item"
            && let Some(active) = r3::attribute(snapshot, module, file, item, source)
        {
            cfg_active &= active;
            continue;
        }
        if ![
            "attribute_item",
            "inner_attribute_item",
            "line_comment",
            "block_comment",
        ]
        .contains(&item.kind())
        {
            let active = cfg_active;
            cfg_active = true;
            if !active {
                continue;
            }
        }
        let evidence = snapshot.evidence(file, item.start_byte(), item.end_byte());
        let vis = visibility(item, source);
        if !["private", "pub", "pub(crate)"].contains(&vis.as_str()) {
            snapshot.gap(module, "visibility_not_supported", Some(evidence.clone()));
        }
        match item.kind() {
            "attribute_item" | "inner_attribute_item" => {
                let t = text(item, source);
                let attribute_body = t
                    .trim_start_matches("#![")
                    .trim_start_matches("#[")
                    .trim_start();
                let attribute = attribute_body
                    .split(|ch: char| !ch.is_alphanumeric() && ch != '_')
                    .next()
                    .unwrap_or("");
                if ![
                    "allow",
                    "deny",
                    "warn",
                    "forbid",
                    "doc",
                    "inline",
                    "cold",
                    "track_caller",
                    "must_use",
                ]
                .contains(&attribute)
                    || !attribute_body[attribute.len()..]
                        .trim_start()
                        .starts_with(['(', '=', ']'])
                {
                    snapshot.gap(
                        module,
                        "configuration_or_attribute_not_evaluated",
                        Some(evidence),
                    );
                }
            }
            "macro_invocation" | "macro_definition" | "extern_crate_declaration" => snapshot.gap(
                module,
                "macro_or_external_environment_not_captured",
                Some(evidence),
            ),
            "mod_item" => {
                let Some(name_node) = item.child_by_field_name("name") else {
                    continue;
                };
                let name = text(name_node, source);
                let qualified = qualify(module, name);
                if snapshot.modules.contains_key(&qualified) {
                    snapshot.gap(module, "duplicate_module", Some(evidence.clone()));
                }
                let directory = snapshot.modules[module].directory.clone();
                let subdir = if directory.is_empty() {
                    name.into()
                } else {
                    format!("{directory}/{name}")
                };
                snapshot.modules.insert(
                    qualified.clone(),
                    Module {
                        name: qualified.clone(),
                        parent: module.into(),
                        visibility: vis,
                        file: file.into(),
                        directory: subdir.clone(),
                        evidence,
                    },
                );
                if let Some(body) = item.child_by_field_name("body") {
                    extract_items(snapshot, &qualified, file, body, source, visited)?;
                } else {
                    let candidates = [format!("{subdir}.rs"), format!("{subdir}/mod.rs")];
                    let files: Vec<_> = candidates
                        .into_iter()
                        .filter(|p| snapshot.input.files.contains_key(p))
                        .collect();
                    if files.len() == 1 {
                        snapshot.modules.get_mut(&qualified).expect("inserted").file =
                            files[0].clone();
                        load_file(snapshot, &qualified, &files[0], visited)?;
                    } else {
                        snapshot.gap(
                            &qualified,
                            if files.is_empty() {
                                "module_file_absent"
                            } else {
                                "module_file_ambiguous"
                            },
                            None,
                        );
                    }
                }
            }
            "use_declaration" => {
                if let Some(argument) = item.child_by_field_name("argument") {
                    let mut imports = vec![];
                    if !expand_use(text(argument, source), "", &mut imports) {
                        snapshot.gap(module, "import_form_not_supported", Some(evidence));
                    } else {
                        for (path, alias) in imports {
                            snapshot.imports.push(Import {
                                module: module.into(),
                                alias,
                                path,
                                visibility: vis.clone(),
                                evidence: evidence.clone(),
                            });
                        }
                    }
                }
            }
            "function_item" | "struct_item" | "enum_item" | "type_item" | "const_item"
            | "static_item" | "trait_item" => {
                if let Some(name_node) = item.child_by_field_name("name") {
                    let name = text(name_node, source);
                    let namespaces: &[&str] = match item.kind() {
                        "function_item" | "const_item" | "static_item" => &["value"],
                        "struct_item"
                            if item
                                .child_by_field_name("body")
                                .is_none_or(|b| b.kind() == "ordered_field_declaration_list") =>
                        {
                            &["type", "value"]
                        }
                        _ => &["type"],
                    };
                    for namespace in namespaces {
                        let id = format!(
                            "sym_{}",
                            hash(
                                format!(
                                    "{}:{file}:{}:{}:{module}:{namespace}:{name}",
                                    snapshot.snapshot_id,
                                    name_node.start_byte(),
                                    name_node.end_byte()
                                )
                                .as_bytes()
                            )
                        );
                        snapshot.declarations.push(Declaration {
                            id,
                            name: name.into(),
                            module: module.into(),
                            namespace: (*namespace).into(),
                            kind: item.kind().into(),
                            visibility: vis.clone(),
                            evidence: snapshot.evidence(
                                file,
                                name_node.start_byte(),
                                name_node.end_byte(),
                            ),
                        });
                    }
                }
                if item.kind() == "function_item" {
                    extract_references(snapshot, module, file, item, source);
                }
            }
            "impl_item" => {
                for function in children(item.child_by_field_name("body").unwrap_or(item)) {
                    if function.kind() == "function_item" {
                        extract_references(snapshot, module, file, function, source);
                    }
                }
            }
            "expression_statement" if contains_kind(item, "macro_invocation") => {
                snapshot.gap(
                    module,
                    "macro_or_external_environment_not_captured",
                    Some(evidence),
                );
            }
            _ => {}
        }
    }
    Ok(())
}
fn expand_use(input: &str, prefix: &str, result: &mut Vec<(String, String)>) -> bool {
    let input = input.trim();
    if input.contains('*') || input.contains(" as _") || input.starts_with("::") {
        return false;
    }
    if let Some(open) = input.find('{') {
        if !input.ends_with('}') {
            return false;
        }
        let before = input[..open].trim().trim_end_matches("::");
        let base = if before.is_empty() {
            prefix.to_string()
        } else if prefix.is_empty() {
            before.to_string()
        } else {
            format!("{prefix}::{before}")
        };
        let inside = &input[open + 1..input.len() - 1];
        let mut level = 0;
        let mut start = 0;
        for (i, ch) in inside.char_indices() {
            if ch == '{' {
                level += 1;
            } else if ch == '}' {
                level -= 1;
            } else if ch == ',' && level == 0 {
                if !expand_use(&inside[start..i], &base, result) {
                    return false;
                }
                start = i + 1;
            }
        }
        return inside[start..].trim().is_empty() || expand_use(&inside[start..], &base, result);
    }
    let (path, alias) = input
        .split_once(" as ")
        .map_or((input, None), |(p, a)| (p.trim(), Some(a.trim())));
    // Module aliases / self groups need a module-valued binding and are explicitly deferred.
    if path == "self" || path.ends_with("::self") {
        return false;
    }
    let path = if prefix.is_empty() {
        path.into()
    } else {
        format!("{prefix}::{path}")
    };
    let alias = alias.unwrap_or_else(|| path.rsplit("::").next().unwrap_or(""));
    if alias.is_empty() {
        return false;
    }
    result.push((path.clone(), alias.into()));
    true
}
fn extract_references(
    snapshot: &mut Snapshot,
    module: &str,
    file: &str,
    function: Node<'_>,
    source: &str,
) {
    if snapshot.input.rules == RULES_R3 {
        r3::extract(snapshot, module, file, function, source);
        return;
    }
    let body = function.child_by_field_name("body");
    let Some(body) = body else {
        return;
    };
    let scope_local_id = snapshot.scopes.len();
    snapshot.scopes.push(Scope {
        local_id: scope_local_id,
        kind: "function".into(),
        module_owner: module.into(),
        parent_scope_local_id: None,
        evidence: snapshot.evidence(file, function.start_byte(), function.end_byte()),
    });
    let params = function
        .child_by_field_name("parameters")
        .map_or("", |n| text(n, source));
    let mut stack = vec![body];
    // Unsupported bindings/patterns may shadow a name anywhere in the function. Conservatively block its calls.
    let body_gap = has_binding_gap(body);
    while let Some(node) = stack.pop() {
        if node.kind() == "call_expression"
            && let Some(callee) = node.child_by_field_name("function")
        {
            let path = text(callee, source).to_string();
            let gap = body_gap
                || !["identifier", "scoped_identifier"].contains(&callee.kind())
                || (callee.kind() == "identifier"
                    && params
                        .split(|ch: char| !ch.is_alphanumeric() && ch != '_')
                        .any(|part| part == path));
            let evidence = snapshot.evidence(file, callee.start_byte(), callee.end_byte());
            snapshot.references.push(Reference {
                occurrence_id: format!(
                    "occ_{}",
                    hash(
                        format!(
                            "{}:{file}:{}:{}",
                            snapshot.snapshot_id,
                            callee.start_byte(),
                            callee.end_byte()
                        )
                        .as_bytes()
                    )
                ),
                scope_local_id,
                module: module.into(),
                path,
                namespace: "value".into(),
                role: "callsite".into(),
                evidence,
                resolution: {
                    let mut result = unknown(
                        if gap {
                            "binding_receiver_or_macro_not_demonstrated"
                        } else {
                            "pending"
                        },
                        vec![format!(
                            "{}:{}:{}:{}",
                            snapshot.snapshot_id,
                            snapshot.configuration_id,
                            scope_local_id,
                            snapshot.producer_fingerprint
                        )],
                    );
                    result.evidence.push(snapshot.evidence(
                        file,
                        callee.start_byte(),
                        callee.end_byte(),
                    ));
                    result
                },
            });
        }
        stack.extend(children(node));
    }
}
fn has_binding_gap(node: Node<'_>) -> bool {
    if [
        "struct_item",
        "enum_item",
        "type_item",
        "const_item",
        "static_item",
        "mod_item",
        "impl_item",
        "trait_item",
        "let_condition",
        "let_declaration",
        "closure_expression",
        "match_expression",
        "for_expression",
        "if_let_expression",
        "while_let_expression",
        "function_item",
        "use_declaration",
        "macro_invocation",
    ]
    .contains(&node.kind())
    {
        return true;
    }
    children(node).into_iter().any(has_binding_gap)
}
/// Conservative package rebuild. No fact or negative lookup from A is attached to B.
pub struct Index {
    pub current: Snapshot,
    pub generation: u64,
}
impl Index {
    pub fn new(input: Input) -> Result<Self, String> {
        Ok(Self {
            current: build(input)?,
            generation: 1,
        })
    }
    pub fn update(&mut self, input: Input) -> Result<&Snapshot, String> {
        let next = build(input)?;
        self.current = next;
        self.generation += 1;
        Ok(&self.current)
    }
}

fn contains_kind(node: Node<'_>, kind: &str) -> bool {
    node.kind() == kind || children(node).into_iter().any(|n| contains_kind(n, kind))
}
