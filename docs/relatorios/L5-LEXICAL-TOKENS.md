# L5-01 — envelope lexical sob cotas controladas de tokens, L5-C05

Implementada a medição prospectiva do produtor lexical existente, com BM25/TF-IDF e cotas 2k/4k/8k/16k/32k. O ranking, fontes, queries, labels e resultados originais permanecem intactos. A primeira verificação local cobriu código/freeze e contador sintético explícito. Depois, o agente raiz executou a medição no Python3.13.13 fixado, e o subagente recompôs os resultados usando o mesmo L4; a seção separada abaixo registra essas curvas controladas locais. **A autoridade de CI e uso/cobrança de provider continuam pendentes/desconhecidos.**

## Critérios e evidências

| Critério | Evidência | Estado/limite |
|---|---|---|
| Freeze antes do driver/resultados | `logs/L5-C05/lexical-tokens/freeze-before-driver.json`, `2026-10-13T15:11:18.011882+00:00`; driver/resultados ausentes | 99 pins de entradas originais + protocolo/rubrica/matriz e fonte do freezer; verificação final passou |
| Tokenizer L4 fixado | Perfil `l4:d9430ef6fbbc087da841dc7433b4d31857e33f48ea1ebd8c5556db6af3fe76c7`, loader original `offline_measurement.tokenizer()` | Python3.13.13, tiktoken0.12.0, regex2026.9.29, merges/config vendored; sem substituir perfil ou baixar dados de vocab |
| Whole wrapper e contadores autorreferentes | `driver.LexicalTokenDelivery`, JSON canônico completo com request ecoado, hashes, candidates, omissions, snippets e budget | Contagem até ponto fixo, 32 iterações; ciclo/insuficiência de metadata falha fechado e CLI preserva incident parcial; sem clipping |
| Curvas/casos reais | 16 queries congeladas ×2 métodos ×5 cotas ×2 repetições =320 registros, cada um busca + expansão; 32 baselines originais | Execução local pinned recomposta; autenticação CI pendente. Nenhum orçamento em bytes foi apresentado como tokens |
| Ranking/legacy preservados | Wire novo `lexical-token-delivery.v1`; envelope original inteiro no sidecar, `model_tokens:null` | Seleção posterior greedy de chunks integrais na ordem original; ranks não renumerados. Não há nova variante de ranking |
| Expansão | Chamada original com byte ceiling65.536, seguida de validação integral do wrapper | Arquivos completos deduplicados ou recusa do conjunto; razão original-byte, controlled-byte e controlled-token separadas |
| Avaliação externa | `external-rubric.json`, leitor `evaluate()` depois de selecionar todas entregas; source/anchor, distractors declarados e outros caminhos separados | Labels originais mantidos; sem precisão semântica ou anotação exaustiva; ressalvas GO-02/RS-03 preservadas |
| Verificação/replay | `verifier.verify(event)` recomputa baselines +320 pares, perfil, sidecars, tokens, IDs/spans, seleção e avaliação; closure354 arquivos | Recomposto localmente após raiz disponibilizar runtime/pacotes L4; CI autêntica pendente |
| Testes locais | `tests.stderr`:28 descobertos,27 passaram,1 prova factual CI ausente pulada | Contadores próprios explicitamente `synthetic-test-units-not-tokens`; não são resultados L4. Nada exportado como prova quantitativa |

Os dois métodos já existentes continuam usando as mesmas 82 fontes completas capturadas (819.020 bytes) e os mesmos parâmetros/chunks originais. O protocolo novo congela medição/seleção por orçamento, não redesenha ranking nem acrescenta uma terceira alternativa. Cota32k **não amplia** o top5 nem o byte ceiling65.536 do produtor original. Resultados poderão saturar antes disso e essa saturação deverá ser registrada, sem aumentar candidatos depois de observadas curvas.

## Entrega, custos e interpretação

O wrapper tem schema próprio. `budget.controlled_wire_tokens` e `wire_bytes` representam a resposta controlada **inteira**, incluindo todos os metadados entregues e os próprios contadores. O sidecar preserva o envelope original byte-for-byte e mede sua projeção original separadamente; também preserva wire Base64/SHA e hash dos token IDs. Os campos de provider e cobrança permanecem `null`.

A projeção do request inicial é medida separadamente (`controlled_request_projection_tokens`). O response wrapper ecoa esse request como parte de seus metadados, e esse eco também custa tokens no response. Não se deve somar os números e chamá-los de uso de provider: schema/orientação/prompts/transporte de um provider real não foram definidos, emitidos ou cobrados. Não há preço, custo financeiro, performance, vantagem competitiva ou sucesso de agente estimados.

