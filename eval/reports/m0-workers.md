# M0-06 — Workers/IPC, incremento L3-03

12/10/2026. Implementação experimental em `xrai-eval`; não promovida à CLI/MCP de produto. ADR 023 §2 executado nos incrementos de framing/identidade e supervisão/limites; pool inicial implementado. M0-06 permanece em andamento: prova nativa Linux/macOS será conciliada pela integração e comparação completa CPU/RSS agregado permanece pendente. Piso literal macOS 15.0 não foi executado localmente.

## Contrato do experimento

`worker-spike` reexecuta **seu próprio executável**, modo `worker`. Fonte existe apenas em bytes no pedido; nenhum campo de path ou AST/pointer nativo é transmitido. Gramáticas e queries são as incorporadas em M0-05. Fingerprint produtor inclui runtime 0.27.1, versão/ABI de gramática, node types, query e proveniência incorporada. A configuração é identidade opaca, sem alteração de semântica do parser neste recorte; cada request recompila parser/query, sem cache compartilhado.

Framing binário little endian: magic `XRW1` (4 bytes), versão u16=1, comprimento u64, payload exato. Header tem 14 bytes. Decoders recusam magic/versão/comprimento antes de alocar payload; limites e overflow são verificados de novo nos blobs/contagem de spans, enum, bytes extras internos e trailing bytes de transporte. Resposta é única, seguida de EOF.

Identidade comum: request u64, attempt u32, dialect blob UTF-8 até 32 bytes, source BLAKE3[32], producer[32], configuration[32]. Cada blob tem comprimento u64 seguido de bytes. Request acrescenta source blob. Response acrescenta state u8 (complete=0/partial=1/error=2), source length/node count/query matches u64, contagem de spans u64 e pares start/end u64, payload blob. O payload contém JSON serializado do resultado lógico e diagnósticos do parsing, ou erro. Seus spans são diagnósticos de byte; não se anuncia extração semântica. Pai verifica identidades da tentativa, comprimento e `0 ≤ start ≤ end ≤ source_length` antes de aceitar. Estado partial preserva erros/missing do parser; error não merece retry.

## Limites fixados antes da medição

Configuração em [workers-configuration.json](../../docs/relatorios/logs/L3/workers-configuration.json): dois slots workers, fila de oito, fonte 8 MiB, resposta 16 MiB, reserva agregada de payload 64 MiB, deadline total/admissão e máximo por tentativa 5 s, retry no máximo um em processo novo, stderr retido até 64 KiB. Reserva conta source+response ceiling até conclusão; o teto agregado normalmente recusa um quarto pedido antes da fila de oito encher. Limites não foram aumentados em resposta a falhas.

Supervisores executam até dois processos em paralelo e iniciam processo novo por tentativa. Não há worker persistente ocioso: slot ocioso é thread em fila; restart e PID/attempt são observáveis. Essa escolha elimina cache entre configurações no primeiro incremento e inclui spawn na latência. A reserva é orçamento lógico da fila/processamento, **não teto de RSS** do parser nativo, temporários de serialização ou respostas já transferidas ao consumidor.

Deadline inclui espera na fila. Caller pode apertar o deadline, nunca estendê-lo. Pipes são lidos/escritos em threads supervisionadas, deadline/cancelamento mata e recolhe filho, e threads são reunidas. Crash/EOF/pipe truncado admite somente uma tentativa nova dentro do deadline total; identidade/versão/limites/protocolo inválidos são definitivos. Saída excedente é recusada antes de alocação. stderr continua drenado, mas retém no máximo 64 KiB. `ipc_bytes` conta leituras/escritas efetivamente completadas no transporte, inclusive tentativas com falha, separado de stderr.

Ticket cancelado ou abandonado não publica resultado; resultado é rechecado após teardown e na entrega do ticket. Shutdown fecha a admissão, processa/cancela até deadlines finitos e recolhe filhos. Este supervisor conhece seu próprio parser e seus hooks; não comprova contenção de shells/daemons arbitrários, obrigação separada L3-02.

## Critérios e evidências

