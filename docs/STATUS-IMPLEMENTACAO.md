# Estado da implementação

Atualizado em: 12/10/2026. Continuação C03/S01 em [L5-C03](relatorios/L5-C03.md): dispatch offline integrado, quatro descritores congelados, primeiro evento Rust executado/conciliado com30 checks no CI38309739709 do código4972f02; 55 alertas com recusa operacional S01. Execução: Implementador, retomada L5 com R3 experimental e dois dossiês reais em [L5-CONTINUACAO](relatorios/L5-CONTINUACAO.md); código `c48b599`, CI38283109016 aprovada nos cinco jobs, pares Rust/JavaScript comprovados, R3/P3 aprovado em Linux/macOS e12 executáveis/4ZIPs revalidados. Conciliação C02 implementada em [L5-C02](relatorios/L5-C02.md): quatro novos dossiês individualmente elegíveis após CI38294106923 do código e02370a, eventos A→B reais separados e pendentes, zero admissão; primeiro incremento L5 em [L5](relatorios/L5.md), código `e4cd4d4`, CI38259048931 aprovada nos três jobs e artefatos revalidados; incremento L4 anterior em [L4](relatorios/L4.md), com medição/ledger offline, XRW2 funcional e semântica Rust R1/R2; histórico L3 em [L3](relatorios/L3.md). Planejamento vigente: Arquiteto, revisão L5-C03; aceite do fake, quatro descritores e primeiro evento Rust; E02/D01/S02 concretizam alocação, envio e inspeção. Roteiro v1/ADR028 e mesmos seis incrementos preservados. A revisão arquitetural alterou somente documentos; o incremento L4 executado pelo Implementador está registrado abaixo. Quatro dossiês verticais aceitos e CI L3 aprovada no código `21e9279`, run38239765003; primeiras falhas Linux/Seatbelt corrigidas e preservadas. A [CI pública anterior](relatorios/CI-PUBLICO.md), commit `9b5411c`, permanece aceita; [CI nativa L2](relatorios/L2.md) do commit `1e09318` passou nos três jobs; gate de admissão corrigido e revisado com nove testes e provas negativas adicionais.

**Situação:** L0 e retificações M0-01.R1/M0-02.R1 concluídas. Revisão L1 resolveu C01/S01/S02. M0-03 foi aceita no escopo revisado de corpus inicial: 20 D0/32 D1-seed e 78 fixtures. A qualificação competitiva permanece obrigatória em M0-03.R1: gate/triagem e quatro pilotos verticais revisados; zero tarefas admitidas na matriz global32. Usuário liberou L2; harness local/replay e spikes de parsing/filesystem implementados com evidência local em [L2](relatorios/L2.md). Provas nativas de parsing/filesystem/harness passaram em Ubuntu24.04.5 e macOS15.7.9; smokes de modelos reais, execução literal15.0 e pendências de contenção permanecem separados. Com o repo público, a tentativa 2 do run `38197775334` passou nos três jobs: **M0-02.R2 e M0-07 concluídas**, com seis testes SQLite em cada alvo nativo. V1: Linux x86_64/macOS arm64. Parsing, consultas e MCP de produção continuam indisponíveis; nenhum gate competitivo avaliado.

