# L5-01 — recuperação lexical real, entrega local L5-C04

Implementado um recuperador lexical independente da ablação P2/P3 existente. BM25 e TF-IDF cosseno recebem os mesmos bytes de fontes reais, tokenização, chunks, consultas e orçamento. A entrega comprova recuperação lexical em subárvores capturadas, sem promover resolução semântica, sucesso de agente, completude dos repositórios ou gates do plano.

## Aceite e evidências

| Critério | Evidência | Estado/limite |
|---|---|---|
| Congelar entradas antes do algoritmo | `logs/L5-C04/lexical/freeze-before-algorithm.json`, timestamp `2026-10-13T01:02:02.642273+00:00`; retriever e resultados ausentes; SHA por ativo | Verificado; não houve relabel/tuning após resultados |
| Fontes reais, quatro famílias | `eval/context/lexical/manifest.json`, arquivos integrais em `sources/`, arquivos de licença e pins dos quatro tarballs já retidos | 82 arquivos, 819.020 bytes, 832 chunks; captura explícita abaixo |
| Baseline lexical competente | `crates/xrai-eval/harness/lexical_retrieval.py`, BM25 com IDF positiva e normalização por comprimento | Implementado; parâmetros fixos antes do código |
| Alternativa comparável | TF-IDF cosseno com TF sublinear e IDF suavizada, mesmo universo/tokenizador/chunks/limite | Implementado; resultado não favorece necessariamente BM25 |
| Consultas/rótulos separados do algoritmo | `queries.json` (16), `expected-labels.json` separado; `benchmark.py` passa só query e bytes, lê rótulos depois de coletar todos os outputs | Verificado; segunda leitura independente dos rótulos pendente |
| Ranking e provas de fonte | Outputs completos em `logs/L5-C04/lexical/benchmark.json`: caminho, byte-span, texto, SHA da fonte e trecho, score, rank, snapshot/config/producer | Bytes recalculados para as 64 células; interpretação semântica desconhecida |
| Orçamento e expansão | JSON canônico inteiro medido, limites/contraprovas no teste; API literal em `api-example.json` | 773–10.447 bytes nas buscas, teto 65.536; expansão integral ou recusa, sem truncar |
| Matriz congelada/reprodutibilidade | `matrix.json`: 16 consultas × 2 métodos × 2 repetições, seed 20261012, ordem declarada | 64 células; saídas idênticas entre repetições. Repetições não são amostras independentes |
| Testes próprios sem execução upstream | `tests.stderr`: 27 testes, OK; benchmark/asserts próprios; verificação final do freeze | Verificado localmente com Python 3.15.0; nenhuma execução native/upstream/download |

A captura reutiliza arquivos já retidos, sem aquisição nova:

| Família | Repositório/pin registrado no manifesto | Universo capturado | Arquivos / bytes / chunks |
|---|---|---|---|
| Rust | rust-lang/rust-analyzer `3a5f65784a90278fa1de97fe89a7a529dd44765a` | `crates/stdx/src/**/*.rs` | 13 / 76.529 / 83 |
| TS/JS | facebook/react `77912d9a05d7a90287fabdec76486f25869b2981` | `packages/react/src/**/*.js`, excluindo testes separados | 28 / 112.122 / 132 |
| Python | scikit-learn/scikit-learn `156ef141f3b270edb06c8ae9af37c55253c0aabe` | `sklearn/metrics/**/*.py`, excluindo diretórios de testes | 19 / 576.337 / 544 |
| Go | go-gitea/gitea `8eefa1f6dedf2488db2c9e12c916e8e51f673160` | `modules/util/**/*.go`, excluindo `*_test.go` e testes separados | 22 / 54.032 / 73 |

