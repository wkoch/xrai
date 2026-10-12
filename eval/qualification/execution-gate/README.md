# C03 — entrada de dispatch offline

`smoke-offline.json` é uma fixture sintética do consumer, não uma tarefa admitida
no corpus. Contém o manifesto e todos os bytes de evidência em base64. O consumer
congela esses bytes por conteúdo e consome o pedido previamente vinculado, acima
da reserva do ledger. O custo é em unidades sintéticas; não representa preço de
provedor ou teto autorizado para recurso pago.

O protocolo `offline-paired-smoke-v1` declara braços `direct` e `indexed`, limites
comuns e destino `development_only`. A fixture verifica o gate/dispatch; não
executa dois agentes reais nem comprova contenção operacional. O adapter
habilitado é somente `FakeAdapter`, sem rede, credenciais ou subprocessos.

`replay_offline` reconstitui um ledger válido e não chama o adapter. `smoke_seed`
valida tarefas, oracles, revisão de fixture, protocolo e configuração sem exigir
D1. `campaign_d1` permanece recusada por dimensão: corpus imutável global,
recomposição dos quatro eventos e provider/autorização reais ainda não conectados.
Descritores, números e flags fornecidos pelo chamador não liberam a campanha.

Uma mudança dos objetos originais não muda o snapshot já consumido. Consumidores
que acompanham plano/evidência atuais fornecem `current_manifest` e
`current_evidence`: a divergência invalida a sessão até novo preflight. A reserva
é atômica, inclusive retries; timeout/cancelamento/falha após envio e usage ausente
mantêm a reserva de cobrança possível. Erro de recibo invalida admissões seguintes.

Verificação: `python -m unittest discover -s crates/xrai-eval/harness/tests -p
test_execution_gate.py -v`. Provas em `docs/relatorios/logs/L5-C03/gate/`.
