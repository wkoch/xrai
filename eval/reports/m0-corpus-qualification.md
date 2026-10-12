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
