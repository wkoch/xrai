# Harness local M0-04

Executor de desenvolvimento em Python std, fora do runtime da CLI. Requer Seatbelt (`sandbox-exec`) no macOS ou bubblewrap no Linux; recusa fallback sem sandbox. `verify_records.py` usa jsonschema fixado em `docs/contracts/examples/requirements.txt`.

```sh
python3 -m unittest discover -s crates/xrai-eval/harness/tests -v
python3 crates/xrai-eval/harness/runner.py baseline --output /tmp/xrai-baseline
python3 crates/xrai-eval/harness/verify_records.py /tmp/xrai-baseline
python3 crates/xrai-eval/harness/runner.py replay /tmp/xrai-baseline/D0-RS-01.json
cargo build --locked -p xrai-eval --bin incremental-probe
python3 crates/xrai-eval/harness/incremental.py --binary target/debug/incremental-probe --output /tmp/xrai-incremental.json
```

O pai materializa cada checkout por allowlist. Processos recebem somente aquele workspace e ferramentas/libraries do SO, ambiente novo e rede negada. Os testes têm controles positivos de leitura/edição e negativos de leitura/escrita entre braços, acesso ao avaliador, symlink e conexão a um listener real. No Linux, namespace de rede é separado e o avaliador não está montado; no macOS, Seatbelt nega acesso ao conteúdo fora da allowlist. Metadados de filesystem e listagem do diretório `/` são permitidos para carregar ferramentas do SO. Isso não autoriza leitura dos filhos do diretório raiz.

`execute()` permite configurar comando absoluto, timeout, limite total de captura e fase. Cada rodada preserva stdout/stderr binários como base64, SHA-256, bytes capturados/observados, truncamento, status, exit code e tempo. Registros usam `scripted_retrieval`; a baseline escolhe palavras somente do prompt público, lista arquivos e lê até três ocorrências com três linhas de contexto. Ausência de resultado ou erro permanecem no registro. Nenhum oracle/anchor privado escolhe o trecho. `result.schema.json` reserva `human` e `agent_run` para adapters futuros; o executor entregue não roda agentes/modelos reais.

Replay verifica bytes, hashes e contagens capturadas. Modelo, tokenizer, usage e custo financeiro são `null` porque não foram observados. Bytes não são apresentados como tokens de modelo. O replay do mesmo registro é determinístico; nova execução pode ter tempos, PIDs e ambiente diferentes. Edição/testes podem usar fases próprias em `execute()`, mas a baseline D0 entregue é de recuperação seletiva sem solução julgada.

`incremental-probe` conserva o inventário em memória no mesmo processo. A sequência é INDEX A → QUERY A → evento B do avaliador → QUERY ainda A → UPDATE → QUERY B → rebuild B em processo novo, comparado também com materialização fria e hashes SHA-256 do avaliador. Recibos identificam `hash_inventory_probe`: não é índice semântico, prova de retrieval nem sucesso de agente. Em cada família há uma demonstração usando D0, sem promover seed a corpus competitivo.

Limites ainda abertos do cartão: tokenizer/adapters/modelos reais, quatro smokes pareados com recursos/teto definidos, custo completo e auditoria das sessões reais. A prova de supervisor resistente a descendentes que mudam sessão/process group no macOS está pendente: o executor encerra o dreno e retorna dentro do deadline, mas `killpg` não assegura matar esses descendentes. O teste usa um descendente finito de dois segundos; não promete eliminar processo adversarial daemonizado. Registrado como L2-H01 em `docs/relatorios/L2.md`, antes de agentes reais. No Linux a morte do wrapper encerra o namespace PID de bubblewrap.
