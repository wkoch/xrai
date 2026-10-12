//! M0-05 development experiment: grammars and extraction queries linked into one executable.
use std::error::Error;
use tree_sitter::{Language, Node, Parser, Query, QueryCursor, StreamingIterator};

pub type Result<T> = std::result::Result<T, Box<dyn Error>>;
pub const DIALECTS: [&str; 7] = [
    "rust",
    "javascript",
    "jsx",
    "typescript",
    "tsx",
    "python",
    "go",
];

pub struct Grammar {
    pub language: Language,
    pub version: &'static str,
    pub node_types: &'static str,
    pub query: &'static str,
    pub crate_name: &'static str,
}

pub fn grammar(dialect: &str) -> Result<Grammar> {
    let (language, version, node_types, query, crate_name) = match dialect {
        "rust" => (
            tree_sitter_rust::LANGUAGE.into(),
            "0.24.2",
            tree_sitter_rust::NODE_TYPES,
            include_str!("../queries/rust.scm"),
            "tree-sitter-rust",
        ),
        "javascript" | "jsx" => (
            tree_sitter_javascript::LANGUAGE.into(),
            "0.25.0",
            tree_sitter_javascript::NODE_TYPES,
            include_str!("../queries/javascript.scm"),
            "tree-sitter-javascript",
        ),
        "typescript" => (
            tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into(),
            "0.23.2",
            tree_sitter_typescript::TYPESCRIPT_NODE_TYPES,
            include_str!("../queries/typescript.scm"),
            "tree-sitter-typescript",
        ),
        "tsx" => (
            tree_sitter_typescript::LANGUAGE_TSX.into(),
            "0.23.2",
            tree_sitter_typescript::TSX_NODE_TYPES,
            include_str!("../queries/tsx.scm"),
            "tree-sitter-typescript",
        ),
        "python" => (
            tree_sitter_python::LANGUAGE.into(),
            "0.25.0",
            tree_sitter_python::NODE_TYPES,
            include_str!("../queries/python.scm"),
            "tree-sitter-python",
        ),
        "go" => (
            tree_sitter_go::LANGUAGE.into(),
            "0.25.0",
            tree_sitter_go::NODE_TYPES,
            include_str!("../queries/go.scm"),
            "tree-sitter-go",
        ),
        _ => return Err(format!("unsupported dialect: {dialect}").into()),
    };
    Ok(Grammar {
        language,
        version,
        node_types,
        query,
        crate_name,
    })
}

#[derive(Debug)]
pub struct Diagnostic {
    pub kind: &'static str,
    pub start_byte: usize,
    pub end_byte: usize,
    pub start_line: usize,
    pub start_column_byte: usize,
    pub end_line: usize,
    pub end_column_byte: usize,
}

#[derive(Debug)]
pub struct Parsed {
    pub tree: String,
    pub complete: bool,
    pub diagnostics: Vec<Diagnostic>,
    pub source_bytes: usize,
    pub node_count: usize,
    pub query_matches: usize,
}

fn collect(node: Node<'_>, diagnostics: &mut Vec<Diagnostic>, nodes: &mut usize) {
    *nodes += 1;
    if node.is_error() || node.is_missing() {
        diagnostics.push(Diagnostic {
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
        collect(child, diagnostics, nodes);
    }
}

pub fn parse(dialect: &str, source: &[u8]) -> Result<Parsed> {
    let grammar = grammar(dialect)?;
    // Compile the embedded query too: incompatible query nodes must fail the spike.
    let query = Query::new(&grammar.language, grammar.query)?;
    let mut parser = Parser::new();
    parser.set_language(&grammar.language)?;
    let tree = parser
        .parse(source, None)
        .ok_or("parser returned no tree")?;
    let root = tree.root_node();
    let mut diagnostics = Vec::new();
    let mut node_count = 0;
    collect(root, &mut diagnostics, &mut node_count);
    let mut cursor = QueryCursor::new();
    let mut matches = cursor.matches(&query, root, source);
    let mut query_matches = 0;
    while matches.next().is_some() {
        query_matches += 1;
    }
    Ok(Parsed {
        tree: root.to_sexp(),
        complete: !root.has_error(),
        diagnostics,
        source_bytes: source.len(),
        node_count,
        query_matches,
    })
}

pub fn json_string(value: &str) -> String {
    let mut out = String::from("\"");
    for ch in value.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c < ' ' => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

pub fn inventory() -> Result<String> {
    let mut rows = Vec::new();
    for dialect in DIALECTS {
        let grammar = grammar(dialect)?;
        Query::new(&grammar.language, grammar.query)?;
        rows.push(format!("{{\"dialect\":\"{dialect}\",\"crate\":\"{}\",\"version\":\"{}\",\"license\":\"MIT\",\"grammar_abi\":{},\"node_types_blake3\":\"{}\",\"query_blake3\":\"{}\"}}", grammar.crate_name, grammar.version, grammar.language.abi_version(), blake3::hash(grammar.node_types.as_bytes()), blake3::hash(grammar.query.as_bytes())));
    }
    Ok(format!(
        "{{\"runtime\":\"tree-sitter\",\"version\":\"0.27.1\",\"license\":\"MIT\",\"incorporated_component_notices\":\"Unicode/ICU and nested upstream notices in source_provenance\",\"dialects\":[{}],\"source_provenance\":{}}}",
        rows.join(","),
        include_str!("../parsing-provenance.json")
    ))
}

impl Parsed {
    pub fn json(&self, dialect: &str) -> String {
        let diagnostics: Vec<String> = self.diagnostics.iter().map(|d| format!("{{\"kind\":\"{}\",\"start_byte\":{},\"end_byte\":{},\"start_line\":{},\"start_column_byte\":{},\"end_line\":{},\"end_column_byte\":{}}}",d.kind,d.start_byte,d.end_byte,d.start_line,d.start_column_byte,d.end_line,d.end_column_byte)).collect();
        format!(
            "{{\"dialect\":{},\"complete\":{},\"source_bytes\":{},\"node_count\":{},\"query_matches\":{},\"tree\":{},\"diagnostics\":[{}]}}",
            json_string(dialect),
            self.complete,
            self.source_bytes,
            self.node_count,
            self.query_matches,
            json_string(&self.tree),
            diagnostics.join(",")
        )
    }
}
