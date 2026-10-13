# L5-02 — TSJS-A e recorte lexical TSJS-B

12/10/2026. Entrega experimental em `xrai-eval`; não é frontend M1, aprovação de campanha ou nova tarefa D1. Matriz/entradas e critérios foram congelados em [freeze-before-resolver](../../eval/semantics/tsjs/freeze-before-resolver.json) antes de criar o resolver. SHA256 dos labels: `812837d7c86e79cc19bcbde2141a1f4ddd9e75d4d93ab1733f8e55b19fa322d0`.

## Implementação

`tsjs_semantics` tem perfil `captured-relative-exact-v1`: ESM declarado, dialeto por fonte, função de módulo, import nomeado/alias e export nomeado/lista local. Relação traz ocorrência, import, export e declaração, spans em bytes, hashes por fonte/snapshot e dependências. A resolução procura exclusivamente o mapa capturado. Fingerprint inclui resolver/fonte, perfil, gramáticas/queries/ABI/proveniência do produtor, configuração, fontes, paths e dialetos. Não reutiliza resolução Rust.

TSJS-B inclui parâmetros simples, const simples em função/bloco, escopo/posição e barreira antes da inicialização. Let/var não são suportados como alvo: o nome bloqueia no alcance pertinente, var na função. Destructuring/eval/ambiente não modelado bloqueiam alcance mais amplo. Capturas locais e alias chamáveis não demonstrados ficam unknown. Identidade lexical de parâmetro/const/import não promove chamada: todos os alvos chamáveis continuam unknown.

## Fonte real e perdas

uuidjs/uuid v9.0.1, commit `b3f142f7efa6d335cd667413b8a5860d2dd04ebf`, fonte oficial adquirida como dados via GitHub API. Cinco unidades inteiras e licença foram retidas; duas unidades analisadas (`src/v4.js`, `src/stringify.js`); uma relação named `unsafeStringify` rotulada. Árvore oficial completa: 140 arquivos, 67 JS/TS, 21 unidades src; 19 unidades src ficam fora da análise. [Inventário e metadados](logs/L5-C04/TSJS/source-universe.json). Default imports/outros usos não foram forçados ao perfil. Nenhum import, build, teste ou compilador upstream foi executado.

## Evidências e estado do aceite

- Labels pré-resultado: 45 casos (22 JS, 22 TS, um real), 13 consultas resolvíveis e 32 contraprovas unknown; recall exigido ≥80%, zero promoção indevida e callable sempre unknown.
- Contraprovas incluem alias/homônimos, export/arquivo ausente, path fora da raiz/extensão ausente/bare, duplicidade, parse parcial, parâmetro, bloco irmão, TDZ/autoinicialização, alias lexical, let/var/destructuring/eval, import default/namespace e ambiente de tipos/captura.
- Local: sete verificações data-only aprovadas; 15 verificações de snapshots nativos explicitamente não executadas localmente. [Log](logs/L5-C04/TSJS/offline-tests.stderr), [freeze recomposto](logs/L5-C04/TSJS/labels-verified.json).
- Rustfmt e py_compile aprovados. Reconciliador prospectivo `reconcile_tsjs_ci.py` exige workflow/job/steps/API/ZIP/export e binário exatos, recompõe o batch e rejeita substituições. 24 verificações offline de metadados/ZIP aprovadas; sete ataques ao bundle real aguardam recibo CI. Compilação/clippy, resultados de 45 cases, relação real e 15 contraprovas dos snapshots aguardam CI descartável. Esse estado não declara recall observado nem aceite native concluído.

Runner novo executa só o analyzer próprio e retém binário/45 snapshots/invocações/recibo. Verificador data-only exige closure de campos, inputs, fingerprints, evidências, cadeia e denominador congelado; `--labels-only` não é prova de resultado. Reconciliador CI vincula hashes de gramáticas ao binário retido/lockfile: recompor hashes declarados isoladamente não autentica sua origem.

## Pendências para o Arquiteto