Busca tenta cada chunk original, sem truncá-lo, mantendo sua posição/rank. Se um chunk exceder as cotas, poderá entregar um menor que vinha depois. A lista completa de candidatos e omissions entra no wire medido. Os detalhes de propostas rejeitadas permanecem em sidecar avaliador, explicitamente fora do wire que seria entregue. A mesma decisão é recomposta pelo verificador.

Expansão não transforma uma parte em arquivo inteiro: entrega bytes integrais ou recusa. O limite de bytes do produtor e o limite do wrapper continuam técnicos e distintos da cota em tokens. Nos campos de avaliação, unidade de busca é chunk; unidade de expansão é arquivo capturado integral. `chunks_omitted_by_controlled_limits` compara unidades realmente propostas pelo produtor com as entregues; handles repetidos de chunks da mesma fonte não contam como múltiplos arquivos perdidos, e uma recusa original em bytes não é reclassificada como perda causada pela cota de tokens.

Há dois arquivos declarados como distractors por família, presentes em cada universo de busca. A rubrica os fixa para localização da declaração esperada, depois de o ranking original já estar visível e antes das novas cotas serem executadas. Não é revisão cega/holdout nem anotação completa de irrelevância. Entregas de outros caminhos continuam `unannotated_other_file_chunks`; chunks da fonte esperada que não cobrem o anchor são contados à parte. O selector recebe apenas oito chaves de política, não a rubrica, annotations ou matriz.

GO-02 conserva o target de conversão de file URL, mas sua cláusula de rejeitar authorities inválidas não tem suporte na fonte. RS-03 conserva o anchor de leitura até EOF; `child.wait()` está em função vizinha. As ressalvas da [revisão de rótulos](L5-LEXICAL-REVISAO.md) não foram removidas dos denominadores, convertidas em novos anchors ou tratadas como comportamento confirmado. Anchors são declarações curtas, positivas em geral incluem nome exato, e as quatro negativas ainda compartilham uma string artificial. Nada disso se torna dataset independente pela presença de contagem exata.

## API, execução e arquivos

`LexicalTokenDelivery(index, encoding, profile, protocol)` em `eval/context/lexical-token-v1/driver.py` expõe:

- `search(query, method='bm25', controlled_token_ceiling=2000) -> {wire,sidecar}`;
- `expand(handles, controlled_token_ceiling=2000) -> {wire,sidecar}`;
- handle SHA lowercase64, lista de até5 distinta; query até16.384 bytes UTF-8; cotas inteiras até1.000.000, booleanos recusados.

O uso próprio sintético é opt-in por `synthetic_test_mode=True`, encoding com nome explícito e saída marcada como unidades de teste. O verificador de evidência factual rejeita essa marcação mesmo se o restante do JSON coincidir.

CLI collector: `python eval/context/lexical-token-v1/driver.py --output event`. CLI recomposição: `python eval/context/lexical-token-v1/verifier.py --output event`. Checagem documental sem tokenizer: `--design-only`. Teste factual usa `XRAI_LEXICAL_TOKEN_OUTPUT=event` com `test_lexical_tokens.py`; sua ausência explica o skip local, nunca sucesso factual.

Event completo tem354 arquivos: `preregistered.json`, `evaluation.json`, `baselines/000..031.json`, `records/000..319.json`. Teto64MiB total e512KiB/arquivo. Fonte/bindings incluem nove arquivos novos de código/protocolo/workflow/test/requirements, mais os99 pins originais; CI imprime Python/pacotes e preserva collector/verificação/testes fora do event. O autenticador API/ZIP dedicado pertence ao agente raiz, não à seleção lexical. Pinned packages podem ser instalados pela CI autorizada; o loader de tokens consome somente vocab/config vendored.

## Resultados controlados locais, separados da prova CI

A raiz disponibilizou `/private/tmp/xrai-c05-lexical-tokens-local`; seu environment GITHUB tem quatro valores `null`. A recomposição própria por Python3.13.13 foi idêntica ao stdout da raiz, com354 arquivos e20.492.762 bytes. Com o event local fornecido via `XRAI_LEXICAL_TOKEN_OUTPUT`, os28 testes passaram sem skips em `local-pinned-tests.stderr`; esse teste factual verifica contagem pinned, não autenticidade CI. `local-controlled-review.json` retém curvas, SHA/bytes de cada arquivo e fontes; `local-controlled-verification.json` retém a recomposição. O dataset completo local permanece no path temporário indicado e poderá desaparecer; a cópia completa autenticada da CI é pendência de preservação.

