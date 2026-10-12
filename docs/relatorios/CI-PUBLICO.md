# CI após tornar o repositório público

Data: 12/10/2026, America/Sao_Paulo. Arquiteto, verificando a evidência de execução já implementada. O usuário informou que tornou `wkoch/xrai` público; a API confirmou `private=false` e `visibility=public`.

**Bloqueio anterior de Actions superado. M0-02.R2 e M0-07 concluídas no escopo dos respectivos cartões.** Reexecutada a tentativa do commit `9b5411cce300fead7c62335539b317645f2d9577`, sem alteração de workflow, código, cobrança ou proteção pelo assistente.

## Execução comprovada

[Run 38197775334, tentativa 2](https://github.com/wkoch/xrai/actions/runs/38197775334/attempts/2), iniciado às 03:01:15 UTC e concluído com sucesso às 03:01:47 UTC em 12/10/2026. A primeira tentativa falhou antes da mudança de visibilidade; permanece histórica e não conta como teste executado.

| Job | Ambiente e resultado |
|---|---|
| Documentary contracts | Ubuntu 24.04.5; 26 exemplos válidos aceitos, 30 adversos rejeitados, zero falhas; dez testes do verificador passaram. |
| x86_64-unknown-linux-gnu | Ubuntu 24.04.5, host Rust conferido pelo próprio workflow; fmt, clippy, nove testes Rust, build e smokes help/version passaram. Inclui seis testes SQLite. |
| aarch64-apple-darwin | macOS 15.7.9 arm64, host Rust conferido; os mesmos checks e nove testes passaram, incluindo os seis SQLite. |

Os seis testes SQLite comprovados em **cada host** cobrem FTS5/trigram incorporados, recusa de schema/aplicação desconhecidos, FKs/hashes/spans, backup/rebuild preservando arquivos humanos, leitores em A durante publicação B e rollback/diagnóstico após interrupção do writer. Os nomes e resultados estão nos trechos de log registrados. Medição de retenção e demais resultados locais anteriores permanecem em [sqlite-L1.md](sqlite-L1.md).

M0-02.R2 também exigia conferir checks externos: a API agora respondeu. Na consulta, `main` estava sem proteção ativa e o repositório sem rulesets; não havia exigência residual de job Windows. Nenhuma configuração foi modificada. O workflow executou exatamente os dois hosts Rust e o job documental esperados.

## Evidências e limites do aceite

- [Metadados finais do run e de cada passo](logs/ci-publico/run.json).
- [Hosts, resultados dos testes e hashes do workflow/fontes](logs/ci-publico/output.json).
- [Visibilidade, proteção de main e rulesets observados](logs/ci-publico/repository.json).
- [Verificação documental desta atualização](logs/ci-publico/documentacao.json).

O aceite fecha a prova nativa pendente do **spike** e da matriz R2. Não conclui M0-05/06/08, não prova autonomia do produto em ambiente limpo nem o piso exato macOS 15.0, pois o runner executou 15.7.9. Não promove persistência de produção, corpus qualificado ou gates G0/G1/G2. As decisões do ADR 022 continuam trabalho M1 após G1.

O próximo lote permanece L2: harness/replay M0-04, qualificação M0-03.R1 e spikes M0-05/08. O implementador não precisa reabrir o bloqueio de billing já superado; deve observar qualquer falha nova pelos resultados reais. Orçamento de modelos e licença conservam seus responsáveis e momentos de definição.
