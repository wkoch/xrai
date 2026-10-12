# Python controlled contract candidate — scikit-learn 1.5.2

Pinned source is the complete archive of commit `156ef141f3b270edb06c8ae9af37c55253c0aabe`, resolved from the public annotated tag 1.5.2. `provenance/` retains GitHub commit/tag metadata and official PyPI package metadata. The original BSD license and setup are in the archive. `capture.json` and the independently recomputed gzip inventory bind every regular source member, production size, setup, and all evaluator/input/reference bytes. No historical bug/PR is asserted: this is a controlled contract change.

The natural request adds a dense NumPy masked-array container output mode. The evaluator checks the requested public APIs and numeric/mask semantics independently of the reference implementation. A nested ColumnTransformer branch contains a FeatureUnion; the exercised necessary chain is outer composition → branch union → output adapter. There are three semantically necessary production modules and two subsystems, although the reference changes only two modules: the existing FeatureUnion adapter dispatch in `pipeline.py` is already needed and correct. Necessity and floor still require independent semantic review and actual behavioral proof.

`oracles/` is evaluator-only. It contains the reference patch plus exact reference production bytes and three requirement/two regression probes. Comparative agents receive only the pinned checkout and `agent/input.md`, never evaluator files or patches. The reference does not alter upstream tests, source packaging, or dependencies. Direct and temporary global masked configurations preserve values, per-cell masks and concatenation order; existing default dense arrays, sparse-output rejection in an existing mode, invalid-mode rejection and context restoration provide regression controls.

Setup is Linux x86_64 Python 3.11.13 with five official wheels identified by exact URL/SHA256/size. `run_l5_python.py` downloads and extracts wheel **data** without pip/build hooks. The sklearn wheel contributes only compiled `.so` modules and bundled shared libraries from version 1.5.2; all sklearn Python executed comes from the complete captured checkout. The hidden oracle records exact origin paths and SHA256 for the three semantic modules, and the executor compares them with baseline/reference bytes. Full captured source/setup/oracle bytes are checked before/after each pair side. The Python runtime is copied into the workspace; namespace commands have no package-install or network steps.

```sh
python eval/scripts/prepare_l5_python.py verify
python -m unittest discover -s eval/scripts -p test_l5_python.py -v
# Disposable Linux GitHub Actions only; never run upstream on local macOS:
python eval/scripts/run_l5_python.py run --cache "$RUNNER_TEMP/l5-python-wheels" --output "$RUNNER_TEMP/l5-python-proof" --timeout 300
```

Four fresh `runner.execute(arbitrary_agent=True)` domains each have 300 seconds and 1 MiB per stream. Teardown must be confirmed before workspace removal; an inconclusive domain preserves its workspace. Receipt checks require exact test IDs, no duplicates, exact statuses, import origins, complete untruncated streams, expected baseline config errors, unchanged full source/setup, and confirmed shutdown. Import/bootstrap failures never count as baseline contract failures.

Input/oracle/reference/executor were frozen in `docs/relatorios/logs/L5-C02/python/freeze-before-ci-v2.json (original freeze-before-ci.json retained)` before any behavioral run. Fourteen own-code/data-only tests passed on the local host, with no upstream imports/builds/tests. Behavioral probes and independent second reading remain pending. Same-index/process A→B and full rebuild B belong to the external incremental quota; no universal A→B gate is imposed on this controlled contract candidate. A possible future unchanged-source rename/restore exercise is supplementary and not prepared: there is no descriptor, collector ownership, or execution proof, and it does not represent one of the four required real incremental cases. Global admission still requires the complete 32-case corpus quotas and applicable acceptance evidence. `admitted=false`, D1 global delta 0, no competitive runs authorized by this dossier.

Revisão independente de fontes/input/oracle/reference/setup aceita em `docs/relatorios/logs/L5-C02/integration/python-source-review-root.json`. Esta revisão é anterior à prova comportamental; elegibilidade do dossiê e admissão permanecem pendentes até seus critérios, conforme C02. Recibos/freeze anteriores preservados.

## Estado corrente após C02

Os parágrafos de preparação acima preservam o histórico anterior à prova. O par comportamental e a revisão independente foram concluídos no código `e02370a`, [CI38294106923](https://github.com/wkoch/xrai/actions/runs/38294106923). Consulte a [matriz factual derivada](../../c02-status-matrix.json) e o [relatório C02](../../../../docs/relatorios/L5-C02.md) para a elegibilidade individual corrente. Os casos, oracles, pins e recibos congelados permanecem originais; admissão global continua 0/32 e o evento obrigatório da família é separado.
