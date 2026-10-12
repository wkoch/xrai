# Revisão da continuação L5 e direção para v1.0

12/10/2026, Arquiteto. Base `27290e4`; código da CI `c48b5993550fd258f1efe5677704a59d9eb73de0`. [Relato examinado](L5-CONTINUACAO.md). A avaliação de estágio e os critérios de lançamento estão no [roteiro v1 / ADR028](../ROTEIRO-V1.md). Este parecer escreve planejamento e registros de verificação; nenhuma implementação de produto.

## 1. Progresso aceito e limites

Aceitar R3 opt-in, correção conservadora de cfg composta e consumidor P3 no recorte documentado. Aceitar as provas comportamentais e revisão de fontes dos novos candidatos Rust/JavaScript. Não repetir os quatro runs de CI nem apresentar falha de setup como comportamento esperado do baseline.

| Evidência | Resultado e interpretação |
|---|---|
| CI 38283109016 | Cinco jobs aprovados no código acima; Rust 115 Linux / 114 macOS; harness 49+1 skip/45+5 skips |
| R3 | 34/34 corretos, 16/16 pré-rotulados resolvíveis; oito contraprovas/controles cfg aprovados e dois eventos sintéticos incremental=rebuild |
| Fonte real R3 | Tokio-test, três queries/uma resolvível; 201 chamadas unknown. Não mede cobertura de todas as chamadas |
| Rust real | Dois panics esperados no baseline; referência 2/2 e 16 regressões, locks preservados e teardown registrado |
| JavaScript real | Baseline 0/3, referência 3/3 e duas regressões em cada lado; checkpoint e aviso DEV atribuídos, sem silenciamento global |
| Proveniência | Recibos conferem 12 executáveis e quatro ZIPs originais na execução do Implementador; recuperação de artefatos até 10/01/2027 conforme metadata retida |

[Revalidação desta revisão](logs/revisao-v1/evidencias.json): 55 arquivos retidos e oito fontes de publicação com hashes corretos; conciliador de corpus reexecutado, inclusive bytes dos dois ZIPs locais e conjuntos completos 25/12; verificadores de curadoria Rust/JS aprovados. CI/semântica/contexto nativos foram conciliados pelos recibos retidos, **sem nova execução nativa**. Os binários/ZIPs nativos não estão no checkout nem no diretório temporário original nesta revisão; sua conferência byte a byte é evidência anterior do Implementador, não uma verificação repetida agora.

Estado real: 9 cartões M0 concluídos, 7 em andamento, 2 não iniciados; todos os 23 M1 não iniciados. CLI pública só help/version. Sem G0/G1/G2, sem resultado competitivo próprio e sem alteração de estados de cartão neste parecer.

## 2. C02 — Separar dossiê comportamental e evento incremental

O ADR021 exige **pelo menos um caso de estado A→B por família**; não exige executar A→B em cada correção/contrato histórico. Os novos slots Rust/JS são correção/contrato, não slots de estado. O `event-plan.json` Rust se declara exercício **suplementar** à correção; o caso JS declara expressamente que não é o evento de estado obrigatório. Apesar disso, ambos ficaram com `incremental_pending` como único impedimento para contar o dossiê. Há mistura de unidades de acompanhamento.

**Decisão C02:** reconhecer dois pares históricos com curadoria/revisão/probes comportamentais comprovados (**2/4 nessa dimensão**) e manter separadas admissão global e prova incremental. O Implementador deve conciliar schemas, verificadores, planos e relatórios para que representem esses estados separados. Não editar recibos históricos nem trocar `admitted:false` por true só por esta revisão. O quadro oficial de dossiês continua com 0/4 aceitos até essa conciliação local de critérios; D1 global permanece 0/32.

Preservar o exercício Rust já planejado como prova suplementar útil. Selecionar e congelar, antes das campanhas, os quatro casos que cobrem estado/configuração, um por família, sem duplicar a correção histórica como outra tarefa independente. Evento real exige processo/índice preservado e comparação integral com rebuild B no recorte declarado; não exige que todo o projeto seja semanticamente resolvido. Unknown/cobertura também entram na comparação. Eventos sintéticos R3 são regressões técnicas, não os quatro casos reais do corpus.

**Aceite da conciliação:** campos separados para curadoria/revisão, comportamento, preparo/execução de evento, elegibilidade individual e admissão global; guard continua recusando D1 incompleto. Se a revisão encontrar outro critério individual faltando, registrá-lo concretamente. Não acrescentar A→B universal para explicar um contador zero nem remover caso já congelado após derrota competitiva. Não há flexibilização dos pisos/quotas/independência de ADR021.

## 3. Próxima execução, com os mesmos IDs L5

| Prioridade | Atividade / responsabilidade | Próxima entrega revisável |
|---|---|---|
| 1 | L5-04 / corpus, materializador e verificadores | Conciliação C02; dossiês Python/scikit-learn e Go/Gitea ou substitutos elegíveis; casos reais de estado e matriz atualizada |
| 2 | L5-02 / frontends experimentais, IR e labels | Preservar R3/cfg; primeira fatia TS/JS de imports/bindings/exports com evidência e homônimos, mais trabalho R4 delimitado pelas perdas reais |
| 3 | L5-01 / recuperação/contexto e avaliador | Busca lexical sem âncora e alternativas em fonte real, comparadas sob mesmo pedido/limites; recall de evidência não identificada, custos de expansão e perdas |
| 4 | L5-05 / harness/adapters | Adapter real testável offline, configuração e estimativa concreta dos quatro smokes pareados; executar só dentro dos recursos autorizados |
| 5 | L5-03 / recursos | `direct_cached`, fontes reais, concorrência e decomposição conforme L5-R01; preservar matrizes e separar ganho de cache/IPC |
| 6 | L5-06 / avaliação | Triagem dos oito comparadores e preflight; desenho de campanha condicionado ao corpus/P2/P3 e orçamento |

