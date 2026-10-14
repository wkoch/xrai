# L5-05 — fronteira pública do transporte fake

14/10/2026, Implementador. Perfil prospectivo `public-transport-session.v1`,
conforme §4 do fechamento C06. O consumer concreto usa o mesmo dono público de
sessão para dispatch, snapshot e reconciliação. Nenhum arquivo histórico da guarda,
ledger, immutable v4 ou consumer v3 foi alterado.

## Implementação

`transport_receipt_session.py` deriva o owner de `DispatchSessionV2` e reutiliza
integralmente `_State`, lock, checks, autorização, transições e reconciliação
financeiras. O override organiza apenas a captura e a fronteira pública; não
implementa outra máquina financeira. O adapter built-in exigido pelo construtor
histórico inicializa a autoridade herdada e permanece sem invocações. O transporte
novo recebe bytes imutáveis via `send`, emite observações reais na sua entrada e
na resposta; o owner confere os receipts ao recebê-los. I/O/barriers ficam fora do
lock; a publicação de observações e o snapshot usam o mesmo lock curto.

Lógico e wire são distintos. O envelope wire completo, LF, versão, tamanho e
SHA-256 são preparados antes de reservar. Não há novo decode do dict do chamador
no envio. O receipt da entrada vincula task/arm/run/call/attempt e o hash do evento
financeiro de commit, além do lógico e dos bytes wire efetivamente consumidos.

Replay puro reexecuta o ledger original e valida a bijeção de todos os requests,
capturas, términos, entradas, respostas e reconciliações tardias. Prefixos do
ledger e hash-chain observados preservam ordem/correlação. Receipts são evidência
local reprodutível, sem assinatura remota; reescrever consistentemente todo o
método/input não seria autenticação de provider.

## Evidências de aceite

[Consumer concreto](logs/L5-C07/Transport/public-consumer.json), [recomposição](logs/L5-C07/Transport/verification.json)
e [38 testes](logs/L5-C07/Transport/tests.stderr), Python 3.15.0 local, sem skips.

| Critério | Teste / evidência |
|---|---|
| Wire diferente do lógico e bytes consumidos | `test_final_wire_differs_from_logical`; receipt inteiro do caso response |
| Mutação do chamador antes/depois de commit | `test_caller_mutation_before_commit`, `test_caller_mutation_after_commit`; mutated-caller |
| Truncamento, serializer/attempt/commit errados | Tests `truncated_wire`, `public_wire_truncated_refuses_before_entry`, `wrong_live_*`, `wrong_serializer`, `wrong_attempt`, `wrong_commit` |
| Recusa antes de entrada com ausência factual | pre-entry; nenhuma reserva/commit/entrada |
| Entrada seguida de exceção/timeout | exception/timeout, entrada=1, reserva incerta retida=500 |
| Retorno ausente | no-return, entrada=1, resposta=0, reserva retida=500 |
| Receipt omitido/duplicado/fabricado | Tests `omitted_*`, `missing_*`, `duplicated_entry_receipt`, `duplicate_live_receipt_cannot_be_adopted`; reseal não remove recusa |
| Retry e resultado tardio idempotente | retry-late, duas entradas/identidades próprias; receipt financeiro conta uma vez; repetição não publica evento |
| Snapshot em execução | inflight explicitly active, incomplete; fechamento recusado; `snapshot_during_actual_entry_io` |
| Cancelamento e lock sem I/O | `cancel_before_commit_no_entry`, `revoke_during_io_lock_free` |
| Custo desconhecido conservado | resposta fake sem recibo financeiro conserva reserva; receipt sintético tardio pode reconciliar somente o ledger fake |

São oito records: sete fechados e uma observação inflight sobre a mesma operação
final de mutated-caller. Não somar essas duas observações como duas chamadas.
Contagens distinguem requests/reservas/commits/entradas/respostas; resposta
observada recusada pelo owner não é automaticamente resposta financeira aceita.

Limites reais: 16 requests incluindo capturas pendentes/recusas; 128 eventos;
128 KiB por objeto lógico/wire/resposta; 16 MiB para record/proof no replay. Sem
medição de tokens, cobrança real, envio remoto, modelo, agente ou qualificação.
O authorization/ledger herdado mantém teto agregado e reservas incertas no retry.

## Pendências para o Arquiteto / integração

A prova encerra somente a interface pública fake local. A ponte Store aguardará
seu binding prospectivo e API retida; o request sintético desta fatia não representa
um checkout completo. ABA/fencing monotônico e blobs permanecem abertos. Não houve
provider, Django, subprocesso nativo ou projeto upstream local. O replay aceita
somente os hashes reais do método atual; receipts históricos foram preservados.
Verificação CI Python 3.13 é posterior à publicação, distinta dos 38 testes locais.

## Correções da revisão independente

O reviewer Django encontrou duas contraprovas no método inicial: remoção de entry
mais entry_observed=false resealed ainda passava após exception; resposta tardia
maior que128KiB mutava o ledger antes da recusa. Fonte/records/contraprova iniciais
foram preservados em `logs/L5-C07/Transport/pre-repair/`. O método atual fixa um
plano fake antes da reserva; os caminhos exception/timeout da fonte fixa exigem
entrada. Reconcile limita e captura resposta/receipt antes de tocar a autoridade
financeira. Dois testes novos verificam rejeição consistente e snapshot preservado.