TSJS-C não implementado: não confundir esta semântica com evento de presença React/Flow. JSX/TSX, chamadas demonstradas, alias chamáveis, TDZ completo, type namespace/merging, package/default/namespace/reexports, resolução Node/bundler e recuperação semântica geral ficam fora. A gramática Tree-sitter não implica suporte a todas essas construções. Não há mudança de labels para atingir meta e não há admissão de corpus.

Referências oficiais consultadas antes dos labels: [TypeScript módulos](https://www.typescriptlang.org/docs/handbook/modules/reference.html), cuja resolução geral tem substituição de extensões deliberadamente excluída; [ECMAScript 2024 declarações lexicais](https://tc39.es/ecma262/2024/multipage/ecmascript-language-statements-and-declarations.html#sec-let-and-const-declarations), base da barreira temporal. Não foi feita alegação de conformidade geral.

## Primeiro recibo native: falha preservada

CI `38329117468`, commit `3463bdc7bd6ad085d784f0b45fc7ef496f9ee80b`, compilação/clippy aprovados, 45 snapshots emitidos; verificação recusou `javascript-partial` porque a ocorrência consultada foi omitida pela interpretação de recuperação da AST. Inspeção data-only do ZIP original encontrou o mesmo problema em `typescript-partial`; as outras 43 consultas coincidiram com os labels. Isso não foi aceito como prova completa e não houve alteração de rótulos. [Diagnóstico e hash do ZIP](logs/L5-C04/TSJS/partial-occurrence-diagnosis.json).

Correção prospectiva preserva tokens de identificador/propriedade da AST parcial como ocorrências explicitamente unknown no alcance do gap de módulo, com spans originais e diagnóstico parse_partial. Não usa a recuperação para promover bindings. Runner prospectivo expande de oito para 12 hashes de fonte, acrescentando helpers parsing/producer e queries JS/TS. Nova compilação/prova CI é necessária para esse código. A falha original e o manifesto antes do primeiro CI permanecem preservados.

## Primeira prova e correção observada

CI 38329117468 no código 3463bdc compilou/clippy aprovados, mas o verificador recusou duas ocorrências ausentes (javascript-partial/typescript-partial). [ZIP/API/log preservados](logs/L5-C04/TSJS/native-attempt-1/acquisition.json), [diagnóstico data-only dos 45 snapshots](logs/L5-C04/TSJS/partial-occurrence-diagnosis.json): 43 casos tiveram consultas representadas; esse run não é aceite semântico.

Correção recupera identifier/property_identifier no AST parcial como referências unknown, sob gap parse_partial, sem criar alvo/binder. Labels/SHA/denominador permanecem congelados. Novo runner acrescenta bindings de helpers/queries do produtor; reconciliação exige rustc/host realmente impressos, registra que Cargo não foi impresso separadamente. Segunda CI dedicada pendente neste checkpoint.

## Aceite nativo do recorte congelado

CI [38329944063](https://github.com/wkoch/xrai/actions/runs/38329944063), código `96b377c9c12be862d9ce90c92816ac499cb1bfc7`: clippy/build, 45 outputs e 22 checks de snapshots aprovados. [ZIP/API/export e recomposição completa](logs/L5-C04/TSJS/native-proof/reconciliation.json) vinculam job 115077202462 e artifact 11782770003, ZIP SHA256 `279373e40db06b9b241d3322465a0d3ad512656f6dc63c04eaec7ea263208be4` e 53 arquivos exatos. Treze de treze consultas resolvíveis corretas (100% do denominador pré-fixado), zero promoções indevidas, zero callable targets e nenhuma perda nos labels. Relação real v4→unsafeStringify demonstrada com ocorrência/import/export/declaração.

[31 checks ZIP/API e 22 checks de snapshots sobre o export real](logs/L5-C04/TSJS/native-recheck/ci-tests.stderr) também passaram data-only. O executável retido foi lido/hasheado; nenhuma execução local. Gramáticas são declarações de produtor cuja origem está vinculada ao run compilado e fontes/lock/proveniência; o reconciliador não executa binário para recompor seu fingerprint interno, mantendo o campo específico `grammar_fingerprints_verified_against_retained_binary_by_ci_reconciler=false`. Recorte não significa conformidade TSJS geral, chamadas resolvidas, precisão fora dos labels ou corpus admitido.
