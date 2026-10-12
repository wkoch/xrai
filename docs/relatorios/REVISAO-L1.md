# Revisão arquitetural L1 e próximo lote L2

Data local: 11/10/2026, America/Sao_Paulo; verificações em 12/10 UTC. Arquiteto. Base revisada: `0ae00e58f557489dc31348c4accced725c012cca`. Escopo: resolver minhas pendências e deixar atividades executáveis para a outra IA. Código do produto, scripts do corpus e workflow não foram alterados nesta entrega.

**C01, S01 e S02 estão resolvidas em arquitetura. O usuário pode liberar o implementador para L2.** Não resta uma confirmação rotineira do Arquiteto para esse início. A qualificação do corpus, os testes futuros e as provas nativas continuam atividades reais, não são concluídas por este parecer.

## Parecer e decisões

| Item | Resultado desta revisão | Execução e condição |
|---|---|---|
| L1-C01 | Aceitar D0 e 32 propostas como corpus inicial/D1-seed; exigir D1 qualificado para o piloto. Requisitos locais são admitidos sob critérios, sem fingir que todos vêm de issues públicas. [ADR 021](../decisoes/CORPUS-QUALIFICADO.md). | M0-03 concluída **no escopo revisado de preparação inicial**; qualificação original permanece em M0-03.R1, obrigatória antes de M0-12/G0. |
| L1-S01 | Lock exclusivo do dono, encarnação/epoch/tentativa e recuperação por estado de commit; PID ou heartbeat não provam abandono. [ADR 022](../decisoes/PERSISTENCIA-E-RETENCAO.md). | M1-04/19 após G1. Não aumentar o spike M0-07 agora. |
| L1-S02 | FTS de conteúdo externo por versão, busca limitada à revisão antes de top-k, pins persistidos contra GC e pressão com recusa de novas admissões. [ADR 022](../decisoes/PERSISTENCIA-E-RETENCAO.md). | M1-04/15/16/19 após G1, com medição e falhas reais. |
| Pisos do v1 | Baseline Ubuntu 24.04/glibc 2.39 e macOS 15.0 arm64; [ADR 020 atualizado](../decisoes/PLATAFORMAS-V1.md). | M0-05/M1-20 verificam ABI/autonomia no piso. Smoke em macOS posterior não comprova o piso. Windows continua pós-v1. |

Preservar sucesso como objetivo primário e os limites competitivos. A revisão acrescenta admissão e análise explícita de casos complexos para impedir uma vitória sustentada apenas por tarefas pequenas. Não observamos resultados de competição nem ajustamos thresholds em resposta a vitórias/perdas.

## O que a evidência sustenta

O verificador existente passou novamente: 52 tarefas materializadas, 20 D0/32 D1-seed, oito repositórios, 20 snapshots e 78 fixtures; zero arquivos de oracle nos inputs reconstruídos. [Comando/saída](logs/revisao-L1/corpus-check.json). Isso comprova a preparação mecânica, não isolamento efetivo do processo nem sucesso de agente.

A [inspeção de manifest, tarefas e metadados dos oracles](logs/revisao-L1/corpus.json), com hashes das fontes, encontrou:

- Snapshots com 7–37 arquivos e 18.072–200.965 bytes. Os 1.546.610 bytes totais somam snapshots repetidos, não representam uma grande base única.
- 19 tarefas com um arquivo relevante, 11 com dois e duas com três. Quantidade de âncoras não equivale a relações necessárias entre módulos.
- Oito fixes históricos, oito contratos locais, oito perguntas de fonte, quatro estados materializados e quatro revisões simuladas. Doze têm probe executável; os oito novos contratos precisam de testes/referências antes de avaliar agentes.
- Os 32 metadados D1 ainda declaram revisão por segundo leitor pendente, enquanto o relatório L1 registra revisão. R1 deve reconciliar evidência e hash por tarefa, sem atestar uma revisão ausente.
- O materializador aplica mudanças antes de entregar o checkout. M0-04/R1 devem acrescentar a sequência índice A → evento B → consulta no mesmo índice para medir atualização.

Leitura estrutural usou codebase-memory Tier 2 e fonte direta. [Cobertura consultada](logs/revisao-L1/graph-coverage.json): scripts/SQLite sem problema registrado, vários documentos mudados e JSONL sem frescor rastreado; todos os pontos usados nessas conclusões foram conferidos no filesystem. O sinal do grafo é best effort, não prova de completude. Graft foi usado uma vez para localizar as rotinas, com estimativa de 15.682 tokens poupados.

