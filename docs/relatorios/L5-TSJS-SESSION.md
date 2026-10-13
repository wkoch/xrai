# L5-02 — sessão semântica TSJS-C no recorte capturado

13/10/2026, Implementador. Continuação do recorte TSJS-A e TSJS-C do roteiro L5.
Perfil `captured-relative-exact-v1`; este controle operacional usa duas fontes reais
uuid capturadas anteriormente. Remover/restaurar disponibilidade de `src/stringify.js`
é uma intervenção controlada na captura, não bug upstream ou mudança histórica.
Não substitui os dossiês naturais, não recebe crédito de quota e não admite campanha.

## Código e protocolo

Novo binário `crates/xrai-eval/src/bin/tsjs-semantic-session.rs` possui um `Index`
por processo com `Snapshot` completo do resolver existente. Operações JSONL: abrir
A uma vez, snapshot, lookup por path/offset exato UTF-8, update com revisão esperada
e fechar uma vez. Update chama `build` completo antes de publicar; erro mantém A
e geração. Fingerprint de sessão BLAKE3 liga binário fonte novo, resolver, Cargo.lock
e toolchain; fingerprint analítico/grammar do Snapshot antigo permanece inalterado.
Envelopes identificam PID, sessão, geração, snapshot, produtor e contadores completos.

O protocolo congelado pela raiz antes do binário possui 15 operações no índice vivo
+6 no rebuild independente. A nega lexicalmente `unsafeStringify` (offset 645), B
resolve cadeia ocorrência/import/export/declaration; `rnds` (661) mantém referência
resolvida e `native` default (155) permanece unknown. **Alvos runtime callable são
unknown em todos os casos.** Os dois updates inválidos (revisão errada e configuração
CommonJS) devem preservar o Snapshot A completo e a geração.

Bounds do perfil: frame de entrada 8MiB, saída 16MiB, 64 operações, 128 fontes/8MiB
de fonte capturada. O writer nativo impõe cap serializado antes de escrever no pipe.
O helper Process reutilizado tem cap efetivo mais estrito de **4MiB por frame**,
registrado no recibo. Artefato limitado a 128MiB e 32MiB/membro no verificador; este
recorte pequeno não exercita garantia de alocação de produto.

## Consumidor e contraprovas

`run_tsjs_semantic_session.py --binary ... --output <fresh/event>` recusa execução
fora de Linux `GITHUB_ACTIONS=true`, copia/torna somente leitura e executa o ELF
próprio **retido**, preserva bytes/inputs/frames/stdout/stderr/counters/close e hashes.
Nenhum comando/código upstream é invocado. Bundle possui 15 arquivos essenciais,
16 após `verification.json`; workflow/ambiente/toolchain e API/ZIP pertencem à raiz.

`verify_tsjs_semantic_session.py --design-only` verifica a congelação;
`--output <event>` recompõe o recibo data-only. Comparações incluem todos os campos
de Snapshot/Reference, sem retirar evidências, dependencies, gaps, cobertura,
diagnósticos ou callable. B deve ser integralmente igual ao rebuild e ao Snapshot
nativo anterior aceito de TSJS-A, cujo SHA256 está fixado em
`e6f9ff38e7e54b00d98271a3bdb9ee6a82b85faeec7eec3b015e91be860b2717`.
Gramática/producer atuais devem concordar com esse Snapshot retido; não há execução
ou nova extração de grammar no verificador Python.

Bindings abrangem a fonte da sessão, resolver/parser/worker, JS/TS queries,
provenance, Cargo/toolchain, os três scripts novos, helper Process/verifiers
reutilizados, Snapshot anterior fixado e workflow novo. Arquivo/configuração/decoder
mudado invalida o recibo. Autenticidade da captura exige conciliação de API/ZIP CI
pela raiz; JSON local arbitrário não é assinatura.

## Evidência e estado

- **45 checks data-only passaram**, sem skips: consumidores/contadores, frames,
  types bool/float, cold B relabelado, restart/PID/sessão, rebuild independente,
  update stale/config inválida, preservação integral A, produtor/gramática/fontes,
  campos/unknown/dependencies/evidence/gaps/callable sem normalização.
- Design-only passou para protocolo SHA256
  `97199bfff21899597767b9cda6c2e99fb51bca77fc223f8ea07fbb878262534c`.
- `rustfmt --edition 2024 --check` passou; `py_compile` dos scripts próprios passou.
  Nenhuma compilação Cargo, parser ou análise nativa foi executada localmente.
- Logs em `logs/L5-C05/TSJS-session/{development-evidence.json,design.json,tests.stderr}`.
  Primeiro teste encontrou `IndexError` no transcript vazio: recusa explícita
  `ValueError` foi acrescentada antes de ler o primeiro frame; falha preservada em
  `attempt-1.stderr`, protocolo/labels intactos.

Sem `XRAI_TSJS_SESSION_OUTPUT`, a bateria usa **fixture de transporte sintética**
e dados do Snapshot B anterior; isso prova contraprovas do checker, não execução
nova de A/B. Com essa variável no CI, os mesmos checks consomem o bundle efetivamente
coletado. Esse contraste permanece explícito na evidência de desenvolvimento.

**No checkpoint de preparação, pendentes de CI:** compilação/clippy nativos, prova live dos 15+6 frames e conciliação
API/ZIP autêntica. A raiz possui workflow/collector separado e atualizará este estado
após resultado. Até lá, não declarar evento novo comprovado. Também pendentes ao
Arquiteto: dossiês naturais/eligibilidade e limites além do perfil; nenhuma decisão
extra foi tomada. Resolver/fingerprints/gramáticas e provas históricas permaneceram
inalterados; M0-11/M0-09 continuam abertos, oito elegíveis/zero admitidos.

