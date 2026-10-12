use std::collections::BTreeMap;
use xrai_eval::semantics_spike::{Index, Input, RULES, build};
fn input(source: &str) -> Input {
    Input {
        files: BTreeMap::from([("src/lib.rs".into(), source.into())]),
        root: "src/lib.rs".into(),
        edition: "2021".into(),
        configuration: BTreeMap::new(),
        rules: RULES.into(),
    }
}
#[test]
fn negative_export_then_module_create_and_remove_are_full_rebuilds() {
    let a = input("mod a; use a::target as entry;");
    let mut index = Index::new(a.clone()).unwrap();
    let old = index.current.snapshot_id.clone();
    let absent = index.current.resolve("", "entry", "value");
    assert_eq!(absent.state, "unknown");
    assert!(!absent.dependencies.is_empty());
    let mut b = a.clone();
    b.files
        .insert("src/a.rs".into(), "pub fn target() {}".into());
    assert_eq!(index.update(b.clone()).unwrap(), &build(b.clone()).unwrap());
    let result = index.current.resolve("", "entry", "value");
    assert_eq!(result.state, "resolved");
    assert_ne!(old, index.current.snapshot_id);
    assert!(
        result
            .evidence
            .iter()
            .all(|e| e.snapshot_id == index.current.snapshot_id)
    );
    assert_eq!(index.update(a.clone()).unwrap(), &build(a).unwrap());
    assert_eq!(index.current.resolve("", "entry", "value").state, "unknown");
}
#[test]
fn config_rules_path_rename_and_shadow_updates_compare_every_field() {
    let a = input("fn f() {}");
    let mut index = Index::new(a.clone()).unwrap();
    let mut changes = vec![];
    let mut b = a.clone();
    b.configuration
        .insert("feature:x".into(), "known:true".into());
    changes.push(b);
    let mut b = a.clone();
    b.edition = "2024".into();
    changes.push(b);
    let mut b = a.clone();
    b.rules = "new-query-fingerprint".into();
    changes.push(b);
    let mut b = a.clone();
    b.files = BTreeMap::from([("src/main.rs".into(), "fn f() {}".into())]);
    b.root = "src/main.rs".into();
    changes.push(b);
    let mut b = a.clone();
    b.files.insert(
        "src/lib.rs".into(),
        "fn f() {} fn run() { let f = || {}; f(); }".into(),
    );
    changes.push(b);
    for b in changes {
        assert_eq!(index.update(b.clone()).unwrap(), &build(b).unwrap());
    }
    assert_eq!(index.current.references[0].resolution.state, "unknown");
}
#[test]
fn references_are_calls_with_evidence_not_textual_name_matches() {
    let snapshot = build(input("fn target() {} fn run() { target(); } ")).unwrap();
    assert_eq!(snapshot.references.len(), 1);
    let r = &snapshot.references[0];
    assert_eq!(r.role, "callsite");
    assert_eq!(r.resolution.state, "resolved");
    assert_eq!(
        &snapshot.input.files[&r.evidence.path][r.evidence.start..r.evidence.end],
        "target"
    );
}
#[test]
fn local_bindings_parameters_macros_and_methods_do_not_promote_calls() {
    for src in [
        "fn f() {} fn run(f: fn()) { f(); }",
        "fn f() {} fn run() { let f=||{}; f(); }",
        "fn f() {} fn run() { unknown!(); f(); }",
        "fn f() {} fn run() { object.f(); }",
    ] {
        let snapshot = build(input(src)).unwrap();
        assert!(!snapshot.references.is_empty());
        assert!(
            snapshot
                .references
                .iter()
                .all(|r| r.resolution.state == "unknown")
        );
    }
}
#[test]
fn macro_namespace_and_constructor_namespace_never_fuse() {
    let snapshot = build(input("struct Named { x: u8 } struct Unit; fn f() {}")).unwrap();
    assert_eq!(snapshot.resolve("", "Named", "type").state, "resolved");
    assert_eq!(snapshot.resolve("", "Named", "value").state, "unknown");
    assert_eq!(snapshot.resolve("", "Unit", "value").state, "resolved");
    assert_eq!(snapshot.resolve("", "f", "macro").state, "unknown");
}
#[test]
fn reexports_have_each_import_and_destination_in_evidence() {
    let snapshot = build(input(
        "mod a { pub fn f() {} } mod b {pub use crate::a::f as g;} use b::g as entry;",
    ))
    .unwrap();
    let result = snapshot.resolve("", "entry", "value");
    assert_eq!(result.state, "resolved");
    assert!(result.evidence.len() >= 4);
    assert!(result.dependencies.len() >= 3);
    assert!(result.evidence.iter().all(|e| {
        e.source_hash
            == blake3::hash(snapshot.input.files[&e.path].as_bytes())
                .to_hex()
                .as_str()
    }));
}
#[test]
fn unicode_crlf_empty_and_path_validation() {
    let snapshot = build(input("// café\r\nfn ação() {}\r\n")).unwrap();
    let r = snapshot.resolve("", "ação", "value");
    let e = r.evidence.last().unwrap();
    assert_eq!(&snapshot.input.files[&e.path][e.start..e.end], "ação");
    assert!(build(input("")).unwrap().declarations.is_empty());
    let mut bad = input("");
    bad.files.insert("../outside.rs".into(), "".into());
    assert!(build(bad).is_err());
}
#[test]
fn pre_registered_matrix_and_real_sample_are_verified() {
    for matrix in [
        "eval/semantics/rust-r1-r2.json",
        "eval/semantics/tokio-development.json",
        "eval/semantics/rust-counterproofs.json",
    ] {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let output = std::process::Command::new(env!("CARGO_BIN_EXE_semantics-spike"))
            .arg(root.join(matrix))
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{matrix}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        let v: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
        assert_eq!(v["false_promotions"], 0);
        assert_eq!(v["cases"], v["correct"]);
    }
}

