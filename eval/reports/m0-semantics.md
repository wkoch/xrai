# M0-11 / L4-03 — primeira entrega Rust R1/R2

2026-10-12. Experimento em `xrai-eval`, conforme ADR 025. Esta entrega permite consultar ambientes de módulos Rust com destinos e cadeia de evidências ancorados nos bytes capturados. Não fecha M0-11 nem demonstra sucesso de agente/H1.

## Recorte e identidade

`semantics_spike.rs` recebe manifesto imutável de paths relativos, fontes UTF-8 originais, edição explícita e configuração capturada. Nenhum Cargo, build, macro ou código do projeto analisado é executado. Tree-sitter permanece interno. Há módulos, declarações em namespaces separados, imports, escopos de função, ocorrências de chamada, lacunas, cobertura e dependências positivas/negativas.

IDs de snapshot incluem todos os inputs e produtor; IDs de símbolos incluem snapshot, path, span, módulo, namespace e nome. Hash de fonte usa BLAKE3 sobre o buffer inteiro; evidências preservam CRLF, Unicode e intervalos `[start,end)`. Produtor combina `worker_spike::producer("rust")` (runtime/grammar/query/ABI/proveniência fixados), versão de regras e bytes do próprio resolver. Configuração/edição têm fingerprint próprio. Alterações de fonte/path/configuração/query/resolver invalidam o pacote completo.

