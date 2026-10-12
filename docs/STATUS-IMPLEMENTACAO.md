# Estado da implementação

Atualizado em: 11/10/2026, pelo Arquiteto, na [revisão L1 e preparação de L2](relatorios/REVISAO-L1.md), sobre a base `0ae00e5`.

**Situação:** L0 e retificações M0-01.R1/M0-02.R1 concluídas. Revisão L1 resolveu C01/S01/S02. M0-03 foi aceita no escopo revisado de corpus inicial: 20 D0/32 D1-seed e 78 fixtures. A qualificação competitiva permanece obrigatória em M0-03.R1, ainda não executada. L2 está pronto para o usuário liberar: harness local, qualificação e spikes. M0-07 passou seis testes locais, mas prova Linux e CI R2 continuam bloqueadas externamente; usuário já escolheu registrar a pendência. V1: Linux x86_64/macOS arm64. Parsing, consultas e MCP de produção continuam indisponíveis; nenhum gate competitivo avaliado.

**Entrada:** [IMPLEMENTADOR.md](../IMPLEMENTADOR.md). **Próxima execução:** [lote L2](relatorios/REVISAO-L1.md). M0-04/05/08 podem começar com o corpus inicial; M0-12 exige qualificação R1. L0-A01 permanece escolha do mantenedor antes de distribuição, sem bloquear trabalho local. [ADR 021](decisoes/CORPUS-QUALIFICADO.md) e [ADR 022](decisoes/PERSISTENCIA-E-RETENCAO.md) fecham as decisões solicitadas ao Arquiteto.

## Decisões vigentes

- O arquiteto planeja; outra IA escreve código, testa e executa as atividades.
- Qualidade/sucesso é o objetivo primário definido pelo usuário. Economia é secundária.
- Os limiares iniciais de arquitetura estão no [protocolo de diferenciação](PROVA-DE-DIFERENCIACAO.md); ainda não são resultados medidos ou autorização de despesas.
- Nenhum gate competitivo foi avaliado. Não há autorização por evidência para M1-B ou M2/M3 completos.
- Git configurado com `origin` em `https://github.com/wkoch/xrai.git`, branch `main`. Instrução do usuário: commit e push após cada entrega concluída e verificada; regra persistida em [AGENTS.md](../AGENTS.md).

## Quadro de tarefas

Fonte do escopo, dependências e aceite: [plano de implementação](PLANO-DE-IMPLEMENTACAO.md). Este quadro registra execução, não substitui os cartões.

Estados: `não iniciada`, `em andamento`, `bloqueada`, `concluída` ou `cancelada por decisão`. Só concluir com evidência; bloqueio informa causa e trabalho independente possível. Resultado negativo de experimento pode concluir a atividade de avaliação, mas não libera seu gate de avanço.

