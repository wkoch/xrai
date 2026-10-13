# Verificação histórica do adapter C04

O plano atual foi atualizado legitimamente pelo Arquiteto. O receipt C04,
seus sete transcritos e o verifier original continuam vinculados aos bytes
originais e não foram alterados. O entrypoint original continua recusando o
plano atual; esta entrada distinta reconcilia explicitamente a prova histórica.

```sh
python eval/adapters/historical-v1/verify.py
python -m unittest discover -s eval/adapters/historical-v1 -p test_historical_adapter.py
```

`original-PLANO-DE-IMPLEMENTACAO.md` são os bytes exatos de
`git show f8881d4:docs/PLANO-DE-IMPLEMENTACAO.md`, hash
`5bffa29b5223ac305663a6e4cbf28a0325a277d96c44e863ebb50ac639d74bbc`, igual ao
receipt original. Não é o plano vigente.

`provenance.json` fixa 30 inputs (2.223.633 bytes), incluindo os nove bindings
originais, oito imports/assets próprios transitivos, sete fixtures, dois arquivos
de protocolo e quatro proofs. Seu hash é compilado no novo verifier. Somente
`docs/PLANO-DE-IMPLEMENTACAO.md` usa o snapshot histórico; todos os métodos atuais
e dados permanecem byte a byte ligados à closure explícita.

API: `capture(root)` → bytes verificados, `run_capsule(members)` → original
result, `verify(root)` → resultado de escopo histórico. Uma cápsula temporária
privada copia apenas a closure; fresh Python `-I -B -X utf8` executa o verifier
próprio original por `runpy.run_path`. Seu ROOT deriva do path normal dentro da
cápsula. Não há monkeypatch de ROOT, import de módulos do parent, execução de
producers/comandos gravados/ELF/upstream ou lookup Git no runtime.

Limites: 16 MiB por membro, 32 MiB agregado, 128 membros máximo, closure exata de
30, paths conhecidos sem symlink, deadline 30 s. Captura e cápsula conferem bytes
antes/depois; resultado integral coincide com o root-recheck C04 preservado.
Snapshot, own code, suporte transitivo, receipt, fixture e provenance adulterados
são recusados. O resultado mantém `current_plan_binding_claimed=false`,
`new_qualification=false`, zero provider/agent e campanha false.
