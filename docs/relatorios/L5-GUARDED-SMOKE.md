# L5-05 — consumer CLI guardado offline, checkpoint C06

Entrega prospectiva `guarded-smoke-consumer.v2`, adotando `immutable-request-dispatch.v3` após o achado da revisão C05 §2. Primeira tentativa v1 e seus source bytes/ZIP foram retidos em `logs/L5-C06/guarded-smoke/first-attempt`, sem relabeling.

Entrega implementada: `harness/guarded_smoke.py` chama o factory público D01 C05 e
consome seu guard em dispatch fake, recuperação BM25/TF-IDF, expansão, retry,
reconcile tardio e final. A entrypoint valida a matriz pré-congelada; não permite
bypass por uma flag de disponibilidade. O verificador separado recompõe recibos
readonly a partir de diretório ou ZIP regular conhecido. Fontes de upstream são
somente dados; ledger/adapter/dispatch/retriever/guard/recibos anteriores não foram
alterados por esta entrega.

## Freeze e universo efetivamente consumido

Antes do consumer: dez cenários e 27 inputs registrados em
`eval/adapters/guarded-smoke-v1/freeze.json`, SHA-256
`47a70dd00b62778429b347c2aef1847dac11ac91a28ad61a9126e4d6ed82354f`.
Matriz `scenarios.json`, SHA-256
`211a7aaa1929b822bb200b91bba97566e4e9d07ac6edc671d13ed08544846adf`.
As 22 fontes Go inteiras C04, 54.032 bytes, mantêm hashes originais e licença
capturada. A query GO-03 original é reutilizada como input de desenvolvimento.
Não houve escolha de fontes por hit nem relabeling após resultados; o perfil é
explicitamente o subtree Go completo previamente capturado. Task `D0-RS-01` é
somente o ID da fixture fake legada, sem claim de qualificação Rust/Go.

## Critérios e evidências

| Critério | Observação própria registrada |
|---|---|
| Caller público efetivo | Dez execuções de `run`; CLI `collect` conserva dez records e receipt. Sem acesso a privados ou patch do guard/adapter. |
| Task/arm/run/intent e snapshots | `smoke_seed`, `D0-RS-01`, `indexed`, run IDs únicos; input/review/oracle/manifest/evidence, arquivos inteiros/config/producer copiados em snapshots. Verificador compara snapshots completos aos bytes frozen atuais. |
| BM25/TF-IDF reais | Dois cenários completed; cada um tem 1 recover + 1 expand, envelopes completos recompostos pelo retriever original sem clipping e sem tokenizer. |
| Manifest/evidence antes da ferramenta | Cada cenário tem zero invocações de handler e zero resultado aceito; dispatch fake anterior permanece no histórico. |
| Manifest/evidence durante handler, depois antes do retorno | Cada cenário tem 1 invocação de handler, 1 tool result delegado retido e zero resultado público aceito/retornado; encerramento partial. |
| Fonte/producer alterado antes de recover | Zero invocações de handler; captura actual de ToolSnapshot falha por incompatibilidade entre bytes atuais e handler original (`callback_capture_failed`); encerramento partial. |
| Retry/late accounting | Duas invocações fake e mesmo logical call; reconcile tardio retorna `[true,false]`; primeira reserva desconhecida de 500 permanece; known fake observed 35, intervalo virtual `[35,535]`, custo total virtual incompleto. |
| Final alterado | Recover/expand já registrados continuam; final completed recusado por `gate_snapshot_changed`, seguido de partial. |
| Teto antes do uso e artefatos bounded | Intent/task/arm/run/query/ranking/teto/fonte são exatamente os frozen; ready/unknown/dup/nonfinite/oversize/depth/traversal recusados, sem output criado para manifesto inválido. |
| Receipt readonly | Closure exata de 11 JSON canônicos; hashes/bytes, binding método atual, guard journal, delegated prefix e ledger/history replays; retorno falso não pode virar resultado aceito. |

Prova completa preservada em `logs/L5-C06/guarded-smoke/owned-output.zip`:
3.605.445 bytes, onze membros, 10.618.544 bytes expandidos; SHA-256
`fabf5107495ead52ad09c54535f9577f0b4f8a7de115d18b6a747796ce1d9841`.
Os outputs `directory-verification.json`, `archive-verification.json` e
`pinned-runtime-verification.json` são byte a byte idênticos. O terceiro foi
recomputado por CPython 3.13.13, além da coleta e 31 testes por CPython 3.15.0.
31 testes passam, zero skips; substituições de identidade/retorno/custos/tokens,
JSON e ZIP são contraprovas. Warning de duplicate ZIP no teste negativo é
intencional, com exit code zero.

Desenvolvimento reteve falhas anteriores em `initial-*.stderr`,
`initial-tests.stderr` e `initial-collector-incident.json`: validação de ID
inicialmente não admitia os dígitos de `bm25`; classificação do source/producer
é callback capture failure efetiva, e depth passou a ser limite explícito 64,
independente da tolerância maior do Python 3.15. Cenários e fontes ficaram
inalterados durante os reparos. Todos os comandos/hashes e a prova final estão
em `development-evidence.json`.

## Escopo e pendências para o Arquiteto

Esta fatia fecha o caller offline explícito do factory C05 por composição com captura prospectiva imutável de request. [L5-D01-REQUEST.md](L5-D01-REQUEST.md) registra 25 testes adicionais e a limitação de ausência de observação de transporte independente no runtime. Permanece
`guarded_scripted_retrieval`, `agent_run=false`, campaign false, zero
provider/network/upstream/native observados. Teto/reserva/receipts são fake:
35 micro-USD observados sintéticos por receipt; nenhum custo/usage de provider
foi medido. `model_tokens`, `provider_usage` e `provider_charge` continuam null;
wire é a medição em bytes original, sem promoção ao token profile C05.

Persistem: adoção deste factory pelos futuros callers reais, provider adapter e
smoke pago com autorização efetiva, mecanismo para ABA/observação atômica de
filesystem, containment factual, corpus/admission/competitive run, conexão da
seleção lexical à avaliação P3. Nenhuma dessas pendências foi convertida em
critério atendido, card concluído, M1 aberto ou gate avaliado nesta entrega.
A integração do CI e publicação são responsabilidade do parent/root, com hashes
estáveis do consumer/verificador incluídos na prova; execução CI ainda não é
claim deste relatório local.
