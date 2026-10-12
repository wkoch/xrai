# CI nativa L5

Run [38259048931](https://github.com/wkoch/xrai/actions/runs/38259048931), código
`e4cd4d47090ca93715e82c4623a6a2463af3bdb4`: três jobs aprovados. O recibo aceito é
`native-receipt.json`, reproduzido por `reconcile.py`; inclui ambientes, resultados,
quatro verificações externas de contexto e hashes dos artefatos preservados.
`resource-native-review.json` preserva duas verificações externas de recursos e
suas limitações. Comandos do contexto estão em `../integration/ci-context-*.json`.

`native-receipt-before-count-label.json` preserva a primeira conciliação, que
chamava os 50 casos descobertos de `harness_executed` mesmo incluindo skips.
O recibo aceito distingue 50 casos, 49 aprovados/1 omitido em Linux e
45 aprovados/5 omitidos em macOS. Resultados brutos não foram alterados.

`run-start.json`, `run-completed.json` e `run.log` preservam origem, conclusão,
versões das ferramentas e logs. O runner macOS é 15.7.9; não comprova host literal
15.0. Nenhum executável foi enviado como artefato: hashes declarados dos binários
ficam ligados ao build/job, mas não são reconferidos a partir de bytes ausentes.
Capturas de contexto são de desenvolvimento e matriz de recursos é sintética.
M0-06/M0-09 e os gates continuam abertos/sem avaliação; D1 permanece0/32.
