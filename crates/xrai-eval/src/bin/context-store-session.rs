//! Limited persistent Store bridge. No analyzed program or provider is executed.
use serde::Deserialize;
use serde_json::{Value, json};
use std::io::{BufRead, Read, Write};
use xrai_eval::context_spike::validated_diff::{DiffInput, ValidatedDiff};
use xrai_eval::context_spike::{Case, Limits, Meter, Request, Store};
const FRAME: usize = 512 * 1024;
const OPERATIONS: usize = 512;
const PROFILE: &str = "xrai.eval.store-session.v1";
#[derive(Deserialize)]
#[serde(tag = "operation", rename_all = "snake_case", deny_unknown_fields)]
enum Command {
    Context {
        command_id: u64,
        case: Case,
        now_ms: u64,
    },
    ContextValidated {
        command_id: u64,
        diff: DiffInput,
        request: Request,
        now_ms: u64,
    },
    Expand {
        command_id: u64,
        context_id: String,
        item_ids: Vec<String>,
        limits: Limits,
        now_ms: u64,
    },
    Inspect {
        command_id: u64,
        context_id: String,
        now_ms: u64,
        max_bytes: usize,
    },
    Close {
        command_id: u64,
    },
}
fn outer(id: u64, instance: &str, operation: &str, result: &Value, error: Option<&str>) -> Value {
    json!({"profile":PROFILE,"command_id":id,"instance_id":instance,"operation":operation,"revision_role":if operation=="context" {"initial_base"}else{"base_head_or_retained"},"result":result,"error":error,"outer_wire_bytes":0,"model_tokens":null,"meter_unit":"serialized_bytes"})
}
fn encode(mut value: Value) -> Result<Vec<u8>, String> {
    for _ in 0..16 {
        let wire = serde_json::to_vec(&value).map_err(|e| e.to_string())?;
        if value["outer_wire_bytes"] == wire.len() {
            return Ok(wire);
        }
        value["outer_wire_bytes"] = json!(wire.len());
    }
    Err("outer_counter_unstable".into())
}
struct FinalBytes<'a> {
    id: u64,
    instance: &'a str,
    operation: &'a str,
}
impl Meter for FinalBytes<'_> {
    fn profile(&self) -> &str {
        "store-final-wire-bytes-v1:model-tokens-unmeasured"
    }
    fn tokens(&mut self, bytes: &[u8]) -> Result<usize, String> {
        if bytes.len() > FRAME {
            return Err("meter_wire_cap".into());
        }
        let value = serde_json::from_slice(bytes).map_err(|e| e.to_string())?;
        let wire = encode(outer(self.id, self.instance, self.operation, &value, None))?;
        if wire.len() + 1 > FRAME {
            return Err("meter_wire_cap".into());
        }
        Ok(wire.len() + 1)
    }
}
fn bound(limits: &mut Limits) -> Result<(), String> {
    if limits.max_bytes > FRAME || limits.max_bytes < 1024 {
        return Err("invalid_request:frame_budget".into());
    }
    // This functional profile counts bytes, not model tokens. It applies the
    // stricter of both supplied caps to the final outer wire before publication.
    limits.max_tokens = limits.max_tokens.min(limits.max_bytes);
    Ok(())
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut store = Store::new()?;
    let instance = store.instance_id().to_string();
    let mut input = std::io::stdin().lock();
    let mut output = std::io::stdout().lock();
    let mut previous = 0;
    for _ in 0..OPERATIONS {
        let mut raw = Vec::new();
        let n = input
            .by_ref()
            .take((FRAME + 1) as u64)
            .read_until(b'\n', &mut raw)?;
        if n == 0 {
            return Ok(());
        }
        if n > FRAME || raw.last() != Some(&b'\n') {
            return Err("invalid_frame_or_cap".into());
        }
        let command: Command = serde_json::from_slice(&raw)?;
        let (id, op) = match &command {
            Command::Context { command_id, .. } => (*command_id, "context"),
            Command::ContextValidated { command_id, .. } => (*command_id, "context_validated"),
            Command::Expand { command_id, .. } => (*command_id, "expand"),
            Command::Inspect { command_id, .. } => (*command_id, "inspect"),
            Command::Close { command_id } => (*command_id, "close"),
        };
        if id == 0 || id <= previous {
            return Err("invalid_command_order".into());
        }
        previous = id;
        let close = op == "close";
        let mut meter = FinalBytes {
            id,
            instance: &instance,
            operation: op,
        };
        let mut cap = FRAME;
        let result: Result<Value, String> = (|| match command {
            Command::Context {
                mut case, now_ms, ..
            } => {
                cap = case.request.limits.max_bytes;
                if case.base.is_some()
                    || case.request.p2
                    || !case.request.hunks.is_empty()
                    || !case.head.root.ends_with(".rs")
                    || !["2021", "2024"].contains(&case.head.edition.as_str())
                    || ![
                        xrai_eval::semantics_spike::RULES,
                        xrai_eval::semantics_spike::RULES_R3,
                    ]
                    .contains(&case.head.rules.as_str())
                {
                    return Err("invalid_request:initial_base_only".into());
                }
                bound(&mut case.request.limits)?;
                store.context(case, now_ms, &mut meter).map(|d| d.response)
            }
            Command::ContextValidated {
                diff,
                mut request,
                now_ms,
                ..
            } => {
                cap = request.limits.max_bytes;
                bound(&mut request.limits)?;
                store
                    .context_validated(ValidatedDiff::try_from(diff)?, request, now_ms, &mut meter)
                    .map(|d| d.response)
            }
            Command::Expand {
                context_id,
                item_ids,
                mut limits,
                now_ms,
                ..
            } => {
                cap = limits.max_bytes;
                bound(&mut limits)?;
                store
                    .expand(&context_id, &item_ids, limits, now_ms, &mut meter)
                    .map(|d| d.response)
            }
            Command::Inspect {
                context_id,
                now_ms,
                max_bytes,
                ..
            } => {
                cap = max_bytes.min(FRAME);
                let result = store.inspect(&context_id, now_ms)?;
                if encode(outer(id, &instance, op, &result, None))?.len() + 1 > cap {
                    return Err("audit_export_budget".into());
                }
                Ok(result)
            }
            Command::Close { .. } => {
                Ok(json!({"closed":true,"retained_contexts":store.retained_contexts()}))
            }
        })();
        let value = match result {
            Ok(value) => outer(id, &instance, op, &value, None),
            Err(error) => outer(id, &instance, op, &Value::Null, Some(&error)),
        };
        let wire = encode(value)?;
        if wire.len() + 1 > FRAME {
            return Err("response_frame_cap".into());
        }
        // Refusal frames still spend bytes and are recorded; no truncation.
        // Successful selection has already measured this exact outer envelope.
        if wire.len() + 1 > cap && serde_json::from_slice::<Value>(&wire)?["error"].is_null() {
            return Err("response_budget_invariant".into());
        }
        output.write_all(&wire)?;
        output.write_all(b"\n")?;
        output.flush()?;
        if close {
            return Ok(());
        }
    }
    Err("session_operation_cap".into())
}