**Entrada:** [IMPLEMENTADOR.md](../IMPLEMENTADOR.md). **Próxima execução:** [revisão L5-C03](relatorios/REVISAO-L5-C03.md): E02 slots/quotas, D01 compromisso de envio, TSJS-A, três eventos de presença e S02 offline; não refazer provas aceitas. [Caminho até 1.0](ROTEIRO-V1.md). M0-12 exige qualificação R1. L0-A01 permanece escolha do mantenedor antes de distribuição, sem bloquear trabalho local. [ADR 021](decisoes/CORPUS-QUALIFICADO.md) e [ADR 022](decisoes/PERSISTENCIA-E-RETENCAO.md) fecham as decisões solicitadas ao Arquiteto.

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
| M0-03.R1 | Qualificar D1 para piloto/G0 | em andamento | [Gate fechado, triagem e quatro pilotos verticais revisados](../eval/reports/m0-corpus-qualification.md); 0/32 qualificados, seed preservado; [plano condicional32 L5](../eval/qualification/l5-slot-plan.json), quatro novos dossiês4/4 individualmente elegíveis após C02, com matriz factual vinculada e oito elegíveis contando os pilotos; Rust/JS CI38283109016 e Python/Go CI38294106923 comprovados; [C03](relatorios/L5-C03.md): quatro descritores preparados, Rust1/4 executado/conciliado, três eventos pendentes |
| M0-04 | Harness, baseline e agentes | em andamento | [L4-01 offline: tokenizer/serializer fixados, sidecar, ledger fake, replay e readiness](../eval/reports/m0-agent-readiness.md); 19 testes novos e 20 legados. Gate/dispatch fake C03 entregues; D01 e perfil real ainda pendentes. Adapter e smokes de modelos reais permanecem pendentes |
| M0-04.R1 | Contenção do domínio de execução do harness | em andamento | [Supervisor/domínio/replayv2 e31testes](../eval/reports/m0-harness-containment.md); [CI L3 Linux aprovada](relatorios/logs/L3/ci-native-run.json), adapter mac descartável indisponível |
| M0-05 | Gramáticas e autonomia | em andamento | [Sete dialetos e autonomia local](../eval/reports/m0-packaging.md); [Matriz nativa aprovada](relatorios/logs/L2/ci-native-fsfix.json); host literal15.0 ainda pendente |
| M0-06 | Workers e IPC | em andamento | [L4-02 XRW2 funcional, cache/reset e reservas retidas](../eval/reports/m0-workers-persistent.md); XRW1 preservado. Matriz sintética direto/XRW1/XRW2 e CPU/RSS em [L5](relatorios/L5.md); fontes reais/concorrência/calibração integral pendentes; histórico funcional em [L4](relatorios/L4.md) |
| M0-07 | Snapshots e armazenamento | concluída | [Seis testes SQLite passaram em Linux x86_64 e macOS arm64](relatorios/logs/ci-publico/output.json); [aceite e limites](relatorios/CI-PUBLICO.md); spike experimental, produção permanece M1 |
| M0-08 | Filesystem e checkout | concluída | [Recibo final do recorte original e Git adiado ADR023](../eval/reports/m0-filesystem.md); 14testes nativos L2. Captura adversarial ampliada pertence a R1 |
| M0-08.R1 | Captura e enumeração ancoradas | concluída | [Aceite nativo do spike](../eval/reports/m0-filesystem.md); 35testesLinux/34mac, drivers e4eventos por host aprovados; limites live-bindings/not-atomic documentados |
| M0-11 | Protótipo semântico P2 | em andamento | [Primeira fatia Rust R1/R2, labels, evidência, lacunas e invalidação conservadora](../eval/reports/m0-semantics.md); R3 experimental opt-in implementado com matriz 16/16; correção de cfg composta passou oito novos casos nos dois alvos nativos, zero promoção nas contraprovas atuais; R4 e outras três famílias pendentes |
| M0-09 | Protótipo de contexto P3 | em andamento | [Primeiro incremento P3/expansão e contrato experimental v3](../eval/context/README.md), conforme ADR027; aceite integral continua pendente |
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
| C03/E02: eventos e corpus | Quatro preparados, Rust1/4 comprovado; três restantes, mapa externo de slots e compensação multimódulo 19/20. Oito elegíveis, nenhum admitido |
| D01: compromisso de envio | Definir ponto linearizado, cancelamento e reserva; tratar I/O bloqueante antes de provider real |
| S01/S02: setup Gitea | Inventário 55/55 e guard aceitos; alcance desconhecido mantém execução bloqueada. Próxima entrega: disponibilidade e perfil de inspeção offline separado |
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

[Revisão histórica L2](relatorios/REVISAO-L2.md), [ADR 023](decisoes/EXECUCAO-E-CAPTURA.md) e [ADR 024](decisoes/BIBLIOTECAS-PROPRIAS.md). H01 exige domínio descartável para comandos arbitrários; F01 exige captura ancorada com modelo explícito de concorrência; Git incorporado fica adiado até consumidor. Decisão concluída não significa teste/implementação concluídos. Bibliotecas próprias de qualquer porte são admitidas por necessidade, começando por experimentos delimitados.

Primeiro incremento L3-01/02/03/04 entregue com CI e evidências em [L3](relatorios/L3.md). M0-08 original e R1 concluídas nos escopos documentados. Restam matriz global32/eventos, contenção mac descartável, CPU/RSS/pool calibrado, L3-05 medição/adapters, L3-06 P2, L3-07 P3 e L3-08 preparação/piloto; estados específicos no quadro acima.