## Ajuste prospectivo de permissões antes do primeiro CI

A revisão de integração somente leitura identificou que `copytree` conserva os
modos 0400 dos inputs e 0500 do ELF retido. Os testes adversos que escrevem na
cópia privada falhariam com `PermissionError` em runner sem privilégio; a fixture
local anterior tinha modo 0644 e não exercitava essa condição.

`SessionTests.setUp` agora copia a fonte para diretório temporário privado, confere
**todos os arquivos byte a byte com a origem antes de qualquer mutação**, e só então
acrescenta escrita do proprietário às cópias. Origem/artefato/ELF retido permanecem
intactos. A fixture fake passou a usar os mesmos modos somente leitura do collector
antes de passar pela mesma cópia. Nenhum oracle, label, produtor, workflow ou
contagem foi alterado: **45 testes continuam passando** sob Python 3.13.13.

`readonly-private-copy-proof.json` reproduz os dois testes existentes de substituição
de input/ELF: modos fonte 0400/0500, cópia 0600/0700; bytes e modos da origem iguais
antes/depois e mutação somente da cópia. Não são dois novos casos no denominador.
Logs de desenvolvimento anteriores ficaram preservados em
`pre-readonly-fix.stderr` e `pre-readonly-fix-development-evidence.json`; evidência
corrente foi atualizada com hashes do teste ajustado. Execução nativa permanece
pendente do workflow ainda não disparado no momento deste ajuste.

## Prova nativa autenticada e revisão data-only concluídas

O [run CI 38425676814](https://github.com/wkoch/xrai/actions/runs/38425676814),
head `15547eddb4e23bce6d3668b2ef0329a77b1421ec`, passou no job
`C05 captured TSJS semantic session` (ID `115394328476`), com Rust/Cargo 1.98.1,
Python 3.13.13 e host Linux x86_64. Compilação/clippy, coleta live, recomposição e
**45 contraprovas sobre o artefato real passaram, sem skips**. A cópia privada
writable dos testes preservou os bytes da origem antes das mutações.

A aquisição autenticada da raiz preserva API run/jobs/artifacts, helper/recibo,
original ZIP e export exato em `logs/L5-C05/TSJS-session/native-proof/`. Artefato
`11827954072`, 24 arquivos, **1.218.796 bytes**; SHA256 do ZIP original
`ef2495dcdb27916c6e662eeea7e9d6d784be76d1447ce8abf2a4efcc741a1328`.
ELF próprio realmente consumido no CI: SHA256
`363910e42ee128f66e266dbdef303fd8ee2391758d800aeeaae95cef7a4f1660`.
Ele foi somente lido/hasheado na revisão local, nunca reexecutado.

Uma segunda passagem data-only recompôs todo o recibo em processo Python isolado e
conferiu igualdade completa com `reconciliation.json`, API/head/attempt/steps/upload,
hashes dos quatro comandos de aquisição, ZIP original e export. A revisão também
conferiu diretamente os 15 frames vivos e seis frames do rebuild, sem retirar
campos de Snapshot/Reference, dependencies, gaps, cobertura, diagnóstico ou callable.
Nenhum achado. Recibo em `logs/L5-C05/ci-reconciler/independent-review.json`; revisão
operacional de artefato, sem alegar leitor cego independente de labels de tarefa.

| Consulta congelada | A aquecido | B após update | Rebuild B |
|---|---|---|---|
| `unsafeStringify`, offset 645 | unknown, módulo exato ausente da captura | resolved → `src/stringify.js:unsafeStringify`, cadeia reference/import/export/declaration | Reference inteiro igual |
| `rnds`, offset 661 | resolved → `src/v4.js:rnds` | resolved, referência local preservada | Reference inteiro igual |
| `native`, offset 155 | unknown | unknown, default fora do perfil | Reference inteiro igual |

**Callable permanece unknown em todas as três consultas, nos dois lados.**
O índice vivo conservou PID `4673` e uma sessão; rebuild independente usou PID `4674`
e outra sessão. Revisão esperada errada e configuração inválida recusadas com
Snapshot A integral e geração 1 preservados. B integral é igual ao rebuild e ao
Snapshot nativo anterior aceito, inclusive input, producer, scopes/bindings,
exports/gaps/references/coverage e toda evidência.

Contadores finais live: 15 pedidos, três tentativas de build, dois builds publicados,
seis consultas e dois updates recusados. Rebuild: seis pedidos, um build publicado,
três consultas e zero update recusado. Snapshots:
A `f83b60dd0abee6867fcf183e7a9a83213dad05f7182bb1786fb4eedfc17afd56`;
B `7b529c7285869dcd6b614c61b68667e2b4f2e3eb0a9ea3c30fa7d96f5db2b5d8`.
Produtor analítico e componente JavaScript conferem com o Snapshot nativo anterior;
produtor da sessão liga o binário fonte novo, resolver, lock e toolchain.

A pendência de compilação/prova live desta fatia está resolvida. Permanecem os
limites do recorte: transformação controlada de disponibilidade nas fontes reais
uuid, sem mudança histórica upstream ou novo dossiê natural; resolução lexical
ESM exata, callable runtime desconhecido e rebuild conservador sem ganho de cache
medido. **Nenhum crédito de quota/evento D1, elegibilidade nova, campanha ou gate**.
M0-11/M0-09 permanecem abertos, oito elegíveis/zero admitidos. O módulo/labels/
fingerprints históricos ficaram intactos.
