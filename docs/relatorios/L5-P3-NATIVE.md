# L5-01 — intake P3 nativo com presença explícita (C06)

Estado: código prospectivo e contraprovas data-only concluídos; build/execução/prova autenticada nativa pendentes de CI. Nenhum Cargo/analisador/upstream/provider foi executado localmente.

## Contrato e separação de autoridade

`context-diff-spike` é uma extensão experimental por bytes, independente do `context_spike::Store` anterior. O decoder Python C05 lê o diff bruto e entrega arquivos BASE/HEAD, presença, spans e bytes retirados/substituídos. O Rust revalida UTF-8, fronteiras de caracteres, presença, espécie da alteração, ordem/localização dos hunks, retiradas/substituições e reconstrução integral de todos os arquivos HEAD, inclusive arquivos não mencionados. Flags do decoder não autorizam o consumo.

O diff bruto, seu SHA-256, identidade BLAKE3 dos bytes e perfil/hash do decoder são preservados no manifesto. O SHA-256 do diff/origem do decoder é proveniência carregada e conferida pelo verifier Python; o Rust não implementa parser de diff nem valida esse SHA-256 por si. Sua autoridade é a reconstrução dos pares e spans tipados. O verifier relê diff e snapshots congelados e exige igualdade da resposta completa com a recomputação independente, além do hash do produtor/ELF e transcript.

Presença é obrigação própria em cada revisão. Um arquivo ausente gera `present:false`, sem evidência de conteúdo; um arquivo presente vazio gera `present:true`, hash da fonte vazia e evidência com span `[0,0]`. Nenhuma ausência é promovida a blob presente. Evidências preservam path, lado, revisão, hash/tamanho da fonte, span do hunk e handle vinculado ao contexto e sua encarnação.

O planner/IR semântico legado não é chamado ou alterado. `semantic_support` e o estado semântico das evidências ficam `unknown`. O perfil não promove esta entrega a seletor semântico P3 completo, à admissão de dossiês ou a eventos naturais de quota. A intervenção de presença do React continua sendo captura controlada, não correção histórica upstream.

## Critérios e evidências antes da prova nativa

| Critério | Implementação/contraprova | Evidência local |
| --- | --- | --- |
| Protocolo/casos antes do código | `freeze-before-native.json` com hash de protocolo, 55 casos C05 e decoder; ausência do bin/collector/verifier na criação do freeze | `logs/L5-C06/P3-native/design.json`: 21 aceitos, 34 negativos Python preservados; freeze `7547a49814fa2530d10d96c51de21ef4b05ce92d6e8d65b8025a28ecbdcf487e` |
| Criação/remoção/vazio/UTF-8/CRLF/EOF | Todos os 21 pares aceitos C05 viram typed intake; origem/bytes permanecem exatos | Casos/labels C05 congelados sem mudança; teste explícito de presente vazio versus ausente |
| HEAD integral antes das obrigações | Rust reconstrói todas as alterações e compara o mapa inteiro; negativos tipados alteram HEAD, presença, kind, span, replacement, path duplicado e UTF-8 | Sete mutações planejadas pelo protocolo; oracle data-only deriva a recusa e preservação do contexto anterior |
| Seleção/expansão | Contexto entrega os bytes dos spans; expansão entrega a fonte inteira dos handles selecionados | Oracle gera seleção/expansão, orçamento baixo com recusa, omissões identificadas no manifesto e fórmula determinística de piso de metadata |
| Revisão/imutabilidade | IDs incluem intake, encarnação e produtor; uma nova abertura encerra o contexto anterior; expansão de ID antigo é recusada | Trocas entre os 21 pares; expansão após abertura inválida deve permanecer byte a byte igual à expansão anterior |
| Envelope completo | Canonical JSON UTF-8 inteiro da resposta, excluindo somente LF de framing; estabilização do próprio `wire_bytes` | Todas as respostas, inclusive recusas, recomputadas; `model_tokens:null`, `controlled_tokens:null`, meter declarado por bytes |
| Produtor/execução/evidência completa | Collector restrito a Linux/GitHub Actions executa somente o ELF próprio retido; inputs/source hashes/ELF e stdout/transcript/process closure vinculados | Collector/verifier com segundo processo de rebuild prontos; execução/autenticidade nativas pendentes |
| Adversarial/data-only | Alterações em orçamento, tokens, PID, produtor, revisões, spans, bytes, hashes, presença, handles, decoder e promoção semântica recusadas | 47 testes descobertos: 46 passaram e 1 factual ficou skip sem `XRAI_C06_P3_OUTPUT`; rustfmt e py_compile passaram |

`commands()` deriva 182 comandos para um processo: 21 pares, consultas de revisão antiga, expansão integral, recusa de orçamento/handle, abertura inválida seguida de expansão preservada e sete mutações tipadas. A fórmula adicional de omissão usa o tamanho do manifesto derivado antes da execução mais 32 bytes; é uma contraprova técnica do seletor de bytes, sem mudar rankings/labels ou escolher orçamento após ver resposta nativa. Ela não é um resultado de curva de tokens ou campanha competitiva. O oracle local prevê 90 recusas e 36 omissões de evidências; esses números ainda não são prova factual do binário. Um segundo processo recebe os mesmos 21 intakes, com abertura/expansão integral/fechamento, totalizando mais 43 comandos. Incarnations são as mesmas sequências determinísticas de publicações bem-sucedidas, portanto os IDs e os resultados completos devem coincidir sem normalizar evidências, presença, spans, hashes, unknowns ou manifesto. Cada envelope/PID/contador é verificado integralmente em seu próprio processo.