Continuam externos: host literal macOS 15.0, recursos/teto para runs reais e licença antes de distribuição. Não bloqueiam todas as frentes locais. Os gates seguem não avaliados; nenhuma biblioteca de produção foi implementada pelo Arquiteto.

Verificação da entrega: [recibo documental](relatorios/logs/revisao-L2/documentacao.json), com links, IDs/dependências e hashes. Commit/push desta revisão serão informados após confirmação; este registro não atesta publicação antecipadamente.


## Revisão arquitetural L3 e continuação L4

[Revisão histórica L3](relatorios/REVISAO-L3.md), [ADR 025](decisoes/SEMANTICA-P2.md) e [ADR 026](decisoes/WORKERS-E-MEDICAO.md). Mantidos todos os estados de execução anteriores; nenhuma tarefa M0 foi concluída nesta revisão. Seis incrementos L4 planejados: medição/ledger, worker persistente/recursos, IR/Rust, expansão do corpus, contexto e preparação competitiva.

A próxima implementação tem contrato específico: XRW2 conclui por mensagem sem EOF; reservas incluem respostas ainda retidas pelo pool; CPU/RSS identificam método e lacunas. P2 diferencia escopos/namespaces, fato/candidato/unknown e dependências negativas. Quatro pilotos históricos de correção permanecem separados da admissão global; a projeção dos slots restantes está no parecer.

Host literal15.0, mac descartável, modelos/tetos e licença de distribuição permanecem pendências nos respectivos cartões. Não impedem L4-01 local/L4-03. Gates não avaliados. [Verificação documental](relatorios/logs/revisao-L3/documentacao.json) registra links, IDs/estados e hashes; publicação comunicada após commit/push.

## Execução do primeiro incremento L4

