# Reconciliação offline dos pares Rust/JavaScript

O verificador lê JSON, logs e fontes congeladas. Não importa produtores, executa comandos de recibos, entra em namespaces nem extrai arquivos para disco. Seu resultado confirma a consistência limitada das evidências exportadas; não admite candidatos e não prova execução de agente nem transição incremental A→B.

Execute a partir da raiz do repositório, com o pacote obtido pelo export confiável do GitHub:

```sh
python3 docs/relatorios/logs/L5-continuacao/reconcile_corpus.py <export-root> --commit c48b5993550fd258f1efe5677704a59d9eb73de0 --run 38283109016
```

O pacote deve conter `run.json`, `artifacts.json`, `rust/summary.json`, os recibos/logs de `rust/baseline` e `rust/reference`, e os JSON de `js/base` e `js/reference`. Os nomes seguem o export preservado de `ci-second`. O padrão confere ambos os jobs concluídos com sucesso; `--only rust` ou `--only js` permite revisão isolada, sem declarar sucesso dos demais jobs.

Quando disponíveis, conserve os ZIP originais `l5-real-rust.zip` e `l5-real-js.zip` na raiz do pacote. O verificador compara seus bytes ao digest informado pelo GitHub e cada membro ao arquivo exportado. Sem ZIP, registra explicitamente que os arquivos descompactados não estão vinculados criptograficamente ao digest do ZIP. JSON fornecido offline não recebe autenticação por este programa.

A conferência inclui pins dos arquivos compactados, executores, oracles, locks, comandos/filtros/configuração, contagens e resultados individuais, ausência de timeout/truncamento, hashes dos streams e confirmação do encerramento de cada domínio. Rust exige as duas falhas por panic na base, os dois sucessos na referência e os 16 testes da família na referência. JavaScript exige três falhas por hook ausente na base, três sucessos na referência e dois controles de regressão em cada lado, incluindo o controle de transição ordinária preservado pelo guard congelado. As provas de materialização dependem dos produtores: os workspaces e executáveis nativos históricos não são reconstituídos por esta revisão.

`freeze-checks.json` registra os 13 métodos de teste, contrachecks com mutações somente em memória, hashes das entradas preservadas, o sucesso isolado Rust CI2 e a rejeição do pacote CI2. A rejeição do oracle JavaScript antigo também é verificada diretamente, independentemente da falha do job. O erro inicial de duas subverificações que selecionavam o artefato errado está registrado; a seleção foi corrigida pelo nome do artefato. `coverage.json` registra cobertura de índice best effort, sem transformá-la em prova de completude.

```sh
python3 docs/relatorios/logs/L5-continuacao/integration/corpus-reconcile-review/test_reconcile.py
```

O quarto CI e sua exportação ainda estavam pendentes no congelamento deste verificador. Não há sucesso retroativo das execuções JavaScript anteriores.
