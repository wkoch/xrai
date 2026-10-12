# Estado da implementação

Atualizado em: 12/10/2026. Execução: Implementador, primeiro incremento L2. Planejamento: Arquiteto, revisão L2/ADRs 023–024 e lote L3. Nenhuma tarefa de código foi executada nesta revisão documental. A [CI pública anterior](relatorios/CI-PUBLICO.md), commit `9b5411c`, permanece aceita; [CI nativa L2](relatorios/L2.md) do commit `1e09318` passou nos três jobs; gate de admissão corrigido e revisado com nove testes e provas negativas adicionais.

**Situação:** L0 e retificações M0-01.R1/M0-02.R1 concluídas. Revisão L1 resolveu C01/S01/S02. M0-03 foi aceita no escopo revisado de corpus inicial: 20 D0/32 D1-seed e 78 fixtures. A qualificação competitiva permanece obrigatória em M0-03.R1: gate/triagem iniciados, zero casos qualificados. Usuário liberou L2; harness local/replay e spikes de parsing/filesystem implementados com evidência local em [L2](relatorios/L2.md). Provas nativas de parsing/filesystem/harness passaram em Ubuntu24.04.5 e macOS15.7.9; smokes de modelos reais, execução literal15.0 e pendências de contenção permanecem separados. Com o repo público, a tentativa 2 do run `38197775334` passou nos três jobs: **M0-02.R2 e M0-07 concluídas**, com seis testes SQLite em cada alvo nativo. V1: Linux x86_64/macOS arm64. Parsing, consultas e MCP de produção continuam indisponíveis; nenhum gate competitivo avaliado.

**Entrada:** [IMPLEMENTADOR.md](../IMPLEMENTADOR.md). **Próxima execução:** [lote L3](relatorios/REVISAO-L2.md), continuação de L2. Começar quatro casos verticais R1 e incrementos locais de contenção/workers/captura; M0-12 exige qualificação R1. L0-A01 permanece escolha do mantenedor antes de distribuição, sem bloquear trabalho local. [ADR 021](decisoes/CORPUS-QUALIFICADO.md) e [ADR 022](decisoes/PERSISTENCIA-E-RETENCAO.md) fecham as decisões solicitadas ao Arquiteto.

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
| M0-02.R2 | Adequar CI aos dois alvos v1 | concluída | [CI do commit `9b5411c`, tentativa 2](relatorios/CI-PUBLICO.md); dois hosts Rust e contratos passaram; proteção/rulesets consultados, sem check Windows exigido |
| M0-03 | Corpus inicial D0/D1-seed e fixtures | concluída | [Aceite no escopo revisado](relatorios/REVISAO-L1.md); [52 materializações revalidadas](relatorios/logs/revisao-L1/corpus-check.json); qualificação original transferida para R1, sem aceite competitivo |
| M0-03.R1 | Qualificar D1 para piloto/G0 | em andamento | [Gate fechado e oito candidatos medidos](../eval/reports/m0-corpus-qualification.md); 0/32 qualificados, seed preservado |
| M0-04 | Harness, baseline e agentes | em andamento | [20 D0, replay, isolamento e quatro eventos A→B](relatorios/L2.md); 13 testes locais; modelos/tokenizer/custo reais pendentes; H01 decidida, implementação em M0-04.R1 |
| M0-04.R1 | Contenção do domínio de execução do harness | não iniciada | Decisão H01 no [ADR 023](decisoes/EXECUCAO-E-CAPTURA.md); L3-02 define execução e provas |
| M0-05 | Gramáticas e autonomia | em andamento | [Sete dialetos e autonomia local](../eval/reports/m0-packaging.md); [Matriz nativa aprovada](relatorios/logs/L2/ci-native-fsfix.json); host literal15.0 ainda pendente |
| M0-06 | Workers e IPC | não iniciada | — |
| M0-07 | Snapshots e armazenamento | concluída | [Seis testes SQLite passaram em Linux x86_64 e macOS arm64](relatorios/logs/ci-publico/output.json); [aceite e limites](relatorios/CI-PUBLICO.md); spike experimental, produção permanece M1 |
| M0-08 | Filesystem e checkout | em andamento | [14 testes e capacidades reais locais](../eval/reports/m0-filesystem.md); [Matriz nativa aprovada](relatorios/logs/L2/ci-native-fsfix.json); F01/Git decididas no ADR 023; fechamento original e nova prova R1 pendentes |
| M0-08.R1 | Captura e enumeração ancoradas | não iniciada | Decisão F01 no [ADR 023](decisoes/EXECUCAO-E-CAPTURA.md); L3-04 precede promoção de produção |
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
| Toolchain, MSRV e versões das dependências | Rust/MSRV 1.98.1, edição 2024; runtime xrai sem deps externas. Spike dev-only usa rusqlite 0.40.2 bundled/backup, blake3 1.8.2 e Tree-sitter/gramáticas com pins exatos e avisos em [packaging](../eval/reports/m0-packaging.md), transitivas no lockfile |
| Repositórios e tarefas reais do corpus | M0-03 inicial aceita; M0-03.R1 qualifica 32 desafios com porte, relações e oracles independentes; escolha de candidatos cabe ao implementador pelos critérios do ADR 021 |
| Licença de distribuição do produto | L0-A01: decisão do mantenedor antes de M1-20; manter publish=false |
| Contrato de revisão e admissão | M0-01.R1: direção A02/A03 concretizada em exemplos/schema/verificador v2; adapters/tokenizers reais nos cartões consumidores |
| CI dos exemplos documentais | M0-02.R1: check aprovado no commit `0669f71`, 26 positivos/30 adversos e dez testes; Rust preservado e aprovado nos três hosts |
| Hardware de referência e autonomia nativa | Referência competitiva ainda precisa ser fixada; M0-05 prova gramáticas/ambiente limpo. CI `9b5411c` comprova scaffold, contratos e spike SQLite nos dois alvos, sem concluir a autonomia do produto |
| Baselines de SO/ABI | Decisão definida no ADR 020: Ubuntu 24.04/glibc 2.39 e macOS 15.0 arm64; verificar em M0-05/M1-20 |
| Modelos, limites de runs, esforço e teto monetário de campanha | Antes do uso pago correspondente em M0-04/12; preparar replay/local enquanto isso |
| Tamanho final de H1 e método estatístico | M0-10/M1-22, após dados D1 e antes de abrir H1 |

