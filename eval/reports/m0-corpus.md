# M0-03 — preparação do corpus de desenvolvimento

Data do projeto: 11/10/2026, America/Sao_Paulo. Implementador. Corpus preparado. **Adendo do Arquiteto:** [L1-C01 resolvida no ADR 021](../../docs/decisoes/CORPUS-QUALIFICADO.md); preparação inicial aceita, 32 propostas passam a D1-seed. M0-03.R1 qualifica o conjunto obrigatório para o piloto. Os achados e a solicitação histórica abaixo são preservados; não houve sessão de agente nem campanha paga.

## Entrega e evidências

| Critério | Evidência verificável | Resultado / limite |
|---|---|---|
| D0: 20 tarefas, cinco por família | `tasks/dev.jsonl`; `scripts/verify_corpus.py`; `../../docs/relatorios/logs/L1/corpus-verification.json` | 2 localização, 1 compreensão, 1 após edição, 1 configuração/limite por família; todos os 20 têm input, fontes, capacidades, falhas e oracle separado |
| D1: 32 propostas, oito por família, pelo menos dois repos | `tasks/challenge-dev.jsonl`; manifest e verificador | 2 correções, 2 contratos, 2 estado/config, 1 revisão, 1 controle por família; oito repos no total; TS mitt e JS ms são upstreams reais |
| Recuperação versus sucesso do agente | `recovery_criteria` / `agent_success_criteria`; 52 `oracles/*/oracle.json` | Recuperação exige bytes/revisão, fontes atuais novas, hashes pós-edição e ausência dos removidos. Sucesso julga fatos/comportamento final separadamente; não foi medido |
| Fontes e labels independentes | commits completos, hashes e byte spans no manifest/tasks; leitura de fonte upstream e patches | Labels manuais a partir de fonte, sem xrai/parser/grafo; segundo leitor independente revisou fontes/oracles e trouxe correções incorporadas, incluindo fonte de importação removida e Go sem versão declarada |
| Correções com regressão demonstrada | `scripts/verify_oracles.py`; `../../docs/relatorios/logs/L1/corpus-oracles.json` | Oito baselines falham nos asserts/tipos e passam após patch de referência. Quatro revisões passam antes e falham após diff proposto. 12/12 probes; isso não executa agente nem comprova suíte upstream inteira |
| Patches/respostas fora do input/ranking | materializador com allowlist; 52 inputs reconstruídos e inspecionados | Zero arquivos oracle/Git no input; referência fica em oracles. Revisão entrega diff natural proposto. Harness M0-04 deve impor isolamento de processo/FS e indexar só workspace materializado |
| Fixtures exigidas | `fixtures/manifest.json`; gerador determinístico | 78 arquivos: CRLF, Unicode, homônimos, sem símbolos, incompleto, grande função, JSX/TSX, config alterada, create/remove e mesma mtime/tamanho com bytes distintos; não contam como casos reais |
| Deduplicação/reconstrução | lineage por fix upstream ou requisito local; hash de patch; 20 archives determinísticos | IDs e linhagens D1 únicos, 12 patches distintos, todos os arquivos/hashes/spans conferidos; caso negativo com lineage duplicada é rejeitado |
| H1 separado | `../HOLDOUT-POLICY.md` | Política preparada, sem tarefas/soluções H1 em checkout; tamanho depende de dados futuros e pré-registro |

## Proveniência e reprodução

| Família | Upstreams oficiais | Licença nos snapshots |
|---|---|---|
| Rust | [strsim-rs](https://github.com/rapidfuzz/strsim-rs), [shell-words](https://github.com/tmiasko/shell-words) | MIT; MIT OR Apache-2.0 |
| TS/JS | [mitt](https://github.com/developit/mitt), [ms](https://github.com/vercel/ms) | MIT; MIT |
| Python | [cachetools](https://github.com/tkem/cachetools), [python-slugify](https://github.com/un33k/python-slugify) | MIT; MIT |
| Go | [uuid](https://github.com/google/uuid), [go-humanize](https://github.com/dustin/go-humanize) | BSD-3-Clause; MIT |

`sources/manifest.json` fixa commit completo de cada árvore, arquivo, tamanho e SHA-256, license files por snapshot e comandos de reconstrução. O baseline histórico mitt de D1-TJ-01 declara MIT em package.json/README, mas precede LICENSE: notice do commit oficial posterior é armazenado e materializado como suplemento identificado; não alteramos os bytes históricos como se esse arquivo existisse no commit.

São 20 snapshots, 1.546.610 bytes de arquivos upstream, 360.234 bytes de archives gzip. Fontes inteiras preservam licenças, documentação e testes existentes no baseline; correções futuras/reference nunca entram em histórico Git ou no pacote do agente. Clones externos são só origem para rebuild; rodar corpus/fixtures/materialização não precisa rede nem APIs de modelo. Requisitos de desenvolvimento para probes estão em `README.md`; `text-unidecode==1.3` foi instalado somente no diretório temporário do avaliador e não é distribuído no produto/corpus.

Comandos executados:

```sh
python3 eval/scripts/build_corpus.py /private/tmp/xrai-corpus-upstream
python3 eval/scripts/build_oracle_probes.py
python3 eval/scripts/generate_fixtures.py eval/fixtures
python3 eval/scripts/verify_corpus.py --output docs/relatorios/logs/L1/corpus-verification.json
python3 eval/scripts/verify_oracles.py --output docs/relatorios/logs/L1/corpus-oracles.json
python3 -m py_compile eval/scripts/*.py
git diff --check -- eval docs/relatorios/logs/L1/corpus-*.json
```

Ambiente em `../../docs/relatorios/logs/L1/corpus-environment.json`: macOS arm64, Python 3.15.0, Rust 1.98.1, Node 26.11.1, TypeScript 7.0.2, Go 1.27.2. Download de objetos Git não teve bytes de rede medidos; não atribuímos custo financeiro desconhecido. Custo de campanha: zero sessões de modelos. Não usar tamanhos/probes como resultados de latência ou superioridade xrai.

Codebase-memory Tier 2 retornou `not_tracked` para os seis scripts novos na geração 2026-10-12T01:26:56Z. Verificação foi por fonte direta, bytes, materializações e execução local; a ausência no grafo não foi usada como prova. Graft consultou materializador (957 tokens estimados poupados, uma consulta).

## Solicitação L1-C01 original — resolvida na revisão

D1 contém oito correções históricas públicas, oito requisitos novos locais de contrato sobre APIs upstream, quatro perguntas de configuração ativa mais quatro cenários de estado materializado, quatro revisões de regressão simulada pela reversão de fixes históricos distintos e quatro controles sobre fontes upstream. Não são 32 issues/PRs novos upstream. Nenhum patch foi duplicado para inflar independência; os casos compartilham repos e sua dependência deve ser considerada na análise.

Confirmar elegibilidade e representatividade desses requisitos locais/cenários de revisão/estado como “desafios reais” antes de selecionar finalistas ou estimar potência competitiva. Se for exigido que todos os desafios venham de pedidos/incidentes públicos, substituir os casos correspondentes mantendo estratos e registrar a nova versão; não converter 52 arquivos em confirmação de aceite competitivo. Não prepara soluções de holdout nem inicia campanha enquanto limites operacionais permanecerem indefinidos.
