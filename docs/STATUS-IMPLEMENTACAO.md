# Estado da implementação

Atualizado em: 11/10/2026, pelo implementador, ao retomar L1 após a revisão arquitetural `257b91d`.

**Situação:** L0 aceito no escopo de contrato/exemplos e scaffold, conforme [revisão arquitetural](relatorios/REVISAO-L0.md). Reexecução local passou e CI do scaffold foi confirmada em Linux x86_64, macOS arm64 e Windows x86_64. M0-01.R1 foi concretizada em contrato/schema v2 e passou em 56 exemplos e dez testes locais. M0-02.R1 acrescenta CI dos exemplos, aguardando run do commit. Parsing, consultas e MCP ainda indisponíveis. Nenhum gate competitivo foi avaliado.

**Entrada:** [IMPLEMENTADOR.md](../IMPLEMENTADOR.md). **Lote L1 em execução:** M0-01.R1 e M0-03, com M0-07 como frente independente; depois M0-02.R1. M0-04 aguarda corpus/retificação; M0-05/M0-08 aguardam corpus. L0-A01 depende do mantenedor; A02/A03 já têm direção arquitetural e trabalho concreto para o implementador.

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
| M0-02.R1 | Validação documental em CI | em andamento | Job documental configurado; [suíte local](relatorios/logs/L1/contracts-tests.json); aguardando CI do commit |
| M0-03 | Corpus D0/D1 e oracles | em andamento | — |
| M0-04 | Harness, baseline e agentes | não iniciada | — |
| M0-05 | Gramáticas e autonomia | não iniciada | — |
| M0-06 | Workers e IPC | não iniciada | — |
| M0-07 | Snapshots e armazenamento | em andamento | — |
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
| Toolchain, MSRV e versões das dependências | L0: Rust/MSRV 1.98.1, edição 2024, zero dependências externas; verificar bibliotecas nas tarefas consumidoras |
| Repositórios e tarefas reais do corpus | M0-03, com versões e oracles |
| Licença de distribuição do produto | L0-A01: decisão do mantenedor antes de M1-20; manter publish=false |
| Contrato de revisão e admissão | M0-01.R1: direção A02/A03 concretizada em exemplos/schema/verificador v2; adapters/tokenizers reais nos cartões consumidores |
| CI dos exemplos documentais | M0-02.R1: novo check implementado, aguardando run do commit; workflow Rust L0 já passou nos três hosts |
| Hardware de referência e autonomia nativa | Hardware permanece não medido; M0-05 ainda precisa provar gramáticas/ambiente limpo. CI atual comprova somente scaffold |
| Modelos, limites de runs, esforço e teto monetário de campanha | Antes do uso pago correspondente em M0-04/12; preparar replay/local enquanto isso |
| Tamanho final de H1 e método estatístico | M0-10/M1-22, após dados D1 e antes de abrir H1 |

## Relatórios de execução

[Relatório L0](relatorios/L0.md): critérios M0-01/M0-02, ambiente, escolhas, revisões, limitações e próxima ação. [Logs M0-02](relatorios/logs/L0/workspace-checks.json), [checks dos exemplos](relatorios/logs/L0/contract-examples.json), [compatibilidade/licenças](relatorios/dependencias-L0.md) e [manifesto dos entregáveis](relatorios/logs/L0/artifacts.json).

[Revisão arquitetural L0](relatorios/REVISAO-L0.md): parecer de aceite, resposta às pendências, nova lacuna de seletor, CI remota confirmada e lote L1. [Checks reexecutados](relatorios/logs/revisao-L0/checks.json), [CI consultada](relatorios/logs/revisao-L0/ci.json) e [sondagens](relatorios/logs/revisao-L0/sondagens-contrato.json). Esses logs se referem ao commit L0; retificações planejadas continuam não executadas.

## Questões para o arquiteto

L0-A02 foi resolvida em arquitetura com alcance explícito do cap de diagnóstico; contrato e testes documentais foram concretizados em R1. L0-A03 define snapshot fixo versus latest e seus exemplos passaram; implementação de produto segue os cartões consumidores. L0-A01 permanece escolha do mantenedor, sem bloquear M0-03/M0-07. Referência e critérios: [revisão, decisões e lote L1](relatorios/REVISAO-L0.md).

Nenhuma decisão competitiva foi tomada com base nos smokes. A preferência do usuário por qualidade e os tetos propostos de custo permanecem inalterados.

[Relatório L1](relatorios/L1.md): contrato retificado e CI em verificação; corpus e spike SQLite em execução.