Os32 envelopes originais mediram267–3.325 tokens controlados L4. Busca encapsulada mede531–3.962: o wrapper inteiro agrega hashes/metadados/request echo, sem reinterpretar `model_tokens:null` do original como provider. Os resultados abaixo contam12 queries positivas **distintas** por método/cota; o JSON tem24 por incluir duas repetições deterministas. File hit12/12 em todas as cotas nos dois métodos; negativas4/4 sem snippets também em todas.

| Cota controlada | Busca BM25 anchor | Busca TF-IDF anchor | Expansão BM25 file/anchor | Expansão TF-IDF file/anchor |
|---:|---:|---:|---:|---:|
| 2k | 8/12 | 9/12 | 1/12 | 1/12 |
| 4k | 10/12 | 11/12 | 0/12 | 1/12 |
| 8k | 10/12 | 11/12 | 5/12 | 5/12 |
| 16k | 10/12 | 11/12 | 9/12 | 9/12 |
| 32k | 10/12 | 11/12 | 9/12 | 9/12 |

Em2k, BM25 perde os anchors de PY-02/PY-03 além das ausências originais RS-03/JS-01; TF-IDF perde PY-01/PY-03 além de RS-03. Em4k a busca restaura os anchors do baseline original e entrega todos os seus candidatos; acima disso a busca satura. Essa comparação mede anchors literais, não conclusão das perguntas/claúsulas ou vantagem em tarefa de agente.

A expansão **não é monótona** quando os handles vêm da busca sob cada cota: GO-03/BM25 em2k entrega apenas chunks de `shellquote.go` e seu arquivo integral cabe; em4k a busca adiciona `string.go`, `error.go` e `url.go`, e a união de arquivos inteiros é recusada sob a mesma política all-or-none. Não é tuning nem defeito do contador: mudam o request de expansão e o conjunto de arquivos com a cota. Uma escolha de handles feita por agente seria outra política/tarefa, ainda não avaliada.

Em16k/32k restam as três queries Python recusadas pelo byte ceiling original, não pela cota de tokens. Por grupo/método,6 recusas de bytes no JSON são3 queries×2 repetições. Nenhum32k contorna65.536 bytes nem aumenta o top5. Metadata/recusa também ocupa tokens: a resposta de expansão sem entrega ficou entre404 e1.134 tokens nas curvas com recusas; não é token zero.

Distractors declarados entregues na busca:1 chunk por método em2k e2 em4k+ por execução distinta. Outros caminhos sem anotação entregam5 chunks BM25/4 TF-IDF em2k e28/27 em4k+ por conjunto de16 queries. Esses outros caminhos são de relevância desconhecida, não falsos positivos confirmados. As expansões maiores também incluem conteúdo desses caminhos; custo/pertinência não deve ser inferido só de file hit. Todas as contagens do wire final respeitam simultaneamente as duas cotas controladas; nenhuma interpretação financeira/provider foi acrescentada.

## Pendências

1. Produzir na CI3.13.13, reexecutar o teste factual sem skip e autenticar API+ZIP+recomposição. O receipt de testes sintéticos declara `actual_token_measurement:false`; o review local posterior declara `actual_pinned_tokenizer_replay:true`, sem autoridade CI. Preservar essa distinção.
2. Revisar curvas reais de file versus anchor, recusas de expansão e custo de metadata/request; registrar falhas sem tuning de parâmetros/labels.
3. Integração com agente/provider e custos de schema/orientação/usage real continuam desconhecidos. Contagem controlada não fecha orçamento do provider, agente real, D1 ou gate global.
4. Holdout prospectivo, negativas naturais diversas e correções GO-02/RS-03 exigem novo conjunto congelado antes da execução. Os originais desta campanha continuam preservados.
5. Comparação final P3 versus baseline lexical sob mesmas tarefas, contexto e orçamento completo permanece pendente. Nenhuma promoção de M0/L5-01 global nesta entrega local.

Exploração estrutural usou skill codebase-memory/graft; coverage Tier2 final dos cinco paths novos/relacionados: geração `2026-10-13T15:30:07Z`, metadata_match/no_recorded_issue, sinal best-effort. Graft reportou23.133 tokens poupados em1 chamada desta frente. Nenhum binário do projeto/upstream ou provider foi executado localmente; nenhuma aquisição nova por este subagente. Commit/push cabe ao agente raiz.
