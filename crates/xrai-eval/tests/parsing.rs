use std::io::Write;
use std::process::{Command, Stdio};
use xrai_eval::parsing_spike::{self, DIALECTS};

#[test]
fn every_embedded_dialect_parses_valid_and_reports_incomplete_sources() {
    for dialect in DIALECTS {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/parsing");
        let valid = std::fs::read(root.join(format!("{dialect}.valid"))).unwrap();
        let parsed = parsing_spike::parse(dialect, &valid).unwrap();
        assert!(parsed.complete, "{dialect}: {}", parsed.tree);
        assert!(parsed.node_count > 3);
        assert!(
            parsed.query_matches > 0,
            "{dialect}: query executed no matches"
        );
        assert!(parsed.diagnostics.is_empty());
        let broken = std::fs::read(root.join(format!("{dialect}.incomplete"))).unwrap();
        let parsed = parsing_spike::parse(dialect, &broken).unwrap();
        assert!(!parsed.complete, "{dialect}");
        assert!(!parsed.diagnostics.is_empty());
        for diagnostic in parsed.diagnostics {
            assert!(diagnostic.start_byte <= diagnostic.end_byte);
            assert!(diagnostic.end_byte <= broken.len());
            assert!(diagnostic.start_line >= 1);
            assert!(diagnostic.end_line >= diagnostic.start_line);
        }
    }
}

#[test]
fn copied_binary_reports_incomplete_exit_status_and_refuses_unknown_dialect() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_parsing-spike"))
        .args(["parse", "python"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(b"def broken(\n")
        .unwrap();
    let output = child.wait_with_output().unwrap();
    assert_eq!(output.status.code(), Some(2));
    let text = String::from_utf8(output.stdout).unwrap();
    assert!(text.contains("\"complete\":false"));
    assert!(text.contains("\"start_byte\":0"));
    assert_eq!(
        Command::new(env!("CARGO_BIN_EXE_parsing-spike"))
            .args(["parse", "unknown"])
            .output()
            .unwrap()
            .status
            .code(),
        Some(1)
    );
}

#[test]
fn fingerprints_cover_distinct_queries_and_grammars() {
    let inventory = parsing_spike::inventory().unwrap();
    assert_eq!(inventory.matches("node_types_blake3").count(), 7);
    assert_eq!(inventory.matches("query_blake3").count(), 7);
    assert_ne!(
        blake3::hash(
            parsing_spike::grammar("typescript")
                .unwrap()
                .node_types
                .as_bytes()
        ),
        blake3::hash(parsing_spike::grammar("tsx").unwrap().node_types.as_bytes())
    );
    assert!(parsing_spike::grammar("ruby").is_err());
}

#[test]
fn incorporated_unicode_notice_is_preserved_in_binary_inventory() {
    let inventory = parsing_spike::inventory().unwrap();
    assert!(inventory.contains("src/unicode/LICENSE"));
    assert!(inventory.contains("COPYRIGHT AND PERMISSION NOTICE (ICU 58 and later)"));
    assert!(
        inventory.contains("registry package declaration; nested component notices also apply")
    );
    let notice = include_str!("../licenses/parsing/tree-sitter-0.27.1-src--unicode--LICENSE");
    assert!(notice.contains("Unicode, Inc."));
    assert!(notice.contains("ICU License - ICU 1.8.1 to ICU 57.1"));
}
