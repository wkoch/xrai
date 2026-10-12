# M0-07 — spike SQLite de desenvolvimento

Implementador, 11/10/2026 America/Sao_Paulo; verificações em 12/10 UTC. **Implementação e aceite local executados; Linux/Windows ainda aguardam execução nativa da CI deste código.** O sucesso do scaffold de L0 não substitui essa execução. Este relatório não conclui M0-05 nem aprova API de persistência de produção.

O experimento reside somente em `crates/xrai-eval`: módulo `sqlite_spike`, executável de desenvolvimento `sqlite-spike` e seis testes de integração em `tests/sqlite_snapshots.rs`. `cargo tree -p xrai` confirma que o binário do usuário continua sem dependências externas e sem `xrai-eval`. O harness permanece em M0-04.

## Aceite e evidências

| Critério M0-07 | Evidência executada | Resultado e limite |
|---|---|---|
| Dois leitores mantêm geração A durante publicação B; consulta nova identifica B | `two_readers_keep_a_bytes_facts_and_fts_while_writer_publishes_b`; driver `demonstrate` | Três conexões simultâneas, dois leitores com transações estabelecidas em A, escritor WAL; fatos, BLAKE3, bytes CRLF/Unicode e FTS de A preservados, leitor novo explicitamente B |
| Interrupção antes do commit não publica B; reabertura íntegra com staging diagnosticável | `killed_writer_rolls_back_b_keeps_a_and_records_abandoned_staging` | Processo filho real escreve blobs/fatos/FTS/publicação de B dentro de transação e sinaliza handshake; supervisor mata e espera. Reabertura contém A, zero linhas/blobs B; staging previamente persistido passa de `pending` para `abandoned` após confirmação da morte; `integrity_check`/`foreign_key_check` passam |
| Um escritor entre processos, com espera limitada | Mesmo teste de crash | Filho mantém `BEGIN IMMEDIATE`; segundo escritor recebe `SQLITE_BUSY` após busy timeout de 150 ms. Teste permite até 3 s de atraso de escalonamento; sem retry ilimitado |
| FTS5 incorporado e atualização sem resultado antigo anunciado como atual | `bundled_sqlite_fts5_and_trigram_are_available_without_load_extension` e teste A/B | SQLite **3.53.2**, `ENABLE_FTS5`; busca por nome, termo de fonte Unicode, caminho e subpalavra trigram. Query filtra geração: `OldWidget` permanece apenas no leitor A, nunca no leitor B. Nativo macOS arm64 verificado; mesmos testes seguem na matriz de três SOs |
| Backup/rebuild preservam dados humanos | `backup_rebuild_preserve_human_files_and_readers_and_refuse_overwrite` | Backup usa API online, inclui B em WAL; destino existente, arquivo humano e banco externo são recusados sem sobrescrever. Rebuild altera só tabelas derivadas do banco reconhecido, preserva config/notas e leitor A. Não há remoção recursiva nem recriação do arquivo |
| Schema/app-id desconhecidos falham explicitamente | `future_schema_and_foreign_application_are_refused_without_recreation` | `user_version=999` ou application-id externo recusados em abertura, backup e rebuild; banco conservado byte a byte após checkpoint; arquivo ausente não é criado pela abertura |
| Fatos referenciam bytes exatos e custo de retenção é observado | `source_foreign_keys_hashes_and_invalid_spans_are_enforced`; `storage-cost` | FK rejeita fonte órfã e exclusão de blob referenciado, span inválido faz rollback total, blob corrompido falha na leitura. Mesmo conteúdo em duas gerações deduplica blob; conteúdo alterado retém ambos |

Os testes usam conexões reais e um filho real, sem mocks de SQLite. Temporários usam diretório com espaços e todos os handles são fechados antes da limpeza. O filho tem duração máxima de 30 s e nunca faz commit atrasado. `hold-uncommitted` pertence somente ao executável de desenvolvimento e não é comando do `xrai` instalado.

Logs: [checks e inventário de dependências](logs/L1/sqlite-checks.json), [demonstração A/B](logs/L1/sqlite-demonstration.json), [custo de armazenamento](logs/L1/sqlite-storage-cost.json). Eles registram comandos, exits, stdout/stderr, ambiente e hashes SHA-256 das fontes verificadas. O hash de conteúdo do banco é BLAKE3; SHA-256 aqui é apenas recibo dos arquivos de implementação. `base_commit` identifica a base antes desta entrega; os hashes identificam o código novo ainda não commitado no momento do teste.

