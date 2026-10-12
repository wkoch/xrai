# Checagem exploratória: codebase-memory sobre tokensave

Data: 11/10/2026. Checagem pontual, sem benchmark de desempenho ou estimativa de precisão agregada.

- Ferramenta instalada: `codebase-memory-mcp 0.11.0`. SHA do build instalado não confirmado; não presumir identidade com o snapshot do código estudado.
- Repositório analisado: tokensave, commit `d3b99ecb5993e6ac26ac320f82c291f15f040a9c`.
- Modo: `fast`, sem enriquecimento semântico, nome do índice `xrai-study-tokensave`, `persistence=false`.
- Geração registrada: `2026-10-11T22:40:14Z`.
- Uso da skill instalada `codebase-memory`: inventário de projetos, indexação, schema, busca, trecho, trace e verificação de cobertura dos caminhos utilizados.

## Consulta e observação

Busca por `spawn|extract` no arquivo `extraction_worker.rs` encontrou `xrai-study-tokensave.src.extraction_worker.spawn_worker`, linhas 491–519. Fonte retornada por `get_code_snippet`, modo `full`, e conferida no snapshot.

O trecho contém:

```rust
let stdin = child.stdin.take(); // abreviado: original inclui tratamento de erro
let stdout = child.stdout.take();
// ...
let mut stdin = BufWriter::new(stdin);
stdin.write_all(token)?;
stdin.flush()?;
```

Este bloco é uma ilustração abreviada, não código copiado integralmente nem código compilável isolado. [Fonte completa fixada](https://github.com/aovestdipaperino/tokensave/blob/d3b99ecb5993e6ac26ac320f82c291f15f040a9c/src/extraction_worker.rs#L491-L519).

Trace efetuado:

```sh
codebase-memory-mcp cli trace_path \
  --project xrai-study-tokensave \
  --function-name xrai-study-tokensave.src.extraction_worker.spawn_worker \
  --direction outbound --depth 1 --limit 20 \
  --max-output-tokens 1500 --include-evidence true
```

A resposta listou cinco callees. Dois resultados relevantes para esta observação:

| Alvo apresentado | Estratégia | Valor de confiança informado |
|---|---|---|
| `xrai-study-tokensave.src.mcp.transport.McpTransport.flush` | `heuristic` | 0.28 |
| `xrai-study-tokensave.src.mcp.graph_scope.GraphSelector.take` | `heuristic` | 0.38 |

Os receptores do trecho são `BufWriter` e `Option`, respectivamente. Não há nesses callsites evidência para promovê-los a chamadas confirmadas daqueles símbolos do projeto. A ferramenta identifica a estratégia como heurística; o problema para o desenho do xrai é impedir que a apresentação ou o consumidor trate esses candidatos como fatos resolvidos.

## Cobertura verificada

Uma chamada válida de `check_index_coverage` recebeu os caminhos:

```json
{
  "project": "xrai-study-tokensave",
  "paths": [
    "src/extraction_worker.rs",
    "src/mcp/transport.rs",
    "src/extraction/mod.rs",
    "src/mcp/graph_scope.rs",
    "tests/extract_worker_test.rs"
  ],
  "diagnostics": "full"
}
```

Todos os cinco retornaram `no_recorded_issue`, `metadata_match` e `use_graph_with_best_effort_caveat`; nenhuma paginação restante. Metadados: `recording_status=complete`, `hash_records_complete=true`, `generation_matches=true`, `coverage_version=3`.

A própria resposta ressalva que não haver problema registrado não prova completude. Este resultado não certifica precisão semântica. A conclusão é limitada ao arquivo, consulta, modo e versão descritos; não avalia configurações `full`, LSP, outras linguagens ou versões posteriores.

## Consequência para o xrai

Manter cobertura de indexação, resolução semântica e evidência entregue como eixos separados. Preservar candidatos heurísticos para descoberta, com origem e motivo; consultas que prometem relações confirmadas não os promovem silenciosamente. Acrescentar uma fixture de métodos homônimos com receptores diferentes ao corpus Rust.