A referência de linguagem consultada é o conjunto oficial de páginas de namespaces, imports, paths e privacidade, capturado em 2026-10-12 com hashes SHA-256 em `eval/semantics/language-reference-pin.json`; o toolchain de verificação é Rust 1.98.1, commit `48a229ceaefd4985c50990b14116b6d856af0985`. Regras de namespaces/imports e privacidade vêm da [Rust Reference](https://doc.rust-lang.org/reference/items/use-declarations.html) e da [referência de visibilidade](https://doc.rust-lang.org/reference/visibility-and-privacy.html). Edições 2021/2024 são entradas explícitas; outras retornam lacuna.

## Aceite e evidências

Os rótulos foram escritos antes do resolver. `labels-first.json` fixa timestamp/hash da matriz original; `real-labels-first.json` fixa a amostra real. As seis contraprovas da revisão e as contraprovas Rust de atributo com path qualificado e módulo duplicado têm recibos separados, prévio às correções; não substituem os denominadores originais.

| Critério | Evidência | Resultado local |
|---|---|---|
| Homônimos, tipo/valor, crate/self/super, módulos inline e arquivos convencionais | `eval/semantics/rust-r1-r2.json`; `logs/L4/semantics/rust-r1-r2.json` | 33/33 casos; 18/18 pré-rotulados resolvíveis (100%); zero promoção indevida |
| Alias, grupos aninhados, cadeia de reexports, privado/pub/pub(crate), ciclos limitados | Mesma matriz; `reexports_have_each_import_and_destination_in_evidence` | Destino exato, spans/hashes e imports intermediários; ciclos conservam unknown |
| Missing file/config, macro, parse parcial, externo sem identidade, glob e visibilidade fora do recorte | Casos negativos da matriz | Unknown sem alvo inventado; namespace macro não se funde a valor/tipo |
| Revisão adversa: import duplicado ao mesmo alvo, reexport privado/pub(crate), atributo procedural com prefixo seguro, colisão módulo/tipo | `rust-counterproofs.json`, `counterproof-labels-first.json` | 6/6 unknown; zero promoção |
| Mesmo índice A com busca negativa → criar export B → remover; alteração config/edition/rules/path/shadow | `crates/xrai-eval/tests/semantics_spike.rs` | B incremental == rebuild B por igualdade de Snapshot inteiro: estados, IDs, alvos, evidências, config, coverage e gaps |
| Destino com fonte real preservada | `tokio-development.json`; arquivo normalizado Tokio `tokio/src/io/uring/utils.rs`, commit `2fb5757a97a94b3173f8fdd7b6280423b63da6e6` | 4/4 perguntas de lookup de declarações; 3/3 resolvíveis; externo OwnedFd unknown |
| Fonte/identidade/estados verificados independentemente | `eval/scripts/verify_semantics.py` + sete testes adversos | Fonte da amostra igual aos bytes do archive; Cargo.toml/edição capturados; adulterações de snapshot/hash/span/config/contagens/promoção rejeitadas |
| Testes e qualidade Rust | `logs/L4/semantics/checks.json` | Dez testes Rust; fmt e clippy com warnings negados; recibo local separado de CI |

A amostra real é uma unidade de desenvolvimento explicitamente capturada como raiz do experimento, não o crate Tokio inteiro. Para essas quatro perguntas: precisão 3/3, recall 3/3, cobertura de resolução 3/4. São buscas de declaração predefinidas, não avaliação ampla de referências Rust. Os callsites extraídos no mesmo arquivo expõem métodos/externos não demonstrados como unknown; esses callsites não compõem o denominador de declaração. Arquivos reais, queries e números são mantidos separados das fixtures.

## Reproduzir

```sh
cargo test --locked -p xrai-eval --test semantics_spike
cargo run --locked -p xrai-eval --bin semantics-spike -- eval/semantics/rust-r1-r2.json > /tmp/rust-r1-r2.json
cargo run --locked -p xrai-eval --bin semantics-spike -- eval/semantics/tokio-development.json > /tmp/tokio-development.json
cargo run --locked -p xrai-eval --bin semantics-spike -- eval/semantics/rust-counterproofs.json > /tmp/rust-counterproofs.json
python3 eval/scripts/verify_semantics.py eval/semantics/rust-r1-r2.json /tmp/rust-r1-r2.json
python3 eval/scripts/verify_semantics.py eval/semantics/tokio-development.json /tmp/tokio-development.json
python3 eval/scripts/verify_semantics.py eval/semantics/rust-counterproofs.json /tmp/rust-counterproofs.json
python3 -m unittest discover -s eval/scripts/tests -p test_semantics_verifier.py
```

Python usa `blake3` do lock de dependências do harness. O CI executa os mesmos três drivers e verificadores nas plataformas nativas; o aceite de CI fica no relatório integrado do Implementador.

## Perdas e pendências para o Arquiteto

R1/R2 está deliberadamente parcial: aliases de módulo/`self` em grupos, globs, enum variants/associated items, prelude e regras completas de visibilidade restrita não são resolvidos. Busca não faz fallback por basename global. Import/reexport sem prova preserva unknown; candidatos ambíguos ficam separados de resolved. R3 ainda não avalia cfg, parâmetros/bindings/patterns ou shadowing; referências de funções que possam conter binding/macro/receiver fora do recorte ficam unknown. R4 não resolve dispatch de método/trait. Consultas por namespace de macro retornam limitação.

A IR desta entrega registra relações de lookup de módulos e callsites de função; referências gerais de tipos/valores e regras de escopo lexical completas continuam abertas. A invalidação recompõe o pacote inteiro e seus resultados, sem reaproveitar fatos semânticos antigos. Integração com trabalhadores persistentes, snapshots de produção, as três outras famílias, denominadores reais maiores e P3 ainda são etapas posteriores. Nenhuma decisão arquitetural adicional foi necessária nesta fatia; as limitações devem orientar a próxima rodada R3/R4 e expansão de R2.

## Prova nativa conciliada

[CI38248278388](https://github.com/wkoch/xrai/actions/runs/38248278388), código `1d2d40a221dad1a5ec9188158dbc624f329023c7`, Linux x86_64/glibc2.39 e macOS15.7.9 arm64: três jobs aprovados. [L4](../../docs/relatorios/L4.md) e [conferência dos receipts](../../docs/relatorios/logs/L4/integration/native-receipts-verification-final.json) registram comandos/hashes, resultados e limites do primeiro recorte. Prova antes pendente agora concluída para este incremento; os critérios restantes do cartão continuam abertos.

## Continuação L5 — Rust R3 opt-in

2026-10-12. A [revisão L5 §4](../../docs/relatorios/REVISAO-L5.md) avançou R3 em `xrai-eval`, com perfil explícito `rust-r3-v1`. `rust-r1-r2-v1` conserva suas regras, matrizes e recibos históricos. Fontes novas invalidam o produtor dos novos runs, incluindo **ambos** `semantics_spike.rs` e `semantics_spike/r3.rs`. Nada é promovido ao domínio de produção; M0-11 continua aberto.

O recorte distingue parâmetros e `let` simples, alcance temporal após o statement, blocos aninhados e shadowing. `resolve_at` valida ocorrência AST, arquivo, offset, namespace e módulo; uma coincidência de nome não basta. Parâmetro/valor local fica `unknown` quanto ao destino de chamada. Somente alias imutável diretamente inicializado por função demonstrada pode apontar para essa função, conservando callsite, binding, initializer e cadeia de import. Alias mutável, encadeamento entre variáveis, patterns/destructuring, closures, macros e itens locais não demonstrados conservam lacuna. Const generics bloqueiam o ambiente lexical pertinente. A invalidação recompõe o pacote inteiro; não é um motor incremental fino.

`cfg` admite predicados simples, `all`/`any`/`not`, chave/valor sem escapes e valores explicitamente `known:true`/`known:false`. Entradas ausentes ficam `not_evaluated`, salvo fechamento explícito pertinente (`closed:feature=true`, por exemplo). Não herda target/features do host. Cada condição registra predicado, entradas e evidência; `known_false` exclui o item. `cfg_attr`, strings com escapes, condições internas/lexicais e atributos não suportados conservam lacuna. A regra lexical acompanha os [escopos da referência oficial fixada](https://github.com/rust-lang/reference/blob/5baa209fc1998b8425be2ea1e8a57b613fed52d2/src/names/scopes.md); a concretização de predicados segue a [compilação condicional da mesma versão documental](https://github.com/rust-lang/reference/blob/5baa209fc1998b8425be2ea1e8a57b613fed52d2/src/conditional-compilation.md). Commit e hashes de três Markdown oficiais, além dos HTML consultados, estão em [language-reference-pin.json](../semantics/r3/language-reference-pin.json). URLs de release tentadas não ficaram acessíveis; não se afirma equivalência com a edição da documentação do toolchain Rust 1.98.1. Nenhum Cargo/build script/macro de upstream foi executado para indexar.

| Critério | Evidência local concluída | Limite |
|---|---|---|
| Matriz escrita antes das regras | [freeze original](../../docs/relatorios/logs/L5-continuacao/r3/labels-first.json), [34 casos](../semantics/r3/rust-r3.json), fontes/rótulos intactos | Denominador resolvível previamente fixado: 16; resultado 16/16 e 34/34 corretos |
| Negativos e revisão adversa | [4 contraprovas](../semantics/r3/counterproofs-r3.json), [3 extras](../semantics/r3/counterproofs-extra.json), freezes separados e falhas iniciais retidas | 7/7 conservadoras no final; zero promoção final. Const generic/módulo incorreto e mutabilidade com comentário/cfg escapado expuseram dois pares de promoções antes dos ajustes |
| Índice preservado A→B | [eventos](../semantics/r3/incremental-events.json), labels externos e output final com before/incremental/rebuild | Criar binding/export e trocar feature: Snapshot **inteiro** idêntico a rebuild B, incluindo estados, alvos, evidências, configuração, cobertura, gaps e derivações. Teste separado insere/remove shadowing |
| Amostra real de três módulos | [tokio-test-development.json](../semantics/r3/tokio-test-development.json), archive Tokio fixado `2fb5757a97a94b3173f8fdd7b6280423b63da6e6`, Cargo.toml e fonte confrontados pelo verificador | lib/io/task capturados como módulos originais; stream_mock/macros e dependências excluídos com gaps. **Não** é crate completo nem substitui o arquivo Tokio histórico |
| Qualidade real, separada das fixtures | 3 queries externas corretas: block_on resolvido; task::spawn e io::Builder unknown | Precisão 1/1 e recall 1/1 **das queries de declaração rotuladas**, cobertura 1/3. As 201 ocorrências extraídas ficaram unknown; não há recall/precisão rotulados de chamadas. 44 gaps lexicais, 8 atributos, 2 imports e 2 módulos ausentes explicam a perda |
| Primeiro consumidor P3 | [caso semântico](../semantics/r3/p3-consumer.json); prova independente da fixture P3 root em `final/p3-integration*` | Lookup lexical sugere old::target; ocorrência com alias local resolve new::target. Import na base e parâmetro unknown no head preservam revisão e evidência; sem sucesso de agente atribuído |
| Verificação independente | `verify_semantics.py`, 14 contraprovas Python, 13 testes Rust semânticos; [manifest final](../../docs/relatorios/logs/L5-continuacao/r3/final/manifest.json) | Contraprovas rejeitam corrupção de condições, binding, temporalidade, scope, ocorrência, source, snapshot, geração, contagem e eventos. CI usa override `XRAI_R3_RECEIPT_DIR` para conferir os outputs do alvo |

Todos os drivers/verificadores de R3 passaram localmente; os dez testes históricos R1/R2 continuam dentro dos treze testes semânticos, e seus sete testes de verificador preservaram replay dos recibos L4. As saídas mais antigas permanecem nos logs com os fingerprints de então; **`r3/final/` é a prova dos hashes congelados da entrega**. O manifest retém também fontes de implementação e os dois executáveis debug locais comprimidos, com hashes dos bytes originais, permitindo conferir quais binários produziram os diagnósticos. Esse registro local macOS27 arm64 não comprova Linux nem o piso literal macOS15.0. Aprovação nativa final será conciliada no relatório integrado da continuação L5.

Para replay: `semantics-spike eval/semantics/r3/<matriz>.json > <output>` e `python eval/scripts/verify_semantics.py <matriz> <output>`. Matrizes são rust-r3, counterproofs-r3, counterproofs-extra, tokio-test-development, incremental-events e p3-consumer. `language-reference-pin.json` e `incremental-labels.json` são metadados/rótulos externos, não matrizes. Testes: `python -m unittest discover -s eval/semantics/r3/tests -v`. O coletor append-only, os commands/exits e todos os hashes ficam em [logs R3](../../docs/relatorios/logs/L5-continuacao/r3/final/manifest.json).

Pendências para o Arquiteto: R4, dispatch/traits e as outras três famílias; ampliar formas lexicais e qualidade de referências reais, preservando os 201 unknown atuais como diagnóstico; configurar cobertura e mais amostras reais. Não houve decisão arquitetural bloqueante nova. Gates e critérios competitivos continuam fechados.

### Contraprova pós-revisão: forma cfg antes da lógica

Uma revisão independente do Implementador encontrou `any(feature="on", broken(option))` com `feature:on=known:true` promovido indevidamente: o avaliador confundia predicado fora do recorte com configuração válida desconhecida, permitindo que o true mascarasse a lacuna. [Oito casos adicionais congelados](../semantics/r3/counterproofs-cfg.json) incluem `any`/`all` com configuração conhecida, predicado não suportado, string escapada e nesting, além de dois controles de configuração válida desconhecida. A falha inicial foi preservada; o denominador original **34/16 não mudou**.

A correção propaga forma não suportada separadamente da ausência de conhecimento, sem aplicar curto-circuito que oculte a lacuna. Predicado fora do recorte permanece `not_evaluated` com gap; uma flag válida sem configuração continua participando da lógica trivalente. O verificador Python constrói/valida a árvore de predicados antes da lógica e exige o gap para condição não avaliada. Contraprovas rejeitam tanto falseamento do state quanto remoção do gap.

[Manifest da correção](../../docs/relatorios/logs/L5-continuacao/r3/cfg-review/manifest.json): novo conjunto 8/8 correto, zero promoção final; matriz original 34/34 e 16/16 resolvíveis preservada; um teste Rust semântico específico e 15 testes adversos Python passaram. Executável debug e fontes da correção estão retidos com hashes. `r3/final/` e seus recibos anteriores ficam intactos, ligados às fontes daquele momento. Nova prova nativa depende da publicação/CI integrada; M0-11 continua aberto.

### Conciliação nativa final da continuação L5

[CI38283109016](https://github.com/wkoch/xrai/actions/runs/38283109016), código `c48b599`, aprovou R3/P3 em Linux x86_64 e macOS15.7.9 arm64. Matriz R3 34/34 e16/16 resolvíveis preservada, oito casos cfg adicionais aprovados, zero promoção final nas contraprovas; os dois eventos conservam Snapshot inteiro incremental igual ao rebuild B. Quinze testes adversos R3 e13 de recibos P3 passaram por host. R1/R2 e controles anteriores permanecem aprovados. Os seis executáveis por host foram retidos e seus bytes conferidos contra os manifests; artefatos/expiração e provas em [conciliação final](../../docs/relatorios/L5-CONTINUACAO.md) e `logs/L5-continuacao/ci-fourth/native-verification.json`.

Essa prova encerra a pendência nativa da correção cfg, preservando as tentativas anteriores. Não conclui M0-11: 201 chamadas reais continuam unknown; R2 completo, R4, outras famílias e cobertura real ampliada seguem pendentes. Eventos R3 sintéticos não substituem A→B dos dossiês reais.