#[test]
fn safe_attribute_identifier_does_not_allow_qualified_procedural_path() {
    let snapshot = build(input("#[inline::generated] fn f() {}")).unwrap();
    assert_eq!(snapshot.resolve("", "f", "value").state, "unknown");
}

#[test]
fn duplicate_module_does_not_publish_unique_function_from_invalid_environment() {
    let snapshot = build(input("mod a { pub fn f() {} } mod a { pub fn g() {} }")).unwrap();
    assert_eq!(snapshot.resolve("", "a::f", "value").state, "unknown");
}

#[test]
fn r3_preregistered_bindings_cfg_real_modules_and_full_update_events() {
    for matrix in [
        "eval/semantics/r3/rust-r3.json",
        "eval/semantics/r3/counterproofs-r3.json",
        "eval/semantics/r3/counterproofs-extra.json",
        "eval/semantics/r3/counterproofs-cfg.json",
        "eval/semantics/r3/tokio-test-development.json",
        "eval/semantics/r3/incremental-events.json",
    ] {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let output = std::process::Command::new(env!("CARGO_BIN_EXE_semantics-spike"))
            .arg(root.join(matrix))
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{matrix}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        let v: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
        assert_eq!(v["false_promotions"], 0);
        assert_eq!(v["cases"], v["correct"]);
        if let Some(events) = v["events"].as_array() {
            assert_eq!(events.len(), 2);
            for event in events {
                assert_eq!(event["incremental"], event["rebuild"]);
            }
        }
    }
}

#[test]
fn r3_shadow_introduction_and_removal_match_entire_rebuild() {
    use xrai_eval::semantics_spike::RULES_R3;
    let mut a = input("fn target() {} fn run() { target(); }");
    a.rules = RULES_R3.into();
    let mut index = Index::new(a.clone()).unwrap();
    assert_eq!(index.current.references[0].resolution.state, "resolved");
    let mut b = a.clone();
    b.files.insert(
        "src/lib.rs".into(),
        "fn target() {} fn run() { let target=1; target(); }".into(),
    );
    assert_eq!(index.update(b.clone()).unwrap(), &build(b).unwrap());
    assert_eq!(index.current.references[0].resolution.state, "unknown");
    assert_eq!(index.update(a.clone()).unwrap(), &build(a).unwrap());
    assert_eq!(index.current.references[0].resolution.state, "resolved");
}

#[test]
fn r3_cfg_does_not_inherit_host_or_treat_unknown_as_false() {
    use xrai_eval::semantics_spike::RULES_R3;
    let mut a = input("#[cfg(unix)] fn target() {} fn run() { target(); }");
    a.rules = RULES_R3.into();
    let s = build(a.clone()).unwrap();
    assert_eq!(s.conditions[0].state, "not_evaluated");
    assert_eq!(s.references[0].resolution.state, "unknown");
    a.configuration.insert("unix".into(), "known:false".into());
    let s = build(a).unwrap();
    assert_eq!(s.conditions[0].state, "known_false");
    assert!(s.declarations.iter().all(|d| d.name != "target"));
    assert_eq!(s.references[0].resolution.state, "unknown");
}