A ordem é de valor da próxima entrega, não proibição de trabalho independente. Não criar novos agentes/chats por este roteiro. Os critérios originais da [revisão L5](REVISAO-L5.md) continuam válidos quando não concretizados aqui. Não recomeçar R1/R2/R3, retenção P3, proveniência nativa ou as provas Rust/JS aprovadas.

### L5-04: completar corpus e estado sem inflar amostras

Preparar Python/Go seguindo os critérios já definidos: origem/linhagem, fonte completa, porte conservador, três módulos/dois subsistemas/duas relações nos alvos complexos, setup fixado, input natural e oracles separados. Baseline/referência/regressões rodam no domínio permitido do harness. Novo dossiê não precisa ser histórico se seu slot é controlado; quotas globais continuam obrigatórias. Substituir candidato inadequado por evidência, sem nova aprovação por repo.

Depois da conciliação C02, produzir uma matriz **factual** por tarefa, separada dos targets. Somente se os quatro pilotos e os dois novos candidatos forem elegíveis e mantidos, a projeção passa a 26 tarefas restantes, 13 complexas, 10 históricas e 14 provas multimódulo adicionais. É projeção condicional, não admissão 6/32. O gate calcula os valores a partir de evidência; não alterar o contador global de 0 enquanto a admissão requer o conjunto completo.

### L5-02: tornar a interface comum útil a outra família

R3 está aceito no recorte; ampliar suporte só por casos externos pré-rotulados e motivo de perda. TS/JS é a próxima família porque há candidato JS real e parsing dos dialetos; começar por imports/exports/bindings demonstráveis, respeitando configuração/resolução de módulos. O caso React pode exigir relações não suportadas: capturar sua lacuna e usar uma fatia real mais simples para validar a interface, sem alegar resolver React inteiro. Labels e documentação oficial fixados antes de ajustar regras, sem executar JS/TS upstream para indexar.

Python e Go seguem o protocolo P2, com regras próprias. Rust R4 continua necessário; primeiro mapear perdas que pedem receptor/método, sem prometer resolver 201 chamadas Tokio por uma regra genérica. Incerteza e inferência incompleta não mudam de estado para melhorar taxa. Biblioteca maior continua opção quando o dossiê de perda provar a necessidade.

### L5-01/05: aproximar o experimento de uma tarefa de agente

Entregar recuperação lexical/estrutural de desenvolvimento com fonte exata, selecionar sobre dados permitidos e medir com rótulos externos. P2 desligado continua uma ablação; não chamá-lo de baseline competente sem recuperação equivalente. Preservar o ponto 2k recusado e medir overhead completo; não ocultar metadata ou wrappers para aparentar teto cumprido.

Ao mesmo tempo, preparar adapter real com fixtures de protocolo, ledger/cobrança desconhecida, isolamento e controles de orçamento. A próxima solicitação de recurso ao mantenedor, quando necessária, deve identificar provedor/modelo disponível, limite de sessões/tokens/retries, estimativa de custo total e domínio de execução. Não iniciar campanha paga por inferência de preferência por qualidade. A ausência desses recursos não bloqueia corpus, semântica e medições offline.

## 4. Avaliação até v1.0 e critérios de parada

O gargalo atual é transformar protótipos em evidência de utilidade nas quatro famílias. Produção ampla continua após G1. [ADR028](../ROTEIRO-V1.md) define o v1.0 como escopo comprovado estabilizado, com seis atividades condicionais pós-G2; não é necessário terminar M2–M5 inteiros. Nenhuma tarefa de estabilização é marcada executada agora.

Próximo balanço deve mostrar: novos dossiês por estado, eventos reais por família, cobertura/falsas promoções de frontends, recuperação/qualidade P3 e prontidão de agente/campanha. Guardar horas ativas e espera externa para estimativas futuras; contagem de testes/commits não mede distância em calendário. Não repetir ciclos somente de fixtures/proveniência sem avançar um desses resultados, salvo correção de falha concreta.

## 5. Verificação e publicação

Exploração dirigida: graft; codebase-memory Tier2, geração `2026-10-12T17:47:21Z`, cobertura de 14 paths sem lacuna registrada. Search/trace/snippet da entrada CLI confirmam scaffold. A busca do grafo não localizou funções R3 pelos filtros usados; leitura direta de `r3.rs` sustentou a inspeção da validação recursiva antes da combinação de cfg. Não inferir ausência de código por esse resultado vazio. Revisão limitada, sem auditoria exaustiva de runtime ou nova execução upstream.

[Evidências](logs/revisao-v1/evidencias.json) e [checks documentais](logs/revisao-v1/documentacao.json) preservam comandos/exits/hashes, contagem de cartões e limitações. Commit/push conforme AGENTS.md após verificação; não equivale a publicar 1.0.
