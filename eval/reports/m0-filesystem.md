# M0-08 — Spike de filesystem e identidade de checkout

Incremento L2, 12/10/2026. Código experimental em `xrai-eval`, sem dependência runtime da CLI `xrai`. O aceite nativo Linux x86_64 / macOS 15 arm64 aguarda as execuções da CI; o smoke local macOS 27.0.1 arm64 não comprova o piso.

## Implementação e evidências por critério

| Critério | Implementação / teste | Evidência local |
|---|---|---|
| Diretório sem Git e estado independente entre checkouts iguais | `checkout_id` usa BLAKE3 do root canônico em bytes nativos + device/inode; `state_directory` associa o namespace ao checkout; teste escreve estados A/B separados em dois projetos iguais | `no_git_and_identical_named_checkouts_have_independent_writable_state` |
| Worktrees reais | Fixture cria repositório e linked worktree Git; inventários idênticos e IDs/estado distintos. `.gitfile` é lido como bytes e não seguido | `actual_git_linked_worktrees_have_independent_checkout_state`, `linked_worktrees_preserve_separate_identity_and_exclude_gitfile` |
| Unicode, espaços, nomes nativos e CRLF | `Source.path: Vec<u8>` deriva de `OsStrExt::as_bytes`; fonte capturada é binária, sem normalização ou conversão UTF-8. Driver registra nomes observados em hex | `unicode_spaces_invalid_utf8_and_crlf_preserve_native_and_source_bytes`; driver |
| Case sensitivity / normalização Unicode por volume | Criação `create_new` detecta alias real, sem assumir comportamento por SO; erro diferente de `AlreadyExists` falha | `filesystem_case_capability_is_observed_and_names_are_not_lowercased`; driver |
| Links e loops | Todos os symlinks, mesmo internos, são excluídos. Componentes de path são checados; abertura final usa `O_NOFOLLOW`. Links ao exterior e ciclos nunca entregam a fonte externa | `symlink_escape_inside_link_and_cycle_are_explained_and_never_read`, `gitfile_symlinks_and_invalid_pointers_cannot_load_external_metadata` |
| Precedência de exclusões e configuração | `.git`/`.xrai` em qualquer componente > subárvores explicitamente configuradas > captura; motivos consultáveis e configuração relativa validada antes da descoberta | `explicit_exclusions_have_reason_and_internal_state_takes_precedence`, `invalid_configuration_fails_before_inventory` |
| Mesmo tamanho e mtime | Hash refeito sobre bytes capturados; teste escreve AAAA → BBBB e repõe o mtime original, confirmando tamanho/mtime iguais e hash diferente | `same_size_and_mtime_change_is_detected_by_content_hash` |
| Permissão, remoção e substituição durante captura | Diagnósticos `PermissionDenied`, `Removed` e `ChangedDuringRead`; hook experimental determinístico após abertura demonstra o caso Unix de FD ainda legível após unlink | quatro testes de permissão/remoção e `replacement_after_open_is_a_diagnostic_instead_of_misattributed_source` |

Log reproduzível: [`filesystem-local.json`](../../docs/relatorios/logs/L2/filesystem-local.json), com hashes SHA-256 das três fontes, base Git, plataforma, comandos, saídas e códigos. Execução final: **14 testes aprovados**, clippy `-D warnings` aprovado, driver aprovado. O primeiro recibo de desenvolvimento preserva a falha de clippy por literal não octal, depois corrigida: [`filesystem-local-attempt1.json`](../../docs/relatorios/logs/L2/filesystem-local-attempt1.json).

Comandos:

```sh
cargo test --locked -p xrai-eval --test filesystem_inventory -- --nocapture
cargo clippy --locked -p xrai-eval --bin filesystem-spike --test filesystem_inventory -- -D warnings
cargo run --locked -p xrai-eval --bin filesystem-spike
```

## Matriz nativa observada

| Host / volume | Case | NFC versus NFD | Filename inválido UTF-8 | Mode 000 | Situação |
|---|---|---|---|---|---|
| macOS 27.0.1 arm64; APFS local, journaled, volume `/System/Volumes/Data` | Insensível | Alias de NFC/NFD na criação | Criação rejeitada com `EPERM`; representação `OsString` sem perda testada | Leitura negada, diagnóstico comprovado | Smoke local, não piso 15 |
| Ubuntu 24.04 x86_64 / glibc 2.39 | A medir | A medir | A medir nativamente | A medir | CI pendente |
| macOS 15 arm64 | A medir | A medir | A medir nativamente | A medir | CI pendente |

