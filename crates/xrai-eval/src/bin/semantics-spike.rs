use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use xrai_eval::semantics_spike::{Index, Input, Resolution, Snapshot, build};
#[derive(Deserialize)]
struct Matrix {
    cases: Vec<Case>,
    #[serde(default)]
    events: Vec<Event>,
}
#[derive(Deserialize)]
struct Case {
    id: String,
    files: BTreeMap<String, String>,
    #[serde(default = "root")]
    root: String,
    module: String,
    path: String,
    namespace: String,
    expected_state: String,
    expected_target: Option<String>,
    edition: String,
    configuration: BTreeMap<String, String>,
    rules: String,
    #[serde(default)]
    query_file: Option<String>,
    #[serde(default)]
    query_start: Option<usize>,
}
#[derive(Deserialize)]
struct Event {
    id: String,
    a: Input,
    b: Input,
}
#[derive(Serialize)]
struct EventRow {
    id: String,
    generation_before: u64,
    generation_after: u64,
    before: Snapshot,
    incremental: Snapshot,
    rebuild: Snapshot,
}
fn root() -> String {
    "src/lib.rs".into()
}
#[derive(Serialize)]
struct Row {
    id: String,
    correct: bool,
    expected_state: String,
    expected_target: Option<String>,
    result: Resolution,
    snapshot: Snapshot,
}
#[derive(Serialize)]
struct Output {
    cases: usize,
    resolvable: usize,
    resolvable_correct: usize,
    correct: usize,
    false_promotions: usize,
    rows: Vec<Row>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    events: Vec<EventRow>,
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args()
        .nth(1)
        .ok_or("usage: semantics-spike matrix.json")?;
    let matrix: Matrix = serde_json::from_slice(&std::fs::read(path)?)?;
    let mut output = Output {
        cases: matrix.cases.len(),
        resolvable: 0,
        resolvable_correct: 0,
        correct: 0,
        false_promotions: 0,
        rows: vec![],
        events: vec![],
    };
    for case in matrix.cases {
        let snapshot = build(Input {
            files: case.files,
            root: case.root,
            edition: case.edition,
            configuration: case.configuration,
            rules: case.rules,
        })?;
        let result = match (&case.query_file, case.query_start) {
            (Some(file), Some(offset)) => {
                snapshot.resolve_at(&case.module, &case.path, &case.namespace, file, offset)
            }
            (None, None) => snapshot.resolve(&case.module, &case.path, &case.namespace),
            _ => return Err("occurrence query requires file and offset".into()),
        };
        let target = result
            .target_id
            .as_ref()
            .and_then(|id| snapshot.declarations.iter().find(|d| &d.id == id))
            .map(|d| {
                if d.module.is_empty() {
                    format!("{}:{}", d.evidence.path, d.name)
                } else {
                    format!("{}:{}::{}", d.evidence.path, d.module, d.name)
                }
            });
        let correct = result.state == case.expected_state && target == case.expected_target;
        output.correct += usize::from(correct);
        if case.expected_state == "resolved" {
            output.resolvable += 1;
            output.resolvable_correct += usize::from(correct);
        }
        if result.state == "resolved" && !correct {
            output.false_promotions += 1;
        }
        output.rows.push(Row {
            id: case.id,
            correct,
            expected_state: case.expected_state,
            expected_target: case.expected_target,
            result,
            snapshot,
        });
    }
    for event in matrix.events {
        let mut index = Index::new(event.a)?;
        let generation_before = index.generation;
        let before = index.current.clone();
        let incremental = index.update(event.b.clone())?.clone();
        let rebuild = build(event.b)?;
        if incremental != rebuild {
            return Err("full incremental snapshot differs from rebuild".into());
        }
        output.events.push(EventRow {
            id: event.id,
            generation_before,
            generation_after: index.generation,
            before,
            incremental,
            rebuild,
        });
    }
    println!("{}", serde_json::to_string(&output)?);
    if output.correct != output.cases || output.false_promotions > 0 {
        return Err("semantic fixture mismatch".into());
    }
    Ok(())
}