Os seis testes SQLite locais e 12 probes de regressão permanecem evidências **do implementador em L1**; não foram reexecutados nesta revisão documental. Também não executamos CI, agentes ou campanhas pagas. M0-07 e M0-02.R2 conservam seus impedimentos externos.

## L2 — atividades prontas, em ordem prática

O implementador recebe este lote quando o usuário o liberar. Pode alternar frentes conforme tempo de build/dados; esta lista não pede criar outros agentes ou conversas.

| Ordem | Cartão e primeiro incremento | Entregável revisável e aceite imediato |
|---|---|---|
| 1 | **M0-04, parte local:** executor/replay e baseline seletiva sobre D0/seed; registrar ambiente disponível. | Execuções roteirizadas identificadas como tais, eventos/timeouts/saída parcial e custos desconhecidos corretamente rotulados; isolamento de diretórios/processos e replay determinístico. Não concluir o cartão sem seus smokes reais restantes. |
| 2 | **M0-03.R1:** triagem de projetos e qualificação dos 32 casos. | Primeiro matriz de candidatos/porte/build/origem; depois prompts/oracles/probes e recibos de revisão. Critérios completos no ADR 021; atualizar manifest/materializador para impedir promoção acidental do seed. Não depende de M0-04 concluída. |
| 3 | **M0-05 e M0-08:** gramáticas incorporadas e filesystem/checkout. | Usar fixtures já entregues; evidência nativa local, versões/licenças/ABI e limites; registrar separadamente alvos ainda não executados. Não exigir harness pago ou corpus qualificado para começar. |
| 4 | **M0-06**, após M0-05, e **M0-11/P2**, após os critérios pertinentes de M0-04. | Isolamento/IPC e recortes semânticos do plano, sem construir frontends universais. M0-09/P3 segue P2; o piloto só após R1 e demais dependências. |
| Oportunidade externa | **M0-02.R2/M0-07:** retomar provas nativas quando infraestrutura mudar. | Registrar commit, runner/host e resultado dos testes do código correspondente. Runner equivalente pode provar o spike; R2 ainda exige comprovar o workflow previsto. Não repetir execução bloqueada sem mudança de condição. |

Cada incremento deve atualizar [STATUS-IMPLEMENTACAO.md](../STATUS-IMPLEMENTACAO.md), criar/atualizar `docs/relatorios/L2.md` com comandos/evidências e ser verificado, commitado e enviado a origin conforme AGENTS.md. Não misturar conclusão parcial com conclusão do cartão inteiro. Escolhas locais previstas pelos ADRs dispensam novo pedido ao Arquiteto.

## Impedimentos externos e definições posteriores

| Item | Responsável / momento | O que continua agora |
|---|---|---|
| GitHub Actions bloqueado por billing/limite; proteção retornou 403 na consulta anterior | Mantenedor/infra. O usuário já escolheu registrar prova pendente; esta revisão não muda cobrança nem permissões. | Todo o trabalho local de L2. M0-02.R2/M0-07 não são marcadas concluídas. |
| Teto monetário e recursos para modelos | Mantenedor antes do uso pago; implementador prepara manifest e estimativa concreta da matriz, usando disponibilidade real. | Replay, adapters, corpus, probes e spikes. Sem contratação ou campanha paga automática. |
| Hardware/modelos/configuração de campanha | Implementador registra o que existe, compara braços no mesmo ambiente e congela antes de M0-12; versão exata de modelos depende de disponibilidade nessa execução. | Não comprar hardware nem aguardar uma decisão abstrata para medir localmente. Escolha operacional dentro dos recursos autorizados. |
| L0-A01, licença do produto | Mantenedor antes de M1-20. | Código local e testes; manter `publish=false` e avisos das dependências. Não escolher a licença em nome do usuário. |
| Quotas, TTLs, limites e tamanho final H1 | Implementador calibra nos spikes/D1; M0-10 fixa antes de M1-A. | Aplicar invariantes e limites configuráveis; não inventar resultados ou prometer números sem medição. |

Nenhum desses itens reabre C01/S01/S02. G0/G1/G2 continuam não avaliados e M1-B não está liberado. Se a prova não demonstrar ganho suficiente, registrar resultado negativo/foco; não completar infraestrutura por inércia.

## Verificação desta entrega

O [registro documental](logs/revisao-L1/documentacao.json) confere links, correspondência plano/estado, cartões/dependências sem ciclos e ausência de alteração de código. O corpus foi revalidado pelo comando existente; os números e o limite da revisão estão acima. Não é necessário repetir testes Rust para mudanças exclusivamente documentais. Publicação só será comunicada após commit/push confirmado.
