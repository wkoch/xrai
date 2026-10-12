# Quatro pilotos verticais L3-01

`selection.json` congela um caso histórico por família. Estes pilotos servem à qualificação reprodutível do corpus; **não admitem dataset competitivo nem abrem o gate global de 32 tarefas**. Dossiês, revisões independentes e admissão parcial são verificados separadamente por `verify_vertical.py`. O runner abaixo somente verifica a regressão baseline e a referência usando oracles privados do avaliador.

## Receita

Use `eval/scripts/run_vertical_probes.py`. Cada execução cria checkouts novos em um diretório `mkdtemp` e exige um diretório de saída que ainda não existe. Nunca utiliza as árvores de build preexistentes em `/private/tmp/xrai-l3-corpus/{projeto}-{base,reference}`. Fontes baseline vêm dos archives normalizados e inventories SHA-256 em `eval/sources/manifest.json`; referências vêm dos upstream archives em `--cache`, com SHA-256 exato de `selection.json`. Não existe download automático de fonte. Symlinks internos a arquivos da referência são copiados como bytes do destino pela mesma política de `prepare_vertical_sources.regular_tree`; links externos, ausentes, de diretório ou ciclos são recusados.

Ferramentas congeladas neste recorte: Cargo/Rust 1.98.1, Python 3.15.0, Node 26.11.1, npm 11.20.0 e Go 1.27.2. O runner verifica a versão da ferramenta pertinente ao caso e permite caminhos explícitos por `--cargo`, `--rustc`, `--python`, `--node`, `--npm`, `--go`; não instala toolchains. Versão diferente é readiness failure preservada, não execução equivalente. Estes são os ambientes dos pilotos disponíveis, não afirmação sobre toda a matriz upstream.

Tokio, com dependencies já presentes no cache Cargo:

```sh
python3 eval/scripts/run_vertical_probes.py \
  --case tokio \
  --cache /private/tmp/xrai-l3-corpus \
  --output /private/tmp/xrai-vertical-proof-tokio-NEW
```

Quatro pares, autorizando explicitamente preparação local de dependencies:

```sh
python3 eval/scripts/run_vertical_probes.py \
  --cache /private/tmp/xrai-l3-corpus \
  --python-dependencies /private/tmp/xrai-l3-python \
  --prepare-dependencies \
  --output /private/tmp/xrai-vertical-proof-all-NEW
```

Sem `--case`, executa os quatro; `--case` pode se repetir. `--work-root` escolhe o diretório pai dos checkouts frescos. A saída e as árvores de julgamento são preservadas, inclusive em falha. Para repetir, forneça nova saída; não apague recibo anterior nem reutilize a árvore compilada como fonte da prova.

`--prepare-dependencies` é opt-in explícito, registrado: pode executar `cargo fetch --locked`, `npm ci --ignore-scripts --no-audit --no-fund`, preparação focada dos dependencies de `./storage/remote` com toolchain local e pip para os dois pins Python. Não consulta modelos nem recursos pagos. TypeScript precisa desse flag para povoar `node_modules` do checkout fresco e executar seu build declarado. Com o flag ausente, Cargo e Go usam dependencies existentes offline; Python exige tooling pré-instalado no path informado. Falta de dependency/tool/archive é infraestrutura incompleta, não regressão reproduzida.

## Comandos de julgamento e isolamento de build

| Caso | Baseline adverso | Referência/regressões |
|---|---|---|
| Tokio #8371 | `cargo test --locked --offline -p tokio --features full --test sync_mutex mutex_fifo_with_coop_budget -- --exact --nocapture` | Mesmo comando sem filtro, executando todo `sync_mutex` (9 testes no pin atual) |
| TypeScript #62656 | `npm ci` pelo lock upstream, scripts de instalação ignorados; `npm run build:compiler`; `node <evaluator>/probe.cjs` | Mesmo pipeline; probe verifica regressão e dois controles (3 checks) |
| Django #22051 | Python 3.15, `tests/runtests.py model_fields.test_jsonfield.TestQuerying.test_in_value_without_explicit_output_field --settings=test_sqlite --parallel=1 --verbosity=2` | `model_fields.test_jsonfield` inteiro, 129 testes |
| Prometheus #19866 | Go 1.27.2, `go test -mod=readonly -p 2 ./storage/remote -run '^TestCalculateDesiredShardsDetail$' -count=1 -v` | Mesmo comando com prefixo `^TestCalculateDesiredShards`, incluindo controles |

O avaliador copia apenas os testes hidden necessários nos checkouts de julgamento. Tokio recebe o mesmo `sync_mutex.rs` e **Cargo.lock congelado** em ambos. Django recebe `test_jsonfield.py`; Go recebe `queue_manager_test.go`; o probe TypeScript permanece fora da fonte. Nenhum desses arquivos, lock/oracle de referência ou solução deve entrar na materialização para agentes. Esse runner não é um adapter de agente.

