# Dependências e compatibilidade — M0-02 / L0

**Atualização da revisão:** a [CI do commit L0](https://github.com/wkoch/xrai/actions/runs/38190368368) já concluiu os três jobs com sucesso. A matriz abaixo preserva o estado histórico observado pelo implementador; evidência atual e limites do aceite estão em [REVISAO-L0.md](REVISAO-L0.md).

Data da decisão: 11/10/2026, America/Sao_Paulo. Escopo: esqueleto compilável; não demonstra parsing, persistência, consultas, MCP ou resultados de avaliação.

## Escolhas locais

| Item | Escolha | Motivo e evidência |
|---|---|---|
| Toolchain | Rust/Cargo 1.98.1, canal numérico fixo | Já instalado e testado nativamente em `aarch64-apple-darwin`; evita atualização implícita de `stable`. A publicação oficial confirma a release e a correção de geração de vtables. |
| Edição | Rust 2024 | Edição estável desde Rust 1.85; compatível com 1.98.1. |
| MSRV declarado | 1.98.1 | Corresponde ao mínimo efetivamente verificado neste lote. Não se reivindica suporte a toolchains anteriores; reduzir este piso exige teste próprio. |
| Resolver | `3` | Declarado no workspace virtual; alinhado à edição 2024. |
| Dependências de terceiros | Nenhuma | `std` atende aos dois smokes da CLI. `Cargo.lock` contém somente os cinco crates locais; não há registry, FFI, build scripts ou gramáticas. |
| Versão do produto | `0.1.0-dev` | Identifica o esqueleto; `--version` inclui arquitetura e SO compilados. |
| Publicação | `publish = false` em todos os crates | A política de licenciamento/distribuição do xrai permanece questão aberta da RFC. Não foi atribuída uma licença ao produto. |

`clap`, `serde`, Tree-sitter, SQLite, Tokio e RMCP continuam propostas para tarefas consumidoras posteriores; nenhum deles é requisito do build L0. A seleção não muda os componentes previstos pela arquitetura: evita incorporá-los antes dos spikes e dos consumidores. A decisão local de usar `std` para duas flags pode ser revista quando a CLI ganhar comandos.

## Fronteiras

```text
xrai-core  -> nenhuma dependência
xrai-index -> xrai-core
xrai-query -> xrai-core
xrai       -> xrai-core, xrai-index, xrai-query
xrai-eval  -> xrai-core, xrai-index, xrai-query
```

Essas arestas estabelecem o fluxo de compilação; as bibliotecas só contêm documentação e ainda não oferecem APIs de parsing, armazenamento ou consulta. O núcleo não conhece adapters; query não depende de index nem de backend concreto. A escolha de interfaces e a implementação dos contratos pertencem aos cartões posteriores, sem compromisso prematuro com um adapter. `xrai-eval` é biblioteca de desenvolvimento neste lote; não é transitiva do executável e ainda não oferece harness.

`cargo metadata --locked --offline` e revisão das fontes verificaram cinco membros locais, ausência de ciclos, zero dependências no núcleo e ausência de `xrai-eval` na árvore do produto. Evidência: [workspace-boundaries.json](logs/L0/workspace-boundaries.json), [metadata](logs/L0/workspace-metadata.json) e [árvore](logs/L0/workspace-tree.json).

## Licenças verificadas nas fontes oficiais

| Componente incorporado ou de build | Informação oficial | Alcance |
|---|---|---|
| Rust e biblioteca padrão | MIT OR Apache-2.0; projetos oficiais normalmente têm licenciamento duplo | Toolchain e biblioteca padrão usadas em L0; a política oficial ressalva licenças específicas por repositório. Não equivale a um inventário completo de todos os componentes internos do compilador. |
| `actions/checkout@v6` | MIT, repositório oficial Actions | Ferramenta de CI; não incorporada ao executável. |
| Cinco crates locais | Licença do produto ainda não decidida | `publish = false`; não foi escolhido SPDX ou texto de licença em nome do usuário. |

As dependências Rust são fixadas pelo canal numérico e pelo lockfile de paths/versões locais; a action de checkout está fixada no major v6, sem promessa de imutabilidade por SHA. As imagens de runner também recebem atualizações do provedor; nomes de SO e a checagem do host impedem confundir arquiteturas.

Fontes primárias consultadas em 11/10/2026:

- [Release Rust 1.98.1](https://blog.rust-lang.org/releases/1.98.1/).
- [Guia oficial da edição 2024](https://doc.rust-lang.org/edition-guide/rust-2024/index.html).
- [Cargo: workspace, herança e resolver](https://doc.rust-lang.org/cargo/reference/workspaces.html).
- [Cargo: MSRV](https://doc.rust-lang.org/cargo/reference/rust-version.html).
- [Rustup: rust-toolchain.toml](https://rust-lang.github.io/rustup/overrides.html#the-toolchain-file).
- [Política oficial de licenças Rust](https://rust-lang.org/policies/licenses/).
- [Checkout oficial e licença MIT](https://github.com/actions/checkout).
- [Tabela oficial de runners e arquiteturas](https://github.com/actions/runner-images#available-images).

## Matriz e resultado

| SO/arquitetura | Runner configurado | Host exigido | Resultado neste lote |
|---|---|---|---|
| Linux x86_64 | `ubuntu-24.04` | `x86_64-unknown-linux-gnu` | Configuração revisada; execução nativa não verificada. |
| macOS aarch64 | `macos-15` | `aarch64-apple-darwin` | Build, lint, testes e smokes nativos locais passaram; job remoto não executado. |
| Windows x86_64 | `windows-2025` | `x86_64-pc-windows-msvc` | Configuração revisada; execução nativa não verificada. |

A tabela oficial identifica `macos-15` como Arm64. A CI instala a toolchain fixada, registra `rustc --version --verbose` e falha se o host divergir. Os três jobs têm fmt, clippy, test, build e smokes; build/lint/test usam `--locked`. Não foi alegada validação por cross-build. Sem Git/remoto no checkout, os jobs não foram disparados; a prova nativa nos três SOs permanece em M0-05. A revisão sintática/estrutural do YAML por Ruby/Psych passou com saída 0, documentada em [workspace-ci-config.json](logs/L0/workspace-ci-config.json); Ruby não é dependência do projeto nem do workflow.

| Verificação local | Código de saída | Evidência |
|---|---|---|
| `cargo fmt --all -- --check` | 0 | [fmt](logs/L0/workspace-fmt.json) |
| `cargo clippy --workspace --all-targets --locked -- -D warnings` | 0 | [clippy](logs/L0/workspace-clippy.json) |
| `cargo test --workspace --locked` | 0 | [test](logs/L0/workspace-test.json), três testes de integração da CLI |
| `cargo build --workspace --locked` | 0 | [build](logs/L0/workspace-build.json) |
| `./target/debug/xrai --help` | 0 | [help](logs/L0/workspace-smoke-help.json) |
| `./target/debug/xrai --version` | 0 | [version](logs/L0/workspace-smoke-version.json): `xrai 0.1.0-dev (aarch64-macos)` |

Os logs incluem comando, cwd, timestamps UTC, stdout, stderr e código de saída. Os testes verificam só a superfície implementada: ajuda/aliases, versão/plataforma e recusa explícita de operações inexistentes/argumentos extras, sem saída de dados. Não são testes de contratos ou de capacidade semântica.

A checagem de cobertura do codebase-memory em `crates` informou `not_tracked` para os seis arquivos Rust novos (índice de 11/10/2026 22:57:19 UTC anterior à criação). As conclusões foram verificadas por leitura integral das fontes novas e metadata Cargo; não se usa “sem gaps registrados” como prova de cobertura. É necessário reindexar antes de usar o grafo como fonte estrutural desses arquivos.
