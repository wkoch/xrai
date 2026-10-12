# C02 — conciliação individual e admissão global

12/10/2026. O conciliador próprio `eval/scripts/verify_c02.py` revalida fontes como dados, os quatro pilotos preservados, os dois pares históricos Rust/JS e seus recibos. Não executa árvores upstream, probes históricos, modelos ou campanhas. `verify_slot_plan.py` compara a matriz integral com essa conciliação fresca: reescrever o relatório e recalcular seus hashes/contadores não permite promover fatos.

| Critério C02 | Evidência / resultado |
|---|---|
| Curadoria, revisão e comportamento distintos | `c02-state.schema.json`; estados separados nos dois `case.json` e seis linhas de `c02-status-matrix.json` |
| Elegibilidade individual por critérios | Quatro pilotos passam `validate_task_rows` com IO; Rust/JS passam verificação de captura, recibos comportamentais e revisão independente atual. Seis elegíveis, dos quais três complexos, seis históricos e seis com relações multimódulo |
| Hashes da revisão de rótulos | Rust vincula request, hidden oracle, fontes e patch atuais; o hash antigo de `case.json` é apenas tracking histórico preservado. JS recebeu revisão final do oracle9938 e input, patch e sete âncoras em `integration/js-final-artifact-review.json` |
| Eventos independentes dos pares históricos | Rust: suplementar/preparado/não executado; JS: não aplicável ao contrato. Nenhum é outra tarefa primária. O caso `state_config` selecionado como requerido exige preparo; o outro caso de estado/configuração da família pode ter outra classificação |
| Quota real de estado por família | Gate global conta apenas evento requerido em `state_config`. Correção/contrato suplementar não preenche quota. Não há execução nem preparo comprovado dos quatro casos reais requeridos nesta entrega |
| Projeção factual sem admissão | 26 tarefas, 13 complexas, 10 históricas e 14 multimódulo adicionais; dimensões sobrepostas. Novos dossiês elegíveis/comportamentais: 2/4. D1 admitido: 0/32 |
| Guard preservado | `global-gate-final.json`: exit1 esperado, exatamente32 tarefas ainda requerido; seed e conjunto qualificado não alterados |
| Contraprovas e regressões próprias | 23 testes C02, 25 de alocação, 9 de schema/admissão, 5 de pilotos. Seis mutações da matriz rehashada cobrem complexidade, família, unidade/source, origem histórica, relações multimódulo e elegibilidade |

Recibos são imutáveis. `reconcile-initial.json` preserva um erro do novo collector (raiz `docs` em vez de checkout), corrigido no retry. `slot-unit-first.json` e `slot-recompute-and-mutations.json` preservam dependências de import ausentes na API carregada por `importlib`; o caminho dos módulos próprios foi corrigido, sem contornar verificação. A tentativa inicial de usar o venv temporário antigo encontrou arquivo ausente; criou-se `/private/tmp/xrai-c02-tools` com `jsonschema==4.25.1`, sem instalar/executar projeto upstream.

O grafo Tier2 marcou `verify_c02.py` e a matriz como `metadata_changed` na verificação final retida; ambos foram lidos integralmente após as edições. Não é alegação de cobertura estrutural completa. Logs antigos, oracle/probe-plan históricos e derrotas anteriores permaneceram intactos; seus estados de tracking anteriores são conciliados por recibos atuais separados.

Pendências para o Arquiteto: selecionar/congelar os quatro casos reais de estado por família e depois preparar/executar A→B com processo/índice preservado e comparação integral B, incluindo unknown/configuração/gaps. Completar Python/Go e a amostra inteira antes de abrir D1. O exercício suplementar Rust continua útil e pendente. Não foi identificada nova decisão arquitetural necessária para a separação C02.
