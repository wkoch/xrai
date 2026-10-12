# Estado da implementação

Atualizado em: 11/10/2026, pelo implementador, ao concluir o lote L0.

**Situação:** L0 concluído: M0-01 e M0-02 com aceite demonstrado em [relatório L0](relatorios/L0.md). Contrato especificado, cinco crates compiláveis e CLI de ajuda/versão funcionando localmente. Parsing, consultas e MCP ainda indisponíveis. Nenhum gate competitivo foi avaliado.

**Entrada:** [IMPLEMENTADOR.md](../IMPLEMENTADOR.md). **Próxima tarefa:** M0-03, corpus D0/D1 e oracles. Pendências L0-A01/A02 para o Arquiteto não bloqueiam corpus/spikes locais; veja relatório.

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
| M0-01 | Contrato mínimo | concluída | [Contrato](contracts/m1.md); [25 exemplos verificados](relatorios/logs/L0/contract-examples.json); [aceite L0](relatorios/L0.md) |
| M0-02 | Workspace Rust e CI | concluída | [Escolhas, compatibilidade e verificações](relatorios/dependencias-L0.md); [logs](relatorios/logs/L0/workspace-checks.json) |
| M0-03 | Corpus D0/D1 e oracles | não iniciada | — |
| M0-04 | Harness, baseline e agentes | não iniciada | — |
| M0-05 | Gramáticas e autonomia | não iniciada | — |
| M0-06 | Workers e IPC | não iniciada | — |
| M0-07 | Snapshots e armazenamento | não iniciada | — |
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
| G0 | não avaliado | nenhuma; M0 pode começar |
| G1 | não avaliado | nenhuma; M1-B depende de G1 favorável |
| G2 | não avaliado | nenhuma; disponibilização da alpha depende de G2 |

## Pendências que não bloqueiam L0

| Item | Momento de definição |
|---|---|
| Toolchain, MSRV e versões das dependências | L0: Rust/MSRV 1.98.1, edição 2024, zero dependências externas; verificar bibliotecas nas tarefas consumidoras |
| Repositórios e tarefas reais do corpus | M0-03, com versões e oracles |
| Hardware, disponibilidade de runners e plataformas verificadas | M0-02/05; não declarar execução ausente como teste passado |
| Modelos, limites de runs, esforço e teto monetário de campanha | Antes do uso pago correspondente em M0-04/12; preparar replay/local enquanto isso |
| Tamanho final de H1 e método estatístico | M0-10/M1-22, após dados D1 e antes de abrir H1 |

## Relatórios de execução

[Relatório L0](relatorios/L0.md): critérios M0-01/M0-02, ambiente, escolhas, revisões, limitações e próxima ação. [Logs M0-02](relatorios/logs/L0/workspace-checks.json), [checks dos exemplos](relatorios/logs/L0/contract-examples.json), [compatibilidade/licenças](relatorios/dependencias-L0.md) e [manifesto dos entregáveis](relatorios/logs/L0/artifacts.json).

## Questões para o arquiteto

Questões documentadas em [L0, §5](relatorios/L0.md#5-pendências-para-o-arquiteto): L0-A01, licença do produto antes de distribuir; L0-A02, analisar diagnóstico de admissão fora do teto solicitado quando o envelope mínimo não cabe. Alternativas e recomendação estão no relatório. Sem bloqueio para M0-03 ou spikes independentes. Execução nativa Linux/Windows segue pendência operacional de M0-05, sem validação alegada.
