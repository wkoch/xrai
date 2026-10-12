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
