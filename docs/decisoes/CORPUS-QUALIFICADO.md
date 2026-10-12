# Corpus de desenvolvimento e admissão do piloto — ADR 021

Data: 11/10/2026. **Decisão do Arquiteto, em resposta a L1-C01.** Aplicável antes de qualquer resultado competitivo. Resolve a elegibilidade; a execução fica em M0-03.R1. Não altera os limiares de G0/G1/G2.

## Decisão e motivo

Aceitar a entrega atual de M0-03 como **corpus inicial para desenvolvimento**: 20 D0, 32 propostas D1, fontes reproduzíveis, oracles e fixtures. Chamar as 32 propostas de **D1-seed**. Elas permitem implementar materialização, replay, adapters e regressões; **ainda não são o D1 qualificado para decidir G0**.

Os oito upstreams são reais, mas os 20 snapshots têm apenas 7–37 arquivos cada, incluindo documentação/testes; somam versões repetidas de bibliotecas pequenas. Das 32 propostas, 19 citam um único arquivo relevante, 11 citam dois e duas citam três. Isso não mede relações efetivamente necessárias nem demonstra dificuldade em bases grandes. Os prompts frequentemente nomeiam o ponto da solução; revisões descrevem a regressão esperada. Os cenários de estado são aplicados antes da primeira consulta, portanto não comprovam invalidação de um índice existente. [Evidência desta revisão](../relatorios/logs/revisao-L1/corpus.json).

Requisitos locais e regressões controladas **podem** ser tarefas válidas. Não exigir 32 issues públicas, nem confundir uma fonte upstream com um problema representativo. Exigir proveniência explícita, necessidade real de contexto e oracle independente. Preserve os arquivos, IDs, linhagens e resultados atuais; não reescreva os logs para sugerir um aceite anterior.

O escopo original foi dividido explicitamente: M0-03 encerra a preparação inicial; **M0-03.R1 recebe a qualificação obrigatória antes de M0-12/G0**. M0-04/05/08 podem usar o material inicial imediatamente. A mudança remove uma dependência desnecessária do trabalho local, sem dispensar a prova em projetos complexos.

## Contrato de admissão do D1

O implementador prepara uma versão de **32 tarefas primárias**, escolhidas antes das execuções comparativas. As 32 atuais não são somadas a essa amostra. Casos reaproveitados preservam a linhagem; casos substituídos continuam como regressões suplementares.

| Dimensão | Critério obrigatório de M0-03.R1 |
|---|---|
| Famílias e tipos | Oito por família: duas correções, dois contratos, dois estado/configuração, uma revisão e um controle simples. Rust, TS/JS, Python e Go; ao menos duas tarefas TS e duas JS no grupo conjunto. |
| Projetos | Pelo menos dois repositórios por família; máximo de quatro tarefas primárias por repositório. Commits completos, arquivos/tamanhos/hashes e licenças preservados. |
| Relações necessárias | Pelo menos 20 das 28 tarefas fora dos controles precisam de evidência em dois ou mais módulos de produção. Documentar a relação concreta; testes, README e arquivos triviais não inflam essa contagem. |
| Bases grandes e complexidade | Pelo menos 16 tarefas, quatro por família, em pelo menos dois projetos por família, com ao menos duas tarefas complexas de cada projeto. Cada tarefa exige três módulos de produção, dois subsistemas/pacotes e um caminho de pelo menos duas relações relevantes. |
| Porte desses projetos | Checkout completo elegível com pelo menos 50 mil linhas não vazias de produção **ou** 500 arquivos de produção. Excluir gerados, vendored, testes e documentação da contagem; registrar método e exclusões. Este é um piso operacional da prova, não uma definição universal de complexidade. Não acrescentar arquivos artificiais para alcançá-lo. |
| Origem do problema | Pelo menos 16 tarefas fora dos controles, quatro por família, ligadas a pedido, incidente, PR ou mudança histórica pública verificável. Até 12 podem ser requisitos/regressões controlados sobre uso real, com motivação e origem claramente distintas. Controles não contam para esse piso. |
| Simplicidade | Manter quatro controles simples para medir overhead. Um problema pequeno pode permanecer nos demais estratos, desde que respeitados os pisos acima; não inventar dependências desnecessárias só para cumprir contagem. |
| Independência | Sem variantes do mesmo patch como casos independentes. Registrar parentesco com D0, seed e outras tarefas, inclusive entre repositórios/forks; agrupamento por repositório continua na análise. |

O checkout fornecido aos braços deve preservar o universo de busca natural, manifests e configuração pertinente. Não reduzir um projeto grande aos três arquivos da resposta. Dependências externas e comandos permitidos ficam fixados; sua instalação é trabalho de avaliação, não nova dependência runtime do xrai.

Repositórios exatos são escolha de execução orientada por esses critérios, sem nova aprovação arquitetural por candidato. Primeiro faça triagem de porte, build/probe reproduzível e disponibilidade de casos; só então invista na rotulagem. A triagem não usa vitórias do xrai. Registre candidatos descartados e motivo; falta de dados suficientes mantém R1 pendente, não reduz o piso silenciosamente.

## Entradas e oracles

