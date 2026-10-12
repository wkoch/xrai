# Gitea / controlled query-credential contract

Full source: Gitea v1.22.6, commit `8eefa1f6dedf2488db2c9e12c916e8e51f673160`, MIT. This is a **controlled new requirement**, with no historical bug or upstream reference claim. The API repository `original_url` exposure follows converter → repository model → URL utility; three production modules and two dependent edges are frozen with exact pinned excerpts in `oracles/source-relations.json`.

The complete archive contains 6127 regular files (verify reports the actual count). Production measurement counts only `.go` sources after excluding test names, explicit test/fixture/docs/assets/vendor/build paths and generated-prefix markers. Comments are included; source files are not a semantic compiler classification. The capture measures **1,740 production files / 247,058 nonempty lines**, beyond both size thresholds. Second-reader necessity/classification review remains pending.

Evaluator-only oracle has three named requirements (helper, model, API with existing SQLite fixtures) and two named regressions. It checks every secret-key occurrence, decoded/case-insensitive keys, repeated ordinary parameters, escaped values/path and fragment, empty addresses, userinfo removal, and errors. Reference changes only `modules/util/url.go`; original request has no file paths or suggested implementation. Evaluator materialization includes the full source plus the hidden test; **never use it as agent materialization**. An agent receives the original full source archive and natural request only.

Data-only verification and own counterchecks:

```sh
python eval/scripts/prepare_l5_go.py verify
python eval/scripts/test_l5_go.py
```

Upstream compilation/testing is authorized only in disposable Linux CI through the existing namespace harness. Use Go1.22.12, `CGO_ENABLED=1`, SQLite build tags, an unchanged `go.mod/go.sum`, and prepare `go mod download` as data fetch in CI. Then:

```sh
python eval/scripts/run_l5_go.py materialize --workspace DIR --side base
python eval/scripts/run_l5_go.py materialize --workspace OTHER --side reference
# go mod download from DIR in CI, prior to contained probes
python eval/scripts/run_l5_go.py probe --workspace DIR --side base --goroot GOROOT --module-cache CACHE --output OUT --timeout 900
python eval/scripts/run_l5_go.py probe --workspace OTHER --side reference --goroot GOROOT --module-cache CACHE --output OTHER_OUT --timeout 900
```

Toolchain/cache are verified byte copies, never host hardlinks; all source bytes are checked before probing. Each operation has a new domain, offline dependency resolution, bounded wall time/output, exact named Go JSON outcomes, immutable stream hashes and confirmed teardown. A compile/setup/panic failure does not count as baseline behavioral failure. Invalid timeout, local macOS execution, altered production, changed oracle/locks, links and extra Go source are rejected. Native C/C++ compilers are resolved to visible `/usr` paths to avoid hidden alternatives symlinks.

At preparation: behavioral pair **not run**, independent review pending, admission false and competitive runs false. C02 keeps the separate Go family state A→B event open; it does not become an artificial dependency of this contract dossier. Global D1/quota gates remain open.

Revisão independente de fontes/input/oracle/reference/setup aceita em `docs/relatorios/logs/L5-C02/integration/go-source-review-root.json`. Esta revisão é anterior à prova comportamental; elegibilidade do dossiê e admissão permanecem pendentes até seus critérios, conforme C02. Recibos/freeze anteriores preservados.

## Estado corrente após C02

Os parágrafos de preparação acima preservam o histórico anterior à prova. O par comportamental e a revisão independente foram concluídos no código `e02370a`, [CI38294106923](https://github.com/wkoch/xrai/actions/runs/38294106923). Consulte a [matriz factual derivada](../../c02-status-matrix.json) e o [relatório C02](../../../../docs/relatorios/L5-C02.md) para a elegibilidade individual corrente. Os casos, oracles, pins e recibos congelados permanecem originais; admissão global continua 0/32 e o evento obrigatório da família é separado.

Novas execuções Gitea estão bloqueadas pelo [gate S01](../../../../docs/relatorios/L5-S01.md) enquanto a exposição dos 55 alertas permanece desconhecida. Os comandos acima são documentação histórica e não substituem esse gate.