| ID | Atividade | Estado | Evidência |
|---|---|---|---|
| M0-01 | Contrato mínimo, escopo L0 | concluída | [Contrato](contracts/m1.md); [25 exemplos revalidados](relatorios/logs/revisao-L0/checks.json); [aceite e ressalva para promoção](relatorios/REVISAO-L0.md) |
| M0-01.R1 | Retificação de seletor de revisão e admissão | concluída | [Aceite L1](relatorios/L1.md); [checks e preservação L0](relatorios/logs/L1/contract-r1-checks.json) |
| M0-02 | Workspace Rust e CI | concluída | [Escolhas e verificações](relatorios/dependencias-L0.md); [CI do commit](relatorios/logs/revisao-L0/ci.json) |
| M0-02.R1 | Validação documental em CI | concluída | [CI do commit `0669f71`](relatorios/logs/L1/contracts-ci.json); [saída e contagens](relatorios/logs/L1/contracts-ci-output.json) |
| M0-02.R2 | Adequar CI aos dois alvos v1 | bloqueada | [Matriz inspecionada](relatorios/logs/L1/platform-matrix.json), Linux x86_64/macOS arm64; CI do commit pendente por billing/limite; proteção não verificável (403) |
| M0-03 | Corpus inicial D0/D1-seed e fixtures | concluída | [Aceite no escopo revisado](relatorios/REVISAO-L1.md); [52 materializações revalidadas](relatorios/logs/revisao-L1/corpus-check.json); qualificação original transferida para R1, sem aceite competitivo |
| M0-03.R1 | Qualificar D1 para piloto/G0 | não iniciada | [Admissão definida em ADR 021](decisoes/CORPUS-QUALIFICADO.md); nova tarefa obrigatória antes de M0-12 |
| M0-04 | Harness, baseline e agentes | não iniciada | — |
| M0-05 | Gramáticas e autonomia | não iniciada | — |
| M0-06 | Workers e IPC | não iniciada | — |
| M0-07 | Snapshots e armazenamento | bloqueada | [Spike/seis testes locais](relatorios/sqlite-L1.md); [CI sem execução por billing/limite](relatorios/logs/L1/sqlite-ci-blocked.json); usuário optou manter prova nativa v1 pendente; Windows pós-v1 |
| M0-08 | Filesystem e checkout | não iniciada | — |
| M0-11 | Protótipo semântico P2 | não iniciada | — |
| M0-09 | Protótipo de contexto P3 | não iniciada | — |
| M0-12 | Piloto competitivo | não iniciada | — |
| M0-10 | Decisão G0 | não iniciada | — |
| M1-01 | Contratos do domínio | não iniciada | — |
| M1-22 | Confirmação M1-A / G1 | não iniciada | — |
| M1-02 | Inventário e configuração | não iniciada | — |
| M1-03 | Fontes e revisões | não iniciada | — |
| M1-04 | Persistência e publicação | não iniciada | — |
| M1-05 | Supervisor de extração | não iniciada | — |
| M1-06 | Adapter comum | não iniciada | — |
| M1-07 | Frontend Rust | não iniciada | — |
| M1-08 | Frontend TS/JS | não iniciada | — |
| M1-09 | Frontend Python | não iniciada | — |
| M1-10 | Frontend Go | não iniciada | — |
| M1-11 | Índice completo | não iniciada | — |
| M1-12 | Atualização incremental | não iniciada | — |
| M1-13 | Cobertura e frescor | não iniciada | — |
| M1-14 | Fonte, outline e relações | não iniciada | — |
| M1-15 | Busca | não iniciada | — |
| M1-23 | Integração de recortes comprovados | não iniciada | — |
| M1-16 | Contexto e expansão | não iniciada | — |
| M1-17 | CLI | não iniciada | — |
| M1-18 | MCP | não iniciada | — |
| M1-19 | Falhas e concorrência | não iniciada | — |
| M1-20 | Distribuição da alpha | não iniciada | — |
| M1-21 | Decisão G2 e alpha | não iniciada | — |

## Gates

| Gate | Situação | Próxima etapa liberada por evidência |
|---|---|---|
| G0 | não avaliado | nenhuma; M0 em andamento, com L0 concluído |
| G1 | não avaliado | nenhuma; M1-B depende de G1 favorável |
| G2 | não avaliado | nenhuma; disponibilização da alpha depende de G2 |

## Pendências correntes