[L4](relatorios/L4.md) registra os critérios dos primeiros recortes L4-01/02/03, revisões independentes e falhas corrigidas. Nenhum cartão M0 adicional foi encerrado: tokenizer mede conteúdo controlado; ledger é fake; P2 usa um recorte Rust; o benchmark de recursos do pool permanece pendente. A [CI38248278388](https://github.com/wkoch/xrai/actions/runs/38248278388) do código `1d2d40a` passou nos três jobs; receipts/replay/verificadores reconciliados em L4. L4-04/05/06 seguem como atividades de execução restantes, conforme o parecer vigente. Não surgiu decisão arquitetural nova impeditiva.

## Revisão arquitetural L4 e atividades L5

[Revisão histórica L4](relatorios/REVISAO-L4.md) aceita os recortes L4 sem concluir novos cartões. Revalidação offline dos recibos nativos passou: fontes no SHA, replay/medição, ledger e resultados de workers/semântica. [Registro desta revisão](relatorios/logs/revisao-L4/recibos-nativos.json); não é nova execução de CI ou testes Rust.

L4-P01/P02 resolvidas no [ADR 027](decisoes/CONTEXTO-P3.md): perfil v3 experimental para comparação que o verificador v2 ainda não suporta, obrigações/seleção, orçamento integral e expansão vinculada ao par original. Primeiro incremento implementado em L5-01; aceite integral continua pendente. L4-M01 esclarece quatro smokes pareados totais (um por família), sem ampliar a obrigação para 16 tarefas; errata no ADR 026. L5-02/03/04/05/06 continuam semântica, recursos, corpus, adapter e preparação competitiva.

Estados dos 41 cartões e gates preservados. Persistem host literal15.0, mac descartável, recursos/teto de modelo e licença nos momentos próprios. [Verificação documental](relatorios/logs/revisao-L4/documentacao.json) registra evidências; publicação só será informada após confirmação de commit/push.

## Execução do primeiro incremento L5

[L5](relatorios/L5.md) registra contexto P3, perfil documental v3, seleção/expansão e recursos de workers, com evidências por critério e pendências para o Arquiteto. M0-09 passou a em andamento; os demais estados e os gates permanecem. A matriz sintética não encerra M0-06 e a vertical de desenvolvimento não encerra M0-09. D1 permanece0/32; L5-04 tem alocação condicional32 verificada; os quatro dossiês novos continuam 0/4 e nenhuma tarefa foi admitida. Readiness corrente conciliado com L4-M01: quatro smokes pareados no total, uma tarefa por família, oito sessões mínimas antes de retries, sem chamadas pagas.

## Revisão arquitetural L5 e retomada

[Revisão histórica L5](relatorios/REVISAO-L5.md) aceita os recortes P3/v3 e recursos sintéticos; não conclui novos cartões. Revalidação local: 59 hashes de fontes, 199 artefatos, quatro provas P3 e duas matrizes de 18.900 pedidos aprovados. [Recibo](relatorios/logs/revisao-L5/evidencias.json); nenhuma nova execução nativa/competitiva.

L5-C01 permite realocar candidatos inadequados preservando os pisos; L5-P01 mantém falha em 2k como observação da implementação; L5-P02 separa ablação de P2 e baseline lexical; L5-R01 acrescenta controle direto com cache equivalente; L5-E01 exige proveniência recuperável dos executáveis de novos runs. Sem novo ADR ou lote: os seis incrementos L5 continuam, priorizando dossiês reais 0/4 e Rust R3.

41 cartões/estados/dependências e gates preservados. M0-09 permanece em andamento, como já registrado pelo Implementador; D1 global 0/32. Host literal15.0, mac descartável, recursos/modelo/teto e licença seguem nos momentos próprios. [Checks documentais](relatorios/logs/revisao-L5/documentacao.json); publicação comunicada somente após commit/push confirmado.

## Avaliação arquitetural da continuação L5 e v1.0

[Revisão anterior](relatorios/REVISAO-L5-CONTINUACAO.md): R3 e provas comportamentais Rust/JS aceitos no recorte; verificação offline de 55 arquivos e oito fontes, dois ZIPs de corpus e verificadores de curadoria aprovados. Proveniência nativa conciliada por recibos, sem nova execução ou download de binários nesta revisão. [Evidências](relatorios/logs/revisao-v1/evidencias.json).

São 9 cartões concluídos, 7 em andamento e 25 não iniciados entre os 41 M0/M1; M1 ainda não começou. Isso não é percentual do v1.0. C02 reconhece 2/4 pares comportamentais/revisados e separa evento incremental por família da elegibilidade individual; contadores oficiais dos casos aguardam conciliação pelo Implementador e D1 permanece 0/32. Nenhum estado de cartão ou gate foi alterado pelo Arquiteto.

[ADR028 / roteiro v1](ROTEIRO-V1.md): produto estabilizado no escopo comprovado, sem exigir todo M2–M5. Seis cartões V1-01…06 condicionais pós-G2, todos não iniciados, separados dos 41 atuais. Interface, recursos, migração/recuperação, uso do artefato, distribuição e qualificação de release. Sem data/percentual fictícios. [Checks documentais](relatorios/logs/revisao-v1/documentacao.json); publicação desta documentação comunicada após commit/push confirmado.

## Execução da conciliação C02

[Entrega e evidências](relatorios/L5-C02.md): schemas/verificadores/casos/plano representam estados separados, preservando seed e recibos. Matriz factual reconhece4/4 novos dossiês elegíveis e oito tarefas elegíveis ao incluir os pilotos; projeção condicional24/11/10/12, admissão global0/32. Gate só aceita evento requerido state_config na quota por família. Python/Go comprovados no código e02370a, CI38294106923, com dois ZIPs/relatórios reconciliados; os estados dos41 cartões permanecem.

## Revisão arquitetural L5-C02

[Revisão corrente](relatorios/REVISAO-L5-C02.md) aceita C02 e quatro novos pares no recorte; oito tarefas elegíveis contando pilotos, cinco complexas/seis históricas/oito multimódulo. Restam condicionalmente 24 tarefas, 11 complexas, 10 históricas e 12 multimódulo. São seis tarefas adicionais por família; os quatro casos de estado estão incluídos nessas 24. D1 continua 0/32 e nenhum gate foi avaliado.

C03 distingue elegibilidade preparada e readiness de campanha: integrar recibos reais A→B e comparação integral com rebuild ao gate consumido pelo executor. S01 resolve a classificação dos alertas como setup congelado do Gitea, com avaliação de exposição/tratamento por advisory ainda a executar. Nenhuma dependência/alerta foi alterado ou fechado pelo Arquiteto. Próximas entregas: eventos/C03, TS/JS e recuperação/adapter; demais L5 preservados.

Revalidação offline de dois ZIPs e 27 arquivos exportados, provas/matriz/slots e recusa do gate global aprovadas. Manifests históricos conferidos nos commits correspondentes. Consulta autenticada de alertas somente leitura. [Evidências](relatorios/logs/revisao-L5-C02/evidencias.json), [snapshot de dependências](relatorios/logs/revisao-L5-C02/dependencias.json) e [checks documentais](relatorios/logs/revisao-L5-C02/documentacao.json). Sem nova execução upstream/nativa/competitiva; 41 estados e seis cartões V1 condicionais preservados. Publicação desta revisão comunicada após commit/push confirmado.

## Detalhamento da próxima execução com agentes

12/10/2026: HEAD remoto consultado e checkout local em `a8f3764`; nenhuma nova entrega do Implementador. Dois agentes de arquitetura revisaram somente leitura C03/dispatch e adapter TS/JS. [Roteiro concretizado](L5-PROXIMA-EXECUCAO.md): três fatias C03 e três TS/JS dentro dos IDs L5 existentes; formato de avaliação S01. Smokes D0/seed não exigem D1 completo; campanha exige. Perfil TS/JS inicial é explicitamente limitado e experimental.

Nenhum aceite, gate ou estado de cartão mudou. Oito tarefas elegíveis, zero admitidas, quatro eventos reais pendentes; 9 cartões concluídos, 7 em andamento, 25 não iniciados e seis V1 condicionais. [Checks e escopo da revisão](relatorios/logs/proxima-execucao/checks.json). Nenhuma reexecução de provas históricas, upstream, CI ou chamadas de modelo. Commit/push desta documentação informado após confirmação.


## Implementação C03/S01

[L5-C03](relatorios/L5-C03.md) registra gate/dispatch fake consumido, 23 testes, quatro descritores state_config required preparados, 18 testes e primeiro protocolo persistente Rust com comparação integral antes/depois/rebuild. Prova nativa ainda pendente neste checkpoint; nove checks estruturais passaram, 21 contraprovas aguardam export real. [S01](relatorios/L5-S01.md): 55 decisões bloqueantes e 32 testes; guard integrado antes de download e na referência com `!cancelled()`. Nenhuma execução Go/provider ou fechamento de alerta. Quatro eventos preparados/zero executados, oito elegíveis e D1 global0/32; estados dos cartões/gates preservados.

Primeira tentativa C03 publicada em `5191baa`: evento+verificador passaram, job38309110235 falhou somente na escrita da cópia readonly usada por uma contraprova. Falha/ZIP/metadata preservados; correção do teste passou30 checks offline no export real, com36 checks adicionais do reconciliador. Aceite CI integral aguarda segunda tentativa dedicada; código produtor/oracle permanecem congelados.


## Aceite nativo do primeiro evento C03

Código `4972f02`, CI38309739709 aprovada,30 checks e [ZIP/API/recibo recomputados](relatorios/logs/L5-C03/native-proof/reconciliation.json). Quatro descritores preparados; Rust1/4 executado e conciliado no mesmoIndex A→B versus rebuild independente completo. Três eventos restantes não executados. Gate offline/fake permanece separado de campanha/provider real; D1global0/32 e oito elegíveis inalterados.37 contraprovas de metadata/ZIP passaram. CI regular5191baa passou emLinux/macOS/contratos. [Relatório corrente e pendências](relatorios/L5-C03.md); estados41cartões eG0/G1/G2 preservados.

CI regular4972f02/run38309739317 também aprovada nos três checksLinux/macOS/contratos; dois probes upstream históricos skipped. ZIP/API/native-proof e revisão independente preservados emL5-C03. Nova descrição documental da proveniência do reconciliador foi recomposta data-only; produtor/inputs/oracle congelados permanecem iguais.

## Revisão arquitetural L5-C03 e continuidade

[Revisão corrente](relatorios/REVISAO-L5-C03.md) aceita fake/gate, quatro descritores, evento operacional Rust1/4 e guard S01 nos recortes. E02 resolve alocação prospectiva por mapa externo: preservar slots originais congelados, usar slots-2 na admissão, recomputar quotas e compensar projeção multimódulo19/20. Nenhum evento foi contado como novo dossiê elegível.

D01 define compromisso de envio/cancelamento; a contraprova fake observou cancelamento depois do Ledger.send e antes do adapter, sem chamar provedor. S02 separa inspeção de dados da execução bloqueada do setup. Próximas implementações incluem TSJS-A, três eventos de presença, recuperação/adapter e frentes L5 abertas. Oito elegíveis/0 admitidos, 9 cartões concluídos/7 em andamento/25 não iniciados; nenhum gate avaliado.

[Revalidação](relatorios/logs/revisao-L5-C03/evidencias.json): 275 hashes, ZIP/23 arquivos e recibo nativo reconciliados data-only, preparo/fake/S01 aprovados, três fases Go recusadas. [Contraprova](relatorios/logs/revisao-L5-C03/cancelamento.json), [alocação prospectiva](relatorios/logs/revisao-L5-C03/alocacao.json) e [checks documentais](relatorios/logs/revisao-L5-C03/documentacao.json). Arquiteto não executou binários nativos/upstream/CI/provider nem alterou implementação. Publicação informada após commit/push confirmado.

## Continuação E02/D01 e preparação das provas TSJS/presença

[L5-C04](relatorios/L5-C04.md): E02 validado com mapa prospectivo v2 e déficit multimódulo 19/20 explícito; quatro tarefas de estado preparadas, Rust 1/4 operacional, nenhum novo dossiê elegível, oito tarefas individuais e 0/32 admitidas. [D01](relatorios/L5-D01.md) separa reserva/compromisso/envio, com 17 testes e seis replays; CLI seed consumiu v2 e replay aprovado. [TSJS](relatorios/L5-TSJS.md) tem labels congelados de 45 casos e resolver limitado; resultados nativos ainda pendentes neste checkpoint. Três eventos de presença usam fontes React/Flow/sklearn/Gitea como dados e analyzer próprio em CI dedicado. Contraprovas locais sintéticas e reconciliador ZIP/API estão implementados. [Verificações offline](relatorios/logs/L5-C04/integration/checks.json); estados dos 41 cartões e gates preservados. S02 e diagnóstico factual de campanha continuam em paralelo, sem execução upstream/provider.

## Quatro eventos operacionais conciliados

CI presença38329111797/código3463bdc aprovada: três casos JS/Python/Go, 73 checks no job e 79 checks posteriores data-only no export real. [ZIP/API e 53 arquivos exatos](relatorios/logs/L5-C04/presence-native-proof/reconciliation.json). Progresso v2 agora recompõe quatro eventos operacionais (um por família), quatro preparados, zero novos dossiês elegíveis, oito individuais/0 admitidos. Déficit multimódulo 19/20 permanece. Primeira CI TSJS38329117468 falhou nos casos partial após clippy/build aprovados; ocorrências foram preservadas como unknown na correção, labels intactos e segundo aceite pendente. Estados de cartões/gates preservados.

## S02 disponível para revisão

[Inventário/contrato S02](relatorios/L5-S02.md) concluídos com 48 checks offline: bytes declarados do cache enumerados como ausentes no ZIP histórico, requisitos/versões separados de seleção e compilação unknown. Guard S01 e 55 alertas continuam bloqueantes. Nenhum downloader ou autorização de execução implementado; próxima análise depende de bytes/closure/contextos e contenção prospectiva. Continuidade L5, sem avanço de cartões/gates.

## TSJS experimental e preflight factual comprovados

TSJS38329944063/código96b377c aprovado e [ZIP/API recompostos](relatorios/logs/L5-C04/TSJS/native-proof/reconciliation.json):45 casos,13/13 referências resolvíveis nos labels, zero promoções indevidas, relação real uuid e callable unknown. Limites em[L5-TSJS](relatorios/L5-TSJS.md); nenhum novo dossiê/admissão. [D01 factual](relatorios/logs/L5-C04/D01/factual/proof.json) passou18 contraprovas e recomposição real em snapshot/cópia privada: quatro eventos operacionais, oito elegíveis,0/32 admitidos,19/20 multimódulo; provider/teto e demais requisitos faltantes continuam recusados. CI regular3463bdc38329094983 passou Linux/macOS/contratos, probes upstream históricos skipped. Frentes de recuperação/adapter/recursos seguem em implementação; 41 estados/gates preservados.

## Baseline lexical e alternativa reais

[L5-LEXICAL](relatorios/L5-LEXICAL.md) entrega API BM25/TF-IDF e expansão de fontes integrais sob limite do JSON em bytes; 27 checks e 64 células recompostas pelo raiz. Quatro famílias em subárvores capturadas; fontes@3 12/12 para ambos, anchors@5 10/12 e11/12 com perdas preservadas. Consulta/labels congelados antes do algoritmo; tokens/provider/agentes reais e revisão independente dos labels pendentes. [Evidências](relatorios/logs/L5-C04/lexical/root-recheck.json). Estados de cartões/gates e 8 elegíveis/0 admitidos inalterados.
