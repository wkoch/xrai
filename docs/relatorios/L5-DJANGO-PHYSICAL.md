# L5-04 — Django router v2 físico

14/10/2026. Implementador `/root/django_physical`. Contrato: §3 de `REVISAO-L5-C06-FECHAMENTO.md`. Esta fatia preserva todos os arquivos e receipts v1 e prepara uma execução física nova, em domínio Linux descartável. Nenhum Django, projeto upstream ou ELF retido foi executado localmente.

## Preparação concluída e aceite previsto

- Checkout completo pin `8abacfc36d755d8e762a4d2074601b8dc412bfee`: os mesmos 7.084 arquivos capturados/licenças, hash integral conferido pelo intake seguro. Políticas `DefaultPolicy`/`LedgerPolicy` permanecem byte a byte iguais ao v1.
- Pública v2 contém `ledger.LegacyEntry`, `managed=False`, e a exigência de nunca criar sua tabela, mesmo quando router isolado permite. A referência troca somente a ordem `primary,scoped` → `scoped,primary`. Baseline/ref recebem a mesma tarefa e modelos.
- Oracle independente tem 12 células A/B × dois aliases × três modelos e quatro controles físicos adicionais: all-None permite; componente sem método seguido de False recusa. Sentinelas externas ao alvo são preparadas por alias/processo.
- Segunda leitura `/root` antes de qualquer output físico: `logs/L5-C07/Django/root-oracle-review.json`. Freeze posterior `b15a9b8ccb6975918c1b0461a355e204517428a072ea4028ddd1977a191a4765`, nove inputs. Não ajustar os resultados esperados depois do run.
- O oracle chama `CreateModel.state_forwards`, obtém modelo histórico, chama `database_forwards` e schema editor/SQLite reais capturados. Observação de `ConnectionRouter.allow_migrate` delega a decisão original; células unmanaged exigem zero consultas durante a operação e controle isolado do router. Introspecção física verifica tabelas, sentinelas e bancos de nomes/inodes distintos.
- Bootstrap separado: Python 3.13.13 Linux x86_64, wheels asgiref 3.12.1 e sqlparse 0.5.3 por URL oficial/bytes/SHA256/licença. Extração de dados sem import/build/setup.py; cópia de executable/stdlib sem site-packages. Inventário de Python, libs dinâmicas/SQLite, dependências, licenças e source antes do primeiro import Django. Rechecagem após execução.
- Execução serial via `runner.execute` existente, com domínio PID/pidfd e teardown confirmado obrigatório. Bwrap interno monta checkout/runtime/deps somente leitura; material privado só no avaliador. Probe de visibilidade da ferramenta real tenta onze paths, incluindo traversal, link, índice e `/proc/1/root`; lê pública, recusa privados e escrita no checkout. Não há agente/provider/modelo envolvido nesse probe.
- Tetos prospectivos: 60 s por processo, 300 s lote, streams combinados 1 MiB (mais restritivo que 1 MiB por stream), scratch tmpfs 64 MiB, RLIMIT_AS 1 GiB/processo, NPROC 64 por UID, FSIZE 16 MiB/arquivo. Cgroup de memória/processos agregado **não** é alegado. Ambiente limpo, namespace sem rede, sem secrets, sem pacote herdado do host. Falha de domínio/teardown invalida o resultado e preserva workspace.

## Evidência local efetiva

`python3 eval/scripts/django_router_physical.py verify`: freeze/7.084 fontes/pública privada/12+4 planos conferidos. Receipt `logs/L5-C07/Django/preparation.json`: `oracle_executed=false`.

`python3 -m unittest discover -s eval/scripts -p test_django_router_physical.py -v`: **34 testes PASS, zero skips**. `tests.stdout` e `tests.stderr` retidos. São testes próprios de JSON, mounts, wheels e recusas; fixtures sintéticos não viram prova física. Incluem célula omitida/duplicada, int versus bool, unmanaged criado/router consultado, veto isolado apagado, sentinela, inode, origem, hashes da ordem/policy, decisão fabricada e promoção/provider recusados.

## Prova física e pendências

Workflow novo `.github/workflows/l5-django-router-physical.yml`, job `C07 Django real SQLite physical pair`, artifact `c07-django-router-physical-v2`. Entrada:

```text
python eval/scripts/django_router_physical.py fetch --cache CACHE
python eval/scripts/django_router_physical.py run --cache CACHE --output EVENT
python eval/scripts/django_router_physical_verify.py --output EVENT
```

Até a aquisição/autenticação do run, **prova física pendente**: nenhuma contagem de tabela, SQLite, visibilidade ou import real é promovida pelo preparo. A CI conserva instalação/readiness antesexec, quatro receipts originais do domínio, stdout/stderr, reports e pair. Verificador recompõe os 20 arquivos integrais, vínculos, 12+4 resultados, teardown e diferença entre `oracle_executed` e `requirement_satisfied`. É necessário autenticar APIs/ZIP e vincular o head/code da execução antes de aceitar a prova.

Para o Arquiteto: o comportamento físico testa uma cadeia do framework, mas necessidade multimódulo do agente ainda não está demonstrada. `multimodule=false`, projeção **19/20**, `individual_eligible=false`, `qualified=false`, `admitted=false`; nada atualiza E02/consumer ou D1 nesta preparação. Não há tarefa histórica nem ganho de agente medido. Reusar esses fatos prospectivamente somente depois da prova física e parecer sobre relações necessárias.

Integração root antes da primeira execução: verificador fixa os11 targets de ataque/4 públicos e os app/model/table/gate/router dos controles físicos. Contraprova anterior aceitava tabela sintética `unused`; fontes e fato retidos em `pre-verifier-hardening`. Quatro testes novos, total38PASS/zero skips emPython3.15.0; `root-tests.stderr` e `root-design.json`. Inputs frozen/expectativas físicas permanecem iguais; compilação/execução upstream local ausentes.