| Item | Momento de definição |
|---|---|
| Toolchain, MSRV e versões das dependências | Rust/MSRV 1.98.1, edição 2024; runtime xrai sem deps externas. Spike dev-only usa rusqlite 0.40.2 bundled/backup e blake3 1.8.2, transitivas no lockfile |
| Repositórios e tarefas reais do corpus | M0-03 inicial aceita; M0-03.R1 qualifica 32 desafios com porte, relações e oracles independentes; escolha de candidatos cabe ao implementador pelos critérios do ADR 021 |
| Licença de distribuição do produto | L0-A01: decisão do mantenedor antes de M1-20; manter publish=false |
| Contrato de revisão e admissão | M0-01.R1: direção A02/A03 concretizada em exemplos/schema/verificador v2; adapters/tokenizers reais nos cartões consumidores |
| CI dos exemplos documentais | M0-02.R1: check aprovado no commit `0669f71`, 26 positivos/30 adversos e dez testes; Rust preservado e aprovado nos três hosts |
| Hardware de referência e autonomia nativa | Hardware permanece não medido; M0-05 ainda precisa provar gramáticas/ambiente limpo. CI anterior comprova scaffold e contratos; spike SQLite local passou, CI nova bloqueada por billing/limite |
| Baselines de SO/ABI | Decisão definida no ADR 020: Ubuntu 24.04/glibc 2.39 e macOS 15.0 arm64; verificar em M0-05/M1-20 |
| Modelos, limites de runs, esforço e teto monetário de campanha | Antes do uso pago correspondente em M0-04/12; preparar replay/local enquanto isso |
| Tamanho final de H1 e método estatístico | M0-10/M1-22, após dados D1 e antes de abrir H1 |

## Relatórios de execução

[Relatório L0](relatorios/L0.md): critérios M0-01/M0-02, ambiente, escolhas, revisões, limitações e próxima ação. [Logs M0-02](relatorios/logs/L0/workspace-checks.json), [checks dos exemplos](relatorios/logs/L0/contract-examples.json), [compatibilidade/licenças](relatorios/dependencias-L0.md) e [manifesto dos entregáveis](relatorios/logs/L0/artifacts.json).

[Revisão arquitetural L0](relatorios/REVISAO-L0.md): parecer de aceite, resposta às pendências, nova lacuna de seletor, CI remota confirmada e lote L1. [Checks reexecutados](relatorios/logs/revisao-L0/checks.json), [CI consultada](relatorios/logs/revisao-L0/ci.json) e [sondagens](relatorios/logs/revisao-L0/sondagens-contrato.json). Esses logs se referem ao commit L0; a execução posterior das retificações R1 está registrada em L1.

## Decisões do arquiteto e execução restante

L0-A02 foi resolvida em arquitetura com alcance explícito do cap de diagnóstico; contrato e testes documentais foram concretizados em R1. L0-A03 define snapshot fixo versus latest e seus exemplos passaram; implementação de produto segue os cartões consumidores. L0-A01 permanece escolha do mantenedor, sem bloquear M0-03/M0-07. Referência e critérios: [revisão, decisões e lote L1](relatorios/REVISAO-L0.md).

Nenhuma decisão competitiva foi tomada com base nos smokes. A preferência do usuário por qualidade e os tetos propostos de custo permanecem inalterados.

[Relatório L1](relatorios/L1.md): histórico do contrato/CI aprovados, corpus preparado e spike verificado localmente. [Revisão L1](relatorios/REVISAO-L1.md): parecer vigente, resolução das decisões e sequência L2.

L1-S01/S02 **resolvidas** no ADR 022: lock/epoch/tentativa, FTS por conteúdo e pins persistidos/GC; implementação e verificação em M1-04/15/16/19 depois de G1. O spike M0-07 continua descartável; sua promoção não foi executada.

L1-C01 **resolvida** no ADR 021: seed aceito para desenvolvimento; M0-03.R1 qualifica o corpus antes do piloto. Campos legados do manifest/oracles ainda serão conciliados pelo implementador nessa tarefa; não são nova pendência arquitetural. Nenhuma decisão do Arquiteto bloqueia iniciar L2.

Escopo vigente de plataformas v1: Linux x86_64 e macOS arm64, conforme plano atualizado. M0-02.R2 remove Windows da matriz obrigatória; histórico preservado. Aceite remoto R2/M0-07 continua pendente por billing/limite. Consultas de branch protection/rulesets retornaram 403, sem mudança de proteção.
