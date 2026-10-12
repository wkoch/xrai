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
