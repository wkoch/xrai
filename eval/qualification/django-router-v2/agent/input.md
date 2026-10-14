# Route ledger migrations to reporting

The captured Django checkout is the complete search universe. Fix only the order of
the two existing router components in deployment.json. Keep both policy.py components
and all models unchanged. ledger.Entry must be created only in reporting; catalog.Item
represents other apps and must be created only in default. ledger.LegacyEntry is an
unmanaged legacy model (managed=False): its table must never be created by this migration,
even when an isolated router would allow it. Both databases initially lack all three
model tables. Existing unrelated sentinel data must remain unchanged.

No evaluator oracle or reference is part of agent input. This controlled configuration
task does not claim a historical upstream bug. Equivalent source evidence is accepted;
listing three source paths alone does not prove multimodule necessity.
