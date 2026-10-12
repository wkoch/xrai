# Harness local M0-04

Executor de desenvolvimento em Python, fora do runtime da CLI. Requer Seatbelt (`sandbox-exec`) no macOS ou bubblewrap no Linux; recusa fallback sem sandbox. `verify_records.py` usa jsonschema fixado em `docs/contracts/examples/requirements.txt`. Para a medição L4 e a suíte completa, usar Python3.13.13 e instalar também `requirements-measurement.txt` num ambiente isolado.

```sh
python3 -m unittest discover -s crates/xrai-eval/harness/tests -v
python3 crates/xrai-eval/harness/runner.py baseline --output /tmp/xrai-baseline
python3 crates/xrai-eval/harness/verify_records.py /tmp/xrai-baseline
python3 crates/xrai-eval/harness/runner.py replay /tmp/xrai-baseline/D0-RS-01.json
python3 crates/xrai-eval/harness/demonstrate_measurement.py --baseline /tmp/xrai-baseline --output /tmp/xrai-measurement
cargo build --locked -p xrai-eval --bin incremental-probe
python3 crates/xrai-eval/harness/incremental.py --binary target/debug/incremental-probe --output /tmp/xrai-incremental.json
```

O pai materializa cada checkout por allowlist. Processos recebem somente aquele workspace e ferramentas/libraries do SO, ambiente novo e rede negada. Os testes têm controles positivos de leitura/edição e negativos de leitura/escrita entre braços, acesso ao avaliador, symlink e conexão a um listener real. No Linux, namespace de rede é separado e o avaliador não está montado; no macOS, Seatbelt nega acesso ao conteúdo fora da allowlist. Metadados de filesystem e listagem do diretório `/` são permitidos para carregar ferramentas do SO. Isso não autoriza leitura dos filhos do diretório raiz.

`execute()` permite configurar comando absoluto, timeout, limite total de captura e fase. Cada rodada preserva stdout/stderr binários como base64, SHA-256, bytes capturados/observados, truncamento, status, exit code e tempo. Registros usam `scripted_retrieval`; a baseline escolhe palavras somente do prompt público, lista arquivos e lê até três ocorrências com três linhas de contexto. Ausência de resultado ou erro permanecem no registro. Nenhum oracle/anchor privado escolhe o trecho. `result.schema.json` reserva `human` e `agent_run` para adapters futuros; o executor entregue não roda agentes/modelos reais.

Replay verifica bytes, hashes e contagens capturadas. Modelo, tokenizer, usage e custo financeiro são `null` porque não foram observados. Bytes não são apresentados como tokens de modelo. O replay do mesmo registro é determinístico; nova execução pode ter tempos, PIDs e ambiente diferentes. Edição/testes podem usar fases próprias em `execute()`, mas a baseline D0 entregue é de recuperação seletiva sem solução julgada.

`incremental-probe` conserva o inventário em memória no mesmo processo. A sequência é INDEX A → QUERY A → evento B do avaliador → QUERY ainda A → UPDATE → QUERY B → rebuild B em processo novo, comparado também com materialização fria e hashes SHA-256 do avaliador. Recibos identificam `hash_inventory_probe`: não é índice semântico, prova de retrieval nem sucesso de agente. Em cada família há uma demonstração usando D0, sem promover seed a corpus competitivo.

L3-02 separa `adapters.py` (política de montagem/Seatbelt) de `supervisor.py` (vida do domínio). Linux mantém o init bloqueado em `--userns-block-fd`, recebe identidade em `--info-fd`, adquire pidfd, verifica namespace privado e escreve os mapas UID/GID de uma identidade e setgroups=deny antes de liberar o comando. O gate userns desativa o mapeamento automático do wrapper. No término normal, timeout, limite de saída ou cancelamento, SIGKILL no pidfd do init e readiness desse descriptor são a prova; enumeração de PIDs e killpg não substituem isso. A captura e dreno são limitados. Cada chamada cria UUID e namespace novos; teardown incompleto invalida o resultado, preservando o status original e bytes.

Novos registros são `xrai.eval.local.v2` / `result-v2.schema.json`. `result.schema.json` v1 permanece íntegro e ambos passam no replay/verificador. Rodadas v2 incluem `execution_status`, `containment`, `cleanup_status`, `domain_id`, `termination_evidence` e `eligible_for_agent_run`. Elegibilidade significa somente recibo de contenção; não autoriza recursos/modelos nem comprova sucesso funcional. `cancel=threading.Event()` distingue cancelamento de timeout.

macOS local permanece `macos_local_known_smoke`, `cleanup_status=not_proven`, inelegível para agente com shell arbitrário. `arbitrary_agent=True` nesse host retorna `containment_unavailable` antes de executar. `MacDisposableAdapter` informa indisponibilidade da VM/runner dedicado; não simula destruição. Smokes conhecidos e replay continuam disponíveis.

A matriz Linux roda duas repetições dos ataques finitos: setsid/double fork/pipes/saída contínua/fork de quatro filhos/timeout/saída normal com filho e morte do avaliador. Sentinelas positivas comprovam execução; pidfd externo comprova init morto após morte do avaliador. Dois braços concorrentes verificam leitura/escrita isoladas e cancelamento independente. `XRAI_CONTAINMENT_EVIDENCE=/caminho/containment.jsonl` salva recibos por teste no avaliador e não é herdado pelo executor. Mac não recebe aceite Linux por analogia. Relatório: `eval/reports/m0-harness-containment.md`.

L4-01 acrescenta medição offline versionada e ledger de sessões fake. O sidecar fixa tokenizer/serializer e preserva históricos v1/v2 com usage/custo null; o roteador `agent_ledger.py replay` valida cada versão. Timeout/stream parcial sem receipt conserva reserva financeira e lacuna de cobrança. Readiness separa D0/seed de D1 e informa os recursos ausentes; não autoriza chamadas. Critérios e evidências: [medição/readiness](../../../eval/reports/m0-agent-readiness.md).

Limites restantes: adapter/modelos reais, quatro smokes pareados e orçamento; VM macOS indisponível. O namespace não é limite de CPU/RSS/disco nem defesa contra kernel vulnerável/escritor hostil do mesmo usuário. Os testes evitam fork bomb/OOM global e não tornam builds não materializados disponíveis. Supervisor não integra o runtime obrigatório do produto.
