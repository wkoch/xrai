# P3 typed presence context — prospective C06 profile

`protocol.json`, `cases.json`, and `freeze-before-native.json` were created before the owned Rust bin/collector/verifier existed. Cases preserve all 21 positive and 34 negative labels from C05. No rankings, quotas, competitive tasks or frontend semantics are inferred.

Python decodes raw unified diff and constructs typed BASE/HEAD/maps/hunks. Rust independently reconstructs the complete HEAD map before generating byte/presence obligations. The raw parser remains Python, and the legacy semantic planner is unchanged. Missing and present-empty files remain different states; all captures preserve exact UTF-8/CRLF/EOF bytes.

A byte budget covers the complete canonical JSON response, including request references, identities, metadata, snippets and omissions, excluding only the newline transport delimiter. No model/controlled tokens are estimated. Context handles bind source revision and incarnation; old contexts close on successful replacement and invalid opening preserves the previous context.

Local checks are data-only. An artificial ELF marker in verifier fixtures never establishes native execution or API provenance. The owned bin may only be built/run in disposable CI. Original GitHub run/jobs/artifact metadata plus ZIP/export reconciliation are required for a native claim. Read `docs/relatorios/L5-P3-NATIVE.md` for checks and gaps.
