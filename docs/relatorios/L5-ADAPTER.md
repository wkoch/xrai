# L5-05/L5-06 — boundary experimental de adapter e comparadores

Entrega: protocolo estrutural offline `xrai.eval.adapter-scripted.v1`, ligado ao dispatch D01 v2 e ao produtor lexical Python próprio. Não encerra M0-04/M0-12 nem libera D1. Trinta e sete testes passaram e sete transcritos foram recompostos; zero chamadas de rede/provider, zero builds nativos e zero execução de fontes upstream.

## Critérios implementados e evidências

| Critério do plano/revisão | Implementação | Evidência |
|---|---|---|
| Identidade task/arm/run/call/attempt e transcrito versionado | Cada frame possui identidade explícita, sequência e hash anterior; replay exige identidade do dispatch corrente, limites e campos exatos. Retries retêm o histórico D01 e metadados imutáveis. | `tests.stderr`; contraprovas re-seladas trocam final/usage/ledger/call/attempt e flags extras. |
| Recuperação/expansão ancorada no contexto atual | `ToolSnapshot` possui bytes imutáveis das fontes, configuração canônica real e produtor; recomputa seus IDs/hashes. Callbacks comparam bytes atuais antes/depois do handler. Recuperação BM25/TF-IDF e expansão deduplicada verificam hashes, spans UTF-8, texto e handles por conteúdo/configuração. | Fixtures `completed-bm25`/`completed-tfidf`; testes de mutação, configuração, spans false/float, hash/texto e reuso legítimo de handles. |
| Entrega limitada e falhas explícitas | JSON completo cabe no teto; expansão nunca trunca arquivos. Requests sem resposta sobrevivem em error/partial/cancelled e não podem terminar completed. Envelope semântico/parse permanece unknown e coverage se restringe ao capture. | `partial-unanswered`, `error-before-transport`; contraprovas alteram unknown/coverage/query/method/producer e removem respostas. |
| Cancelamento/invalidação durante execução | Barriers de eventos ordenam mutação/revogação enquanto handler próprio está bloqueado; não há sleeps nem resposta aceita depois da invalidação. O lock do wrapper não envolve o I/O fake D01. | Testes `source_mutation_during_handler` e `revocation_during_handler`; `cancelled-revoked` contém o ledger final revogado. |
| Uso/custo/timeout incertos distinguíveis | Ledger D01 retém a reserva virtual quando não há receipt; receipt fake tardio é idempotente. Final exporta o ledger atual, inclusive revogação, e retorna accounting identificado como virtual. Tokens/usage/cobrança de provider não observados continuam null. | `timeout-unknown`, `late-usage-idempotent`; testes de receipt repetido e adulteração de usage/charge zero. |
| Parser bounded, serializer e replay | Frame ≤1 MiB, transcrito ≤8 MiB/256 eventos, answer ≤64 KiB; rejeita duplicate keys, NaN, JSON não canônico, truncamento e eventos depois do final. Bytes do transcrito/schema/response são medidos exatamente. | Contraprova de frame >1 MiB dentro de transcrito <8 MiB; `fixtures-replay.json`. |
| Comparadores fortes sem substituição fraca | O manifesto retém Graft, trace-mcp, codebase-memory-mcp, code-review-graph, jCodeMunch, tokensave, ProjectAtlas e codegraph-mcp nos regimes common_local/best_documented_enriched. Documento fonte é ligado a bytes reais. Pin/install/configuração forte/autoridade ausentes geram recusa explícita para todos. | `comparator-plan.json`, `comparator-preflight.json`; testes rejeitam pin “latest”, receipt ready/verified, exclusão e regime fraco. |

Evidências: [`logs/L5-C04/adapter/receipt.json`](logs/L5-C04/adapter/receipt.json) fixa hashes do wrapper/testes/produtor lexical/D01 e dos documentos consumidos; [`fixtures-replay.json`](logs/L5-C04/adapter/fixtures-replay.json) fixa bytes/SHA e resultado de cada transcrito; [`prove.py`](logs/L5-C04/adapter/prove.py) registra o comando de teste, stdout/stderr e exit 0. O verificador read-only `eval/adapters/experimental-v1/verify.py` concilia as sete fixtures exatas, protocolo/parâmetros, SHA/bytes/replay typed, recusas dos oito candidatos, interpreter/version histórico e hashes atuais de wrapper/test/produtor/D01/documentos/coletor/verificador; compara a closure antes/depois e não executa comandos do receipt. Os exemplos estão em `eval/adapters/experimental-v1/`; a suíte é `crates/xrai-eval/harness/tests/test_agent_adapter_protocol.py`.

## API para integração

```python
capture = ToolSnapshot.capture(index, files, lexical_producer_bytes)
adapter = ScriptedAdapterProtocol(d01_session, index, capture,
    current_sources=read_current_owned_sources,
    current_producer=read_current_lexical_producer,
    clock=monotonic_clock)
adapter.dispatch_fake(attempt_id, call_id, fake_request(), virtual_ceiling)
search = adapter.recover(tool_call_id, query, method='bm25', top_k=5,
                         max_wire_bytes=65536)
adapter.expand(expansion_call_id, [item['id'] for item in search['snippets']],
               max_wire_bytes=65536)
raw = adapter.finish('completed', scripted_answer_bytes)
result = replay_adapter(raw)
```

`d01_session` deve ser o tipo próprio `DispatchSessionV2` com seu transporte fake. O wrapper não instala transporte de modelo e não transforma a chamada fake em agent_run. Callbacks fornecem bytes, não autorização. `reconcile_fake` mantém receipt/response tardios do mesmo attempt sem contar duas vezes. Root mantém CLI/workflows compartilhados; arquivos v1 e gates antigos não foram alterados.

## Pendências para o Arquiteto

1. Escolha e prova de provider/modelo/adaptador reais, versions disponíveis, serializer de provider, tokenizer e medição de ferramentas/usage/charge. Este protocolo não consulta documentação oficial de candidatos novos, não afirma compatibilidade externa nem inventa preço/modelo. O teto atual é de **bytes**; orçamento de tokens real segue pendente.
2. Autorização, janela, moeda/teto concretos e contenção de processo/sessão para chamadas reais. Os quatro smokes pareados reais previstos por M0-04/L5-05 (oito sessões-base) continuam ausentes; os transcritos atuais não os substituem.
3. Pins efetivamente instaláveis, setup observado e configuração enriquecida forte de cada um dos oito comparadores; critérios de exclusão documentados e denominadores comparáveis antes de campanha/ranking. M0-12 ainda requer campanha qualificada, repetições, checkouts separados e accounting completo de tentativas.
4. Definir a API pública de verificação de admissão D01 para usos de ferramenta posteriores a um dispatch: a interface atual observa revoke/expiry/invalidation e os próprios bytes de ferramenta; a recomposição dos callbacks de manifest/evidence do gate acontece no dispatch D01. O wrapper não acessa métodos privados para antecipar essa recomposição. Não há transporte pago nesta fronteira e nenhum flag do caller libera campanha.
5. A captura exportada deve caber no limite de frame depois de base64 e metadados; o corpus máximo lexical de 16 MiB pode ultrapassar o frame de 1 MiB. Este perfil falha de forma explícita; decidir formato de blobs separados/manifest antes de ampliar o capture. Receipts transportam produtor como **dados**, nunca executam esses bytes nem os tornam qualificação/admissão.

Estado: boundary e contraprovas estruturais implementados; adapter/provider real, comparadores fortes medidos e prova de agent_run permanecem pendentes. Não há julgamento, ranking, promoção de corpus nem autorização competitiva derivada destes arquivos.
