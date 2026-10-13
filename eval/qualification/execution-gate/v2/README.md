# Dispatch D01 v2, sintético/offline

Seis registros novos, recomponíveis por `execution_dispatch_v2.replay_dispatch_v2`.
A versão v1 e seus recibos permanecem intactos. Cada registro contém os bytes
consumidos pelo preflight, task/arm/run explícitos, vínculo de modelo/configuração,
perfil do tokenizer vendorizado e serializer. Vincular o perfil não equivale a
executar tokenização ou medir wire/usage de provider.

`commit` é o ponto de linearização: recusa anterior libera reserva e implica
zero invocações fake. Depois dele, cancelamento/revogação registram aborto e não
prometem impedir chamadas. Falha incerta retém reserva; `before_transport_failure`
libera somente com prova do fake embutido antes de contar invocação. Nenhum
transporte real pode apresentar esse marcador nesta implementação.

`late-response-usage.json` preserva o cancelamento, acrescenta resposta tardia e
reconcilia usage uma única vez. Repetição exata não gera evento/custo duplicado;
conteúdo conflitante é recusado. Os eventos recompõem estados, reservas, cobrança,
incidentes e identidades, inclusive unknowns; não basta rehash do journal.

Recibos usam preços e orçamento virtuais. Estes fixtures não qualificam tarefa
D0 nem habilitam campanha D1, provider, credenciais, rede ou contenção do SO.
