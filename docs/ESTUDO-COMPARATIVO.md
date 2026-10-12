# Oito referências para o xrai: o que aproveitar e onde avançar

Pesquisa em 11/10/2026. Leitura de documentação, código e testes em snapshots locais, sem compilar os projetos ou reproduzir seus benchmarks. Também foi feita uma checagem estrutural pontual do tokensave com o codebase-memory instalado, descrita abaixo. Os benchmarks citados são declarações dos próprios projetos.

| Projeto | Snapshot inspecionado | Versão no manifesto |
|---|---|---|
| Graft, trailhq | [`fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad`](https://github.com/trailhq/Graft/tree/fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad) | 0.21.1 |
| trace-mcp, nikolai-vysotskyi | [`d2d7b6fd63dde946a4d593004097f3f6f13e1410`](https://github.com/nikolai-vysotskyi/trace-mcp/tree/d2d7b6fd63dde946a4d593004097f3f6f13e1410) | 3.36.4 |
| codebase-memory-mcp, DeusData | [`475db1edf22b37d56d51a5d12df144dc6e8eef62`](https://github.com/DeusData/codebase-memory-mcp/tree/475db1edf22b37d56d51a5d12df144dc6e8eef62) | 0.11.0 em `server.json` |
| code-review-graph, tirth8205 | [`6b12d11625cbec3b6773e076cb3d136464fa90e5`](https://github.com/tirth8205/code-review-graph/tree/6b12d11625cbec3b6773e076cb3d136464fa90e5) | 2.3.9; branch padrão `staging` |
| jCodeMunch, jgravelle/jcodemunch-mcp | [`97bbd18284cdc1f0fdf9f34a378abc0a65d5542d`](https://github.com/jgravelle/jcodemunch-mcp/tree/97bbd18284cdc1f0fdf9f34a378abc0a65d5542d) | 1.108.342 |
| tokensave, aovestdipaperino | [`d3b99ecb5993e6ac26ac320f82c291f15f040a9c`](https://github.com/aovestdipaperino/tokensave/tree/d3b99ecb5993e6ac26ac320f82c291f15f040a9c) | 7.15.0 |
| ProjectAtlas, styler-ai | [`e41e72af1acdbef9cfb29184a855d3a859b8c82a`](https://github.com/styler-ai/ProjectAtlas/tree/e41e72af1acdbef9cfb29184a855d3a859b8c82a) | workspace 0.5.0-rc3; README anuncia release 0.4.5 |
| codegraph-mcp, websines | [`5e2b37cc58c3d0b0bf7f21edae0fd97519eef6b2`](https://github.com/websines/codegraph-mcp/tree/5e2b37cc58c3d0b0bf7f21edae0fd97519eef6b2) | pacote `codegraph` 0.1.0 |

Os links com SHA fixam a evidência. Páginas públicas sem SHA podem mudar.

**Conclusão revista:** Rust, execução local, grafo, leitura por símbolo e contexto com orçamento já aparecem nessa categoria. São requisitos competitivos. O diferencial a conquistar é resolver tarefas difíceis com evidência suficiente, poucas rodadas, estado consistente e profundidade semântica demonstrada nas quatro famílias escolhidas.

## 1. Comparação útil para o xrai

| Dimensão | Graft | trace-mcp | Direção proposta para xrai |
|---|---|---|---|
| Orientação | Grafo conceitual legível em Markdown; grafo estrutural separado | Consultas especializadas sobre índice estruturado | Mapa pequeno por tarefa; Markdown como projeção |
| Estrutura | Tree-sitter, resolução estática e LSP opcional | Extração por plugins, resolução, LSP e SCIP opcionais | Sintaxe ampla no escopo inicial; semântica com cobertura publicada |
| Frameworks | Ênfase no mapa de código e conceitos | Relações de rotas, ORM, UI e contratos | Relações entre linguagens mediadas por contratos verificáveis |
| Recuperação | Léxico, sinais de grafo e agrupamento por arquivo | FTS5, grafo, recuperação híbrida e montagem por orçamento | Seleção conjunta de evidências, granularidade e próximos passos |
| Atualização | Verificação antes da consulta; cache de extração | Indexação incremental, watchers e atualização após edição | Revisão explícita, atualização dependente de configuração e fontes coerentes |
| Integração | Arquivos, CLI, MCP e hooks | CLI, MCP, presets e ferramentas carregadas sob demanda | CLI e pequena superfície MCP; mesma semântica |
| Distribuição | Node e dependências nativas/WASM | Node e dependências nativas/WASM | Binário autônomo por alvo |

Base: [Graft README](https://github.com/trailhq/Graft/blob/fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad/README.md), [arquitetura do trace-mcp](https://trace-mcp.com/architecture.html), [manifesto Graft](https://github.com/trailhq/Graft/blob/fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad/package.json), [manifesto trace-mcp](https://github.com/nikolai-vysotskyi/trace-mcp/blob/d2d7b6fd63dde946a4d593004097f3f6f13e1410/package.json).

## 2. Graft: achados no código

**Dois níveis de conhecimento.** O schema distingue estrutura determinística e significado produzido por modelo. Símbolos têm localização, assinatura e hash; resumos podem estar pendentes, prontos ou desatualizados. Arestas distinguem extração, inferência e resolução LSP, inclusive candidatos de despacho virtual. Portanto, proveniência e atualização de resumos já fazem parte do concorrente. [Schema](https://github.com/trailhq/Graft/blob/fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad/src/graph/types.ts).

**Atualização faz parte da consulta.** `ensureFreshGraph` verifica alterações antes de responder, compartilha lock com o sincronizador e pode reutilizar o índice de outro worktree. Na falha, admite responder com o grafo existente e uma nota. O probe usa tamanho/mtime como atalho; existe modo de hash completo. A medição de poucos milissegundos refere-se a centenas de arquivos, não prova custo constante em monorepos. [Refresh](https://github.com/trailhq/Graft/blob/fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad/src/graph/refresh.ts), [fingerprint](https://github.com/trailhq/Graft/blob/fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad/src/graph/fingerprint.ts).

**Busca usa estrutura.** O ranking inclui PageRank personalizado a partir de sementes lexicais. A saída com código limita spans a 80 linhas e indica truncamento. Isso oferece um ponto concreto de comparação para seleção por trechos relevantes e cobertura, sem supor que vetores sejam obrigatórios. [Graph rank](https://github.com/trailhq/Graft/blob/fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad/src/ask/graphrank.ts), [recuperação e spans](https://github.com/trailhq/Graft/blob/fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad/src/ask/ask.ts).

**Um teste revela um risco importante.** O projeto protege contra resolver o builtin Go `make` para uma função TypeScript de mesmo nome. O caso está corrigido no snapshot; serve como regressão de referência, não como alegação de defeito atual. O xrai deve usar identidade de linguagem, pacote, escopo e contrato, preservando candidatos desconhecidos. [Teste entre linguagens](https://github.com/trailhq/Graft/blob/fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad/test/graph-cross-language.test.ts).

Aproveitar: mapas em vários níveis, resumos associados às fontes, atualização na consulta, integração simples e leitura progressiva. Avançar: contratos de consistência, cobertura e orçamento sobre a resposta inteira; recortes orientados pela mudança; resolução profunda para as linguagens prioritárias.

## 3. trace-mcp: achados no código

**A amplitude é real, a profundidade varia.** A matriz publicada lista 81 plugins: 29 Tree-sitter, 46 regex e 6 parsers próprios. Lista 22 com resolução de imports, 3 com chamadas e 2 com relações de tipos. Rust e Go têm extração/imports; a coluna de chamadas depende de enriquecimento adicional. Isso não significa ausência de todas as relações de frameworks nessas linguagens. A própria documentação distingue presença de um resolver de cobertura completa. [Matriz de capacidades](https://trace-mcp.com/language-matrix.html).

**SCIP e LSP já existem.** O importador SCIP mapeia ocorrências para símbolos, promove arestas existentes e acrescenta referências resolvidas. O schema possui tiers e valores numéricos associados; eles são convenções de confiança da implementação, não probabilidades demonstradas de correção. No xrai, origem da evidência e probabilidade calibrada seriam campos distintos. [Importação SCIP](https://github.com/nikolai-vysotskyi/trace-mcp/blob/d2d7b6fd63dde946a4d593004097f3f6f13e1410/src/scip/ingest.ts), [schema](https://github.com/nikolai-vysotskyi/trace-mcp/blob/d2d7b6fd63dde946a4d593004097f3f6f13e1410/src/db/schema.ts).

**Contexto por tarefa já existe.** `get_task_context` usa intenção, dependências, callers, tipos e testes. O montador divide o orçamento por categorias e degrada de código completo para assinatura. Há marcadores de corpo omitido e tratamento de duplicação entre contêineres e membros. Oportunidade: otimização conjunta, recebendo diff/stack trace e requisitos de evidência antes de repartir tokens. [Task context](https://github.com/nikolai-vysotskyi/trace-mcp/blob/d2d7b6fd63dde946a4d593004097f3f6f13e1410/src/tools/navigation/task-context.ts), [assembly](https://github.com/nikolai-vysotskyi/trace-mcp/blob/d2d7b6fd63dde946a4d593004097f3f6f13e1410/src/scoring/assembly.ts), [structured assembly](https://github.com/nikolai-vysotskyi/trace-mcp/blob/d2d7b6fd63dde946a4d593004097f3f6f13e1410/src/scoring/structured-assembly.ts).

**Memória e redução da superfície já existem.** Há journal de sessão, deduplicação, checkpoints e presets com carregamento progressivo. Seria incorreto tratar deduplicação ou poucas ferramentas iniciais como novidade exclusiva do xrai, ou supor que todas as ferramentas do trace-mcp sempre entram no contexto. [Journal](https://github.com/nikolai-vysotskyi/trace-mcp/blob/d2d7b6fd63dde946a4d593004097f3f6f13e1410/src/session/journal.ts), [teste de orçamento dos presets](https://github.com/nikolai-vysotskyi/trace-mcp/blob/d2d7b6fd63dde946a4d593004097f3f6f13e1410/src/tools/register/__tests__/preset-surface-budget.test.ts).

Aproveitar: SQLite/FTS5, plugins de frameworks, consultas compostas, ingestão de semântica externa e avaliação explícita das perdas. Avançar: simplificação da distribuição e garantias comuns a todos os caminhos de recuperação.

## 4. Benchmarks: evidência e limites

Graft publica dois experimentos distintos: um conjunto de perguntas com 42% menos tokens e acerto equivalente; outro com 50 instâncias SWE-bench Verified, 27 resolvidas na base e 33 com Graft. Os números não demonstram o mesmo ganho em toda linguagem ou tamanho de repositório. Não foram reproduzidos nesta pesquisa. [Benchmark publicado](https://github.com/trailhq/Graft/blob/fe30ead39d5e6f0c921018d364da2bdbc9d4b3ad/README.md#benchmark).

trace-mcp publica, para **3.23.2 em 07/09/2026**, mediana de 72,7% menos tokens de entrada em 60 PRs de 6 repositórios. A mediana de símbolos alterados com corpo disponível foi 71%, contra 100% na leitura dos arquivos. A avaliação de compreensão registrou 67% contra 65%; falsos positivos por PR, 0,80 contra 0,58. A amostra não autoriza alegar superioridade geral. O estudo é histórico, não uma medição da versão 3.36.4 inspecionada. [Relatório](https://trace-mcp.com/pr-context-benchmark.html), [dados de qualidade](https://github.com/nikolai-vysotskyi/trace-mcp/blob/d2d7b6fd63dde946a4d593004097f3f6f13e1410/docs/_data/pr_context_quality.json).

O pós-mortem identifica pressão de orçamento e duplicação entre contêineres e símbolos. Ele separa localizar um símbolo de entregar seu corpo e reconhece que recuperar mais corpos não demonstrou, por si, melhoria de compreensão. [Análise das perdas](https://github.com/nikolai-vysotskyi/trace-mcp/blob/d2d7b6fd63dde946a4d593004097f3f6f13e1410/docs/perf/pr-context-loss-classes.md).

Decisão para o xrai: medir custo, acerto e evidência entregue separadamente. Comparar também contra um agente competente com busca textual e leituras seletivas. “Ler todos os arquivos” é apenas uma das bases.

## 5. Hipóteses de diferenciação

As propostas abaixo são hipóteses de produto e engenharia, não alegações de invenção inédita:

1. **Pacote de contexto com contrato verificável:** revisão, fontes, evidências obrigatórias, omissões e limites de análise na mesma resposta.
2. **Seleção que conhece a alteração:** diff, diagnóstico e stack trace determinam o menor trecho útil, incluindo configuração e testes quando necessários.
3. **Expansão orientada por incerteza:** a próxima consulta tenta resolver uma dúvida específica; priorização começa determinística e ganha aprendizagem somente se houver benefício medido.
4. **Consistência durante edição:** uma resposta não mistura relações antigas com bytes novos; múltiplos worktrees e clientes mantêm identidades distintas.
5. **Distribuição autônoma:** valor útil no primeiro uso, offline, com as quatro famílias de linguagens. Enriquecedores externos são opcionais e identificados.

## 6. Referências adjacentes

- [Tree-sitter](https://tree-sitter.github.io/tree-sitter/): parser incremental incorporável, com recuperação de erros. Resolve a base sintática; a semântica requer outra camada.
- [SCIP](https://github.com/scip-code/scip): protocolo de ocorrências, definições e relações para interoperar com indexadores existentes.
- [rust-analyzer](https://rust-analyzer.github.io/book/contributing/architecture.html): inspiração para separar entradas, modelo semântico e infraestrutura; Rust depende também de estrutura de crates e configuração.
- [Stack graphs](https://github.com/github/stack-graphs): referência para resolução incremental de nomes. O repositório foi arquivado em 09/09/2025; adoção direta exigiria assumir manutenção. Não equivale a um sistema universal de tipos.
- [Aider repomap](https://github.com/Aider-AI/aider/blob/main/aider/repomap.py): referência adicional para seleção de mapa dentro de orçamento.

Nenhuma dessas referências elimina a necessidade de avaliar precisão por linguagem e por tarefa.

## 7. Os seis projetos acrescentados

### 7.1 codebase-memory-mcp: cobertura e seleção de testes

O snapshot atual usa C e descreve indexação paralela, grafo persistente, resolução híbrida e coordenação de processos. O README informa distribuição com executável nativo **e assets de runtime verificados**; não usar o slogan de binário estático como prova de instalação composta por um único arquivo. A coordenação entre sessões trata admissão por versão/build e propriedade de trabalho compartilhado. É referência para limites de memória e concorrência; copiar um daemon global e seu protocolo de atualização não é necessário ao início do xrai. [README fixado](https://github.com/DeusData/codebase-memory-mcp/blob/475db1edf22b37d56d51a5d12df144dc6e8eef62/README.md).

O código de seleção de testes combina alcance estático e cobertura por teste. Seu princípio é relevante: apenas evidência admitida e completa pode justificar omissão. Diff ou inventário incompleto provoca seleção conservadora. Isso vai além de listar funções conectadas: produz uma decisão acompanhada de motivos. [Seletor](https://github.com/DeusData/codebase-memory-mcp/blob/475db1edf22b37d56d51a5d12df144dc6e8eef62/src/mcp/test_impact_select.c), [validação dos recibos](https://github.com/DeusData/codebase-memory-mcp/blob/475db1edf22b37d56d51a5d12df144dc6e8eef62/src/mcp/test_impact_result_receipt.c).

**Para o xrai:** inventário de cobertura consultável; testes recomendados com caminho de evidência, configuração e revisão; fallback explícito para suíte mais ampla. Cobertura dinâmica observada não garante ausência de dependência em execuções futuras. Recomendar testes e autorizar omitir todos os outros são afirmações diferentes.

**Checagem local limitada:** o executável instalado 0.11.0, em modo `fast`, indexou o snapshot do tokensave. Para `spawn_worker`, retornou entre os callees `McpTransport.flush` e `GraphSelector.take`, ambos marcados como heurísticos. O trecho inspecionado usa `BufWriter::flush` e `Option::take`. A verificação dos cinco arquivos relevantes informou `no_recorded_issue`, `metadata_match` e ressalva de melhor esforço. Isso mostra a diferença entre cobertura registrada e acerto semântico nesse caso; não mede precisão agregada nem o modo completo/LSP. [Registro reproduzível da checagem](evidencias/CBM-TOKENSAVE-FAST.md).

### 7.2 code-review-graph: mudanças e incerteza útil

O projeto Python reúne índice SQLite, atualização incremental, impacto, fluxos, comunidades e contexto para revisão. Há implementação de snapshots que compara nós, arestas e comunidades antes/depois; isso inspira preservar o lado anterior da mudança, inclusive quando um símbolo desaparece. [Arquitetura](https://github.com/tirth8205/code-review-graph/blob/6b12d11625cbec3b6773e076cb3d136464fa90e5/docs/architecture.md), [graph diff](https://github.com/tirth8205/code-review-graph/blob/6b12d11625cbec3b6773e076cb3d136464fa90e5/code_review_graph/graph_diff.py).

Um detalhe especialmente útil é `uncertainty.py`: resultados vazios recebem uma nota curta quando o tipo de consulta e a linguagem têm uma limitação conhecida. A tabela distingue, por exemplo, callbacks registrados como referências de chamadas resolvidas. O xrai deve manter essa distinção também em resultados não vazios: encontrar dois usos não prova que não exista um terceiro. [Marcadores de incerteza](https://github.com/tirth8205/code-review-graph/blob/6b12d11625cbec3b6773e076cb3d136464fa90e5/code_review_graph/uncertainty.py).

**Para o xrai:** comparar grafos `base` e `head`, buscar consumidores anteriores de símbolos removidos e entregar caminhos que expliquem o impacto. Comunidades e criticidade podem ajudar o ranking; não comprovam fronteiras de negócio ou segurança de um patch.

### 7.3 jCodeMunch: fonte exata e orçamento ao longo da exploração

A arquitetura prioriza inventário, outlines, símbolos e leitura de trechos a partir de bytes armazenados e posições de fonte. Isso sustenta navegação progressiva sem reconstruir código por resumo. O xrai já propunha esse modelo; ele passa a ser uma referência concreta de implementação e avaliação. [Arquitetura](https://github.com/jgravelle/jcodemunch-mcp/blob/97bbd18284cdc1f0fdf9f34a378abc0a65d5542d/ARCHITECTURE.md), [leitura de símbolo](https://github.com/jgravelle/jcodemunch-mcp/blob/97bbd18284cdc1f0fdf9f34a378abc0a65d5542d/src/jcodemunch_mcp/tools/get_symbol.py).

`TurnBudget` acumula custo entre chamadas, mas usa singleton por processo e intervalo de inatividade como aproximação de turno. O próprio código documenta que chamadas contínuas transformam isso num orçamento de exploração, compartilhado pelos repositórios daquele processo. A ideia é útil; para xrai, preferir IDs explícitos de sessão/tarefa e reservas para chamadas concorrentes. Tempo decorrido não confirma nova conversa nem compactação. [Contabilidade por turno](https://github.com/jgravelle/jcodemunch-mcp/blob/97bbd18284cdc1f0fdf9f34a378abc0a65d5542d/src/jcodemunch_mcp/tools/turn_budget.py).

**Para o xrai:** fonte por hash e offsets, geração do parser na chave do cache, fallback textual quando a capacidade semântica do arquivo não existe e orçamento agregado opcional. O manifesto usa licença própria `LicenseRef-jCodeMunch-Dual-Use-1`; não classificá-lo como MIT ao planejar reaproveitamento de código. [Manifesto](https://github.com/jgravelle/jcodemunch-mcp/blob/97bbd18284cdc1f0fdf9f34a378abc0a65d5542d/pyproject.toml).

### 7.4 tokensave: Rust e contenção de falhas nativas

É uma referência diretamente próxima: Rust, Tree-sitter, banco incorporado e ferramentas de contexto/impacto. O achado que mais muda a arquitetura é `extraction_worker.rs`: gramáticas C/C++ podem abortar ou provocar falha nativa que `catch_unwind` não captura. A extração usa subprocessos do próprio executável; a função `spawn_worker` inicia o caminho recebido com um subcomando interno e pipes. [Manifesto](https://github.com/aovestdipaperino/tokensave/blob/d3b99ecb5993e6ac26ac320f82c291f15f040a9c/Cargo.toml), [workers de extração](https://github.com/aovestdipaperino/tokensave/blob/d3b99ecb5993e6ac26ac320f82c291f15f040a9c/src/extraction_worker.rs).

**Para o xrai:** manter um único executável distribuído, mas executar parsing nativo em pool limitado de processos desse executável. O pai fornece bytes imutáveis identificados por hash; recebe fatos e diagnósticos. Falha ou timeout afeta o arquivo, produz lacuna e tem retry limitado. Não publicar fatos antigos como atuais nem reiniciar indefinidamente um arquivo que derruba o worker. Isolamento de falha não equivale a sandbox de segurança.

Perfis de gramáticas e amplitude de ferramentas são escolhas secundárias. O primeiro release pode incorporar somente as quatro famílias prioritárias, mantendo boa cobertura e uma superfície pequena. [README](https://github.com/aovestdipaperino/tokensave/blob/d3b99ecb5993e6ac26ac320f82c291f15f040a9c/README.md).

### 7.5 ProjectAtlas: propósito, estrutura e worktrees

O projeto distingue `folder_purpose`, `file_purpose` e `content_summary`. Propósito registra intenção atribuída/aprovada; resumo estrutural descreve o que o analisador observa. Adapters cobrem também manifests, Markdown e configuração. Essa distinção ajuda o agente a escolher a área responsável antes de abrir símbolos, sem apresentar interpretação de intenção como fato sintático. [Resumos estruturais](https://github.com/styler-ai/ProjectAtlas/blob/e41e72af1acdbef9cfb29184a855d3a859b8c82a/docs/structural-summaries.md).

Worktrees têm bancos graváveis independentes. Uma base compatível pode hidratar outro checkout, mas a ativação vem depois de reconciliar seu branch e arquivos modificados. O código de snapshots derivados inclui identidade de fontes e fingerprint de capacidades. Esses são mecanismos existentes, não novidades a reivindicar. [Ciclo de worktrees](https://github.com/styler-ai/ProjectAtlas/blob/e41e72af1acdbef9cfb29184a855d3a859b8c82a/docs/worktree-lifecycle.md), [snapshot derivado](https://github.com/styler-ai/ProjectAtlas/blob/e41e72af1acdbef9cfb29184a855d3a859b8c82a/crates/projectatlas-db/src/derived_snapshot.rs).

**Para o xrai:** navegação `propósito → área → contrato/símbolo → fonte`, com bypass direto para nomes conhecidos. Registrar autor, tipo de aprovação e validade do propósito. Reusar apenas estado derivado compatível entre worktrees; manter identidade, resolução e estado editável locais. Metadados humanos não devem desaparecer ao reconstruir o índice.

### 7.6 codegraph-mcp: aprender com tentativas e medir sessões

O projeto Rust separa grafo de código, estado de sessão e aprendizado. Modela tentativas relacionadas, resultados de sucesso/falha/parcial e padrões com escopo. Isso oferece uma direção útil para não repetir investigações fracassadas. [Tentativas e linhagem](https://github.com/websines/codegraph-mcp/blob/5e2b37cc58c3d0b0bf7f21edae0fd97519eef6b2/src/learning/lineage.rs), [README](https://github.com/websines/codegraph-mcp/blob/5e2b37cc58c3d0b0bf7f21edae0fd97519eef6b2/README.md).

A função de confiança combina taxa de sucesso, tempo, validação, drift e frequência de uso. É uma heurística, não probabilidade calibrada. No xrai, repetir ou recuperar uma nota não comprova sua correção. Experiência deve guardar observação, resultado e fonte de validação; afirmações do agente continuam atribuídas ao agente. [Confiança](https://github.com/websines/codegraph-mcp/blob/5e2b37cc58c3d0b0bf7f21edae0fd97519eef6b2/src/learning/confidence.rs).

O benchmark publicado é instrutivo pelo comportamento da sessão: numa investigação em um projeto predominantemente Python, a configuração compacta relata 23% menos tokens que a base; uma configuração de uso inadequado relata 64% mais. Isso não foi reproduzido e não cobre Rust, TS/JS ou Go. Mostra por que descrições de ferramentas, escolhas e follow-ups entram na avaliação. [Método e resultados publicados](https://github.com/websines/codegraph-mcp/blob/5e2b37cc58c3d0b0bf7f21edae0fd97519eef6b2/BENCHMARK.md).

**Para o xrai:** memória de investigação opcional numa fase posterior, com escopo, revisão, testes ou recibos de execução importados e invalidação. Separar experiência de fatos sobre o programa. Exportar uma nota para um agente não a transforma automaticamente em instrução confiável.

## 8. Mudanças de prioridade após a pesquisa ampliada

| Prioridade | Decisão para o xrai | Inspiração principal |
|---|---|---|
| Núcleo | Fonte exata, capacidades e evidência por afirmação | jCodeMunch, Graft, trace-mcp, codebase-memory |
| Núcleo | Parsing em processos do mesmo executável | tokensave |
| Navegação | Propósito atribuído separado de resumo determinístico | ProjectAtlas |
| Revisão | Grafos antes/depois e impacto com caminho de evidência | code-review-graph |
| Validação | Recomendar testes com motivos e fallback conservador | codebase-memory, code-review-graph |
| Uso contínuo | Orçamento explícito por tarefa; medir sessão inteira | jCodeMunch, codegraph-mcp |
| Escala | Cache derivado compatível e estado independente por worktree | ProjectAtlas, Graft, tokensave |
| Posterior | Memória de hipóteses, tentativas e resultados atribuídos | codegraph-mcp, trace-mcp |

Evitar acumular todas as funcionalidades como requisito do MVP. O ciclo central continua `index → search → inspect → context`, agora com isolamento de parser e cobertura explícita. Propósito, diff semântico e seleção de testes entram nos marcos seguintes. Memória aprendida, daemon global, vetores e frontends próprios precisam justificar custo por experimento.

Não adotar percentuais de economia dos READMEs como ranking. Diminuição de bytes, tokens estimados, fonte entregue, usage faturado e sucesso de tarefa são medidas diferentes. Formatos compactos devem ser comparados com JSON compacto e texto estruturado usando os tokenizers e agentes alvo, incluindo erros de interpretação e chamadas extras.
