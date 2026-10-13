# Captura de request prospectiva v4 — composição offline

`ImmutableRequestDispatch` / `make_immutable_guarded_fake_session` capturam uma
representação JSON canônica única e mantêm seus bytes como autoridade. O guard/v2
recebe um decode privado não devolvido ao caller. A releitura legada de v2 lê essa
cópia privada; mutações do caller deixam de modificar o pedido transportado.
Nenhum método/campo privado dos módulos antigos é usado, e eles permanecem intactos.

Preferir request em `bytes` canônicos. Caller com `dict` deve manter ausência de
escrita concorrente durante **toda a validação/captura**, incluindo serialização;
a cópia não torna múltiplas leituras atômicas. Arrays/objetos são bounded em 4.096
nodes, depth64, strings128KiB, request128KiB e 16 attempts/session.

A API pública é `dispatch_fake`, `recover`, `expand`, `reconcile_fake`, `finish`,
`request_record`, `record`; o target público D01 direto também permite `dispatch`
com cancelamento explícito e `reconcile`. `request_record` contém request version,
payload/bytes/hash, limite virtual, call/attempt/retry e bind task/arm/run/authorization.
`replay_immutable(request_record, target_record)` recompõe reserva e projeção privada.

**Runtime não instala profiler nem intercepta transporte.** O registro mostra
`transport_observed_independently=false`: a projeção deriva dos bytes privados.
Igualdade da entrada fake efetiva é confirmada pelo spy **somente nos testes**,
com `sys.setprofile` no thread diagnóstico. Mutação da cópia descartável recebida
pelo adapter não modifica bytes autoritativos nem a reserva. Provider futuro
precisa de seam público de payload/receipt; esta entrada não fornece autorização.

```sh
python -m unittest discover -s crates/xrai-eval/harness/tests -p test_immutable_request_dispatch.py
python eval/adapters/immutable-request-v1/verify.py
```

`prove.py` é coletor diagnóstico próprio, com spy exclusivamente de teste; ele
regenera evidência apenas durante desenvolvimento autorizado. `verify.py` é
readonly, trata recibos/spy como dados e confere source closure atual.

`freeze.json` registra 12 controles antes do wrapper. Seis execuções completas
retidas exercitam antes/depois compromisso, cancel pre/post, alteração descartável
no adapter e retry/receipt tardio. Trinta e oito testes cobrem também pedido alterado
antes de capture, bytes não canônicos, binding adulterado e recusa de segundo
admission guardado sem reserva. v2 histórico continua reproduzível com divergência
no teste de regressão; não foi consertado retroativamente.

ABA, autoridade por geração monotônica, blob store/perfil e contenção factual
ficam pendentes. Não há provider/network/native/upstream execution ou agent_run.

Profile v4 confere bijeção completa e ordenada com TODOS os begin/end fake (inclusive refusals sem reserva), ou reserves diretos. Ordem é derivada da sequência real pública, com pending ID/cap reservado antes de capture e snapshot wrapper+target coeso. Categorias pré-journal são diagnósticos próprios sem send authority; o denominador observado externamente permanece indisponível. O consumer frozen exige uma/duas chamadas e zero dessas categorias. Próximo passo é owner público/body receipt do transporte, sem adicionar wrappers genéricos.
