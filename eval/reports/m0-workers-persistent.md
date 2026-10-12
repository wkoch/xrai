# M0-06 / L4-02 — primeiro incremento funcional XRW2

12/10/2026. Implementação de desenvolvimento conforme ADR 026 §§1–2 e recorte de entrada da revisão L3. **M0-06 permanece aberto:** este incremento verifica protocolo, reutilização e lifecycle; a matriz comparativa e CPU/RSS nativos ainda faltam. XRW1, sua semântica de EOF/exit0 e seus testes não foram modificados.

## Implementação e ownership

`crates/xrai-eval/src/worker_persistent.rs` e binário `worker-persistent` usam modo explícito `worker`; `demonstrate` produz receipt JSON do smoke. Frames XRW2 têm magic/versão 2, tipo, tamanho e encarnação aleatória de 256 bits obtida do `/dev/urandom` nos dois hosts suportados. Hello/Ready fixam sete dialetos, fingerprints de produtores e limites. Parse/Result preservam identities request/attempt/source/producer/configuration. Tipos desconhecidos, estado inadequado e encarnações incorretas falham.

Antes de alocar corpo, os limites por mensagem são Parse 8 MiB+256 bytes de envelope, Result 16 MiB+256, Hello/Ready 64 KiB e Shutdown vazio. Decode conserva os limites de fonte/resposta e valida hash/produtor. Campos duplicados no payload JSON precisam concordar com envelope: dialeto, complete, comprimento, nodes, matches e spans. Coordenadas de diagnósticos são verificadas contra bytes da fonte, inclusive CRLF; completa/diagnósticos precisa ser consistente. O mapa de inícios de linha é construído uma vez, com lookup binário por diagnóstico, evitando revarrer prefixos para cada span. Validação do pai verifica deadline após JSON, durante scan/diagnósticos e antes de publicação. Result validado conclui o pedido sem EOF, após confirmação supervisionada de que o writer concluiu o pedido. Um peer pode responder antes de consumir a fonte: frame inválido causa kill/reap antes do join; mesmo um Result válido não permite join ilimitado de writer bloqueado. Completion do writer respeita cancelamento/deadline por canal separado. Morte posterior não revoga resposta já entregue; duplicata ou tentativa antiga nunca completa o próximo pedido.

Cada um dos dois threads de serviço possui no máximo um processo/pedido em voo. O cache contém Parser e Query por dialeto com produtor fixado; reset antes/depois e parse sem árvore antiga eliminam estado de fonte/configuração anterior. AST, diagnóstico e QueryCursor temporários são liberados antes de Result. A igualdade integral com `worker_spike::direct` é testada depois de alternar sete dialetos, configurações, fontes incompletas e repetição.

Timeout/cancelamento/violação retiram o processo: kill, `wait` confirmado antes de registrar reaped, fechamento de canais e join dos readers/writer. Retry tem no máximo uma nova tentativa/processo, somente transporte/crash, dentro do deadline total de 5 s; caller não pode ampliá-lo. Incremento de attempt usa arithmetic checked. Erros de protocolo/identidade/limite/cancelamento não dão retry. Poll de Idle a cada recepção de fila com timeout de 10 ms detecta morte ou mensagem duplicada, retirando o processo; uma violação protocolar é conservada para rejeitar a próxima admissão daquele serviço. Shutdown fecha admissão, cancela trabalhos, drena rejeições pendentes e recolhe filhos/threads.

## Memória lógica

Fila estrutural tem oito posições. Cada pedido reserva `source.len + 16 MiB + 256 + 64 KiB`, guardado em token RAII. A reserva acompanha erro ou resposta concluída ainda retida pelo ticket, e só é liberada em erro/drop ou transferência explícita por `Ticket::wait`. Cancelamento é verificado novamente nessa transferência, inclusive quando Result já foi recebido. Abandono de ticket cancela Busy ou descarta a resposta concluída, liberando uma única reserva. Stderr é drenado continuamente e retém no máximo 64 KiB por processo.

