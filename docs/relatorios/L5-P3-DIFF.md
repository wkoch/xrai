# L5-01 — intake de diff unificado com reconstrução integral

13/10/2026, Implementador. Fatia do §5 da revisão L5 e ADR027; sem novo cartão/lote,
promoção de produto ou fechamento de M0-09. Código e dados novos, independentes dos
fingerprints dos perfis P3 históricos.

## Operação e aceite

| Critério | Evidência |
|---|---|
| Diff validado antes de gerar spans/obrigações | `unified_diff.decode_unified` recebe apenas bytes capturados BASE/diff/HEAD; devolve mudanças tipadas após reconstrução integral igual a HEAD |
| Criação/remoção integral, inclusive arquivo vazio | Casos positivos `create-*`, `delete-*`; presença `False`/`True` e hash `None`/SHA distinguem ausência de blob vazio |
| EOF sem newline e byte offsets exatos | Casos `both-eof-no-lf`, `context-eof-marker`, retirada/adição de LF, CR final, CRLF e Unicode; marcadores exatos e apenas no EOF do lado pertinente |
| Equivalência com consumidor typed | Cada um dos 21 positivos reconstrói novamente o HEAD integral com `apply_typed`; spans esperados externos congelados comparados exatamente |
| Conteúdo unchanged, arquivos não citados e hunks omitidos | Contraprovas `forged-unchanged-head`, `unmentioned-created-file`, `omitted-second-hunk`, alteração não citada no intervalo entre hunks; igualdade integral recusa todas |
| Contagem, paths e marcadores sem fallback | 34 negativos congelados: ranges/counts, trechos forjados, path alias/rename, ausência/captura inconsistente, repetição ambígua, EOFmarker ausente/duplicado/fora de posição, binary/combined/preamble |
| Headers dentro do payload | Teste de conteúdo começando `--`, `++`, `@@`: contagem/state distingue registros prefixados de headers |
| Fonte real capturada | ReactCurrentDispatcher.js, 495 bytes, hash e JSON de presença anterior retidos no corpus; criação e remoção reversa no escopo capturado, sem alegar mudança histórica Git |
| Perfil/bounds e ausência de execução | README e constantes do decoder: 2MiB diff, 8MiB arquivo, 32MiB captura, 128 arquivos, 4.096 hunks, 100 mil linhas/índices, 200 mil registros, 4.096 bytes/path; zero native/upstream/provider/acquisition |

## Verificação reproduzível

- `python3 -m unittest discover -s crates/xrai-eval/harness/tests -p test_unified_diff.py -v`: **63 checks passaram** (55 casos congelados e 8 controles de fronteira/consumer).
- `python3 eval/context/diff-v1/replay.py --output docs/relatorios/logs/L5-C05/P3-diff/proof.json`: **21 aceites, 34 recusas esperadas e 21 reconstruções typed integrais iguais a HEAD**; prova conserva recibos/spans/hashes e presença.
- `python3 -m py_compile ...`: módulos próprios decoder/test/replay compilaram somente bytecode Python; nenhuma execução nativa.

Casos congelados antes do algoritmo em `2026-10-13T15:06:24.902222+00:00`, SHA256
`318ea13cf2966a4f2154ada2f6c4470ebe1512a2f9f1b22aca29ecbecda2d7be`.
A primeira execução teve 62/63 checks: o decoder diagnosticava `head_origin` antes
reconhecer conteúdo BASE incompatível na localização repetida. A ordem da validação
foi corrigida; labels/capturas não mudaram. `attempt-1.stderr` preserva a falha,
`tests.stderr` o resultado final, `proof.json` a reprodução completa.

## Interfaces, limites e pendências ao Arquiteto

API em `crates/xrai-eval/harness/unified_diff.py`: `decode_unified`, `ValidatedDiff`,
`FileChange`, `Hunk`, `apply_typed`, `snapshot_id`. Objetos de resultado frozen;
consumer exige spans/bytes/presença/hashes, sem fuzzy search. Unicode não é
normalizado; CR é conteúdo; linhas são divididas somente por LF. JSON/labels/oracles
são usados pelo avaliador após a chamada, não pelo decoder.

Perfil estrito exclui timestamp/header Git, quoted paths, renames, binary/combined,
outros formatos e descoberta no host. Não é um leitor geral de qualquer saída Git.
Reconstrução exige capturas integrais do escopo de ambas as revisões; HEAD incompleto
não sustenta aceite. Hashes identificam bytes, sem afirmar retenção de produto.

**Pendente:** consumir essa entrada validada no planner/context Rust e no adapter P3
sem alterar silently o perfil documental/hashes históricos; criação/remoção podem
precisar presença tipada explícita na interface nativa. A equivalência demonstrada
nesta fatia é com consumidor typed Python data-only, não execução de `context_spike`.
O perfil antigo `docs/contracts/experimental-p3/verify.py` e o código Rust continuam
com suas restrições atuais, preservados. Relevância/seleção/curvas/tokens e demais
aceites de M0-09 permanecem abertos. Oito elegíveis/zero admitidos, gates e cartões
não se alteram por esta entrega. CI nativa/geral ainda não foi atribuída a esta fatia;
a integração/publicação será registrada pelo agente raiz.

Aceite CI da fatia data-only: código cba8214418a7edf523211086cfaf617f41ecaf8e/run38421464241 aprovou Documentary contracts e os dois jobs de workspace. Job documental executou os63 checks e recompôs proof.json por igualdade integral. [API original](logs/L5-C05/root-preflight/p3-published-ci-run.json). Esta integração não executa o novo diff no planner Rust/P3; a pendência nativa permanece.
