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

**Pendente de CI:** compilação/clippy nativos, prova live dos 15+6 frames e conciliação
API/ZIP autêntica. A raiz possui workflow/collector separado e atualizará este estado
após resultado. Até lá, não declarar evento novo comprovado. Também pendentes ao
Arquiteto: dossiês naturais/eligibilidade e limites além do perfil; nenhuma decisão
extra foi tomada. Resolver/fingerprints/gramáticas e provas históricas permaneceram
inalterados; M0-11/M0-09 continuam abertos, oito elegíveis/zero admitidos.
