# TS/JS experimental — captured-relative-exact-v1

Labels congelados antes do resolver em `freeze-before-resolver.json`: 45 casos, sendo 22 JavaScript, 22 TypeScript e uma relação em duas unidades reais uuidjs/uuid. Há 13 consultas previamente rotuladas resolvíveis. O aceite exige ≥80% dessas referências e zero promoção nas 32 contraprovas; todas as chamadas têm alvo `unknown` nesta versão.

A entrada declara ESM, perfil e dialeto por arquivo. Imports relativos com extensão explícita selecionam exatamente uma fonte do mapa capturado. Não há consulta ao host, substituição `.js`→`.ts`, packages, basename, index, tsconfig, default/namespace lookup ou reexports. Tree-sitter permanece interno ao adapter; nenhuma fonte JS/TS é executada.

A saída expõe escopos, bindings, exports, gaps, referências, cobertura e spans UTF-8. Identidade lexical usa evidências ocorrência → import → export → declaração. Parâmetros simples e const simples têm identidade; const antes da inicialização/autoinicialização é unknown. Bindings mutáveis simples bloqueiam seu nome no alcance lexical (var é elevado ao alcance de função). Destructuring/eval/declaradores não modelados criam lacuna ampla, sem revelar import externo. Captura de binding local entre funções permanece unknown. Resolver chamado em função importada não afirma alvo em execução; mutations/flow não são analisados.

Os produtores incluem gramáticas/queries Tree-sitter, proveniência e ABI via `worker_spike::producer`, mais fonte/versionamento do resolver e perfil. Snapshot inclui configuração, fontes, paths e dialetos. O verificador recompõe os fingerprints declarados; a autenticidade dos hashes de gramáticas depende do binário retido/lockfile e recibo CI, não de flags fornecidas por chamador.

A fonte real é uuidjs/uuid v9.0.1, commit `b3f142f7efa6d335cd667413b8a5860d2dd04ebf`, `v4.js` → named `unsafeStringify` em `stringify.js`. As duas unidades inteiras, três unidades inspecionadas adicionais, licença e bytes da API ficam em `real/`. A árvore oficial contabiliza 140 arquivos, 67 JS/TS e 21 unidades em src; somente duas são analisadas, uma relação é rotulada. Os restantes não são prova de completude semântica. Nada entra no corpus D1 por esse ensaio.

Dados locais: `python eval/scripts/verify_tsjs_semantics.py --labels-only` e `python -m unittest discover -s eval/scripts -p test_tsjs_semantics.py -v`.

Native apenas em CI Linux descartável: `cargo build --locked --release -p xrai-eval --bin tsjs-semantics`; `python eval/scripts/run_tsjs_semantics.py --binary target/release/tsjs-semantics --output tsjs-evidence/event`. Recomposição: `python eval/scripts/verify_tsjs_semantics.py --outputs tsjs-evidence/event/outputs`. Contraprovas de snapshots reais: `XRAI_TSJS_OUTPUTS=tsjs-evidence/event/outputs python -m unittest discover -s eval/scripts -p test_tsjs_semantics.py -v`.

Referências oficiais consultadas em 12/10/2026: [TypeScript módulos](https://www.typescriptlang.org/docs/handbook/modules/reference.html) e [ECMAScript 2024 declarações lexicais](https://tc39.es/ecma262/2024/multipage/ecmascript-language-statements-and-declarations.html#sec-let-and-const-declarations). O perfil não reproduz a resolução geral TypeScript. JSX/TSX, chamadas, namespaces/merging e sessão TSJS-C continuam fora desta fatia.
