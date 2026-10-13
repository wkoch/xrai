# Guarda composta de ferramentas: perfil novo, exclusivamente offline

`SessionToolGuard` é um consumer prospectivo que compõe APIs públicas D01/adapter, sem editar suas fontes ou receipts históricos. O factory liga os mesmos callbacks reais de manifest/evidence/autoridade ao dispatch e à rechecagem antes/depois de ferramentas. O índice lexical próprio recebe somente fontes imutáveis capturadas; estes onze casos usam dados sintéticos de desenvolvimento, não tarefas elegíveis de corpus.

API em `crates/xrai-eval/harness/session_tool_guard.py`:

```python
guard = make_guarded_fake_session(snapshot, offline_authorization, index, tool_snapshot,
    bindings=explicit_task_arm_run_bindings,
    current_manifest=read_actual_manifest, current_evidence=read_named_evidence_bytes,
    current_authorization=read_actual_offline_allowance,
    current_sources=read_owned_source_bytes, current_producer=read_actual_lexical_producer,
    clock=monotonic_clock, fake_transport=FakeTransportV2())
guard.dispatch_fake(attempt_id, call_id, fake_request(), virtual_ceiling)
search = guard.recover(tool_call_id, query, method='bm25', top_k=5, max_wire_bytes=65536)
guard.expand(expansion_call_id, [row['id'] for row in search['snippets']], max_wire_bytes=65536)
record = guard.finish('completed', scripted_answer_bytes)
result = replay_guard(load_guard(canonical(record) + b'\n'))
```

`check()` recompõe a rechecagem pública; `revoke()`/`invalidate(reason)` operam pelas APIs públicas D01. `reconcile_fake` mantém resposta/receipt virtual tardio idempotente antes de finalizar. Checks negados geram `GuardRefused`, não retornam dados da ferramenta e invalidam/revogam a sessão quando apropriado. `finish('partial'|'error'|'timeout'|'cancelled')` preserva diagnóstico/histórico recusado. `completed` exige ausência de operações recusadas e uma rechecagem final aceita.

Journal guarda begin/check/end, prefixos SHA/bytes do transcrito delegado e resultado imutável. Se o delegado já registrou resposta, o postcheck pode recusar seu retorno; a resposta continua auditável no transcrito e no resultado guardado. Nenhum evento antigo é removido. Duas ferramentas simultâneas mantêm seus IDs, requests e resultados próprios; novo dispatch/finalização ficam bloqueados enquanto há operação ativa. Handler, transporte fake, captura de callbacks de dados e barriers de teste executam fora do lock da guarda. D01 mantém a seção crítica original para seus callbacks de admissão; estes devem ser leituras limitadas, sem transporte/provider.

Fronteiras observacionais não detectam ABA externo entre callbacks nem oferecem isolamento de processo. O handler lexical usa bytes próprios imutáveis e a validação mantém suas fontes/configuração/produtor atuais. O clock deve ser finito/monotônico e compartilhado com D01; falhas de clock/bounds podem deixar journal incompleto, que o replay fechado recusa, sem apagar o transcrito delegado. Header ≤512 KiB, frame ≤1 MiB, journal ≤8 MiB/128 eventos, record ≤16 MiB. Capturas maiores exigem perfil novo com blobs separados.

Verificação read-only: `python eval/adapters/guarded-v1/verify.py`. Recompõe onze fixtures, fontes atuais e concordância com o receipt histórico dos métodos/sete fixtures antigos; não executa comandos armazenados nem regenera arquivos. Coletor de desenvolvimento: `python docs/relatorios/logs/L5-C05/D01-tools/prove.py`.

Resultados são `guarded_scripted_retrieval`, sem julgamento de agente. `provider_usage`, `provider_charge` e `model_tokens` continuam null; ledger D01 é aritmética virtual sintética. Nenhuma permissão paga, D1 ou gate deriva desta entrega. Callers devem adotar o factory novo; usar diretamente o adapter histórico mantém o comportamento histórico.