## Reproduzir

```sh
cargo test -p xrai-eval --locked
cargo clippy -p xrai-eval --all-targets --locked -- -D warnings
cargo fmt -p xrai-eval -- --check
cargo run -p xrai-eval --bin sqlite-spike --locked -- demonstrate /tmp/xrai-sqlite-demo-new
cargo run -p xrai-eval --bin sqlite-spike --locked -- storage-cost /tmp/xrai-sqlite-cost-new
```

Os dois drivers exigem diretório novo; reaproveitar um caminho existente produz erro. No Windows, use caminhos temporários locais equivalentes. O build requer compilador C para incorporar SQLite/BLAKE3; o executável compilado não carrega extensão SQLite externa. Depois do download inicial autorizado, todos os checks locais registrados rodaram `--offline` com `--locked`.

## Custo observado e escolhas

`rusqlite=0.40.2`, `default-features=false`, features `bundled` e `backup`; `libsqlite3-sys=0.38.2` fixado no lockfile incorpora SQLite 3.53.2. O projeto oficial documenta [MIT e SQLite em domínio público](https://docs.rs/crate/rusqlite/0.40.2), [WAL e isolamento por snapshot](https://www.sqlite.org/isolation.html), [backup online](https://docs.rs/rusqlite/0.40.2/rusqlite/backup/index.html) e [FTS5/trigram](https://www.sqlite.org/fts5.html). `blake3=1.8.2` fornece hashing e tem [CC0/Apache-2.0/Apache-2.0 com exceção LLVM](https://docs.rs/crate/blake3/1.8.2). Cargo metadata registra as 16 dependências externas e suas licenças; `publish=false` permanece, sem atribuir licença ao produto.

Dois documentos pequenos A/B retêm **82 bytes** de fonte em banco/backup de **90.112 bytes**. Páginas de 4.096 bytes e estruturas fixas dominam esse caso; não interpretar a razão como custo típico de repositório. Nos payloads ASCII sintéticos, cada geração tem 1 KiB, 64 KiB ou 1 MiB. Para 1 MiB, gerações iguais retêm um blob de 1.048.576 bytes e banco de 3.559.424 bytes; alterar um byte retém dois blobs, 2.097.152 bytes, com banco de 4.608.000 bytes. WAL antes de checkpoint: 3.724.512 e 4.787.472 bytes, respectivamente. A tabela FTS unicode61 também armazena texto por geração; deduplicar blobs não deduplica essa cópia. Tempos brutos de publicação estão no log, sem amostragem suficiente para meta de latência.

Ambiente local: Rust/Cargo 1.98.1, macOS 27.0.1 arm64, build debug. Sem campanha de modelos, medição de RSS, pressão de disco, benchmark real de repo, retenção com GC ou simulação de perda de energia.

## Limites e pendências para o Arquiteto

- **L1-S01, M1-04:** o supervisor deve distinguir processo vivo de tentativa abandonada antes de recuperar staging. O spike exige confirmação externa de `kill` + `wait`; abrir o banco ou ver `pending` não autoriza concluir que o dono morreu. Produção ainda precisa política de lease/dono, recuperação e retenção. Recomendação: manter a confirmação explícita e definir identidade/estado de tentativa antes da promoção, sem heurística baseada só em PID.
- **L1-S02, M1-04:** medir/revisar duplicação da fonte no FTS e retenção de gerações com contextos válidos; esta entrega retém todos os snapshots até rebuild. O custo sintético sugere investigar FTS com conteúdo externo ou indexação de termos, preservando sempre bytes e hash da geração.
- O schema é descartável e tem application-id exclusivo do spike. Não existem migrações, lock de manutenção do diretório, recuperação automática de todos os processos, garbage collection, schema de domínio, caminhos nativos adversos ou frescor do filesystem. IDs A/B são gerações fixadas do experimento; `Reader` captura a geração publicada antes de consultar e não promete `validated/strict`.
- Backup exige arquivo novo e rebuild valida app-id/schema antes de alterar tabelas. Proteção completa contra troca maliciosa de path/symlink concorrente pertence a M0-08/M1-04; o teste cobre destino já existente, não esse adversário.

Essas questões não impedem o spike autorizado. Concluir o cartão inteiro exige observar estes testes nativamente em Linux, macOS e Windows no commit publicado e registrar a CI no relatório consolidado L1.
