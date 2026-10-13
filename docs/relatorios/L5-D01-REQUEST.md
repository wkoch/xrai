# L5-05 — identidade prospectiva do pedido, D01 v3 / C06

A revisão C05 §2 identificou releitura do dict original depois de reserva e
compromisso em v2. Novo módulo `harness/immutable_request_dispatch.py` compõe
exclusivamente os APIs públicos existentes e captura request em JSON canônico,
privado, uma única vez na entrada. Só seu decode privado chega ao guard/v2; o
objeto do caller deixa de ser relido por v2. A representação autoritativa é bytes:
mesmo que o adapter mude sua cópia descartável, reserva/canonical authority ficam
intactos. v2, guard, adapter, sete fixtures e recibos históricos não foram editados.

O consumer CLI C06 passou do primeiro profile `consumer.v1` para
`guarded-smoke-consumer.v2 + immutable-request-dispatch.v3`, sem alterar os dez
cenários freeze anteriores. Primeira tentativa v1, source bytes, hashes, logs e
ZIP permanecem em `logs/L5-C06/guarded-smoke/first-attempt`. O novo consumer adota
`make_immutable_guarded_fake_session`, que internamente chama o factory público
original, e inclui `immutable_request`/replay em cada cenário.

## Aceite, freeze e execução observada

Doze controles frozen antes do wrapper em `immutable-request-v1/freeze.json`,
SHA-256 `1c9c1e5309291208da79dbf77178cbd64f696b6a6e971ee7cdea2557e4b9fdf8`.
Module final SHA-256
`0ff3fc2abc5a420ab2ae76945f244dcd046c3ac766b8ceb138a55dc66423eb7f`.

| Critério | Evidência |
|---|---|
| Falha antes / correção depois | Teste histórico chama v2 público, muda request depois de reserve e observa hash fake divergente. Com wrapper privado, mesmas mutações em mensagem, output_tokens, tool definitions e listas aninhadas, antes e depois de commit, mantêm entrada fake byte a byte igual ao pedido reservado. |
| Entrada fake efetivamente observada | Spy Python exclusivo dos testes, sobre a entrada pública `FakeTransportV2.invoke`; raw/hash preservados em `proof.json`, não inferidos do ledger. Spy não é instalado pelo módulo/consumer runtime. |
| Authority não modificada pelo adapter | Spy diagnóstico muda o dict descartável que o fake recebeu; caller/canonical bytes/request reservado permanecem idênticos. Não há afirmação de comportamento de provider arbitrário. |
| Registro prospectivo | Request version, payload/base64/bytes/hash, task/arm/run, call/attempt/retry, limite e authorization ligam v3 ao ledger público e à reserva canônica. Projection committed privada tem os mesmos bytes. |
| Replay recusa adulteração | Hash/bytes/version/request/identidade/authorization/max/retry/projection alterados falham; segundo guard admission recusado sem tentativa ledger fica correlacionado ao begin/end público de guarda, com zero projection. |
| Reserva/compromisso/cancelamento | Cancel antes de commit produz zero invocações, zero reserva retida e zero projection. Cancel depois do commit permite fake efetivo e mantém 500 micro-USD virtuais quando receipt falta; before-transport failure libera reserva, uncertain retém. |
| Retry/late receipt | Duas tentativas same call, primeira sem receipt mantém 500; segunda reconcilia receipt fake tardio exatamente uma vez e replay permanece idempotente. |
| Adopção pelo caller | Dez fluxos consumer v2 executados, recover→expand/final com request v3 e recusas; 31 testes consumer + 25 testes D01, todos passando, zero skips. |

`logs/L5-C06/D01-request/proof.json` preserva seis diagnósticos completos,
source closure e os observados; `verify.py` recompõe dados readonly, sem executar
spy/transporte. CPython 3.15.0 coletou/testou; CPython 3.13.13 recompôs a mesma
prova. Verificações são byte a byte iguais. Comandos/hashes estão em
`development-evidence.json`; CI e publicação ficam com o integrador.

A revisão independente pré-publicação encontrou aceitação indevida de relato de falha sobre retorno público aceito e binding de request divergente em tentativa não reservada. Reparo: guard result/error agora coincide exatamente com o `end` público; erro direto só usa enum unobserved quando o lifecycle desta tentativa contém a dupla de eventos de falha D01 correspondente; hash de payload==manifest vale também para refusals não reservados. Contraprovas incluem erro de outra tentativa e begin guard re-selado. Source/prova preliminares ficam em `D01-request/pre-review` e ZIP consumer em `guarded-smoke/pre-review-v2`; freeze12 foi preservado.

## Limitações e pendências

Runtime registra **projeção derivada da captura privada**, e não um recibo
independente da entrada do transporte. `transport_observed_independently=false`
é explícito no replay; igualdade factual de entrada fake foi provada só pelo spy
controlado de testes. Um adapter futuro requer seam público para recibo do payload
realmente enviado, especialmente antes de paid I/O. Não usar profiler no executor
para contornar ausência desse contrato.

Dict requer ausência de escrita concorrente durante validação/captura; bytes
imutáveis são a entrada preferida. O módulo não torna filesystem ou callback
externo atômico. Capturas de sessão permanecem próprias/imutáveis, mas authority
revocation por geração monotônica e garantia contra A→B→A externos não foram
implementadas. Blobs grandes precisam novo perfil/store privado/receipt agregado;
não houve aumento de frame/journal para esconder duplicação.

Escopo continua offline-fake/scripted; nada pago, native/upstream/network ou
agent_run. Teto/reserva/custo são sintéticos, provider usage/charge/model_tokens
null. Corpus, M1, gates, cartões e competitividade não avançam por esta prova.
