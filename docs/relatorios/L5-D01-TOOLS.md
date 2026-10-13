# L5-C05 / D01 — API pública composta de rechecagem de ferramentas

Implementado `SessionToolGuard` em módulo prospectivo próprio: revalida snapshot/manifest/evidence e autoridade antes/depois de ferramentas e na finalização, compõe os métodos públicos existentes e preserva resultado delegado recusado pela fronteira. A lacuna técnica da pendência4 de L5-ADAPTER passa a ter consumer disponível **mediante adoção do factory novo**; o adapter histórico e seus receipts permanecem intactos. Não altera intenção seed/fake nem aprova M0-04, agent_run, provider, D1 ou gates.

## Implementação e decisões internas

`make_guarded_fake_session` constrói D01 e adapter com o mesmo snapshot, task/arm/run explícitos, clock e callbacks efetivos. Para D01, os callbacks de manifest/evidence também verificam a autoridade offline corrente contra a autoridade original; revogação/binding alterado durante a reserva impede compromisso/invocação. A API pública de rechecagem usa `EvidenceSnapshot.assert_current`, `record`, `revoke` e `invalidate`; não acessa `_check`, `_state`, `_lock` ou outros métodos/atributos privados da sessão original e não faz monkeypatch.

A observação copia bytes de manifest/evidence, fontes, configuração/produtor e campos da autoridade; não consome flags ready/verified. Sob lock curto, consulta o ledger público e deriva recusa por snapshot alterado, autoridade revogada/expirada/binding alterado, sessão invalidada, incidente/limite, fonte/configuração/produtor ou método alterado. A captura de callbacks de dados, handler, fake I/O e barriers fica fora do lock da guarda. D01 preserva sua seção crítica existente para os callbacks de admissão; o contrato desta composição exige callbacks de leitura limitados, sem transporte/provider. A aceitação de resultado e journal end são linearizados sob o mesmo lock; revogação posterior não reescreve uma aceitação anterior.

Journal novo tem begin/check/end, controls, bookkeeping e final, com sequência/hash-chain e prefixos do transcrito delegado. Precheck negado não invoca handler; postcheck negado não retorna seu resultado. Se o adapter já guardou tool_result, os bytes permanecem no transcrito original exportado e no end do guard. O replay verifica vínculo de ID/argumentos/resultado, public ledger, histórico de prefixos e contabilidade, distinguindo resultados aceitos dos retidos. Duas tools podem executar simultaneamente; dispatch não troca identidade enquanto houver tool ativa. Finalização espera operações terminarem e completed exige checks aceitos e nenhuma operação recusada.

## Critérios e evidências

| Critério | Contraprova/resultado |
|---|---|
| Manifest/evidence mudam entre dispatch e ferramenta | Precheck recusa; zero handler, nenhum retorno aceito; snapshot antigo/novo e invalidação pública mantidos no journal. |
| Manifest/evidence mudam durante handler | Barriers sem sleeps; índice trabalha sobre seus bytes imutáveis, delegado pode guardar resultado, postcheck recusa retorno e mantém o resultado. |
| Delegado guardou resultado antes da recusa | Fixture `evidence-after-delegate` possui tool_result completo e resultado end auditável; accepted_tool_results0, retained_but_not_returned1. Nenhum rollback/remoção. |
| Revogação/expiração/autoridade mutável | Revogação externa antes do compromisso produz fake0/reserva0; revogação durante handler é detectada antes do retorno; binding de budget/expiry/snapshot não é extensão silenciosa; expiry durante handler recusa. |
| I/O fake bloqueado permite controle | Revoke retorna enquanto transporte fake está bloqueado; após compromisso registra aborto/retém reserva virtual500, sem prometer zero invocações/cobrança. |
| Incidente de budget | Receipt fake acima do máximo cria incidente; guarda fecha novas admissões de tool mesmo que haja headroom global. Custo real de provider permanece desconhecido. |
| Retry e usage tardio | Tentativas distintas preservam call/retry e todas as reservas; receipt fake tardio repetido não duplica custo, changed é recomposto. |
| Tools simultâneas | Dois IDs/requests/results correlacionados no replay; não é permitida substituição de dispatch/finalização enquanto I/O está ativo. |
| Tipos/parser/bounds | Negativos re-selados rejeitam accepted1, timeTrue, agent_run/provider_charge falsos, ID/prefixo/resultado adulterados, changed falso; loader rejeita duplicação de chave, NaN/overflow e JSON não canônico. Frame/header/journal/record têm limites. |
| Fontes e histórico preservados | Receipt novo fixa hashes dos métodos consumidos, teste/coletor/verificador; quatro métodos históricos conferidos contra receipt aprovado e sete fixtures antigas byte-a-byte/SHA intactas. Verificador novo é read-only. |

