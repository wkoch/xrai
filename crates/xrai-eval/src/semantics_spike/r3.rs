//! Opt-in ADR025 R3. Parses captured bytes only; no host cfg or upstream execution.
use super::*;
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Binding {
    pub name: String,
    pub kind: String,
    pub scope_local_id: usize,
    pub parent_scope_local_id: Option<usize>,
    pub visible_start: usize,
    pub visible_end: usize,
    pub evidence: Evidence,
    pub initializer: Option<Evidence>,
    pub function_path: Option<String>,
}
#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Condition {
    pub predicate: String,
    pub state: String,
    pub inputs: Vec<String>,
    pub evidence: Evidence,
}
impl Snapshot {
    /// Occurrence-aware lookup. A local name does not by itself prove a function call target.
    pub fn resolve_at(
        &self,
        module: &str,
        path: &str,
        namespace: &str,
        file: &str,
        offset: usize,
    ) -> Resolution {
        let dep = format!(
            "{}:{}:{}:{file}:{offset}:{namespace}:{path}:{}",
            self.snapshot_id, self.configuration_id, self.producer_fingerprint, self.input.rules
        );
        if !self
            .input
            .files
            .get(file)
            .is_some_and(|s| offset < s.len() && s.is_char_boundary(offset))
        {
            return unknown("occurrence_outside_capture", vec![dep]);
        }
        if self.input.rules != RULES_R3 {
            return self.resolve(module, path, namespace);
        }
        if self
            .scopes
            .iter()
            .filter(|s| {
                s.evidence.path == file && s.evidence.start <= offset && offset < s.evidence.end
            })
            .max_by_key(|s| s.local_id)
            .is_some_and(|s| s.module_owner != module)
        {
            return unknown("module_occurrence_mismatch", vec![dep]);
        }
        if let Some(reference) = self.references.iter().find(|r| {
            r.evidence.path == file
                && r.evidence.start == offset
                && r.path == path
                && r.namespace == namespace
                && r.resolution.reason == "binding_receiver_or_macro_not_demonstrated"
        }) {
            return reference.resolution.clone();
        }
        let occurrence = self
            .references
            .iter()
            .find(|r| {
                r.evidence.path == file
                    && r.evidence.start == offset
                    && r.path == path
                    && r.namespace == namespace
            })
            .map(|r| r.evidence.clone())
            .or_else(|| {
                self.declarations
                    .iter()
                    .find(|d| {
                        d.evidence.path == file
                            && d.evidence.start == offset
                            && d.name == path
                            && d.namespace == namespace
                    })
                    .map(|d| d.evidence.clone())
            });
        let Some(occurrence) = occurrence else {
            return unknown("occurrence_not_demonstrated", vec![dep]);
        };
        // Unsupported lexical introductions are bounded by exact function/block evidence.
        if let Some(gap) = self.gaps.iter().find(|g| {
            g.reason == "r3_lexical_form_not_supported"
                && g.evidence
                    .as_ref()
                    .is_some_and(|e| e.path == file && e.start <= offset && offset < e.end)
        }) {
            let mut result = unknown(&gap.reason, vec![dep]);
            result.evidence.extend(gap.evidence.clone());
            result.evidence.insert(0, occurrence);
            return result;
        }
        if namespace == "value"
            && !path.contains("::")
            && let Some(binding) = self
                .bindings
                .iter()
                .filter(|b| {
                    b.name == path
                        && b.evidence.path == file
                        && b.visible_start <= offset
                        && offset < b.visible_end
                })
                .max_by_key(|b| (b.scope_local_id, b.visible_start))
        {
            let mut result = if let Some(target) = &binding.function_path {
                let r = self.resolve(module, target, namespace);
                // Only a demonstrated function item, never a callable parameter or constructor.
                if r.target_id
                    .as_ref()
                    .and_then(|id| self.declarations.iter().find(|d| &d.id == id))
                    .is_some_and(|d| d.kind == "function_item")
                {
                    r
                } else {
                    unknown("local_callable_target_not_demonstrated", vec![dep.clone()])
                }
            } else {
                unknown("local_callable_target_not_demonstrated", vec![dep.clone()])
            };
            result.dependencies.push(dep);
            result.evidence.insert(0, binding.evidence.clone());
            if let Some(e) = &binding.initializer {
                result.evidence.insert(1, e.clone());
            }
            result.evidence.insert(0, occurrence);
            return result;
        }
        let mut result = self.resolve(module, path, namespace);
        result.dependencies.push(dep);
        result.evidence.insert(0, occurrence);
        result
    }
}
/// Validate every supported predicate before three-valued evaluation.
/// Err is unsupported syntax; Ok(None) is valid syntax with unknown configuration.
fn evaluate(
    input: &str,
    config: &BTreeMap<String, String>,
    used: &mut BTreeSet<String>,
) -> Result<Option<bool>, ()> {
    let input = input.trim();
    if let Some((op, rest)) = input.split_once('(') {
        let body = rest.strip_suffix(')').ok_or(())?;
        let mut parts = vec![];
        let mut depth = 0usize;
        let mut start = 0;
        let mut quoted = false;
        for (i, ch) in body.char_indices() {
            match ch {
                '"' => quoted = !quoted,
                '(' if !quoted => depth += 1,
                ')' if !quoted => depth = depth.checked_sub(1).ok_or(())?,
                ',' if !quoted && depth == 0 => {
                    parts.push(body[start..i].trim());
                    start = i + 1;
                }
                _ => {}
            }
        }
        if quoted || depth != 0 {
            return Err(());
        }
        if !body[start..].trim().is_empty() {
            parts.push(body[start..].trim());
        }
        let values: Vec<_> = parts
            .iter()
            .map(|p| evaluate(p, config, used))
            .collect::<Result<_, _>>()?;
        match op.trim() {
            "not" if values.len() == 1 => Ok(values[0].map(|v| !v)),
            "all" => {
                if values.contains(&Some(false)) {
                    Ok(Some(false))
                } else if values.iter().all(|v| *v == Some(true)) {
                    Ok(Some(true))
                } else {
                    Ok(None)
                }
            }
            "any" => {
                if values.contains(&Some(true)) {
                    Ok(Some(true))
                } else if values.iter().all(|v| *v == Some(false)) {
                    Ok(Some(false))
                } else {
                    Ok(None)
                }
            }
            _ => Err(()),
        }
    } else {
        let (key, family) = if let Some((key, value)) = input.split_once('=') {
            let key = key.trim();
            let value = value.trim();
            if value.len() < 2
                || !(value.starts_with('"') && value.ends_with('"'))
                || value.contains('\\')
                || value[1..value.len() - 1].contains('"')
            {
                return Err(());
            }
            (
                format!("{key}:{}", &value[1..value.len() - 1]),
                key.to_string(),
            )
        } else {
            (input.to_string(), input.to_string())
        };
        if !family
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '_')
            || !family
                .chars()
                .next()
                .is_some_and(|c| c.is_ascii_alphabetic() || c == '_')
        {
            return Err(());
        }
        used.insert(key.clone());
        Ok(match config.get(&key).map(String::as_str) {
            Some("known:true") => Some(true),
            Some("known:false") => Some(false),
            None if config
                .get(&format!("closed:{family}"))
                .is_some_and(|v| v == "true") =>
            {
                used.insert(format!("closed:{family}"));
                Some(false)
            }
            _ => None,
        })
    }
}
pub(super) fn attribute(
    s: &mut Snapshot,
    module: &str,
    file: &str,
    node: Node<'_>,
    source: &str,
) -> Option<bool> {
    let t = text(node, source);
    let body = t.strip_prefix("#[cfg(")?.strip_suffix(")]")?;
    let mut used = BTreeSet::new();
    let result = evaluate(body, &s.input.configuration, &mut used)
        .ok()
        .flatten();
    let evidence = s.evidence(file, node.start_byte(), node.end_byte());
    s.conditions.push(Condition {
        predicate: body.into(),
        state: match result {
            Some(true) => "known_true",
            Some(false) => "known_false",
            None => "not_evaluated",
        }
        .into(),
        inputs: used.into_iter().collect(),
        evidence: evidence.clone(),
    });
    if result.is_none() {
        s.gap(module, "configuration_not_evaluated", Some(evidence));
    }
    Some(result != Some(false))
}
fn simple_pattern(node: Node<'_>, source: &str) -> Option<String> {
    let value = text(node, source).trim().trim_start_matches("mut ").trim();
    if value != "_"
        && !value.is_empty()
        && value
            .chars()
            .enumerate()
            .all(|(i, c)| c == '_' || c.is_alphabetic() || (i > 0 && c.is_numeric()))
    {
        Some(value.into())
    } else {
        None
    }
}
fn unsupported(node: Node<'_>) -> bool {
    if [
        "closure_expression",
        "for_expression",
        "match_expression",
        "let_condition",
        "function_item",
        "use_declaration",
        "macro_invocation",
        "struct_item",
        "enum_item",
        "mod_item",
        "impl_item",
        "trait_item",
        "type_item",
        "const_item",
        "static_item",
        "attribute_item",
    ]
    .contains(&node.kind())
    {
        return true;
    }
    if node.kind() == "let_declaration"
        && node
            .child_by_field_name("pattern")
            .is_none_or(|p| !["identifier", "mut_pattern"].contains(&p.kind()))
    {
        return true;
    }
    children(node).into_iter().any(unsupported)
}
pub(super) fn extract(
    s: &mut Snapshot,
    module: &str,
    file: &str,
    function: Node<'_>,
    source: &str,
) {
    let Some(body) = function.child_by_field_name("body") else {
        return;
    };
    let id = s.scopes.len();
    s.scopes.push(Scope {
        local_id: id,
        kind: "function".into(),
        module_owner: module.into(),
        parent_scope_local_id: None,
        evidence: s.evidence(file, function.start_byte(), function.end_byte()),
    });
    let mut env = BTreeMap::new();
    let mut bad = false;
    if let Some(params) = function.child_by_field_name("parameters") {
        for p in children(params) {
            if p.kind() == "parameter" {
                if let Some(pattern) = p.child_by_field_name("pattern") {
                    if let Some(name) = simple_pattern(pattern, source) {
                        let b = Binding {
                            name: name.clone(),
                            kind: "parameter".into(),
                            scope_local_id: id,
                            parent_scope_local_id: None,
                            visible_start: body.start_byte(),
                            visible_end: body.end_byte(),
                            evidence: s.evidence(file, pattern.start_byte(), pattern.end_byte()),
                            initializer: None,
                            function_path: None,
                        };
                        env.insert(name, b.clone());
                        s.bindings.push(b);
                    } else {
                        bad = true;
                    }
                }
            } else if p.kind() == "self_parameter" {
                bad = true;
            }
        }
    }
    if bad
        || function
            .child_by_field_name("type_parameters")
            .is_some_and(|n| contains_kind(n, "const_parameter"))
        || unsupported(body)
    {
        s.gap(
            module,
            "r3_lexical_form_not_supported",
            Some(s.evidence(file, body.start_byte(), body.end_byte())),
        );
    }
    walk(s, module, file, body, source, id, &env);
}
fn walk(
    s: &mut Snapshot,
    module: &str,
    file: &str,
    node: Node<'_>,
    source: &str,
    parent: usize,
    inherited: &BTreeMap<String, Binding>,
) {
    let mut env = inherited.clone();
    let mut scope = parent;
    if node.kind() == "block" {
        scope = s.scopes.len();
        s.scopes.push(Scope {
            local_id: scope,
            kind: "block".into(),
            module_owner: module.into(),
            parent_scope_local_id: Some(parent),
            evidence: s.evidence(file, node.start_byte(), node.end_byte()),
        });
    }
    if node.kind() == "call_expression"
        && let Some(callee) = node.child_by_field_name("function")
    {
        let evidence = s.evidence(file, callee.start_byte(), callee.end_byte());
        let mut resolution = unknown(
            if ["identifier", "scoped_identifier"].contains(&callee.kind()) {
                "pending"
            } else {
                "binding_receiver_or_macro_not_demonstrated"
            },
            vec![format!(
                "{}:{}:{}:{}",
                s.snapshot_id, s.configuration_id, scope, s.producer_fingerprint
            )],
        );
        resolution.evidence.push(evidence.clone());
        s.references.push(Reference {
            occurrence_id: format!(
                "occ_{}",
                hash(
                    format!(
                        "{}:{file}:{}:{}",
                        s.snapshot_id,
                        callee.start_byte(),
                        callee.end_byte()
                    )
                    .as_bytes()
                )
            ),
            scope_local_id: scope,
            module: module.into(),
            path: text(callee, source).into(),
            namespace: "value".into(),
            role: "callsite".into(),
            evidence,
            resolution,
        });
    }
    for child in children(node) {
        if child.kind() == "let_declaration" {
            // Initializer executes in the pre-binding environment and temporal range.
            if let Some(value) = child.child_by_field_name("value") {
                walk(s, module, file, value, source, scope, &env);
            }
            if let Some(pattern) = child.child_by_field_name("pattern")
                && let Some(name) = simple_pattern(pattern, source)
            {
                let initializer = child.child_by_field_name("value");
                let function_path = initializer
                    .filter(|v| ["identifier", "scoped_identifier"].contains(&v.kind()))
                    .and_then(|v| {
                        let p = text(v, source);
                        if contains_kind(child, "mutable_specifier") || env.contains_key(p) {
                            None
                        } else {
                            Some(p.into())
                        }
                    });
                let b = Binding {
                    name: name.clone(),
                    kind: "let".into(),
                    scope_local_id: scope,
                    parent_scope_local_id: s.scopes[scope].parent_scope_local_id,
                    visible_start: child.end_byte(),
                    visible_end: node.end_byte(),
                    evidence: s.evidence(file, pattern.start_byte(), pattern.end_byte()),
                    initializer: initializer
                        .map(|v| s.evidence(file, v.start_byte(), v.end_byte())),
                    function_path,
                };
                s.bindings.push(b.clone());
                env.insert(name, b);
            }
        } else {
            walk(s, module, file, child, source, scope, &env);
        }
    }
}
