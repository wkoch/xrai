# C06 — reconciliação histórica do adapter C04

O CI passou a recusar o receipt original de adapter após a atualização legítima
Arquitetural do `docs/PLANO-DE-IMPLEMENTACAO.md`: o binding antigo
`5bffa29b...d74bbc` deixa de ser o hash do plano vigente. O verifier original,
receipt, fixtures e plano atual permaneceram intactos. Nova entrada
`eval/adapters/historical-v1/verify.py` verifica a prova **histórica** por uma
cápsula própria com proveniência explícita, sem pular o hash antigo ou trocar
silenciosamente seu significado.

## Critérios e evidências

| Critério | Resultado registrado |
|---|---|
| Documento original exato | `git show f8881d4:docs/PLANO-DE-IMPLEMENTACAO.md` capturado como `original-PLANO-DE-IMPLEMENTACAO.md`; SHA-256 `5bffa29b5223ac305663a6e4cbf28a0325a277d96c44e863ebb50ac639d74bbc` é exatamente o digest do receipt original. |
| Método atual continua vinculado | Todos os nove SOURCE_PATHS originais são conferidos; apenas o plano usa a captura histórica. Oito supports/assets transitivos adicionais são pinned em provenance. Código substituído arbitrariamente não entra na cápsula. |
| Runtime privado explícito | Trinta inputs, 2.223.633 bytes. Diretório fresco; fresh Python `-I -B -X utf8` executa somente o verifier próprio original por run_path, ROOT normal derivado do arquivo copiado, sem patch de globais. |
| Replays e comparadores | Sete replays completos e oito recusas recompostos, resultado integral igual ao `root-recheck.json` C04 retido. Producers/commands/nativos nos receipts são dados, nunca executados. |
| Contraprovas | Dezesseis testes passam, zero skips: plano vigente pode mudar; snapshot/code/support/receipt/provenance/fixture adulterados e capsule extra/missing/alias/symlink/oversize são recusados. |
| Refusal original conservado | Entry original direto no checkout atual retorna exit1 / `current own source bytes changed since receipt`, com stdout/stderr próprios preservados. |
| Verificação readonly | Inputs conferidos antes/depois, cápsula conferida depois. Outputs CPython 3.13.13 e host 3.15.0 idênticos; nenhum source original foi modificado. |

Hashes e comandos estão em `logs/L5-C06/historical-adapter/development-evidence.json`.
Provenance SHA-256
`30001ef3fe6674d7746677d70e00e49087cdeeac15709b93f9b25417b1a25757`, compilado no
verifier prospectivo. Module SHA-256
`56f0d8ef9c1d73595c6c7480888fb8751bc5f8c8fa317b69267f04c32c4763f4`.
Limites de captura: membro16MiB, agregado32MiB,128membros máximo, closure30;
timeout30s, outputs owned bounded. Nenhum upstream, provider ou ELF foi executado.

## Escopo e pendências

A saída declara `current_plan_binding_claimed=false` e `new_qualification=false`.
Este aceite conserva evidência histórica e não vincula o plano atual aos métodos
antigos, não atualiza corpus/gates/cards, e não atribui solução ao defeito v2 do
pedido mutável. A correção desse defeito pertence aos perfiles prospectivos D01 e
consumer descritos nos relatórios respectivos.

A integração/push/CI desta entrada ficam com root. Evolução legítima futura de
outro documento histórico requer captura prospectiva explícita; não há fallback
que aceite hashes diferentes ou extensão genérica de fontes substituídas.