## Relatórios de execução

[Relatório L0](relatorios/L0.md): critérios M0-01/M0-02, ambiente, escolhas, revisões, limitações e próxima ação. [Logs M0-02](relatorios/logs/L0/workspace-checks.json), [checks dos exemplos](relatorios/logs/L0/contract-examples.json), [compatibilidade/licenças](relatorios/dependencias-L0.md) e [manifesto dos entregáveis](relatorios/logs/L0/artifacts.json).

[Revisão arquitetural L0](relatorios/REVISAO-L0.md): parecer de aceite, resposta às pendências, nova lacuna de seletor, CI remota confirmada e lote L1. [Checks reexecutados](relatorios/logs/revisao-L0/checks.json), [CI consultada](relatorios/logs/revisao-L0/ci.json) e [sondagens](relatorios/logs/revisao-L0/sondagens-contrato.json). Esses logs se referem ao commit L0; a execução posterior das retificações R1 está registrada em L1.

## Decisões do arquiteto e execução restante

L0-A02 foi resolvida em arquitetura com alcance explícito do cap de diagnóstico; contrato e testes documentais foram concretizados em R1. L0-A03 define snapshot fixo versus latest e seus exemplos passaram; implementação de produto segue os cartões consumidores. L0-A01 permanece escolha do mantenedor, sem bloquear M0-03/M0-07. Referência e critérios: [revisão, decisões e lote L1](relatorios/REVISAO-L0.md).

Nenhuma decisão competitiva foi tomada com base nos smokes. A preferência do usuário por qualidade e os tetos propostos de custo permanecem inalterados.

[Relatório L1](relatorios/L1.md): histórico do contrato/CI aprovados, corpus preparado e spike verificado localmente. [Revisão L1](relatorios/REVISAO-L1.md): parecer histórico, resolução das decisões e sequência L2.

L1-S01/S02 **resolvidas** no ADR 022: lock/epoch/tentativa, FTS por conteúdo e pins persistidos/GC; implementação e verificação em M1-04/15/16/19 depois de G1. O spike M0-07 continua descartável; sua promoção não foi executada.

L1-C01 **resolvida** no ADR 021: seed aceito para desenvolvimento; M0-03.R1 qualifica o corpus antes do piloto. Campos legados do manifest/oracles ainda serão conciliados pelo implementador nessa tarefa; não são nova pendência arquitetural. Nenhuma decisão do Arquiteto bloqueia iniciar L2.

Escopo vigente de plataformas v1: Linux x86_64 e macOS arm64. M0-02.R2 e M0-07 aceitas após [CI pública bem-sucedida](relatorios/CI-PUBLICO.md). Os bloqueios/403 anteriores permanecem históricos. Consulta atual: main sem proteção ativa e rulesets vazios, sem alteração de configuração pelo assistente. Provas dos demais cartões e gates continuam pendentes.

[Relatório L2](relatorios/L2.md): primeiro incremento de corpus/harness/spikes e evidências por critério. Pendências então abertas L2-H01, M0-08.F01 e L2-GIT01 foram resolvidas em arquitetura pela revisão L2; externas L2-E01/E02 distinguem piso de SO e recursos dos smokes reais. Os gates permanecem inalterados; decisões novas estão registradas abaixo.

## Revisão arquitetural L2 e continuidade L3

[Revisão vigente](relatorios/REVISAO-L2.md), [ADR 023](decisoes/EXECUCAO-E-CAPTURA.md) e [ADR 024](decisoes/BIBLIOTECAS-PROPRIAS.md). H01 exige domínio descartável para comandos arbitrários; F01 exige captura ancorada com modelo explícito de concorrência; Git incorporado fica adiado até consumidor. Decisão concluída não significa teste/implementação concluídos. Bibliotecas próprias de qualquer porte são admitidas por necessidade, começando por experimentos delimitados.

Oito incrementos planejados, ainda não executados como L3: L3-01 qualificação vertical/D1; L3-02 contenção; L3-03 workers/IPC; L3-04 captura; L3-05 medição/adapters; L3-06 P2; L3-07 P3; L3-08 preparação/piloto. Estados M0 existentes permanecem; M0-04.R1/M0-08.R1 acrescentados como não iniciados. M0-08 pode fechar seu recorte original mediante recibo, mantendo R1 explícita.

Continuam externos: host literal macOS 15.0, recursos/teto para runs reais e licença antes de distribuição. Não bloqueiam todas as frentes locais. Os gates seguem não avaliados; nenhuma biblioteca de produção foi implementada pelo Arquiteto.

Verificação da entrega: [recibo documental](relatorios/logs/revisao-L2/documentacao.json), com links, IDs/dependências e hashes. Commit/push desta revisão serão informados após confirmação; este registro não atesta publicação antecipadamente.