O manifesto enumera cada arquivo selecionado e cada omissão dentro do prefixo, com motivo, além de contagens/motivos fora dele. Não enumera individualmente os caminhos fora do prefixo: os tarballs pinned preservam esse universo e a contagem delimita a cobertura. Arquivos de produção retêm comentários, docstrings e testes inline; não há filtragem por acerto, LOC efetiva ou parsing. Arquivo vazio de Python consta na cobertura sem gerar chunk. TS/JS aqui é JavaScript real com anotações Flow; não cobre TypeScript geral. Tags Go, configuração Rust/Python/JS e semântica Flow não são interpretadas.

## Método e resultados

Tokenização preserva identificadores Unicode completos com casefold e acrescenta componentes snake_case e camel/PascalCase (heurísticas de caixa ASCII); caminho entra com peso 3. Chunks de 40 linhas, overlap 10; spans são offsets exatos em bytes UTF-8. Ordenação: score decrescente, caminho/início/fim; trechos sobrepostos da mesma fonte são removidos e score zero não é entregue. Comentários e palavras comuns também contribuem; não há stoplist, stemming ou nomes de repositório hardcoded.

BM25 usa `k1=1.2`, `b=0.75`, IDF `ln(1+(N-df+0.5)/(df+0.5))` e termos distintos da consulta. TF-IDF usa `1+ln(tf)`, IDF `ln((N+1)/(df+1))+1` e normalização cosseno. Ambos foram fixados sem ajuste posterior. Ranking mede chunks; `file_hit_at_k` usa o primeiro chunk da fonte esperada entre os k resultados, não um ranking novo de arquivos únicos.

| Métrica por consulta distinta | BM25 | TF-IDF cosseno |
|---|---:|---:|
| Fonte esperada em @1 | 11/12 | 11/12 |
| Fonte esperada em @3 e @5 | 12/12 | 12/12 |
| MRR da fonte | 0,958333 | 0,958333 |
| Anchor literal coberto em @5 | 10/12 | 11/12 |
| Negativas sem resultado lexical | 4/4 | 4/4 |

As agregações JSON têm denominador 24 para positivos e 8 para negativos porque incluem as duas repetições; a tabela acima remove a duplicação determinista. Métricas por família e scores brutos estão preservados no JSON. As consultas negativas usam um identificador ausente dos bytes, comprovando ausência lexical dentro da captura, não entendimento de perguntas sem resposta. Positivas incluem nomes de símbolos e são relativamente diretas; não equivalem a um conjunto independente de tarefas reais de agentes.

Falhas mantidas: `RS-03` nos dois métodos localiza a fonte, mas os trechos escolhidos não incluem o anchor `pub fn streaming_output`; `JS-01` no BM25 localiza a fonte, mas não inclui `function resolveDispatcher`. TF-IDF cobre esse anchor JS. Nenhuma consulta, rótulo, hiperparâmetro ou limiar foi alterado para eliminar falhas. Resultados da primeira execução estão retidos em `first-run/`; depois foi endurecida somente a imutabilidade de mappings/configuração, sem alteração de ranking, spans ou métricas.

## Contrato/API

`LexicalIndex(files: Mapping[str,bytes], chunk_lines=40, overlap_lines=10, path_term_weight=3, k1=1.2, b=.75)` copia os bytes, valida caminhos relativos normalizados/UTF-8 e limita 128 fontes, 1 MiB/fonte, 16 MiB/snapshot e 4.096 chunks. Não importa nem executa linguagens das fontes. `snapshot_id` vincula caminho/SHA/comprimento; `configuration_id` vincula parâmetros/tokenizador/SHA do próprio produtor. O produtor final está registrado no JSON de resultados.

`search(query, method='bm25', top_k=5, max_wire_bytes=65536)` retorna `lexical-delivery.v1`, IDs, SHA da consulta, status, snippets e cobertura. Cada snippet contém `id,path,start,end,source_sha256,snippet_sha256,text,score,rank`. Status: `lexical_matches`, `no_lexical_match_captured_scope` ou `insufficient_byte_budget`. Chunks que não cabem são omitidos inteiros; chunks posteriores menores podem caber. Não há clipping. Um orçamento que não comporta nem o envelope/refusa completa lança `ValueError`.

