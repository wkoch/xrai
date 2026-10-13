# Adapter experimental: prova estrutural offline

Os sete arquivos `*.jsonl` são transcritos de **scripted_retrieval**, obtidos de código Python próprio e do transporte fake D01. Não são `agent_run`, não medem sucesso de tarefas e não autorizam D1. `protocol.json` registra limites e semântica de medição; `comparator-plan.json` retém os oito candidatos do plano com dois regimes, mas pins/instalação/configuração forte permanecem ausentes.

O consumidor de bytes é `replay_adapter(raw)` em `crates/xrai-eval/harness/agent_adapter_protocol.py`. Ele recompõe o ledger D01, os vínculos task/arm/run/call/attempt, fontes/configuração/produtor, pares de ferramentas, spans UTF-8, hashes, envelopes lexicais e bytes do serializer. Não executa o produtor transportado no arquivo. `comparator_preflight(manifest, current_source=bytes_do_documento)` sempre recusa este perfil de planejamento.

A captura da ferramenta usa `ToolSnapshot.capture(index, files, Path(lexical_retrieval.__file__).read_bytes())`. O wrapper recebe callbacks `current_sources` e `current_producer`, para comparar bytes reais antes/depois de cada recuperação/expansão; não recebe `ready`/`verified` do caller. O handler é o `LexicalIndex` próprio, construído apenas com fontes capturadas; expected-labels, oráculos e arquivos ocultos da avaliação não entram no contrato.

Os bytes incluem envelopes, esquema de ferramentas e eventos JSON. `model_tokens`, `provider_usage`, `provider_charge` e `financial_cost` continuam indisponíveis (`null`). Valores do ledger D01 são exclusivamente aritmética virtual da fixture fake. A resposta final é um resultado scripted sem julgamento.

Reprodução estrutural, no ambiente Python do projeto:

```sh
python docs/relatorios/logs/L5-C04/adapter/prove.py
python eval/adapters/experimental-v1/verify.py
python -m unittest discover -s crates/xrai-eval/harness/tests -p test_agent_adapter_protocol.py
```

O coletor regrava fixtures/evidências a partir das fontes próprias atuais. O replay de fixtures já capturadas é data-only. Nenhum comando acima compila código nativo, executa fontes upstream ou chama rede/modelo.

`verify.py` apenas lê as sete fixtures exatas e as evidências, recompõe SHA/bytes/replay e recusa os oito comparadores; confere o protocolo, hashes das fontes atuais e closure antes/depois. Não regrava arquivos nem executa o comando histórico do receipt; seu interpreter/version é registro de origem, sem exigir o mesmo caminho no host da CI.
