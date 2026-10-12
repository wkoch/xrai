# M0-03.R1 — mecanismo de admissão e triagem inicial

12/10/2026. Incremento de execução do ADR021; **R1 permanece em andamento**. Nenhuma tarefa foi declarada qualificada e nenhum modelo/campanha competitiva foi executado.

`dev.jsonl` e `challenge-dev.jsonl` preservam bytes/IDs/linhagens anteriores. `corpus.toml` classifica D1 como seed; `challenge-qualified.jsonl` e `supplementary.jsonl` começam vazios e usam carregamento explícito. O gerador antigo declara desenvolvimento e não escreve esses dois conjuntos. O schema de tarefa qualificada e o gate `verify_qualified.py` definem campos e critérios entre tarefas. O gate recusa 0 tarefas e também recusa as 32 seed; não permite substituição silenciosa. Um dataset sintético vive somente no teste para verificar regras e nunca entra nas tarefas.

O gate exige 32 IDs novos/versionados, linhagens independentes, oito tarefas/estratos por família, equilíbrio de projetos, TS/JS, 20 casos com módulos/ relações, quatro complexos por família distribuídos em dois projetos, piso de produção, proveniência pública, oracles/probes/regressões, configuração, adjudicação cega de revisões e recibos independentes vinculados a hashes. A revisão semântica e o conteúdo verídico dos recibos precisam ser realizados por leitores: validar a forma não estabelece a verdade. Os artefatos precisam existir e corresponder aos hashes para admissão real.

A triagem mediu árvores completas de oito candidatos em SHAs fixos. `qualification/candidate-triage.json` contém URL/hash/tamanho do archive, manifests, licenças, ferramentas declaradas e manifest de cada arquivo contabilizado, comprimido deterministicamente. `triage_candidates.py` reproduz o levantamento a partir dos arquivos públicos; as árvores completas ficam em cache externo e não são entregues ao agente. Todos ultrapassam o piso numérico preliminar. **Builds, probes, casos públicos específicos e classificação semântica permanecem pendentes**; links de busca de PR não constituem proveniência de tarefa. Os comandos de probe são propostas de triagem, não logs de execução. Exclusões por caminho/nome/marker são explícitas; blocos de testes embutidos em arquivos de produção Rust ainda requerem classificação por segundo leitor e os números preliminares não bastam para admissão. Oito upstreams seed foram registrados como descartados para o recorte de porte, preservando seu uso em regressões.

| Família | Candidato | Arquivos preliminares | Linhas não vazias preliminares |
|---|---|---:|---:|
| Rust | rust-analyzer | 1.432 | 451.032 |
| Rust | tokio | 466 | 113.648 |
| TS/JS | TypeScript | 732 | 350.310 |
| TS/JS | vscode | 9.156 | 2.395.796 |
| Python | Django | 929 | 143.263 |
| Python | scikit-learn | 429 | 200.634 |
| Go | Prometheus | 673 | 165.912 |
| Go | Gitea | 2.233 | 312.191 |

`seed-review-receipts.json` liga cada um dos 32 IDs a hashes atuais de prompt/oracle e ao audit L1 disponível. Esse audit registra leitura/parse dos scripts, sem identidade/hash de revisão semântica por oracle; os recibos permanecem explicitamente faltantes. Não foi feita uma troca em massa de “pending” por “accepted”. Antes de reutilizar seed em um caso novo, realizar revisão por segundo leitor com recibo por artefato, e naturalizar prompts sem pistas adicionadas da solução.

`materialize(..., phase='A')` prepara o baseline sem evento. `apply_event(id, workspace)` modifica a mesma raiz e devolve recibos de bytes/hashes/mtime antes/depois; não reinicia processo/cache/índice. O harness de M0-04 controla iniciar, aquecer, consultar e comparar com rebuild. O default `phase='cold'` preserva a sequência anterior e a rotula `cold_changed_checkout`. `request.json` nunca contém `state_changes`: eventos e oracles ficam no avaliador. Eventos recusam links que escapam da raiz, inclusive links inseridos pelo agente após A; IO usa descritores ancorados e `O_NOFOLLOW`, com recusa de hardlinks/arquivos especiais.

Verificação local: sete testes Python, incluindo 12 mutações de falso aceite, gate vazio/seed, quatro famílias A→B com raiz preservada e bytes idênticos ao checkout cold B e recusa de links externos/hardlinks/links nos diretórios pais. O verificador legado continua passando 52 materializações/78 fixtures. Estes testes provam a API de materialização, **não** a atualização de índice/serviço; essa evidência exige executor M0-04 e o evento qualificado futuro. Executar:

```sh
python3 -m unittest discover -s eval/scripts/tests -v
python3 eval/scripts/verify_corpus.py
python3 eval/scripts/verify_qualified.py # esperado: exit 1, não admitido
python3 eval/scripts/verify_corpus.py --qualified # esperado: exit 1
python3 eval/scripts/triage_candidates.py --cache /tmp/xrai-qualified-triage
```

Próximo incremento R1: testar builds/probes sobre esses pins; escolher 32 casos e SHAs históricos pertinentes, preservar checkout completo/manifest/notice, medir produção com exclusões revistas, preparar testes baseline/reference/regressão, relações semanticamente necessárias, eventos A/B e revisão independente. A ausência dessas evidências mantém o gate fechado. Não há decisão arquitetural nova requerida neste incremento.

