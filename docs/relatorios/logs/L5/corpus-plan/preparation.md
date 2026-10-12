# L5-04 — preparação da alocação condicional

12/10/2026. Este incremento entrega **32 slots planejados**, não 32 tarefas prontas. O verificador aceita consistência de alocação e retorna `planning_only=true`, `admitted_tasks=0`, `competitive_runs_allowed=false` e gate fechado. Não modifica D1-seed, tarefas qualificadas ou os quatro pilotos existentes.

São oito slots por família, com 2 correções, 2 contratos, 2 estado/configuração, 1 revisão e 1 controle. O plano conserva os IDs das quatro correções históricas existentes; somente Django permanece complexo. Targets condicionais de 16 complexas, 16 históricas e 20 relações entre módulos deixam **28 tarefas novas, 15 complexas, 12 históricas e 16 provas de relação** adicionais. Essas categorias se sobrepõem. Quatro eventos estado A→B no mesmo serviço são targets; sua execução ainda falta.

Cada família aloca dois complexos em cada um de dois projetos, com quatro primárias por repo. TS/JS aloca quatro TS em TypeScript e quatro JS em React. React é candidato provisório: SHA, porte conservador, setup, necessidade real de módulos JS e casos/oracles ainda não foram coletados. VS Code não é imputado a JavaScript. Duas novas complexas Tokio dependem de prova conservadora do piso após excluir testes inline; o piloto Tokio permanece não complexo. Se o piso não se confirmar, os slots complexos precisam de outro projeto Rust; não flexibilizar o requisito nem inventar arquivos/relações.

**Quatro novos dossiês continuam 0/4 entregues.** Os slots priorizados são uma correção Rust/rust-analyzer e contratos JS/React, Python/scikit-learn e Go/Gitea. Não há issue/commit/solução inventada para esses slots. Cada dossiê precisa de origem/linhagem real, arquivos/configuração/hashes, porte/módulos/relations conservadores, input natural, oracles ocultos, baseline falhando e referência/regressões passando, além de revisão independente. Portanto este preparo não satisfaz o aceite integral L5-04.

Comandos verificados com Python3.13.13 local, exit0:

```sh
python eval/scripts/verify_slot_plan.py
python -m unittest discover -s eval/scripts/tests -p test_slot_plan.py -v
```

22 testes adversos incluem falsa admissão/competição, contagem/ID/estrato/repo inválido, reclassificação de piloto, evidência falsa em slot novo, distribuição complexa, controle inflando quotas, pisos histórico/multimódulo, ausência de evento incremental, JS imputado a TS, prova JS omitida, dossiês declarados concluídos, redução artificial de pendências, tipos booleanos e adulteração de artefato. Validação da forma não estabelece a verdade dos targets.

Pendências para o Arquiteto: nenhum novo bloqueio arquitetural; porte/setup/rotulagem de novos candidatos, quatro dossiês e qualificação global continuam trabalho posterior. Os dois riscos condicionais específicos são piso Tokio e prova JS/porte React. O plano pode realocar candidatos segundo ADR021, preservando pilotos e pisos.