`expand([snippet_id], max_wire_bytes=65536)` deduplica caminhos e entrega cada arquivo capturado integral, com o mesmo vínculo de bytes, ou recusa o conjunto inteiro. Status: `expanded_full_captured_files`, `unknown_handles`, `insufficient_byte_budget`; recusas estruturadas em `refusals`, input preservado em `requested_ids`. Handles de snapshot/configuração diferentes são rejeitados; índices com conteúdo/configuração idênticos têm IDs idênticos. Isso é integridade de conteúdo local, sem promessa de autorização, TTL ou retenção P3.

`wire_bytes` mede **o envelope canônico inteiro**, serializado por `wire_bytes()` com `ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False`, incluindo a própria contagem até ponto fixo. Outra serialização pode ocupar mais bytes. Cobertura sempre explicita `captured_scope_only=true`, `whole_repository=false`, `parse_status=unknown`, `semantic_status=unknown`. `model_tokens` e custo são `null`, não estimativas de caracteres/bytes.

## Pendências para o Arquiteto

1. Revisão independente dos 16 rótulos e desenho de tarefas/holdout mais exigentes. A autoria do implementador permanece declarada no freeze; não substituir silenciosamente os arquivos congelados.
2. Selecionar/autorizar adaptador e tokenizer pinned para medir tokens do envelope inteiro sob orçamento de modelo. Bytes não comprovam esse critério. Provider/custo/sucesso de agente não foram executados nem estimados.
3. Integrar a API lexical ao contrato de contextos/expansão e à campanha de agentes real; o executor atual é `scripted_retrieval`. O worker D01 recebeu API e fixture, mas integração não muda a natureza desta matriz.
4. Comparação final sob tarefas, ambientes e orçamento comuns com P3. Esta entrega cria baseline lexical competente e alternativa, mas não prova vantagem competitiva nem fecha L5-01 completo/gates.
5. Decidir se amplia cobertura além das quatro subárvores e separa TypeScript de JS/Flow. Universo inteiro dos repositórios não foi indexado pelo algoritmo.

## Exploração e reprodução

Estrutura consultada via skill codebase-memory/graft antes das fontes; `context_spike` e `eval/context/README.md` confirmam que a ablação P2 não substitui um lexical otimizado. Graft lexical: 1 chamada, 28.765 tokens poupados informados pelo próprio tool. Coverage Tier2 dos quatro scripts novos: geração `2026-10-13T01:09:50Z`, `metadata_match/no_recorded_issue`, sinal best-effort. O indexador reportou parsing inutilizável de três arquivos JS/Flow capturados; retrieval usa bytes integrais, sem reutilizar esse grafo como prova semântica.

Reprodução autorizada: `python eval/context/lexical/freeze_inputs.py verify`; `python eval/context/lexical/benchmark.py`; `python -m unittest discover -s crates/xrai-eval/harness/tests -p test_lexical_retrieval.py -v`. Executar `freeze` novamente é recusado após existir algoritmo/receipt. Nenhum Cargo/import/build/test upstream, provider ou download é necessário. Entrega delegada sem commit; publicação cabe ao agente raiz.

Primeira CI regular `1130fbd`/38331218569: job macOS falhou antes de fmt/clippy/testes, na instalação do toolchain por conflito `bin/cargo-clippy` do ambiente existente. Log original e diagnóstico em `logs/L5-C04/lexical/ci-attempt-1`. Correção prospectiva usa RUSTUP_HOME novo no runner temporário mantendo Rust1.98.1 pinned; não altera algoritmo/labels/resultados congelados. Revalidação CI pendente neste checkpoint.

Fechamento da mesma CI: Documentary contracts e Linux aprovados; macOS falhou apenas instalação/ausência de artefato subsequente. Dois probes upstream históricos skipped. API original do run também retida; próxima CI recompõe todos os checks após a correção do ambiente.