1. **Pedido natural:** entregar sintoma, comportamento desejado e informações realmente disponíveis ao usuário. Stack trace, API ou arquivo mencionado na issue podem permanecer, com origem atribuída. Não acrescentar a lista do oracle, caminho de solução, nome do símbolo a alterar ou diagnóstico de revisão para facilitar a recuperação. `relevant_sources`, capacidades necessárias e rótulos ficam somente no avaliador.
2. **Correções e contratos:** testes comportamentais/tipos executáveis, independentes do extrator, comandos e ambiente fixados. Demonstrar baseline falhando e referência passando no requisito, mais testes relevantes de regressão passando na referência. Ausência de novo teste não pode ser substituída apenas por julgamento de LLM ou igualdade textual de patch. Manter solução/testes ocultos fora do workspace do agente.
3. **Revisão:** entregar diff e contexto natural da mudança, sem revelar o defeito esperado. Oracle contém defeitos verificáveis, severidade e critério de adjudicação cega ao braço. Uma descoberta válida não prevista não é falso positivo automático: exigir reprodução e registrar adjudicação para todos os braços. Acrescentar controles negativos de revisão para calibrar o julgador/harness, sem inflar as 32 tarefas primárias. O orçamento de falsos positivos do protocolo permanece.
4. **Perguntas/configuração:** rubrica factual com fontes e testes de configuração quando aplicáveis. Não exigir que o agente reproduza o mesmo caminho textual do oracle se a resposta correta tem outra evidência válida.
5. **Estado incremental:** pelo menos um caso por família segue a sequência abaixo. Edição já aplicada antes de indexar é rotulada `cold_changed_checkout`; não é prova de atualização. Outros tipos de estado permanecem explicitamente classificados.
6. **Revisão dos rótulos:** registrar autor, segundo leitor, hashes dos artefatos revisados, achados e correções. Os 32 oracles atuais ainda dizem `second-reader audit pending`, apesar do relato de revisão. Conciliar cada recibo com a evidência existente ou realizar a revisão faltante; não trocar todos os rótulos por sucesso sem rastreabilidade. O Arquiteto não será necessário para aprovar rotineiramente cada tarefa que cumprir este contrato.

```text
materializar A → iniciar braço e indexar A → consulta de aquecimento
→ aplicar evento B do avaliador → consultar o MESMO índice/serviço
→ comparar resultado com oracle de B e reconstrução integral de B
```

O evento altera bytes/configuração/inventário e, no caso adverso, preserva tamanho/mtime. Conservar cache e processo nos braços que os possuem; registrar mecanismo equivalente para ferramentas sem serviço persistente. Timestamps, manifests, respostas e custos de atualização ficam no transcript. Todos os braços recebem o mesmo evento e a mesma informação pública; o tempo/custo da reconciliação entra na sessão.

## Artefatos e término de R1

- Preservar `eval/tasks/challenge-dev.jsonl` como seed. Produzir `eval/tasks/challenge-qualified.jsonl` com novos IDs/versionamento e vínculo `derived_from` quando houver reaproveitamento; não reutilizar um ID para tarefa diferente.
- Atualizar `eval/corpus.toml`, schema/verificador/materializador e gerador para distinguir `seed`, `qualified` e `supplementary`. O campo atual `architect_review_pending...` é legado a corrigir. Nenhum default pode promover o seed silenciosamente a campanha G0.
- Produzir relatório de admissão com matriz tarefa × família/tipo/origem/repo/porte/relações, hashes de prompts/oracles, comandos/resultados de probes, recibos de revisão e motivos das substituições. Verificador rejeita contagens insuficientes, campos ausentes e linhagens duplicadas; a revisão de necessidade semântica não é substituída por contagem de arquivos.
- Preparar eventos incrementais e oracles em R1; M0-04 implementa seu executor. R1 não depende do harness pronto. M0-12 exige ambos e recusa conjunto não qualificado antes de iniciar modelos.
- Manter o seed acessível apenas como desenvolvimento/regressão e registrar resultados separadamente. Não chamar 64 arquivos de 64 desafios independentes.

O aceite é dado pelo checklist e pelas evidências, dentro da autorização existente. Não há nova aprovação do Arquiteto obrigatória para encerrar R1. Uma impossibilidade material de cumprir o desenho deve vir acompanhada de evidência e proposta; tarefas locais independentes continuam.

## H1 e interpretação dos resultados

H1 continua reservado, proposto em 120 tarefas e com teto H1+H2 de 240. Preserva pelo menos três projetos por família, dois novos em relação a todo D0/seed/D1 qualificado; pelo menos metade das tarefas e metade de cada família devem satisfazer o recorte complexo acima. Estratos, controle simples, origem e pesos são fixados antes dos resultados. Não preparar soluções H1 neste checkout.

Na análise de G0, além dos limiares existentes no conjunto, reportar separadamente as 16 ou mais tarefas complexas: o candidato precisa melhorar sucesso nesse recorte, com sinal em pelo menos duas famílias, e respeitar os mesmos tetos pontuais de custo por tentativa/sucesso. Vitória concentrada em controles ou tarefas pequenas não justifica investimento na tese de bases grandes. Esse recorte é exploratório, sem alegar significância em 16 casos; resultado ausente exige foco/revisão, não aprovação automática.

G1 continua exigindo os intervalos e guardrails do protocolo. Reportar o recorte complexo e não extrapolar uma vitória agregada para escala não comprovada. Amostra pequena, efeito incerto ou dificuldade de construir corpus são resultados informativos sobre o risco do investimento.

## Alternativas consideradas

Aceitar todas as propostas como prova suficiente economizaria preparação, mas premiaria tarefas pequenas e pistas da resposta. Exigir exclusivamente incidentes públicos eliminaria experimentos controlados úteis sem resolver esses vieses. Expandir a amostra agora multiplicaria runs pagos antes da primeira evidência. A decisão mantém 32 tarefas primárias, reaproveita os controles e concentra esforço na qualidade dos casos e julgamentos.