Verificação local: **33 testes próprios PASS**, **11 fixtures/replays PASS** e consumer read-only PASS. Coletor final usa CPython3.15.0 de `/private/tmp/xrai-c05-tools/bin/python`; primeira execução dos23 casos iniciais também passou no runtime bundled. Nenhum build nativo, código upstream, provider, rede ou download. Logs: [`receipt.json`](logs/L5-C05/D01-tools/receipt.json), [`fixtures-replay.json`](logs/L5-C05/D01-tools/fixtures-replay.json), `tests.stdout/stderr` e coletor `prove.py`. Fixtures e README/API estão em `eval/adapters/guarded-v1/`; CLI read-only: `python eval/adapters/guarded-v1/verify.py`. Integração de workflow/CLI compartilhados pertence ao agente raiz.

## Limites e pendências do Arquiteto

1. Rechecagens são checkpoints de bytes/autoridade observados: não detectam ABA externo que restaure valores entre callbacks nem garantem um snapshot simultâneo de todo o filesystem. Handler lexical mantém bytes imutáveis verificados; sincronização de writers/storage exige decisão adicional para operação real.
2. Factory é composição de APIs Python, sem contenção de processo ou promessa contra caller que deliberadamente use o adapter histórico diretamente. Adoção explícita do consumer novo é necessária. Callbacks representam a fonte real do caller, não um serviço de autorização pago já implementado.
3. Clock inválido/regressivo ou overflow de prova falha fechado; pode deixar operação/journal incompleto, que não pode passar replay de finalização. Histórico delegado permanece disponível por `record`; não inferir resultado concluído de captura incompleta.
4. Header ≤512 KiB, frame ≤1 MiB, journal ≤8 MiB/128 eventos e record ≤16 MiB. Perfil de blobs grandes está pendente; não alterar receipts antigos para superar limite. Resposta/usage tardios entram antes de final; stream suplementar pós-final real permanece desenho futuro.
5. Provider/modelo/configuração reais, tokenizer do envelope completo, ceiling/janela/moeda/contenção e smokes pareados naturais continuam pendentes. Ledger exportado é exclusivamente virtual fake; provider_usage/provider_charge/model_tokens null. A lacuna de API de rechecagem foi tratada no perfil novo, sem converter scripted_retrieval em execução de agente/campanha.

Estado: consumer público composto e contraprovas estruturais concluídos; submissão/aceite CI e publicação registrados pelo agente raiz. Gates e elegibilidade global inalterados.

Recheck da raiz em Python3.13.13:33 testes e11 fixtures read-only passaram; integrado ao job Documentary contracts. [Checks completos](logs/L5-C05/root-preflight/checks.json). Publicação e conclusão CI regular registradas no relatório C05 corrente.

CI regular f7f940069f5a77e268c2fb9645835fc4b2cc8675/run38424961729 aprovada nos três checks Linux/macOS/contratos; job documental executou33 checks e11 replays read-only, preservando sete fixtures históricas. [API original](logs/L5-C05/root-preflight/published-code-ci-run.json). Nenhum receipt fake foi convertido em provider/campanha.
