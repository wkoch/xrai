# Proveniência do primeiro incremento L5

Falhas e gerações anteriores são preservadas. Um nome contendo `final` indica a
intenção daquele comando, e não substitui a conferência de fingerprint.

- `context/` contém provas debug anteriores, falha C05 antes da correção e testes
  da correção. `contract/context-review-final.json` antecede C04/C05; a revisão de
  retenção posterior é um recibo separado.
- `integration/rust-*-initial.json`, `rust-tests-native.json` e
  `rust-release-final.json` antecedem C04/C05. O primeiro clippy de retenção
  coincidiu com uma edição em andamento e falhou; a falha permanece registrada.
- Os recibos aceitos `integration/*-freeze.json` documentam a verificação integrada após o
  congelamento das fontes. A primeira tentativa de testes do verificador, sem configurar o diretório dos novos recibos, falhou por arquivo ausente; a prova aceita é `context-verifier-tests-with-receipts-freeze.json`. `source-manifest-final.json` liga essa geração às
  fontes/configurações/fixtures e verifica bytes históricos protegidos.
- `resources/` preserva o desenho congelado, erro de `ps` no sandbox, calibração,
  matriz nativa sintética local e arquivos de fontes. `corpus-plan/` verifica
  somente alocação condicional; não comprova admissão nem dossiê concluído.
- Recibos nativos de CI, quando conciliados, ficam em diretório próprio e ligam
  run, commit de código, ambiente e verificação externa dos artefatos.

O [relatório L5](../../L5.md) identifica a evidência aceita e as pendências. Não
atribuir sucesso de agente, uso pago ou encerramento de M0 às provas locais.
