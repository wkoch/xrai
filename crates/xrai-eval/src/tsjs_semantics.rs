//! Experimental exact-captured ESM lexical lookup. This is not Node/tsc resolution.
//! Callable targets are deliberately unknown: binding identity is not runtime flow.
use crate::{parsing_spike, worker_spike};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use tree_sitter::{Node, Parser};

type Result<T> = std::result::Result<T, String>;
const PROFILE: &str = "captured-relative-exact-v1";
const RESOLVER: &str = "xrai-tsjs-lexical-v1";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Source {
    pub dialect: String,
    pub source: String,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Input {
    pub profile: String,
    pub configuration: BTreeMap<String, String>,
    pub files: BTreeMap<String, Source>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Evidence {
    pub snapshot_id: String,
    pub file_id: String,
    pub path: String,
    pub source_hash: String,
    pub start: usize,
    pub end: usize,
    pub role: String,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Scope {
    pub id: usize,
    pub parent: Option<usize>,
    pub path: String,
    pub start: usize,
    pub end: usize,
    pub function_depth: usize,
    pub kind: String,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Binding {
    pub id: String,
    pub name: String,
    pub path: String,
    pub scope: usize,
    pub kind: String,
    pub initialized_at: usize,
    pub evidence: Evidence,
    pub imported_name: Option<String>,
    pub source_specifier: Option<String>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Export {
    pub path: String,
    pub name: String,
    pub local: String,
    pub evidence: Evidence,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Gap {
    pub scope: usize,
    pub name: Option<String>,
    pub reason: String,
    pub evidence: Evidence,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Resolution {
    pub state: String,
    pub target: Option<String>,
    pub binding_id: Option<String>,
    pub evidence: Vec<Evidence>,
    pub dependencies: Vec<String>,
    pub diagnostic: String,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Reference {
    pub name: String,
    pub scope: usize,
    pub evidence: Evidence,
    pub resolution: Resolution,
    pub callable: Resolution,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Snapshot {
    pub schema_version: String,
    pub snapshot_id: String,
    pub producer_fingerprint: String,
    pub producer_components: BTreeMap<String, String>,
    pub input: Input,
    pub scopes: Vec<Scope>,
    pub bindings: Vec<Binding>,
    pub exports: Vec<Export>,
    pub gaps: Vec<Gap>,
    pub references: Vec<Reference>,
    pub coverage: BTreeMap<String, String>,
}
struct Builder<'a> {
    snapshot: &'a mut Snapshot,
    path: &'a str,
    source: &'a str,
    excluded: BTreeSet<(usize, usize)>,
    occurrences: Vec<(String, usize, Evidence)>,
}
fn hash(bytes: &[u8]) -> String {
    blake3::hash(bytes).to_hex().to_string()
}
fn text<'a>(node: Node<'_>, source: &'a str) -> &'a str {
    &source[node.start_byte()..node.end_byte()]
}
fn children(node: Node<'_>) -> Vec<Node<'_>> {
    let mut cursor = node.walk();
    node.named_children(&mut cursor).collect()
}
fn valid_path(path: &str) -> bool {
    !path.is_empty()
        && !path.starts_with('/')
        && !path.contains(['\\', '\0', '?', '#'])
        && path.split('/').all(|part| !matches!(part, "" | "." | ".."))
}
fn import_path(path: &str, specifier: &str) -> Option<String> {
    if !(specifier.starts_with("./") || specifier.starts_with("../"))
        || specifier.contains(['\\', '\0', '?', '#', ':'])
        || !(specifier.ends_with(".js") || specifier.ends_with(".ts"))
    {
        return None;
    }
    let mut parts: Vec<&str> = path.split('/').collect();
    parts.pop();
    for part in specifier.split('/') {
        match part {
            "." => (),
            ".." => {
                parts.pop()?;
            }
            "" => return None,
            _ => parts.push(part),
        }
    }
    let result = parts.join("/");
    valid_path(&result).then_some(result)
}
impl Builder<'_> {
    fn evidence(&self, node: Node<'_>, role: &str) -> Evidence {
        Evidence {
            snapshot_id: self.snapshot.snapshot_id.clone(),
            file_id: format!("fi_{}", hash(self.path.as_bytes())),
            path: self.path.to_string(),
            source_hash: hash(self.source.as_bytes()),
            start: node.start_byte(),
            end: node.end_byte(),
            role: role.to_string(),
        }
    }
    fn exclude_tree(&mut self, node: Node<'_>) {
        if node.kind() == "identifier" {
            self.excluded.insert((node.start_byte(), node.end_byte()));
        }
        for child in children(node) {
            self.exclude_tree(child);
        }
    }
    fn scope(&mut self, node: Node<'_>, parent: Option<usize>, kind: &str) -> usize {
        let depth = parent.map_or(0, |p| self.snapshot.scopes[p].function_depth)
            + usize::from(kind == "function");
        let id = self.snapshot.scopes.len();
        self.snapshot.scopes.push(Scope {
            id,
            parent,
            path: self.path.to_string(),
            start: node.start_byte(),
            end: node.end_byte(),
            function_depth: depth,
            kind: kind.to_string(),
        });
        id
    }
    fn function_scope(&self, mut scope: usize) -> usize {
        loop {
            let s = &self.snapshot.scopes[scope];
            if s.kind == "function" || s.parent.is_none() {
                return scope;
            }
            scope = s.parent.expect("parent checked");
        }
    }
    fn gap(&mut self, node: Node<'_>, scope: usize, name: Option<String>, reason: &str) {
        self.snapshot.gaps.push(Gap {
            scope,
            name,
            reason: reason.to_string(),
            evidence: self.evidence(node, "gap"),
        });
    }
    fn binding(&mut self, node: Node<'_>, scope: usize, kind: &str, initialized: usize) {
        self.excluded.insert((node.start_byte(), node.end_byte()));
        let name = text(node, self.source).to_string();
        self.snapshot.bindings.push(Binding {
            id: format!("{}:{}@{}", self.path, name, node.start_byte()),
            name,
            path: self.path.to_string(),
            scope,
            kind: kind.to_string(),
            initialized_at: initialized,
            evidence: self.evidence(node, "declaration"),
            imported_name: None,
            source_specifier: None,
        });
    }
    fn imports(&mut self, node: Node<'_>, scope: usize) {
        self.exclude_tree(node);
        let specifier = node.child_by_field_name("source").map(|s| {
            let value = text(s, self.source);
            value[1..value.len().saturating_sub(1)].to_string()
        });
        let typed = text(node, self.source).starts_with("import type ");
        for clause in children(node) {
            if clause.kind() != "import_clause" {
                continue;
            }
            for item in children(clause) {
                if item.kind() == "named_imports" {
                    for named in children(item) {
                        if named.kind() != "import_specifier" {
                            continue;
                        }
                        let Some(name) = named.child_by_field_name("name") else {
                            continue;
                        };
                        let alias = named.child_by_field_name("alias").unwrap_or(name);
                        let supported = !typed
                            && !text(named, self.source).starts_with("type ")
                            && name.kind() == "identifier"
                            && text(name, self.source) != "default"
                            && alias.kind() == "identifier";
                        self.binding(
                            alias,
                            scope,
                            if supported { "import" } else { "unsupported" },
                            0,
                        );
                        let b = self.snapshot.bindings.last_mut().expect("binding inserted");
                        b.evidence.role = "import".to_string();
                        b.evidence.start = node.start_byte();
                        b.evidence.end = node.end_byte();
                        b.imported_name = Some(text(name, self.source).to_string());
                        b.source_specifier = specifier.clone();
                    }
                } else {
                    self.unsupported_names(item, scope, "unsupported_import");
                }
            }
        }
    }
    fn unsupported_names(&mut self, node: Node<'_>, scope: usize, reason: &str) {
        if node.kind() == "identifier" {
            self.binding(node, scope, "unsupported", 0);
            self.gap(
                node,
                scope,
                Some(text(node, self.source).to_string()),
                reason,
            );
        } else {
            for c in children(node) {
                self.unsupported_names(c, scope, reason);
            }
        }
    }
    fn exports(&mut self, node: Node<'_>, scope: usize) {
        if node.child_by_field_name("source").is_some() {
            self.gap(node, scope, None, "reexport_not_supported");
            self.exclude_tree(node);
            return;
        }
        let default = text(node, self.source).starts_with("export default");
        if text(node, self.source).starts_with("export type ") {
            self.gap(node, scope, None, "type_only_export_not_value_environment");
            self.exclude_tree(node);
            return;
        }
        if let Some(decl) = node.child_by_field_name("declaration")
            && decl.kind() == "function_declaration"
            && !default
            && let Some(name) = decl.child_by_field_name("name")
        {
            self.snapshot.exports.push(Export {
                path: self.path.to_string(),
                name: text(name, self.source).to_string(),
                local: text(name, self.source).to_string(),
                evidence: self.evidence(node, "export"),
            });
        }
        for c in children(node) {
            if c.kind() == "export_clause" {
                self.exclude_tree(c);
                for spec in children(c) {
                    if let Some(local) = spec.child_by_field_name("name") {
                        let alias = spec.child_by_field_name("alias").unwrap_or(local);
                        if local.kind() == "identifier" && alias.kind() == "identifier" {
                            self.snapshot.exports.push(Export {
                                path: self.path.to_string(),
                                name: text(alias, self.source).to_string(),
                                local: text(local, self.source).to_string(),
                                evidence: self.evidence(spec, "export"),
                            });
                        } else {
                            self.gap(spec, scope, None, "unsupported_export");
                        }
                    }
                }
            } else {
                self.visit(c, scope);
            }
        }
    }
    fn visit(&mut self, node: Node<'_>, mut scope: usize) {
        match node.kind() {
            "import_statement" => {
                self.imports(node, scope);
                return;
            }
            "export_statement" => {
                self.exports(node, scope);
                return;
            }
            "function_declaration"
            | "function_expression"
            | "generator_function_declaration"
            | "generator_function"
            | "arrow_function"
            | "method_definition" => {
                if let Some(name) = node.child_by_field_name("name") {
                    if node.kind() == "function_declaration" && name.kind() == "identifier" {
                        self.binding(name, scope, "function", 0);
                    } else {
                        self.exclude_tree(name);
                        if node.kind() == "generator_function_declaration"
                            && name.kind() == "identifier"
                        {
                            self.binding(name, scope, "unsupported", 0);
                            self.gap(
                                name,
                                scope,
                                Some(text(name, self.source).to_string()),
                                "unsupported_generator_binding",
                            );
                        }
                    }
                }
                scope = self.scope(node, Some(scope), "function");
                if let Some(params) = node.child_by_field_name("parameters") {
                    for p in children(params) {
                        let simple = if p.kind() == "identifier" {
                            Some(p)
                        } else if p.kind() == "required_parameter"
                            && p.child_by_field_name("value").is_none()
                        {
                            p.child_by_field_name("pattern")
                                .filter(|n| n.kind() == "identifier")
                        } else {
                            None
                        };
                        if let Some(id) = simple {
                            self.binding(id, scope, "parameter", 0);
                        } else {
                            self.gap(p, scope, None, "unsupported_parameters");
                        }
                        self.exclude_tree(p);
                    }
                } else if let Some(p) = node.child_by_field_name("parameter") {
                    if p.kind() == "identifier" {
                        self.binding(p, scope, "parameter", 0);
                    } else {
                        self.gap(p, scope, None, "unsupported_parameter");
                    }
                    self.exclude_tree(p);
                }
                if let Some(body) = node.child_by_field_name("body") {
                    self.visit(body, scope);
                }
                return;
            }
            "statement_block" | "for_statement" | "for_in_statement" | "switch_body" => {
                scope = self.scope(node, Some(scope), "block");
            }
            "variable_declarator" => {
                if let Some(name) = node.child_by_field_name("name") {
                    let parent = node.parent().expect("declarator has parent");
                    let var = parent.kind() == "variable_declaration";
                    let constant = text(parent, self.source).starts_with("const ");
                    let binding_scope = if var {
                        self.function_scope(scope)
                    } else {
                        scope
                    };
                    if name.kind() == "identifier" {
                        let initialized = node
                            .child_by_field_name("value")
                            .map_or(usize::MAX, |v| v.end_byte());
                        self.binding(
                            name,
                            binding_scope,
                            if constant { "const" } else { "unsupported" },
                            initialized,
                        );
                        if !constant {
                            self.gap(
                                name,
                                binding_scope,
                                Some(text(name, self.source).to_string()),
                                "unsupported_mutable_binding",
                            );
                        }
                    } else {
                        self.exclude_tree(name);
                        self.gap(
                            name,
                            binding_scope,
                            None,
                            "destructuring_environment_unknown",
                        );
                    }
                    if let Some(value) = node.child_by_field_name("value") {
                        self.visit(value, scope);
                    }
                }
                return;
            }
            "with_statement" => {
                self.gap(
                    node,
                    self.function_scope(scope),
                    None,
                    "with_environment_unknown",
                );
            }
            "catch_clause" => {
                self.gap(
                    node,
                    self.function_scope(scope),
                    None,
                    "catch_binding_unknown",
                );
            }
            "function_signature"
            | "import_alias"
            | "class_declaration"
            | "class"
            | "enum_declaration"
            | "internal_module"
            | "module"
            | "type_alias_declaration"
            | "interface_declaration"
            | "ambient_declaration" => {
                self.gap(node, scope, None, "unsupported_declaration_environment");
                self.exclude_tree(node);
                return;
            }
            "call_expression" => {
                if node
                    .child_by_field_name("function")
                    .is_some_and(|f| text(f, self.source) == "eval")
                {
                    self.gap(
                        node,
                        self.function_scope(scope),
                        None,
                        "eval_environment_unknown",
                    );
                }
            }
            "identifier" => {
                self.occurrences.push((
                    text(node, self.source).to_string(),
                    scope,
                    self.evidence(node, "reference"),
                ));
            }
            _ => (),
        }
        for c in children(node) {
            self.visit(c, scope);
        }
    }
}
impl Snapshot {
    fn unknown(&self, evidence: Evidence, diagnostic: &str) -> Resolution {
        Resolution {
            state: "unknown".to_string(),
            target: None,
            binding_id: None,
            evidence: vec![evidence],
            dependencies: vec![self.snapshot_id.clone(), self.producer_fingerprint.clone()],
            diagnostic: diagnostic.to_string(),
        }
    }
    fn resolve(&self, name: &str, mut scope: usize, evidence: &Evidence) -> Resolution {
        let depth = self.scopes[scope].function_depth;
        let mut ancestor = Some(scope);
        while let Some(id) = ancestor {
            if self
                .gaps
                .iter()
                .any(|gap| gap.scope == id && gap.name.is_none())
            {
                return self.unknown(evidence.clone(), "ancestor_scope_gap");
            }
            ancestor = self.scopes[id].parent;
        }
        loop {
            if self
                .gaps
                .iter()
                .any(|g| g.scope == scope && g.name.as_deref().is_none_or(|n| n == name))
            {
                return self.unknown(evidence.clone(), "scope_gap");
            }
            let candidates: Vec<&Binding> = self
                .bindings
                .iter()
                .filter(|b| b.scope == scope && b.name == name)
                .collect();
            if !candidates.is_empty() {
                if candidates.len() != 1 {
                    return self.unknown(evidence.clone(), "duplicate_binding");
                }
                let b = candidates[0];
                if b.kind == "unsupported" {
                    return self.unknown(evidence.clone(), "unsupported_binding");
                }
                if b.kind == "const" && evidence.start < b.initialized_at {
                    return self.unknown(evidence.clone(), "before_initialization");
                }
                if self.scopes[scope].function_depth != depth && self.scopes[scope].parent.is_some()
                {
                    return self.unknown(evidence.clone(), "closure_capture_not_analyzed");
                }
                if b.kind == "import" {
                    return self.resolve_import(b, evidence);
                }
                return Resolution {
                    state: "resolved".to_string(),
                    target: Some(format!("{}:{}", b.path, b.name)),
                    binding_id: Some(b.id.clone()),
                    evidence: vec![evidence.clone(), b.evidence.clone()],
                    dependencies: vec![self.snapshot_id.clone(), self.producer_fingerprint.clone()],
                    diagnostic: "lexical_binding_only".to_string(),
                };
            }
            match self.scopes[scope].parent {
                Some(parent) => scope = parent,
                None => return self.unknown(evidence.clone(), "binding_absent"),
            }
        }
    }
    fn resolve_import(&self, b: &Binding, evidence: &Evidence) -> Resolution {
        let Some(path) = b
            .source_specifier
            .as_ref()
            .and_then(|s| import_path(&b.path, s))
        else {
            return self.unknown(evidence.clone(), "specifier_outside_profile");
        };
        if !self.input.files.contains_key(&path) {
            return self.unknown(evidence.clone(), "captured_source_absent");
        }
        let exports: Vec<&Export> = self
            .exports
            .iter()
            .filter(|e| e.path == path && Some(&e.name) == b.imported_name.as_ref())
            .collect();
        if exports.len() != 1 {
            return self.unknown(evidence.clone(), "export_absent_or_duplicate");
        }
        let exported = exports[0];
        let Some(module) = self
            .scopes
            .iter()
            .find(|s| s.path == path && s.parent.is_none())
        else {
            return self.unknown(evidence.clone(), "module_absent");
        };
        if self
            .gaps
            .iter()
            .any(|g| g.scope == module.id && g.name.as_deref().is_none_or(|n| n == exported.local))
        {
            return self.unknown(evidence.clone(), "export_environment_unknown");
        }
        let declarations: Vec<&Binding> = self
            .bindings
            .iter()
            .filter(|d| d.scope == module.id && d.name == exported.local)
            .collect();
        if declarations.len() != 1 || declarations[0].kind != "function" {
            return self.unknown(evidence.clone(), "export_not_unique_local_function");
        }
        let decl = declarations[0];
        Resolution {
            state: "resolved".to_string(),
            target: Some(format!("{}:{}", decl.path, decl.name)),
            binding_id: Some(decl.id.clone()),
            evidence: vec![
                evidence.clone(),
                b.evidence.clone(),
                exported.evidence.clone(),
                decl.evidence.clone(),
            ],
            dependencies: vec![
                self.snapshot_id.clone(),
                self.producer_fingerprint.clone(),
                b.evidence.source_hash.clone(),
                decl.evidence.source_hash.clone(),
            ],
            diagnostic: "exact_captured_esm_lexical_binding_only".to_string(),
        }
    }
    pub fn lookup(&self, path: &str, offset: usize) -> Option<&Reference> {
        self.references
            .iter()
            .find(|r| r.evidence.path == path && r.evidence.start == offset)
    }
}

pub fn build(input: Input) -> Result<Snapshot> {
    if input.profile != PROFILE
        || input.configuration.get("module").map(String::as_str) != Some("esm")
    {
        return Err("explicit ESM captured-relative-exact-v1 profile required".to_string());
    }
    if input.files.is_empty()
        || input.files.len() > 128
        || input.files.values().map(|s| s.source.len()).sum::<usize>() > 8 * 1024 * 1024
    {
        return Err("captured snapshot work limit".to_string());
    }
    let mut producers = BTreeMap::new();
    for (path, source) in &input.files {
        if !valid_path(path)
            || !matches!(source.dialect.as_str(), "javascript" | "typescript")
            || !path.ends_with(if source.dialect == "javascript" {
                ".js"
            } else {
                ".ts"
            })
        {
            return Err(
                "canonical source path and explicit supported dialect required".to_string(),
            );
        }
        producers.insert(
            source.dialect.clone(),
            worker_spike::producer(&source.dialect)?.to_vec(),
        );
    }
    let producer_components = producers
        .iter()
        .map(|(dialect, bytes)| {
            (
                dialect.clone(),
                bytes.iter().map(|b| format!("{b:02x}")).collect(),
            )
        })
        .collect();
    let producer_fingerprint = hash(
        &serde_json::to_vec(&(
            RESOLVER,
            PROFILE,
            producers,
            include_str!("tsjs_semantics.rs"),
        ))
        .map_err(|e| e.to_string())?,
    );
    let snapshot_id =
        hash(&serde_json::to_vec(&(&input, &producer_fingerprint)).map_err(|e| e.to_string())?);
    let mut snapshot = Snapshot {
        schema_version: "xrai.eval.tsjs.snapshot.v1".to_string(),
        snapshot_id,
        producer_fingerprint,
        producer_components,
        input: input.clone(),
        scopes: vec![],
        bindings: vec![],
        exports: vec![],
        gaps: vec![],
        references: vec![],
        coverage: BTreeMap::new(),
    };
    let mut occurrences = vec![];
    for (path, source) in &input.files {
        let mut parser = Parser::new();
        parser
            .set_language(
                &parsing_spike::grammar(&source.dialect)
                    .map_err(|e| e.to_string())?
                    .language,
            )
            .map_err(|e| e.to_string())?;
        let tree = parser
            .parse(&source.source, None)
            .ok_or("parse cancelled")?;
        let root = tree.root_node();
        let mut builder = Builder {
            snapshot: &mut snapshot,
            path,
            source: &source.source,
            excluded: BTreeSet::new(),
            occurrences: vec![],
        };
        let module = builder.scope(root, None, "module");
        if root.has_error() {
            builder.gap(root, module, None, "parse_partial");
        }
        builder.visit(root, module);
        for (name, scope, evidence) in builder.occurrences {
            if !builder.excluded.contains(&(evidence.start, evidence.end)) {
                occurrences.push((name, scope, evidence));
            }
        }
        snapshot.coverage.insert(
            path.clone(),
            if root.has_error() {
                "parse_partial_lookup_unknown"
            } else {
                "experimental_lexical_subset_callables_unknown"
            }
            .to_string(),
        );
    }
    for (name, scope, evidence) in occurrences {
        let resolution = snapshot.resolve(&name, scope, &evidence);
        let callable = snapshot.unknown(
            evidence.clone(),
            "runtime_callable_and_mutation_flow_not_analyzed",
        );
        snapshot.references.push(Reference {
            name,
            scope,
            evidence,
            resolution,
            callable,
        });
    }
    Ok(snapshot)
}
