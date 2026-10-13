# L5-E02 — Inventário fechado da compensação multimódulo

13/10/2026, Implementador. Continuação de E02 autorizada pela [revisão do Arquiteto](REVISAO-L5-C03.md#2-e02--conciliar-tarefa-congelada-e-slot-de-admissão). Esta entrega é uma seleção negativa reproduzível no recorte capturado; **o déficit continua 19/20**, sem novo mapa/plano nem promoção de tarefa. Somente Python próprio e leitura de dados, sem aquisição, execução upstream, Cargo, provider ou nova CI dedicada.

[Protocolo](../../eval/qualification/e02-compensation-v1/protocol.json), [freeze anterior ao algoritmo](../../eval/qualification/e02-compensation-v1/freeze.json), [inventário recomponível](../../eval/qualification/e02-compensation-v1/inventory.json), [verificador](../../eval/scripts/e02_compensation.py) e [contraprovas](../../eval/scripts/test_e02_compensation.py). [Evidências locais](logs/L5-C06/E02-compensation/evidence.json) e [37 testes, zero skips](logs/L5-C06/E02-compensation/tests-final.stderr).

## Resultado útil para a seleção

O universo contém os oito dossiês já individualmente elegíveis na matriz C02 e os quatro descritores de estado, cruzados contra os 32 slots prospectivos v2. As **384 combinações** produzem **12 pares compatíveis** em repositório/família/tipo/linguagem, **zero compensações demonstradas nesse recorte**. A matriz C02 é fonte histórica vinculada por SHA; o novo código não reexecuta nem redefine sua qualificação. A elegibilidade factual corrente continua sendo responsabilidade do consumidor existente.

| Grupo | Compatibilidade e evidência | Resultado |
|---|---|---|
| Tokio, TypeScript, Django e Prometheus, correções Q1 | Relações necessárias já qualificadas no dossiê; um slot correction por mesmo repo/família | Esses quatro slots já têm meta multimódulo. Copiar a tarefa cria linhagem duplicada, sem compensação |
| rust-analyzer, correção RA-23422 | Três módulos, relações de diagnóstico/validação/travessia de padrões; slot Rust-correction-2 | Já creditado no alvo multimódulo |
| React, sklearn e Gitea, contratos existentes | Respectivamente hooks/reconciler/work-loop; composição/pipeline/output; converter/modelo/sanitizador | Já creditados nos três slots contract_change-2 |
| Rust de estado rand.rs | Mesmo arquivo de 735 bytes nos dois lados, configuração 2018→2024 | Unidade de produção única, sem relação entre módulos |
| React, sklearn e Gitea de presença | Dois arquivos em B, mas queries/oracle só exigem disponibilidade e SHA | Relação necessária para o problema congelado não demonstrada; dossiês individuais ainda não qualificados |

Os oito dossiês possuem IDs e linhagens distintos; os quatro descritores têm quatro identidades próprias. O inventário conserva essas doze identidades e aplica o mapa externo vigente para os slots de estado, sem relabelar `slot_id` histórico. **Uma tarefa existente movida para review/control conflita com seu tipo e não vira outra tarefa.** Todos os oito repos continuam com quatro slots; metas complexas/históricas permanecem 16/16.

Duas âncoras literais foram recompostas nos bytes B capturados, com hash, byte range e linha:

- ReactHooks.js importa `ReactCurrentDispatcher`; ReactCurrentDispatcher.js exporta esse valor. Origem linha 19, destino linha 23.
- metrics/__init__.py importa de `_ranking`; `_ranking.py` contém `roc_auc_score`. Origem linha 32, destino linha 420.

Esses textos ajudam a escolher uma próxima tarefa, mas **não demonstram necessidade dessa relação para o oracle atual**. O oracle de presença retorna apenas `{available, sha256}` por caminho; não pede import/export nem comportamento entre unidades. O leitor conserva `semantic_resolution_proven=false` e crédito zero. Para Go não foi preregistrado witness de relação entre path.go e url.go; isso não é prova de inexistência de relações no pacote ou repositório.

## Critérios e contraprovas

| Critério | Evidência |
|---|---|
| Seleção anterior ao algoritmo | Freeze de 43 entradas, timestamp UTC e ausência registrada dos dois novos scripts; SHA `f39ac4d5ba3089089aa79cdb94e0dac297aa15afeee069f5ec18dea394bd3996` |
| Derivação integral | Recompõe os 384 pares, inventário, unidades B/hash/tamanho, targets e contagens; CLI `--inventory` exige igualdade completa com a recomposição |
| Nenhuma flag cria evidência | Proposal só recebe `task_id` e `slot_id`; booleans de multimódulo, aliases ou linhagens inventadas recusados |
| Linhagem e teto | Task/slot duplicados, cópia por alias, slot desconhecido, mudança repo/família/tipo/linguagem (JavaScript não vira TypeScript por alias TSJS), quinto slot no repo, extra/duplicado no layout recusados |
| Quota honesta | Flag para chegar a 20, projeção informada distinta da derivada e int no lugar de bool recusados |
| Proveniência | Digest reancorado, byte histórico alterado, symlink, paths com escape/alias, JSON duplicado/não finito recusados; todos os 43 inputs históricos/protocolo permanecem vinculados |
| Recusa de promoção | Contraprovas de elegibilidade, admissão, campanha e crédito da relação no inventário recusadas; oito elegíveis históricos, zero novos elegíveis, zero admitidos |

O código não usa mocks para produzir o inventário factual; contraprovas alteram cópias de dados e diretórios temporários. Não executa probe.py, código capturado nem artefatos nativos. Limites: 4 MiB por input, 16 MiB no conjunto, exatamente 43 entradas de freeze e 32 slots; propostas de análise limitadas a 32, nunca consumidas pela admissão. Primeira recomposição e primeira rodada de 36 testes passaram; revisão final acrescentou a contraprova explícita JavaScript/TypeScript, chegando a 37 testes, sem mudar inputs/rótulos congelados. Logs iniciais preservados.

## Pendência concreta para o Arquiteto

**Selecionar uma tarefa natural independente cujo problema/oracle exija a relação entre unidades, em um dos slots com meta multimódulo false e tipo/repositório compatíveis.** Nenhuma das doze tarefas congeladas satisfaz essa condição adicional. Reutilizar as importações de React ou sklearn como problema novo exigirá comprovar independência de linhagem, universo de busca/contexto, configuração/exclusões, rubrica e segundo leitor; não basta acrescentar um novo nome ao evento atual.

O recorte capturado completo dos oito repos pode conter outras tarefas. Esta auditoria não afirma que não existe candidato natural nessas fontes; demonstra que **nenhum candidato já qualificado/preparado neste universo fechado resolve o incremento exigido**. Próxima seleção poderá inspecionar fontes já autenticadas como dados para escolher um problema distinto e congelar tarefa/oracle antes dos resultados. Isso permanece pendência de seleção/qualificação, sem novo cartão ou mudança de gate.

Não foram alterados mapas v1/v2, descritores, recibos, consumidores históricos, admission, workflows, plano do Arquiteto ou estado da implementação. Tier 2/codebase-memory geração `2026-10-13T17:13:28Z`, cobertura best-effort e leitura direta; JSONL e novos scripts/inventário sem tracking foram lidos/recompostos diretamente como dados. Duas consultas graft deste agente pouparam aproximadamente 8.389 tokens.

Atualização de autoridade durante a execução: o Arquiteto publicou b065e33/[REVISAO-L5-C05 §5](REVISAO-L5-C05.md#5-e02--compensação-concreta-e-qualificação-dos-eventos), escolhendo Django/Python-state_config-1 para investigar. Este inventário anterior não contém esse novo candidato nem altera a escolha. A próxima curadoria está em andamento; déficit continua19/20 até revisão factual, sem recalcular a matriz histórica como se houvesse nova tarefa. Recheck root37tests/0skip e CLIrecomposição passaram emPython3.13.13.