A ausência de suporte do volume a um nome não é falha de conversão de path: o driver registra a rejeição, e o teste Linux exige criação e captura do nome com byte `0xff`. Conteúdo com bytes `0xff`, NUL e CRLF é preservado nos arquivos aceitos. `df` identifica o dispositivo; no macOS `mount` registra tipo/opções desse mesmo dispositivo, evitando depender do DiskManagement framework, indisponível no sandbox local. No Linux o driver usa `stat --file-system` para registrar o tipo. Nenhuma observação deste volume define comportamento de todos os volumes macOS.

## Avaliação de Git incorporado

O recorte presente necessita descoberta sem Git, identidade de checkout e reconhecimento de `.gitfile`; não necessita leitura de objetos, packs, histórico ou diff. O spike comprova esses requisitos com std + BLAKE3 existentes, sem executar Git durante inventário/captura. Git CLI aparece somente na construção da fixture de worktrees, como ferramenta de teste.

| Alternativa | Necessidade atual / decisão proposta |
|---|---|
| std e `.gitfile` advisory | Suficiente para identidade/inventário deste spike; não abre o destino de `gitdir:` |
| `gix` incorporado | Candidato quando forem necessários objetos/packs/histórico ou semântica Git completa de ignore; sem consumo dessas APIs no cartão presente |
| `libgit2` incorporado | Candidato equivalente para capacidades Git futuras, com biblioteca C e build adicionais; também sem consumidor atual |

**Proposta ao Arquiteto para o ADR:** postergar seleção/incorporação de `gix`/`libgit2`, histórico, diff, packs e equivalência completa de `.gitignore` até um consumidor justificado. Regras configuradas aqui são caminhos de subárvores, sem globs ou promessa de semântica Git. Esta entrega registra avaliação implementada; não altera por conta própria os ADRs mantidos pelo Arquiteto.

## Limites e pendências para M1

O spike não é sandbox de filesystem. `O_NOFOLLOW` protege a abertura final e a política estática exclui symlinks; verificações de componentes por path não garantem proteção contra um processo adversarial que troque um diretório ancestral durante a chamada. **Pendência M0-08.F01 para o Arquiteto:** antes de promover esta captura para produção, definir abertura ancorada em handles/capabilities de diretório ou documentar o modelo de concorrência permitido, incluindo teste adversarial de troca de ancestral. Nenhuma leitura neste spike deve ser anunciada como confinamento resistente a esse ataque.

A identidade demonstrada é um namespace experimental por root/device/inode. Persistência da encarnação após renomear/recriar checkout, resolução de aliases de raiz e reutilização futura de inode precisam seguir os contratos de produção de M1; não são garantias de IDs públicos deste spike. Não há watcher, reconciliação de árvore inteira, parser de configuração de produção, parser de `.gitignore`, histórico/diff ou adapter Windows.

Consulta estrutural usou codebase-memory Tier 2, geração 2026-10-12T01:50:21Z, com cobertura limpa nas fontes existentes consultadas. Os três arquivos novos tiveram cobertura `not_tracked`, exigindo leitura direta; nenhum resultado do grafo é tratado como verificação deles.

## Correção após execução nativa da CI

A execução `38200549676` aprovou o job Linux completo e encontrou uma falha no job macOS 15: 13 testes de filesystem aprovados, um reprovado porque o teste aceitava somente `PermissionDenied`/`InvalidInput` ao tentar criar um filename com byte `0xff`. A classe retornada pelo volume/versão do runner ficou fora dessa lista. A lista era uma suposição do teste, não um requisito de representação nativa do projeto. O log original foi preservado pelo Implementador; esta correção não altera os recibos da entrega anterior.