A fixture de ELF artificial nos testes serve somente para exercitar o leitor. Verificação estrutural de transcript não comprova execução/autoria por si: a autenticação exige API/run/job/artifact GitHub originais e reconciliação root. O primeiro erro de teste (`create-empty-file` inexistente em vez do ID congelado `create-empty`) está retido em `initial-empty-case-name-failure.stderr`; a correção alterou apenas o teste, sem relabel.

## Limites implementados

JSONL com frame efetivo de 4 MiB e no máximo 512 operações; 128 arquivos, 8 MiB por arquivo, 32 MiB por snapshot e 4096 hunks, sujeitos ao frame efetivo menor. Sem caminhos absolutos, aliases `.`/`..`, barras invertidas ou controles; maps BASE/HEAD recusam keys duplicadas. Deserialização tipada recusa campos opacos. Budget de resposta até 1 MiB; meter com no máximo 16 passos de estabilização.

A seleção/expansão limita trabalho a 128 evidências selecionadas e 2 MiB de bytes de fonte materializados antes da conversão hexadecimal. O armazenamento de fontes é compartilhado por referência entre hunks do mesmo arquivo, evitando clonagem de um arquivo para cada hunk. O perfil retém somente um contexto; uma nova abertura bem-sucedida encerra o anterior. Abertura inválida, orçamento impossível e expansão inválida não substituem o contexto válido.

O algoritmo preserva ordem e remove itens do fim até a resposta caber, mantendo manifesto/handles e omissões com razão. Se nem metadata cabe, retorna `metadata_budget_floor` com erro e conserva o contexto anterior. Não corta conteúdo arbitrariamente nem omite obrigações para fabricar entrega. Não há TTL, pressão multi-contextos, cache persistente, execução de testes upstream ou desempenho reivindicado neste perfil.

## Interface para CI e reconciliação

- Build próprio: `cargo build --release --locked -p xrai-eval --bin context-diff-spike` em CI descartável.
- Design: `python eval/scripts/p3_diff_native_verify.py --design-only`.
- Coleta: `python eval/scripts/p3_diff_native_collect.py --binary target/release/context-diff-spike --output event`.
- Verificação: `python eval/scripts/p3_diff_native_verify.py --output event`.
- Contraprova factual: `XRAI_C06_P3_OUTPUT=event python -m unittest discover -s eval/scripts -p test_c06_p3.py -v` exige 47 testes sem skip.

Closure do evento concluído: três `inputs/{protocol.json,cases.json,freeze-before-native.json}`, `native-bin/context-diff-spike`, quatro `session/{transcript.jsonl,stdout.jsonl,stderr.bin,process.json}`, quatro `rebuild/{transcript.jsonl,stdout.jsonl,stderr.bin,process.json}`, `receipt.json` e `verification.json`: 14 arquivos. Com os oito topfiles do workflow root são 22 membros. O verifier jamais executa ELF retido; apenas o collector CI executa o binário próprio. Fonte do workflow e ferramentas consumidas fazem parte dos bindings.

## Revisão arquitetural C05 recebida durante a implementação

`REVISAO-L5-C05.md §3` exige intake tipado no protótipo Rust existente, identidade SHA-256/BLAKE3 sobre os mesmos bytes, publicação atômica com preservação de A e rebuild de B, seguido de tarefa inteira/frontend compatível e comparação lexical/estrutura/P3. Esta fatia prospectiva entrega o consumidor por bytes e deixa explícitos os gaps de integração: não usa `context_spike::Store`, não deriva obrigações P2/IR, não implementa referências semânticas e não executa tarefa inteira. A captura React comprova somente equivalência de bytes/presença; não empresta frontend Rust a JavaScript.

A comparação com rebuild independente e a identidade SHA-256 do intake foram adicionadas como engenharia sobre os mesmos pares congelados, antes da execução CI. O request carrega SHA-256 dos mesmos bytes de serialização tipada sobre os quais o Rust calcula BLAKE3; ambos algoritmos ficam explícitos no manifesto. O verifier Python recomputa o SHA-256 e a identidade BLAKE3, sem promover SHA-256 a verificação interna Rust (`intake_sha256_checked_natively:false`). Sem recibos autênticos dos dois processos não há aceite nativo desses itens. A prova de ausência conhecida continua separada de indisponibilidade: este perfil exige snapshots completos e não representa fonte indisponível; ele recusa input incompleto em vez de preencher fonte vazia.

## Pendências para o Arquiteto

1. Integração/adopção deste typed intake pelo planner semântico legado e suas obrigações IR: permanece futura. Esta entrega testa presença e reconstrução com um consumidor prospectivo por bytes, mantendo o contrato anterior intacto.
2. Parser de diff nativo Rust e hashes SHA-256 internos: não implementados; raw parser continua Python, com replay congelado.
3. Granularidade semântica/funções, referências BASE e comparação com P3 anterior/token baselines: não inferir resolução a partir de bytes de fonte.
4. Contextos múltiplos/TTL/persistência, perfil de tokens L4 e provider/agent/budget real: seguem pendentes de escopo/provas próprios.
5. Build/prova CI autenticada desta versão: pendente até root publicar, executar e reconciliar run/API/ZIP; falhas devem ser preservadas antes de qualquer correção.

A revisão root acrescentou sete contraprovas de igualdade tipada: sequence boolean/float, exit/unread boolean, command_count float e span de request boolean/float. O verifier compara JSON canônico das requisições/resposta de fechamento e exige inteiros exatos nos contadores, evitando equivalências Python `False == 0`/`True == 1`. Os primeiros 32 checks estão preservados em `initial-32-tests.stderr`.

M1, gates G0/G1/G2, elegibilidade/admissão e quotas não foram alterados.