## Correção do gate após revisão independente

A revisão de `l2_parsing` encontrou falso aceite de família/language divergentes, `version=true` e oracle incremental não verificado. O incremento corretivo preserva os recibos/logs anteriores e registra nova evidência em `docs/relatorios/logs/L2/qualified-gate-fix.json`.

`verify_qualified.validate()` agora executa o JSON Schema Draft 2020-12 para todas as linhas, antes das regras entre tarefas, tanto com quanto sem IO de artefatos. O schema define tipos dos campos aninhados, enums/condicionais de família/language, versionamento inteiro (booleano recusado), recibos com caminho relativo e SHA-256, operações do evento, probes e oracles. Controles obrigatoriamente têm `complexity.complex=false` e não podem preencher o piso complexo. Em modo real, `oracle_B` precisa existir dentro da raiz do avaliador e corresponder ao fingerprint; falhas IO produzem erro de admissão.

O modo real também vincula `input.snapshot` ao manifest que o materializador usa: repository/commit/archive/hash/licenças devem coincidir. Cada arquivo do tar precisa aparecer no manifest com tamanho/hash corretos; arquivos duplicados, links, entradas proibidas e inventário divergente são recusados. Os módulos necessários precisam pertencer à produção elegível. As contagens declaradas são recomputadas diretamente dos bytes, usando método explícito `xrai.production.path-marker.v1`; inventar porte sobre um snapshot pequeno não passa. Esse filtro conserva a limitação documentada de testes inline/Rust e classificação semântica: antes de fechar R1, a medição precisa excluir esses trechos com recibo independente/método revisto quando pertinente. O gate ainda não prova autenticidade externa de Git/issue, verdade dos rótulos ou execução de probes pelo simples fato de validar recibos; essa curadoria continua obrigatória.

Nove testes passam, incluindo 36 mutações: as 12 anteriores, nove novos erros de tipos/linguagem/recibos/controle exercitados nos dois modos e seis divergências reais de snapshot/commit/módulo/porte/oracle. O positivo real usa somente um tar sintético em diretório temporário com 500 arquivos/50 mil linhas, explicitamente fixture; nunca é escrito no dataset nem contado como desafio.

A validação de 32 linhas e os testes agora reutilizam `jsonschema==4.25.1`, pin de desenvolvimento já existente em `docs/contracts/examples/requirements.txt`. Não há dependência runtime nova. Instalar esse requirements em ambiente de avaliação, como na CI; no ambiente local isolado usado aqui:

```sh
PYTHONPATH=/private/tmp/xrai-contract-blake3 python3 -m unittest discover -s eval/scripts/tests -v
```

O dataset qualificado permanece vazio; o gate continua fechado. As 32 tarefas, builds/probes, revisão semântica e de contagem, e eventos qualificados ainda precisam de execução em R1.

## Adendo L3-01 — quatro pilotos verticais

12/10/2026. Quatro dossiês, um por família, receberam revisão independente aceita e quatro pares baseline/referência passaram em materializações fresh. Três pares estão nos recibos `docs/relatorios/logs/L3/vertical-fresh/`; Go passou no retry `vertical-fresh-retry-go/summary.json`, com baseline=1, referência=0 e `go.mod`/`go.sum` preservados em modo readonly. A tentativa inicial Go por ENOSPC permanece como falha de infraestrutura registrada. A revisão Go delimitada em `review-go-scoped/case.json` também passou, preservando a escrita WAL que provoca a falha do baseline.

As quatro árvores completas normalizadas somam 84.068 arquivos, com quatro archives e inventários comprimidos vinculados por hashes. Quatro links de documentação Django foram materializados como arquivos, com flattening explícito nos recibos. Somente Django é marcado complexo neste lote: Tokio permanece `complex=false`, pois o piso aplicável após excluir testes inline não está comprovado. Fontes grandes ou revisão aceita não substituem esse critério.

Materialização pública dos quatro casos e correspondência de hashes passaram. O verificador tem 14 testes; os controles negativos dos quatro pilotos preservam a recusa da admissão global. O gate de 32 permanece intacto, com **0/32 tarefas admitidas globalmente**. Os quatro pilotos não autorizam campanha competitiva, nem antecipam G0/G1; nenhuma execução paga ou competitiva ocorreu neste incremento.

No primeiro recibo desta entrega, a CI do novo commit permanece pendente. Evidências locais, revisões, falha inicial e retry ficam preservados em `docs/relatorios/logs/L3/`; a integração deve acrescentar commit/run exatos ao conciliar a prova nativa. Próximo recorte: expandir os casos válidos até a matriz integral de 32, mantendo os pisos históricos, complexos, relações entre módulos e oracles/revisões exigidos pelo ADR 021.

Verificações documentais da [CI L3 aprovada](https://github.com/wkoch/xrai/actions/runs/38239765003), código21e9279, incluem verify_vertical com4aceites, preservação seed/materializações52 e14testes do gate. Árvores completas/pins/oracles são os pilotos locais congelados deste relatório; a CI verifica esses artefatos e seus vínculos, não reexecuta os quatro builds upstream. Admissão global permanece0/32 e nenhum braço competitivo foi executado.