O teste agora registra `ErrorKind`, `raw_os_error` e mensagem efetivamente recebidos. Somente a tentativa de nome inválido no macOS pode produzir esse resultado de capacidade: o nome Unicode válido precisa funcionar, e escritas/leituras positivas no mesmo diretório antes e depois confirmam que o diretório permanece utilizável. No Linux, criação e captura dos dois nomes continuam obrigatórias; o driver também falha se a tentativa inválida não funcionar. A representação `OsString` e os bytes de fonte continuam verificados sem perda em ambos os hosts.

O driver mantém a mensagem histórica e acrescenta `invalid_utf8_name_error_kind`, `invalid_utf8_name_error_raw_os` (ou null quando não houve erro) e `native_filename_valid_control_passed`. Nenhuma classe/errno universal é prometida. O novo recibo [`filesystem-fix-local.json`](../../docs/relatorios/logs/L2/filesystem-fix-local.json) registra hashes das fontes alteradas, 14 testes, clippy `-D warnings`, formatação dos dois arquivos alterados e driver. O resultado local continua sendo smoke macOS 27; a nova execução macOS nativa da CI é necessária para concluir a correção do cartão.

## Adendo nativo de CI, 12/10/2026

[Run38200959849](https://github.com/wkoch/xrai/actions/runs/38200959849), commit `1e093189ba52b0b19f8e115f64c1d395a04a3721`: 14 testes filesystem em cada host e todos os jobs aprovados. Recibos `docs/relatorios/logs/L2/ci-native/native-{host}/filesystem.json`; saída dos testes e ambiente no mesmo artifact. A primeira falha macOS e a correção permanecem em L2, sem substituir logs antigos.

| Volume efetivo | Case/NFC-NFD | Filename0xff | Mode000 |
|---|---|---|---|
| Ubuntu24.04.5 x86_64, `stat --file-system` informa `ext2/ext3` | Distintos | Criação/captura nativa aprovadas | Negação comprovada |
| macOS15.7.9 arm64, APFS `/System/Volumes/Data` | Aliases | Rejeição `Uncategorized`, errno92, com controles positivos antes/depois | Negação comprovada |

O APFS mac15 retorna classe/errno distintos do APFS localmac27: a rejeição observada é dado da capacidade do volume. Os recibos conservam kind/mensagem/errno e a representação de path élossless. Linux mantém exigência de criar e capturar o nome nativo. Isso não reinterpreta `stat` como prova de uma versão específica de ext filesystem nem define todos os volumes desses SOs. A análise F01 e o registro da decisão Git pelo Arquiteto continuam pendentes; a CI não prova captura resistente à troca de ancestral.

## Adendo L3-04 — handles, recibo original e M0-08.R1

12/10/2026. Este adendo é o estado vigente; preserva os recibos históricos acima. **M0-08, escopo original, concluído:** as 14 provas nativas em cada alvo no run 38200959849 cobrem o inventário estático e a identidade experimental; ADR 023 §4 encerrou L2-GIT01. Git incorporado, histórico/diff e semântica gitignore ficam adiados até consumidor concreto. A decisão é do Arquiteto e já está registrada; não permanece proposta esperando aprovação. F01 também foi resolvida arquiteturalmente em ADR 023 §3 e sua obrigação de execução é a nova M0-08.R1.

**L3-04/M0-08.R1: implementação e provas locais entregues; matriz nativa adicional pendente.** Nada foi promovido para a CLI ou M1-02/03. [Recibo local](../../docs/relatorios/logs/L3/filesystem-local.json) registra comandos completos, saída, plataforma, base e SHA-256 das fontes/Cargo; [proveniência do wrapper](../../docs/relatorios/logs/L3/filesystem-wrapper.json) registra pin, semântica e licenças. Ambiente local disponível é smoke macOS, não o piso literal 15.0.

### Mecanismo e limites fixados

A raiz explicitamente escolhida é canonicalizada na admissão. Seus handles, device/inode e identidades da linhagem física ficam fixados; abertura/revalidação dessa linhagem também caminha handles com `NOFOLLOW`. Cada fonte resolve componentes a partir do handle da raiz. Linux usa `openat2` com `BENEATH | NO_SYMLINKS | NO_XDEV`, sem fallback silencioso quando não suportado ou em erro de corrida. macOS usa `openat` componente a componente, `DIRECTORY` nos ancestrais, `NOFOLLOW` em todos e recusa mudança de device. Enumeração usa `Dir::read_from` sobre o diretório já aberto; não reabre o ancestral pelo path string. Identidades de diretórios, raiz e arquivo são reconciliadas depois da leitura e antes da publicação do inventário. Stamps observados de todos os diretórios enumerados, incluindo raiz e diretórios vazios, são guardados no início, comparados no fim e reconciliados novamente na publicação; mudança de membership observável gera diagnóstico de cobertura parcial mesmo quando nenhum arquivo antigo mudou de inode. Mudança observada no tamanho/mtime/ctime da fonte também invalida sua revisão. Diretório invalidado perde as fontes coletadas sob ele e produz diagnóstico; fontes independentes ainda podem compor o resultado parcial.

Wrapper seguro [rustix 1.1.5](https://docs.rs/crate/rustix/1.1.5/source/Cargo.toml), MSRV 1.65 compatível com o workspace 1.98.1; API [openat2](https://docs.rs/rustix/1.1.5/rustix/fs/fn.openat2.html), [openat](https://docs.rs/rustix/1.1.5/rustix/fs/fn.openat.html), [enumeração por FD](https://docs.rs/rustix/1.1.5/rustix/fs/struct.Dir.html) verificadas na documentação primária. Licença do pacote `Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT`; opção MIT e COPYRIGHT preservados em `crates/xrai-eval/licenses/filesystem/`. `unsafe_code = forbid` permanece; não há FFI próprio nem dependência adicional na CLI.

Teto experimental congelado **8 MiB por fonte**; API de probe aceita limite explícito para testar fronteiras. Metadata acima do teto é recusada antes da leitura; cada chunk é verificado antes de adicioná-lo, inclusive quando o arquivo cresce. Não é limite global de RSS ou de todos os arquivos do inventário. Paths relativos vazios, absolutos, `.`/`..`, componentes vazios e NUL são recusados; bytes nativos não são normalizados. `.git`/`.xrai` não podem ser fonte, inclusive pela captura direta. O leitor advisory de `.gitfile` tem exceção interna limitada e nunca abre seu destino. Arquivos especiais são recusados; `NONBLOCK` e validação do FD evitam leitura de FIFO numa corrida de substituição.

### Matriz de provas

`filesystem_anchored.rs`: **20 testes no macOS disponível** e um adicional Linux; preservados os **14 testes originais**. Comandos de testes, clippy `-D warnings`, rustfmt dos arquivos alterados e driver passaram no recibo local. O primeiro teste de socket no sandbox recebeu `EPERM`; a execução autorizada fora desse sandbox criou socket/FIFO e passou, sem enfraquecer o controle. Isso não equivale a liberação do harness de agentes no macOS local.

| Obrigação ADR 023 | Prova executável | Resultado/limite |
|---|---|---|
| Ancestral trocado antes ou durante abertura | `ancestor_symlink_before_open_never_delivers_external_sentinel`, `barrier_swap_after_ancestor_handle_open_invalidates_binding`, `ancestor_symlink_after_source_open_never_publishes_as_current` | Symlink recusado; barreira por canais coordena escritor real após abrir handle; sem sleeps |
| Diretório aberto movido para fora | `moving_open_directory_outside_without_link_is_diagnosed`, `anchored_enumeration_of_moved_directory_returns_partial_inventory` | `Removed`/`ChangedDuringRead`, árvore instável parcial; fonte sentinela via symlink nunca entregue |
| Raiz/ancestral físico da raiz substituído | `replaced_root_invalidates_all_inventory_sources`, `replacing_checkout_parent_with_alias_of_moved_parent_invalidates_locator` | Inventário invalidado/alias recusado, mesmo se o objeto original continua legível pelo FD |
| Adição/remoção após enumeração | `new_file_after_enumeration_marks_root_coverage_partial`, `empty_directory_addition_and_removal_are_reconciled_before_publication` | Raiz e diretórios vazios possuem recibo de cobertura; mudanças geram diagnóstico, sem declarar inventário completo |
| Binding invalidado depois de capturar | `last_publication_reconciles_previously_captured_ancestor`, `inventory_final_reconciliation_rejects_changed_source_revision` | Revalidação final descarta binding/revisão alterados; mantém fonte independente |
| Unlink/recreate | teste original post-open e `original_file_unlink_and_recreate_cannot_reuse_old_binding` | Remoção/substituição diagnosticadas |
| Mesmo tamanho/mtime | teste original com hash distinto e `in_place_same_size_and_restored_mtime_is_not_a_snapshot_guarantee` | Alteração em place sondada; se metadata não distinguir, bytes/hash entregues continuam coerentes, sem alegar snapshot |
| Hard link | `hard_link_captures_shared_object_and_does_not_claim_link_confinement` | Permitido e identificado; demonstra deliberadamente que hard links não são isolamento |
| Mount | Linux `existing_proc_mount_is_refused_by_linux_no_xdev` | Prova nativa pendente; usa mount `/proc` existente, não cria mount privilegiado |
| Arquivo especial e teto/growth | `special_files_are_refused_without_fifo_blocking`, `ceiling_is_enforced_for_initial_size_and_during_growth` | Socket/FIFO recusados; crescimento além do teto recusa sem entregar fonte; saída parcial preservada |
| Árvore estabilizada e reconstrução | `stabilized_update_equals_independent_rebuild_and_old_bytes_remain_immutable`; runner incremental L2 usa automaticamente nova captura | Dois inventários B idênticos/hash exato, bytes A retidos imutáveis; runner preservado precisa nova execução nativa |
| Complemento stress finito | `seeded_adversarial_schedule_supplements_deterministic_barriers`, `seeded_concurrent_writer_stress_never_delivers_external_sentinel` | Seeds `0x584e52414902` (32 agendas) e `0x4c3346532026` (64 ciclos/128 capturas concorrentes); contagens reais no log; não substituem as barreiras nem provam todas as agendas |

### Modelo de consistência e limites remanescentes

Hash descreve exatamente o `Vec<u8>` entregue. Revalidações registram observações de uma árvore viva; metadata estável **não prova** um instante coerente, nem ausência de escritor. Corridas depois da última validação, escrita concorrente que não altera metadata observável, rename temporário revertido, reuso de identidade e mudanças de namespace fora das observações não constituem snapshot atômico. Captura só deve servir à geração com esse modelo explícito; tarefa que exige árvore imutável precisa ambiente sem escritor ou snapshot de filesystem validado. Não há sandbox contra escritor hostil do mesmo usuário.

Hard links podem expor um objeto também nomeado fora da raiz. Linux `NO_XDEV` recusa travessia de mounts, inclusive bind mounts; macOS compara device, o que não detecta um mount de mesmo device. Nenhum teste cria mounts novos ou prova um adversário com privilégios de mount; isso permanece limite explícito, não equivalência silenciosa entre plataformas. Handles mantêm acesso a objetos movidos, mas seus nomes são revalidados e binding observado inválido não é publicado. Não há retry automático: captura retorna erro tipado/partial para reconciliação posterior limitada; não faz loop interminável numa árvore instável.

Pendências de execução: nova CI Linux/macOS15 para as 21/20 provas R1 e os 14 legados, driver e incremental; piso literal macOS15.0 continua externo. IDs persistidos de encarnação/cache e regras definitivas de renome/aliases/inode continuam M1-02/03, conforme ADR 023 §4. Não surgiu nova decisão arquitetural para bloquear este incremento.

Exploração estrutural: codebase-memory Tier2 geração `2026-10-12T09:34:55Z`, cobertura `metadata_match` para fontes originais; fonte nova/alterada verificada diretamente. Graft callers `capture_after_open --depth all` antes do refactor, uma chamada, economia reportada 10.251 tokens; mapa de impacto inclui driver, testes e incremental. O grafo não substitui a execução das provas.

### Correção da revisão independente L3

Revisor L3-02 encontrou a ausência de stamps de cobertura dos diretórios: adicionar uma entrada após `walk` mantinha as identidades antigas e podia retornar inventário sem limitação. Correção aplicada antes da entrega: observações de raiz/dirs vazios/no início/fim/final, dois testes determinísticos de adição/remoção e recibo local renovado. Fontes cujo binding/revisão ainda é válido podem permanecer no resultado com diagnóstico explícito de cobertura parcial; um inventário com diagnóstico nunca é prova de cobertura completa. Total local final: 20 provas R1 + 14 originais, clippy/fmt/driver aprovados.
