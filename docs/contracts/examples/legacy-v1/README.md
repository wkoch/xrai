# Fixtures documentais v1 preservadas

Estas 25 fixtures e seu schema são cópias byte a byte da entrega L0, anterior
à retificação M0-01.R1. Mantêm `schema_version:1` e igualdade de snapshot fixo.
Não especificam seleção `latest` nem serialização real de adapters. O histórico
Git e os logs L0 permanecem intactos.

Os pares atuais no diretório pai usam `fixture_version:2`, `schema_version:2`
e seletor explícito `consistency.revision`. A migração documental substitui
`snapshot_id` pelo seletor `fixed` (ou `latest` no status sem geração), recalcula
bytes do envelope e preserva bytes/hash/spans e expectativas adversas originais.
O diagnóstico de admissão ganha as serializações CLI/MCP contabilizadas.
O oracle `fixture_state` é material do teste, nunca campo da API.

O verificador v2 rejeita v1 em vez de inferir selector/versão silenciosamente.
Nenhuma API ou migração de banco de produção foi implementada; compatibilidade
de produto será decidida/testada em M1-01/M1-04.
