# L5 — Dossiê Django de política de migração

13/10/2026, Implementador. Candidato escolhido pelo Arquiteto em [REVISAO-L5-C05 §5](REVISAO-L5-C05.md#5-e02--compensação-concreta-e-qualificação-dos-eventos): `L5-SLOT-Python-state_config-1`, Django. Entrega de **dossiê prospectivo com segundo leitor estático e modelo declarativo próprio**, ainda sem oracle comportamental executando Django e sem elegibilidade/admissão/crédito multimódulo. Plano v2 permanece **19/20**.

[Pedido e material do agente](../../eval/qualification/django-router-v1/agent/input.md), [caso](../../eval/qualification/django-router-v1/case.json), [universo de busca](../../eval/qualification/django-router-v1/search-universe.json), [oracle](../../eval/qualification/django-router-v1/evaluator/oracle.json), [rubrica](../../eval/qualification/django-router-v1/evaluator/rubric.json), [segundo leitor](../../eval/qualification/django-router-v1/evaluator/second-reader.json), [freeze](../../eval/qualification/django-router-v1/freeze.json), [verificador](../../eval/scripts/django_router_verify.py) e [42 contraprovas](../../eval/scripts/test_django_router.py).

[Evidência local](logs/L5-C06/Django-routers/evidence.json), [recomposição completa](logs/L5-C06/Django-routers/verification.json), [42 PASS, zero skips](logs/L5-C06/Django-routers/tests.stderr), [replay exato](logs/L5-C06/Django-routers/replay.stdout).

## Problema e independência

Duas bases: `default` e `reporting`. As tabelas do aplicativo `ledger` devem existir somente em `reporting`; as dos demais aplicativos, somente em `default`. Duas políticas existentes permanecem imutáveis: uma determina a base padrão; a outra dá resposta específica para `ledger` e se abstém para aplicativos diferentes. A configuração A prioriza a primeira regra e eclipsa a segunda. B corrige a configuração, mantendo políticas, modelos e fontes Django idênticos.

O pedido descreve o resultado desejado e as restrições; não fornece a ordem de solução, nomes de métodos internos ou paths de resposta. O material público contém a configuração atual e as políticas existentes. O reference, oracle, rubrica e fontes de revisão são material do avaliador. Nenhuma sessão de agente foi executada; **isolamento/materialização efetiva dessas visibilidades ainda deve ser implementado e verificado antes de usar um agente**. Separar diretórios não constitui por si só isolamento de ferramentas.

É um problema controlado de implantação multi-db sustentado pelo domínio real: o snapshot capturado contém `tests/migrations/test_multidb.py`, cujo teste de CreateModel já cobre abstain/deny/allow e ordens opostas. Esses testes foram apenas lidos como dados; não são novo resultado comportamental. Não se afirma um bug histórico do Django. A linhagem controlada é distinta de `Q1-Python-22051`: compartilha o snapshot, mas o caso anterior trata de primitivas RHS de JSONField e possui outro pedido/oracle/motivação. Não se cria quinto slot nem se reutiliza a mudança JSONField como segunda tarefa.

## Aceite preparado e limites

| Critério | Evidência preparada |
|---|---|
| Fonte/configuração/pin | Archive regular completo de Django commit `8abacfc36d755d8e762a4d2074601b8dc412bfee`, SHA `8450b5075ca9b85f795bb7243296e3faea1928eb1f82b3bb2e9c0b6d3df78826`; 7.084 membros recompostos com manifesto histórico, licenças e cópias exatas das fontes |
| Universo além do anchor | **929 unidades de produção e 143.033 linhas não vazias**, recompostas com regra conservadora `xrai.production.path-marker.v1`. Fontes excluídas/testes/docs/vendored/generated explícitos; as quatro cópias para evidência não restringem a busca do agente |
| Modelo A/B | Oito combinações, dois estados × dois aliases × ledger/catalog, congeladas manualmente antes do algoritmo; ledger muda de base errada para correta, demais aplicativos preservados |
| Controles | Dez controles de None/False/True, ordem, todos abstendo/no-router, método ausente e veto do modelo. `consulted_router_count` conta **invocações**, não entries visitadas: método ausente seguido de False visita dois e invoca um |
| Oracle independente do algoritmo | Root conferiu fontes, oito casos e dez controles antes de qualquer saída nova; revisão UTC `17:34:01Z`, freeze final UTC `17:34:43Z`, 28 entradas, SHA `f403b7a74e43e5175a01adfc997e501f4639b452047d4ae60cc99ab0b201b109` |
| Relações necessárias | [Obrigações entre unidades](../../eval/qualification/django-router-v1/evaluator/source-obligations.json), sete witnesses com linhas e byte ranges/hash recompostos; herança e import explícitos |
| Alternativas | Configuração equivalente aceita se atender à tabela completa, preservar ambos os componentes exatamente uma vez e satisfazer as mesmas obrigações de evidência; texto explicativo não precisa ser literal |
| Campo de aplicação | Retornos bool/None são o **perfil próprio**; Django pode retornar qualquer valor non-None e CreateModel testa truthiness. Recusa de nonboolean nesse modelo não é erro universal do framework |
| ABA | Hash A/B/A restaurado no fixture declarativo; sem sessão viva, query aquecida, invalidação/cache ou prova operacional. Contraprova de receipt com revisão/hash errado recusada; não é teste de atualização de Django |

`catalog` representa o ramo `app_label != "ledger"`. A preservação de outros aplicativos vem do predicado literal da política imutável, não de generalização empírica a partir de uma única amostra. O modelo assume modelos concretos/managed/não swapped, sem restrição adicional de vendor/features; gates negativos são controles declarativos. O teste real dessa compatibilidade continua pendente.

O segundo leitor corrigiu as unidades dos spans, a diferença entre visita e invocação, o limite de retornos nonboolean e a distinção entre representante e generalização. Draft original retido em [draft-before-second-reader](logs/L5-C06/Django-routers/draft-before-second-reader/case.json). Antes de executar o algoritmo, o Implementador percebeu um typo no witness de import: o arquivo usa import absoluto de `django.db.migrations.operations.base`, não `.base`. A fonte estava correta; o witness documental foi corrigido e o [primeiro freeze](logs/L5-C06/Django-routers/intake-correction/freeze.json) permaneceu histórico. Nenhum resultado ou label foi visto/alterado para contornar falha. Primeira recomposição e 42 testes passaram.

## Por que um módulo isolado não fecha o argumento

A cadeia necessária no domínio congelado é:

1. **CreateModel em operations/models.py:** a alteração física usa `schema_editor.connection.alias`, obtém o modelo histórico e só cria a tabela se o gate permitir. A herança literal passa por `ModelOperation(Operation)`; o import de Operation também está fixado.
2. **Operation em operations/base.py:** `model._meta.can_migrate(alias)` pode vetar antes de delegar ao router. Sem esta unidade, o pedido sobre modelos não migráveis fica sem evidência e a ponte operação→política não está demonstrada.
3. **ConnectionRouter em db/utils.py:** a ordem é percorrida e o primeiro resultado diferente de None decide, inclusive False; todas as abstenções caem no permissivo. Sem esta unidade, o gate não explica o efeito da configuração A/B nem os controles de ordem.

Options em db/models/options.py é evidência auxiliar dos flags de compatibilidade. Consultar somente o router fornece a tabela de decisão, mas não prova o uso do alias real pelo CreateModel nem o veto antecipado. Consultar somente CreateModel não explica False versus None; consultar somente Operation não explica a precedência. Isso é argumento estático das obrigações do pedido, revisto por um segundo leitor, **não resolução semântica Python pelo XRAI nem prova de execução através das três unidades**. O gap semântico permanece unknown.

## Verificação e pendências

O verificador usa stdlib, lê o archive sem extrair/rodar seus membros, recompõe o universo e sete anchors e executa apenas o redutor declarativo próprio. **18 casos desse modelo e 42 contraprovas aprovados**, zero skips. Contraprovas incluem aliases, componentes duplicados/substituídos, modelo vetado, não booleanos fora do perfil, ordem, source/labels alterados, symlinks/paths escapes/arquivo duplicado, JSON duplicado/não finito, anchor-only context e tentativas de promover native/SQLite/Python-semântica/elegibilidade/quota. Nenhum mock produz a recomposição factual; nenhuma operação de banco foi realizada.

```sh
python3 eval/scripts/django_router_verify.py --receipt docs/relatorios/logs/L5-C06/Django-routers/verification.json
python3 -m unittest discover -s eval/scripts -p test_django_router.py
```

[Setup prospectivo](../../eval/qualification/django-router-v1/evaluator/setup-readiness.json) permanece insuficiente para domínio nativo: runtime/dependências com lock e proveniência, contenção por fase, scratch separado, import/SQLite controlados e oracle que invoque o **CreateModel capturado + schema editor real nas duas bases**, com receipts originais, são pendências. O modelo declarativo não substitui esse oracle. Preparar também a materialização isolada do agente, ferramentas com universo adequado e rubrica/revisão do resultado dessa execução.

Após qualificação factual suficiente, o Arquiteto pode revisar uma nova alocação prospectiva e o crédito multimódulo, preservando mapa v2, teto quatro/repo, metas complexas/históricas e bijeção. Hoje: candidato preparado, native não verificado, individual não elegível, zero admitido/crédito, **19/20**. O evento requerido scikit-learn e seus descritores/receipts continuam independentes e intactos.

Exploração Tier 2/codebase-memory, geração `2026-10-13T17:39:04Z`, cobertura best-effort e leitura direta dos arquivos comprimidos/JSONL não tracked. Dados upstream foram lidos como fonte sem executar imports. Duas consultas adicionais graft deste agente pouparam aproximadamente 31.673 tokens (quatro consultas acumuladas: 40.062).
