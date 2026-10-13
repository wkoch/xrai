# Captured unified diff v1 — data only

`cases.json` freezes 21 accepted and 34 refused inputs and external expected typed
spans before decoder implementation; `freeze.json` retains its SHA256 and timestamp.
`replay.py` consumes only those retained bytes and the owned decoder, validates the
whole HEAD and reconstructs it a second time through the typed span consumer.

Run: `python3 eval/context/diff-v1/replay.py`.
Tests: `python3 -m unittest discover -s crates/xrai-eval/harness/tests -p test_unified_diff.py -v`.

Profile: UTF-8 bytes and exact relative paths. Every diff physical record ends in
LF; CR is preserved as source content, including CRLF sources. Headers use exactly
`--- a/path` / `+++ b/path`, or `/dev/null` for an absent side. Counts determine hunk
record boundaries; text resembling a header inside a prefixed record is content.
EOF-without-LF uses the exact immediately preceding-line marker
`\ No newline at end of file`, validated at that side's EOF. No source normalization,
path discovery, basename fallback, fuzzy patch search, timestamped headers, Git
preamble, rename, binary, combined diff or unknown extensions. A zero-length hunk
explicitly expresses creation/deletion of a captured empty file. An empty diff is
accepted only when the captured snapshots are wholly equal.

Declared bounds: diff 2MiB; each UTF-8 source 8MiB; total each capture 32MiB;
128 files per snapshot/patch; 4,096 total hunks; 100,000 source lines/line indices;
200,000 physical patch records; 4,096 UTF-8 bytes per path. Source totals and file
limits are checked before parsing hunks. These are experimental implementation
limits, not a measured production allocation guarantee.

The API `decode_unified(bytes, base_map, head_map)` produces frozen `ValidatedDiff`
with `FileChange` and `Hunk` objects, exact byte spans and presence-bound source
hashes. `apply_typed(base_map, changes)` checks presence, hashes, spans and removed
bytes before reconstructing. It retains unchanged bytes and all unmentioned files.
Absent source is never represented as a present empty blob; internal empty bytes
are used solely for a side already proven absent by `/dev/null` and the captures.

Two cases use the actual 495-byte retained ReactCurrentDispatcher source from the
existing JS presence event, creation and reverse deletion in that captured scope.
They are source-real presence transformations, **not historical Git changes**.
Other cases are explicitly technical regressions. No upstream code is imported or
executed, no Git command is run, and no new source is acquired.

This module does not change the legacy Rust typed-hunk planner or documentary
P3 verifier. Their profiles, fingerprints and historical tests stay intact.
Native integration and complete M0-09 acceptance remain pending.