| Critério | Evidência local |
|---|---|
| Identidades, source/config/producer, framing e spans | `identities_spans_and_extra_bytes_refused`, `decoder_refuses_huge_header_before_payload_read_and_corrupt_enums`; HeaderOnly falha se tentar ler payload sob header u64::MAX |
| Parsing direto = pool, complete/partial | `roundtrip_and_direct_pool_equivalence_all_dialects`: 14 fixtures/7 dialetos, resultado inteiro igual; hash/producer reutilizados |
| Abort/truncamento/hash/versão/excesso não afetam pai ou arquivo independente | `faulty_worker_cannot_publish_and_independent_work_progresses`, saudável completa ao lado de cada falha; retry finito registrado |
| Deadline, cancelamento ativo, resposta tardia | `deadlines_cancel_late_and_shutdown_are_bounded`: hang termina em deadline apertado; cancelamento após PID observado invalida late; saudável progride |
| Deadline inclui fila | `queue_wait_consumes_total_deadline_before_spawn`: terceiro pedido expirado não inicia processo/attempt |
| Retry em processo novo, stderr limitado | `finite_retry_in_new_process_and_stderr_capture_bounded`: primeira tentativa aborta, segunda PID diferente passa; 400 KiB drenados/64 KiB retidos |
| Overload e fonte excessiva | `admission_overload_and_duplicate_requests_do_not_grow_memory`: reserva ≤64 MiB, recusa overload/IDs duplicados, fonte >8 MiB recusada |
| Configurações não se misturam | `simultaneous_configurations_remain_distinct`: mesma fonte/config A e B simultâneas preservam respectivas identidades |
| EOF/saída válida e exit code | `valid_frame_requires_successful_exit_and_roundtrips_repeat`: resposta válida com exit nãozero recusa; 32 roundtrips passam. Filho com resposta normal tem `try_wait` sob deadline antes de qualquer kill, evitando corrida EOF→exit |
| Shutdown em sucesso/falha, filhos recolhidos | Todo Outcome registra wait/reaped; `shutdown_with_inflight_failure_reaps_child` destrói pool com hang em andamento e prova recolhimento |
| Caminho do executável com espaços | `executable_path_with_spaces_roundtrips_real_worker`: copia o binário para diretório e filename com espaços, inicia processo real via esse path e compara resultado completo/identidade; filho recolhido, tentativa única |
| Worker não relê fonte | Contrato sem path + `worker_is_given_bytes_and_does_not_reopen_source`, pedido só com bytes e equivalência; inspeção do código confirma worker lê stdin. Não é prova de sandbox de filesystem |
| Latência/throughput/codec/bytes reais | `worker-spike demonstrate`: small, large-comments 1.144.014 bytes, incomplete, seis repetições/caso, p50/p95/arrays crus; equivalência verificada fora do relógio do pool |
| CPU/RSS agregado e piso literal | **Pendente**. Campos null explícitos; não substituir por ru_maxrss de um filho, reserva de payload ou deployment target |

[workers-tests.json](../../docs/relatorios/logs/L3/workers-tests.json), [workers-clippy.json](../../docs/relatorios/logs/L3/workers-clippy.json) e [workers-proof.json](../../docs/relatorios/logs/L3/workers-proof.json) registram comandos, base commit, ambiente, versão Rust, exit codes, saída e hashes das três fontes implementadas. A primeira falha de clippy foi preservada em `workers-clippy-first.json`; a correção retirou alocações supérfluas de hex strings no benchmark. Treze testes integração passam no macOS arm64 disponível; root integra checks gerais e CI nativa. Evidência CI posterior deve citar commit/run exatos, sem herdar execução de base anterior.

## Próximo recorte e limitações

Concluir comparação de CPU e RSS agregado com observador apropriado (amostragem de processos simultâneos, overhead separado); decidir empiricamente se pool persistente justifica cache com owner/config fingerprint. Benchmark atual mede cold spawn por tentativa e entrada grande composta majoritariamente de comentários, não conjunto de grandes projetos/campanha competitiva. Não mede vantagem de retrieval e não libera G0/G1. Aproximação de p95 sobre seis observações é exploratória.

Não surgiu decisão arquitetural nova: limites e mecanismo seguem ADR 023, otimização/medição são execução pendente. Modelo de processo do produto não controla OOM global, CPU/RSS da biblioteca nativa ou execução hostil do mesmo usuário. M1-05 só deve promover o mecanismo após a matriz e calibração pertinentes.
