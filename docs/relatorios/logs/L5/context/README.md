# Recibos locais de desenvolvimento — histórico antes do fix final

`context-removed-consumer.json` e `context-central-hunk.json` foram produzidos pelo
driver debug e verificados contra o código de 17 testes em 12/10/2026. Os hashes
observados e comandos estão em `local-receipts.json`. Os resultados adversos
iniciais de fixture e schema constam em `initial-failures.json`.

A revisão subsequente detectou que tentativas de expansão com falha de medição
não consumiam o cap. O código foi corrigido e recebeu o 18º teste: quatro falhas
admitidas consomem as quatro tentativas, e a quinta não chama o medidor.

Como o `selector_fingerprint` inclui o código inteiro do módulo, estes recibos
anteriores são deliberadamente **históricos**, não a prova do código final.
Rejeição por fingerprint ao compará-los com o módulo final é esperada. O lote
integra novos recibos release e prova nativa em caminhos próprios; não substituir
os históricos nem apresentar seus 17 testes como contagem final.

As capturas são sintéticas de desenvolvimento. Os relógios/IDs e contadores têm
papéis distintos: TTL usa relógio fornecido pelo driver; medição conta bytes do
envelope completo; timestamps fixos nos descritores não são captura de repositório.

## Revisão C05 — encarnação e retenção

`c05-before-fix.txt` preserva a contraprova (exit101): após TTL, recriar o mesmo
input devolvia o mesmo context_id. O teste final cobre TTL, pressão com relógio
igual e liberação; outra prova cobre Store substituto, reuse vivo sem renovar TTL
ou quota, e overflow sem wraparound. Store novo usa epoch aleatório do SO;
identidade inclui contador, criação/expiração e versão da política de retenção.

`c05-final-deadline-tests.txt` registra **21 testes context aprovados**; o clippy
focado está em `c05-final-deadline-clippy.txt`. Os arquivos `c05-after-fix-*`
precedem somente o cheque adicional do deadline após accounting/publicação e a
contabilidade integral de expand. As novas provas de wire release são produzidas
pelo integrador, com o fingerprint final. Recibos anteriores permanecem históricos.
