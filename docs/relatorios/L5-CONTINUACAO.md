# Retomada L5 — R3 e dossiês reais

Implementador, 12/10/2026. Escopo da [revisão do Arquiteto](REVISAO-L5.md): continuar L5-02/L5-04, preservar os seis incrementos, registrar resultados sem fechar os cartões M0 incompletos. Trabalho dividido com agentes R3, Rust e JavaScript; segunda leitura independente entre corpus e integração.

## Entrega implementada

Perfil opt-in `rust-r3-v1` no spike experimental: bindings de parâmetros/`let`, escopos com parentes e visibilidade temporal, sombreamento, condições `cfg` de três estados e `resolve_at` vinculado a arquivo/posição. Somente um alias imutável de função demonstrada pode indicar alvo; parâmetros, formas lexicais não suportadas, receptores/métodos/macros e condições desconhecidas conservam lacunas. Rust Reference fixada por commit e fontes/hash em `eval/semantics/r3/language-reference-pin.json`. Nenhuma execução de Cargo/macros upstream é usada para indexar.

P3 usa a ocorrência do anchor no perfil R3 e conserva query/evidência no manifest. A fixture `eval/context/r3-binding-input.json` contrapõe importação no baseline, alias local no head e parâmetro chamável desconhecido. Labels ficam em arquivo externo. Verificador rejeita troca de homônimo, posição e promoção indevida de parâmetro.

Dois candidatos reais têm arquivos completos base/referência, licenças, configuração fixada, pedidos naturais sem solução e oracles separados. `collect_real_rust.py verify` e `prepare_l5_js.py verify` reconstroem inventários/digests sem executar código capturado. Executores de provas comportamentais usam o harness no Linux descartável, preparação com locks preservados, probes offline, limites e recibos de encerramento. A CI inclui os dois pares; esta entrega ainda precisa dos respectivos resultados.

Novas medições nativas preservam os seis executáveis e manifest com hashes no artefato de cada alvo, retenção de 90 dias. Bytes históricos ausentes continuam explicitamente históricos; nenhuma recompilação é apresentada como aqueles bytes originais.

## Evidência por critério

| Recorte | Evidência e resultado local |
|---|---|
| Matriz R3 congelada antes de execução | `logs/L5-continuacao/r3/labels-first.json`; 34/34 casos corretos, 16/16 previamente resolvíveis, zero promoção |
| Contraprovas | 4 contraprovas R3 + 3 extras unknown; falhas iniciais de mutabilidade/comentário e escape cfg preservadas; corrigidas conservadoramente |
| A→B no mesmo índice/processo | Dois eventos com geração incrementada, bindings/export criado e configuração alterada; Snapshot inteiro incremental igual ao rebuild, labels externos e 14 contrachecks independentes |
| Amostra Rust real | Tokio-test, três módulos originais capturados: 3 queries rotuladas, 1/1 resolvível, cobertura 1/3; **201 ocorrências de chamada unknown**, sem claim de recall de chamadas/crate completo |
| P3 consumidor R3 | Três fixtures atuais verificadas, 13 testes de recibos incluindo quatro novos de ocorrência/homônimo/parâmetro |
| Rust histórico | rust-analyzer PR23422, `3a5f657… → ec5b576…`; piso conservador 825 arquivos/220.645 linhas. Segunda leitura adicional em quatro crates core: 258 arquivos/84.453 linhas; três módulos/duas arestas necessárias; licenças MIT/Apache; hidden test não altera prefixo de produção |
| JavaScript histórico | React PR22239, `77912d9… → 06f98c1…`; 273 arquivos JS/56.440 linhas não vazias de produção, conforme ADR021. Não é TypeScript reclassificado. Três módulos/dois subsistemas/duas arestas necessários para notifications síncronas; segunda leitura dos sete trechos/hashes |
| Preservação | R1/R2 e outputs históricos preservados; fonte do producer inclui o módulo R3. Plano condicional32 permanece válido; D1 global **0/32**, novos dossiês aceitos **0/4** |
| Checks | fmt/clippy/release aprovados; 63 testes documentais mais três contraprovas da captura Rust, 14 contrachecks R3 e 13 de contexto. Logs imutáveis em `logs/L5-continuacao/integration`; primeira tentativa com Python sem deps e diferença gzip entre runtimes preservadas e corrigidas |

`logs/L5-continuacao/r3/final/` retém outputs finais, comandos, tempos e hashes; `integration/context-receipts.json` identifica os três outputs P3 comprimidos. Revisões independentes do corpus estão em `corpus-js/independent-review-root.json` e `corpus-js/rust-second-reader-after-hardening.json`.

## Pendências para o Arquiteto

- **L5-02/M0-11 aberto:** R3 tem escopo explícito; perda real de cobertura ainda grande. R2 completo, R4, outras famílias, integração persistente e denominadores reais maiores permanecem.
- **L5-04/M0-03.R1 aberto:** candidatos Rust/JS curados ainda exigem baseline falhando pelo motivo previsto, referência/regressões passando e prova A→B preservando índice/processo. Eventos R3 sintéticos não substituem eventos reais dos dossiês. Python/Go ainda precisam de novos dossiês controlados. Não há admissão competitiva.
- **L5-01/03 e M0-09/M0-06 abertos:** relevância lexical/estrutural comparável, `direct_cached`, fontes reais/concorrência/decomposição de recursos, custo do envelope e calibração completa seguem conforme revisão vigente. Texto antigo do relatório XRW2 foi conciliado com CI38259048931, sem repetir matriz sintética.
- **L5-05/06:** adapter real/comparadores/gates não foram executados. Nenhuma nova decisão arquitetural foi tomada.
- **Provas nativas desta entrega:** aguardam CI do commit publicado. A revisão automática recusou teste amplo do workspace no macOS local por possível execução upstream; comando não executado, recusa preservada em `integration/workspace-local-rejected.json`. Verificação segue na CI Linux descartável, sem contorno local.

## Publicação e CI

Este primeiro registro acompanha o commit de implementação. Identidade do commit, runs, artefatos recuperáveis com hashes de executáveis e resultados comportamentais serão conciliados em recibo posterior, sem promover um candidato cuja prova falhe ou esteja incompleta.