`RUSTUP_TOOLCHAIN=1.98.1` fixa a toolchain disponível de Rust, inclusive se um checkout declarar outro default. `CARGO_TARGET_DIR` é diferente em baseline/referência e em toda nova execução. Cache de crates baixadas pode ser compartilhado; artefatos compilados não. A prova inicial manual com target compartilhado confundiu baseline; esta receita impede esse reuso. Go também recebe `GOCACHE` por checkout, `GOMAXPROCS=2`, `-p 2`, `GOTOOLCHAIN=local`, `-mod=readonly`, mantendo go.mod/go.sum upstream. Preparação Go executa `go test -mod=readonly -p 2 ./storage/remote -run '^$' -count=1`, compilando sem executar testes e baixando só dependencies do alvo, com GOPROXY autorizado e sem permitir reescrever os pins. O runner recusa qualquer alteração nos hashes upstream de go.mod/go.sum antes do probe `-mod=readonly`. Não usa `go mod download` indiscriminado, que pode baixar pacotes sem consumidor neste caso. Módulos baixados em `--cache/gomodcache` podem ser compartilhados e são tratados pelo próprio Go com os hashes do go.sum.

Django exige `asgiref==3.12.1` e `sqlparse==0.5.4`. Readiness valida `__version__` dos módulos efetivamente importados, sua origem sob `--python-dependencies` e registra SHA-256 do arquivo de entrada. Isso evita escolher uma versão via dist-info antiga duplicada. Em falta, só o opt-in permite pip `--target --upgrade --no-deps` com esses pins, seguido de nova verificação. Não há installer silencioso.

## Recibos e falhas

`summary.json` identifica selection e runner por SHA-256, opções, raiz fresca, os quatro estados e flags de gate sempre falsos. Cada caso tem `case.json`; cada comando de tooling/preparação/probe tem JSON e stdout/stderr crus com hashes. Registra command/cwd, env experimental permitido, pin de source archive, commit, fontes completas, arquivos hidden copiados, locks, duração, exit code, classificação e cleanup.

Readiness exige ao menos **2 GiB livres antes de cada checkout/build** e registra o espaço observado. É margem local inicial, não quota nem garantia de que qualquer build cabe; ENOSPC durante preparação/probe é falha de infraestrutura preservada e excluída do aceite.

Teto fixado: **600 s por comando, 1 MiB retido por stream**. A leitura continua contando/hashing bytes observados, mas os arquivos não crescem além do teto. Truncamento invalida a prova comportamental. Timeout/cancelamento mata o grupo de processo, espera filho com limite de 5 s e drena pipes por até 0,5 s. Spawn failure, deadline, saída truncada, cleanup inconclusivo e failure de preparação permanecem nos recibos. Ctrl-C preserva o recibo e encerra o runner, sem iniciar a referência seguinte.

Isso é execução de comandos de build/probe do avaliador em fontes upstream escolhidas. `killpg` é auxiliar: **não prova contenção de descendentes que escapam da sessão**, nem substitui o domínio descartável de L3-02 para shell arbitrário de agente. Cleanup inconclusivo impede aceitação do par.

Baseline precisa falhar com o marcador comportamental esperado; erro de compilação, import/dependency ou zero testes não constitui regressão válida. Referência exige exit 0, marcador/count pertinente e cleanup concluído. Todas as tentativas preservam resultado; não eliminar uma falha e conservar somente a repetição verde. `vertical_pair_verified` significa somente esse par baseline/reference, não revisão independente, qualificação completa dos quatro dossiês ou vantagem de xrai.

## Prova do runner

Prova local Tokio registrada em `/private/tmp/xrai-vertical-runner-proof-tokio`: baseline fresco exit 101 com `mutex_fifo_with_coop_budget ... FAILED`; referência fresca exit 0 com 9 testes aprovados, targets separados. Uma repetição posterior em `/private/tmp/xrai-vertical-runner-proof-tokio-final` falhou por ENOSPC em compilação; seus recibos foram preservados como infraestrutura, sem apagar a tentativa nem aproveitar a falha como regressão. Somente os quatro targets de build criados nessas duas provas foram removidos para recuperar espaço; fontes e logs permaneceram. O runner passou a registrar headroom e a recusar início abaixo de 2 GiB. O runner não altera `candidates.jsonl`, arquivos de oracles ou admission-status.

Os três autochecks no código final estão em `docs/relatorios/logs/L3/vertical-runner-selfchecks/summary.json`: saída de 1,2 MB por stream retida em 1 MiB e recusada como evidência, timeout de 0,1 s com término finito e executable inexistente. O par Go fresco está em `docs/relatorios/logs/L3/vertical-fresh-retry-go/summary.json`: baseline exit 1 no cenário `sent_timestamp_in_the_future`, referência upstream exit 0 com os controles, caches separados e hashes de go.mod/go.sum preservados. Ambos os conjuntos registram SHA-256 do runner `943f31fae58d99696c4bf4006af319afe54faead75ae30b4cea26f74c3f7a88d`. Essas provas locais permanecem com flags de gate falsas.
