# Consumer guardado offline — L5-05, C06

Esta entrada executa Python próprio e trata Go capturado como bytes. Usa exclusivamente
`make_immutable_guarded_fake_session`, que compõe o factory original `make_guarded_fake_session` e mantém o request canônico privado prospectivo v3; todas as operações passam pelo guard público. O consumer atual tem schema v2. A primeira tentativa v1 está preservada em logs/first-attempt. É um
consumer CLI de recuperação lexical, com transport fake e controles de desenvolvimento.
Não constitui `agent_run`, smoke pago, provider, D1, admissão ou gate.

`scenarios.json` e 27 inputs foram congelados antes da criação do consumer em
`freeze.json`. São dez cenários, o subtree Go C04 inteiro (22 fontes / 54.032 bytes),
mesmo chunking/ranking BM25/TF-IDF original, e intervenção controlada sobre snapshots.
O task ID `D0-RS-01` é exclusivamente o identificador legado da fixture fake; o conteúdo
Go é vinculado ao input/review do cenário e não recebe qualificação Rust.

```sh
python crates/xrai-eval/harness/guarded_smoke.py \
  --manifest eval/adapters/guarded-smoke-v1/scenarios.json \
  --output /tmp/xrai-guarded-smoke-new
python eval/adapters/guarded-smoke-v1/verify.py \
  --output /tmp/xrai-guarded-smoke-new
python eval/adapters/guarded-smoke-v1/verify.py \
  --archive docs/relatorios/logs/L5-C06/guarded-smoke/owned-output.zip
python -m unittest discover -s crates/xrai-eval/harness/tests -p test_guarded_smoke.py
```

O manifest é uma lista exatamente igual à matriz pré-congelada. Intent, task, arm,
run ID, teto virtual, query, fontes e intervenções são estritos. Inputs alterados,
flags `ready`, campos desconhecidos, duplicatas e números não finitos são recusados
antes da criação do output. Cada fonte inteira é copiada para bytes, não executada.

O output exige diretório novo. Contém dez records JSON canônicos e um receipt com
closure/hash/bytes e método atual. Uma falha após criação retém records e grava
`incident.json`, que o verificador recusa como entrega completa. O verificador
é readonly: recompõe o guard/ledger e os envelopes lexicais completos usando só
bytes. ZIP permite apenas os onze membros regulares conhecidos, sem extração.

O orçamento `1.500` micro-USD e cada reserva máxima de `500` são **virtuais**.
Usage/charge/tokens de provider são `null`; wire é o perfil de bytes lexical antigo.
O retry retém reserva de `500` na primeira tentativa sem receipt, mesmo com receipt
fake tardio idempotente da segunda. O final só conclui com checks aceitos.

Limites: manifesto 256 KiB, cada fonte 128 KiB, total fonte 128 KiB, depth JSON 64,
record 16 MiB, output/ZIP expandido 128 MiB, onze membros fixos. Os limites mais
estreitos do guard/frame/journal continuam valendo. Callbacks não provam ausência
de ABA nem contenção atômica do sistema de arquivos. Não há código ou autorização
para credenciais, download, subprocesso/analyzer ou rede nesta entrada.