O cap de 64 MiB é mais restritivo que a fila: **no máximo três tickets podem estar simultaneamente reservados** com o teto pessimista de resposta; a fila cheia de oito não é alcançável nesta configuração. O teste verifica recusa por aggregate_limit antes de extrapolar o cap; não apresenta uma prova artificial de queue_full. Respostas transferidas pertencem ao consumidor externo e deixam de ser cobertas por esse cap. Temporários de codec, parser, threads e overhead de processo não são RSS limitado pela contabilidade lógica.

## Evidências de aceite

São 20 testes funcionais locais neste recorte, incluindo os negativos adicionados após revisão independente. Receipts locais: [testes macOS](../../docs/relatorios/logs/L4/workers/persistent-tests-macos.json), [smoke macOS](../../docs/relatorios/logs/L4/workers/persistent-smoke-macos.json). CI nativo recolhe o mesmo `demonstrate` em Linux/macOS; verificar os receipts do commit publicado no relatório de L4. Comandos reproduzíveis:

```sh
cargo test -p xrai-eval --test workers_persistent -- --test-threads=1
cargo run -p xrai-eval --bin worker-persistent -- demonstrate
```

| Critério | Prova |
|---|---|
| PID/encarnação reutilizados, não EOF por pedido | 42 respostas integrais contra direto; smoke lista 28 requests com dois PIDs/encarnações |
| Falha seguida de reaped/replacement/saudável | crash_once e partial_once, attempt2 em novo processo, pedido seguinte correto |
| Worker saudável progride durante Busy cancelado | hang em um processo, Python no outro, cancelamento libera reserva |
| Handshake inválido e morte em handshake/Idle | bad_handshake/handshake_death/idle_death rejeitados, reserva zero |
| Frame excessivo/parcial, payload/identidade antiga | oversized, partial_once, old_attempt, wrong_incarnation, wrong_payload e headers inválidos |
| Duplicata e morte depois do Result | resultado inicial imutável, duplicata rejeitada sem segunda publicação; falha futura não altera resposta aceita |
| Consumidor lento/drop/cancelamento na entrega | reserva continua retida após conclusão; aggregate_limit; wait/drop libera; cancel de ticket concluído não entrega sucesso |
| Alternância de estado | sete dialetos × completas/incompletas/configs + repetição contra resposta integral direta |
| Shutdown sem leitor/escritor bloqueado | timeout Busy, drop do pool durante hang, reader/writer reunidos em prazo testado; peer lê apenas header e emite Ready/Result inválido ou válido sem consumir fonte de 8 MiB; protocolo/timeout/cancelamento encerram writer bloqueado |
| Validação de muitos diagnósticos | 2048 diagnósticos CRLF; mapa de linhas uma vez e lookup binário, com deadline antes de entregar |
| Deadline e overflow | deadline de 1 hora reduzido a 5 s; attempt u32::MAX rejeita retry sem panic |
| Stderr acima do teto | 1 MiB drenado sem deadlock; retenção interna limitada a 64 KiB |

## Pendências para o Arquiteto

1. Comparação completa direto/XRW1/XRW2 conforme ADR 026 §3: manifesto congelado, três sessões, ≥30 pedidos/classe, fontes reais pequenas/médias/grandes densas, sete dialetos, cold/warm e concorrência separados, amostras cruas e percentis por sessão. O smoke atual usa fontes sintéticas pequenas e é exploratório.
2. CPU user/system pai+filhos com contadores de saída e observer externo; série temporal RSS simultânea com gaps e overhead. Campos são **null com causa** no smoke. Não há alegação de ganho, pico exato ou gate de recursos fechado.
3. Reunir prova nativa do commit final em Linux/macOS. Nenhuma decisão arquitetural nova é necessária para o recorte funcional; os itens acima são implementação/verificação subsequente.

## Prova nativa conciliada

[CI38248278388](https://github.com/wkoch/xrai/actions/runs/38248278388), código `1d2d40a221dad1a5ec9188158dbc624f329023c7`, Linux x86_64/glibc2.39 e macOS15.7.9 arm64: três jobs aprovados. [L4](../../docs/relatorios/L4.md) e [conferência dos receipts](../../docs/relatorios/logs/L4/integration/native-receipts-verification-final.json) registram comandos/hashes, resultados e limites do primeiro recorte. Prova antes pendente agora concluída para este incremento; os critérios restantes do cartão continuam abertos.
