# Concorrência do xrai e avaliação da arquitetura híbrida

Data de consulta: **16/10/2026**. Responsável: Arquiteto, com duas pesquisas paralelas. Entrega documental; nenhum concorrente foi instalado ou executado, nenhuma campanha paga iniciada e nenhum código do produto alterado. Checkout inicial limpo em `16e475b`. A implementação continua pausada.

## 1. Conclusão para decisão

O xrai disputa **qualidade do contexto usado pelo agente para resolver uma tarefa**. Grafo, MCP, Tree-sitter, indexação incremental, orçamento de tokens e execução local já são encontrados na categoria. Combinar Tree-sitter, SCIP e LSP é uma arquitetura plausível, mas não uma exclusividade: trace-mcp documenta esses três mecanismos; Graft documenta LSP opcional; agentmap de Raymond Chins documenta aprofundamento semântico sob demanda.

Recomendação: protótipo isolado no repositório atual, aproveitando experimentos compatíveis, seguido de comparação com alternativas fortes. Não financiar uma reimplementação extensa de analisadores apenas para reproduzir capacidades existentes. Bibliotecas próprias continuam admissíveis quando uma lacuna medida justificar o trabalho.

Hipótese de valor a testar: **o agente recebe fontes e fatos suficientes, coerentes com a revisão e configuração corretas, consegue aprofundar quando necessário e conclui mais tarefas corretamente**. Isso ainda é hipótese do xrai, não resultado demonstrado nem alegação de ausência nos concorrentes. Qualidade permanece primária e economia secundária, conforme a [prova de diferenciação](../PROVA-DE-DIFERENCIACAO.md).

## 2. Método e limites

- Base: páginas oficiais, READMEs e documentação pública. “Documentado” não significa “reproduzido”, “entregue na release estável” nem “correto para toda construção de uma linguagem”.
- Links para branches e sites são mutáveis. Este levantamento não congela commits externos; COMP-01 abaixo fará isso antes de execução. Não substituir os snapshots históricos do [estudo de 11/10](../ESTUDO-COMPARATIVO.md).
- Ausência de confirmação é registrada como desconhecida; não vira uma ausência de capacidade demonstrada.
- Números de marketing, quantidade de linguagens, estrelas e economias estimadas não foram usados como ranking de qualidade. Não reproduzimos benchmarks dos autores.
- A [comparação da Selvedge](https://selvedge.sh/compare/codebase-memory-mcp-servers/) é produzida pelo próprio fornecedor e declara ser documental. Foi usada para descoberta; os projetos adicionais foram consultados nas suas fontes primárias. Categorias se sobrepõem.
- Cobertura do pedido: onze nomes originais, ambos os agentmap relevantes, Aider como candidato para “Aided”, os seis projetos da tabela Selvedge e Selvedge; codebase-memory está deduplicado. trace-mcp foi acrescentado por relevância direta e por já constar no histórico do xrai.

## 3. Identidades que precisam ser preservadas

| Nome recebido | Identidade utilizada | Observação |
|---|---|---|
| trailhq/graft | trailhq/Trail-Code; URLs históricas Graft | README atual anuncia **Graft → Trail-code**. Isso não atualiza automaticamente a ferramenta instalada no xrai. |
| codebase memory mcp | DeusData/codebase-memory-mcp | Não confundir com servidores genéricos de memória. |
| graphifyy | pacote PyPI graphifyy, Graphify-Labs/graphify | Pacote e projeto usam nomes diferentes; não usar um fork homônimo como upstream. |
| Code-Review-Graph | tirth8205/code-review-graph | Preservar owner e revisão, inclusive diferenças entre branches. |
| Pharaoh | Pharaoh-so/pharaoh-mcp e pharaoh-parser | Componentes públicos não representam necessariamente todo o serviço. |
| Harmony MCP | CodeConductor Harmony | Não confundir com projetos Harmony de outros domínios. |
| Aided, antigo Aider repo-map | Aider Repository map, provisoriamente | **Renomeação não confirmada.** Link solicitado ao usuário; não afirmar que Aided não existe. |
| agentmap | raymondchins/agentmap e remorses/agentmap | Produtos diferentes, analisados separadamente. Link solicitado ao usuário. |
| codegraph-mcp | websines/codegraph-mcp | É o projeto do estudo anterior. Não agregar capacidades de homônimos. |

## 4. Concorrentes diretos e substitutos

### Graft / Trail-code

TypeScript/Node, CLI/MCP, extração Tree-sitter e mapa local consultável, com atualização durante consultas. O README atual acrescenta memória de aprendizados e mantém comandos antigos. TS/JS, Go e Python possuem extratores específicos; Rust aparece no nível genérico. LSP opcional escolhe um servidor por build, com resultado best-effort; resumos por modelo são opcionais. Licença MIT declarada. **Relevância:** experiência de navegação e integração cotidiana com agentes. **Verificar:** relações difíceis, falhas de atualização e comportamento em repositório com várias linguagens; não supor que toda aresta tenha origem em LSP. [README oficial atual](https://raw.githubusercontent.com/trailhq/Graft/main/README.md).

### codebase-memory-mcp

Backend nativo C, Tree-sitter, SQLite/FTS5, grafo persistente, MCP/CLI, consultas estruturais, impacto e cobertura. Documenta resolução para Rust, Go, JS/TS e Python. “Hybrid LSP” designa resolução própria inspirada em analisadores, **não o lançamento de servidores LSP externos**. Watcher tem escopo de sessão/configuração. MIT declarada. **Relevância:** concorrente central à instalação simples e ao índice local persistente. **Verificar:** precisão por construção, invalidação entre arquivos/configurações e lacunas detectadas. O README distingue capacidades em `main` de funcionalidades ainda ausentes na release mencionada. [Fonte oficial](https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/README.md).

### Graphify / graphifyy

Python, CLI/skill e MCP opcional; combina extração estrutural de código com relações conceituais de documentação/mídia produzidas por modelo configurado. Documenta grafo persistido e atualização incremental. As linguagens prioritárias aparecem na extração, mas isso não prova resolução semântica completa. **Relevância:** relacionar código e documentação. **Verificar:** separação entre extração e inferência, custos de modelos e validade das relações após edições. Identidade confirmada pelo [PyPI](https://pypi.org/project/graphifyy/); [projeto oficial](https://github.com/Graphify-Labs/graphify), [entradas suportadas](https://docs.graphify.com/concepts/supported-inputs). A licença atual documentada é Apache-2.0, preservando contribuições MIT anteriores no [NOTICE](https://github.com/Graphify-Labs/graphify/blob/v8/NOTICE).

### Code Review Graph

Python, Tree-sitter, SQLite, MCP/CLI e integrações de revisão. Documenta extração para Rust/Go/JS/TS/Python, atualização incremental, watch e contexto orientado ao diff. **Relevância:** selecionar símbolos afetados, dependências e testes para revisão de mudanças. Resolução de frameworks não equivale à profundidade uniforme de linguagem. SCIP/LSP não foram confirmados nesta leitura. MIT declarada. **Verificar:** omissões no impacto e se a seleção de testes conserva os consumidores necessários. A lista de frameworks do concorrente não autoriza ampliar o escopo do xrai. [Fonte oficial](https://raw.githubusercontent.com/tirth8205/code-review-graph/main/README.md).

### Pharaoh

Serviço de inteligência arquitetural; MCP público funciona como proxy Node para endpoint remoto, com autenticação. Parser público TypeScript/web-tree-sitter extrai metadados, assinaturas e docstrings; a saída omite corpos. Atualização por push/webhook é documentada. TS/TSX e Python confirmados no parser; a apresentação também menciona JS, diferença a conferir. Rust/Go não confirmados. **Relevância:** contexto organizacional e arquitetura. **Verificar:** cobertura, limites do serviço, atualização de alterações locais e possibilidade de entregar fontes completas. Licença MIT dos componentes públicos não torna todo o serviço aberto. [Proxy oficial](https://github.com/Pharaoh-so/pharaoh-mcp), [parser](https://github.com/Pharaoh-so/pharaoh-parser).

### Harmony MCP

CodeConductor anuncia índice proprietário, relações de código, busca semântica, expansão adaptativa e montagem de contexto por orçamento. Instalação por npm/MCP. **Relevância:** disputa diretamente a utilidade do pacote de contexto por tarefa. Tecnologias internas, cobertura detalhada por linguagem e operação integral offline não foram comprovadas. A página marca adaptação por agente/modelo e “Deploy Anywhere” como futuros, enquanto apresenta self-hosting empresarial. **Verificar:** disponibilidade efetiva, implantação, custo, fontes citadas e critérios de completude; não classificar itens anunciados como futuros como já entregues. [Página oficial](https://codeconductor.ai/harmony/).

### Repomix

Empacota fontes para modelos, com seleção de arquivos, contagem de tokens, CLI e MCP. Compressão opcional usa Tree-sitter e pode retirar detalhes da implementação. Empacotamento amplo não implica análise semântica de todas as linguagens. **Relevância:** baseline obrigatório e simples para testar se contexto enriquecido melhora algo frente ao código bem selecionado. **Verificar:** pacote completo e comprimido nas tarefas adequadas; não enfraquecer o concorrente obrigando-o a enviar o repositório inteiro. Resolução por compilador/SCIP/LSP não foi confirmada nas fontes consultadas. [FAQ](https://repomix.com/guide/faq), [servidor MCP](https://repomix.com/guide/mcp-server).

### Aider Repository map — candidato para “Aided”

Mapa de repositório do assistente Aider: extrai definições com Tree-sitter e seleciona contexto por grafo, relevância e orçamento. Arquivos completos podem ser pedidos depois. **Relevância:** referência direta para navegação progressiva e seleção antes da leitura integral. Não ficou comprovada uma edição independente MCP chamada Aided. **Verificar:** manter o mesmo agente ao comparar apenas o gerador de mapa; comparar o assistente Aider inteiro é outra avaliação, com esse fator explicitamente diferente. [Documentação atual](https://aider.chat/docs/repomap.html), [mecanismo descrito pelos autores](https://aider.chat/2023/10/22/repomap.html).

### agentmap — Raymond Chins

CLI/MCP local para TS/JS, baseado em ts-morph/compilador TypeScript; mapa por imports e ranking. Consultas experimentais de chamadas inicializam o language service sob demanda. **Relevância:** já materializa mapa barato e aprofundamento semântico seletivo. O README limita chamadas aos alvos resolvíveis e exclui dependências/builtins em consultas descritas; números publicados não provam sucesso do agente. **Verificar:** biblioteca padrão, reexports, homônimos, mudanças no tsconfig e custo frio/aquecido. É um comparador forte específico de JS/TS, não um baseline multilinguagem. [Fonte oficial](https://github.com/raymondchins/agentmap).

### agentmap — Remorses

Inventário YAML com árvore, comentários de cabeçalho, definições e alterações Git; CLI/biblioteca e integração OpenCode. Inclui linguagens prioritárias, mas depende de comentários/docstrings: arquivos sem cabeçalho ficam fora do mapa documentado. **Relevância:** orientação descritiva leve. **Verificar:** cobertura de arquivos e utilidade quando documentação está ausente/desatualizada. Não atribuir a este pacote a resolução do projeto de Raymond Chins. [Fonte oficial](https://github.com/remorses/agentmap).

### codegraph-mcp — Websines

Rust/Tokio, Tree-sitter, petgraph, libSQL/SQLite, MCP e atualização por hash. Combina grafo, sessão, padrões e linhagem de tentativas. README apresenta caráter experimental. **Relevância:** implementação próxima em Rust e memória de investigação. SCIP/LSP não confirmados. **Verificar:** semântica das relações, invalidação e recuperação de experiências sem promovê-las automaticamente a fatos. Resultados de tokens publicados dependem do modo de uso e não foram reproduzidos. [README](https://github.com/websines/codegraph-mcp), [manifesto](https://raw.githubusercontent.com/websines/codegraph-mcp/main/Cargo.toml). Fixar owner final e SHA: há URLs históricas e projetos homônimos.

### OpenLore — acrescentado pela página Selvedge

Índice local e ferramentas de orientação, impacto, decisões ancoradas e verificação de mudanças; caminho central documentado sem LLM. CLI/MCP, runtime Node. Documenta avisos de estado desatualizado e resultados inconclusivos, além de exportação SCIP. **Exportar SCIP não demonstra ingestão de índices produzidos por compiladores.** **Relevância:** concorrente direto a contexto verificável e atualização de decisões. **Verificar:** profundidade das relações, comportamento conservador e custo total. Os benchmarks do próprio projeto incluem perdas; continuam evidência do autor, sem reprodução independente nesta entrega. [Fonte oficial](https://github.com/clay-good/OpenLore).

### trace-mcp — acrescentado pelo histórico e pela proposta híbrida

Documenta Tree-sitter, resolução entre arquivos, armazenamento SQLite/FTS5 e montagem de contexto com orçamento. A configuração distingue fatos AST, inferências, ingestão SCIP opcional e LSP. O LSP é descrito como passe de enriquecimento pós-indexação, com limites e fallback. **Relevância:** comparador técnico essencial para a hipótese híbrida do xrai. **Verificar:** ingestão efetivamente executável na versão fixada, semântica de cada aresta, invalidação e comparação entre enriquecimento antecipado e sob demanda. Não adotar automaticamente a hierarquia de “confiança” do fornecedor como garantia de correção. [Arquitetura](https://trace-mcp.com/architecture.html), [configuração SCIP/LSP](https://trace-mcp.com/configuration.html).

## 5. Memória e ecossistema: complementos ou concorrência parcial

| Projeto | Capacidades documentadas e implicação para xrai |
|---|---|
| [Selvedge](https://selvedge.sh/compare/codebase-memory-mcp-servers/) | Registra motivos, tentativas e resultados por entidade, em SQLite, com CLI/MCP. Complementa índice de código. Testar recuperação de decisão em sessão nova e sua revisão quando a premissa muda; não inferir intenção histórica apenas do código. |
| [Memory Keeper](https://github.com/mkreyman/mcp-memory-keeper) | Contexto de tarefa, checkpoints, decisões, busca e exportação/importação em servidor Node/SQLite. Comparador para retomada de trabalho, não equivalente automático a resolução de símbolos. Relevante à passagem entre computadores e sessões. |
| [mem0](https://github.com/mem0ai/mem0) | Infraestrutura geral de memória, com extração/recuperação, opções gerenciadas e próprias. Caminho padrão documentado usa LLM e embeddings. É possível componente de aplicação, não baseline direto de call graph. Modelos e armazenamento devem entrar no custo e na configuração. |
| [Servidor MCP de memória de referência](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) | Entidades, relações e observações persistidas em JSONL. Boa referência mínima para memória explícita. Armazenar uma relação declarada pelo agente não equivale a verificá-la no programa. |
| [claude-code-memory](https://github.com/ViralV00d00/claude-code-memory) | Python e Neo4j local/remoto, memórias de desenvolvimento, relacionamentos e histórico de tarefas. Documenta análise de codebase, mas esta leitura não estabelece profundidade de parser/resolução comparável aos índices especializados. Infraestrutura operacional diferente do binário autônomo pretendido. |
| [Griptape](https://github.com/griptape-ai/griptape) | Framework Python para agentes, workflows, RAG, ferramentas e memória. Possível consumidor do xrai via MCP, além de alternativa para construir uma aplicação de recuperação. Não foi confirmado um índice semântico pronto equivalente ao xrai. Examinar separadamente biblioteca, Cloud e Nodes; nenhuma adoção de framework foi decidida. [Documentação de ferramentas](https://docs.griptape.ai/stable/griptape-framework/tools/official-tools/). |

## 6. Quem comparar primeiro

Prioridades abaixo são julgamento arquitetural por sobreposição de objetivo, não ranking de desempenho medido.

| Grupo | Seleção | Pergunta que resolve |
|---|---|---|
| Baseline textual | Agente com busca/leitura nativas; Repomix com seleção adequada | A complexidade adicional melhora a tarefa? |
| Índice local geral | Graft/Trail-code, codebase-memory | xrai supera alternativas de adoção simples? |
| Contexto e evidência | OpenLore | Snapshot, insuficiência e rastreabilidade têm benefício concreto? |
| Semântica híbrida | trace-mcp; raymondchins/agentmap em JS/TS | SCIP/LSP seletivo acrescenta valor sobre implementações existentes? |
| Revisão de mudanças | Code Review Graph | Quais dependências e testes o agente deixa de considerar? |
| Referências por necessidade | Aider, Graphify, codegraph-mcp, remorses/agentmap | Seleção de mapa, código+docs e sessão justificam avaliação adicional? |
| Acesso condicionado | Harmony, Pharaoh | Funcionam no ambiente requerido, com cobertura e custo transparentes? |
| Continuidade/memória | Selvedge, Memory Keeper, mem0, MCP memory, claude-code-memory | O histórico relevante reaparece corretamente em outra sessão? |

Não executar todos os braços em todas as tarefas. Fazer triagem de compatibilidade antes de congelar os finalistas; manter dois ou três concorrentes fortes por recorte e registrar exclusões. Não excluir quem exige ferramentas externas apenas para preservar uma vantagem artificial do modo autônomo.

## 7. Consequências para a arquitetura

1. **Camadas por capacidade.** Tree-sitter orienta sintaxe; SCIP fornece fatos do snapshot exportado; LSP responde consultas seletivas. Normalizar proveniência, coordenadas, configuração e capacidades. Origem não é prova automática de precisão; duas respostas do mesmo analisador não são confirmações independentes.
2. **Referência não é chamada.** Conversão de ocorrência SCIP em aresta de chamada exige evidência apropriada. “Possivelmente invoca”, referência e alvo resolvido precisam permanecer distintos.
3. **Aprofundar três arquivos não limita a análise a três arquivos.** O LSP pode carregar o workspace e dependências. Pacote de resposta deve separar bytes originais, fatos associados a spans e caminhos de expansão, com orçamento e lacunas explícitos.
4. **Consistência antes de precedência.** Não misturar SCIP antigo e LSP atual por uma ordem fixa de confiança. Mudanças em dependências/configuração podem invalidar fatos mesmo quando os três arquivos não mudaram. Conflitos exigem diagnóstico e comparação de estados.
5. **Benefício por necessidade.** Antes de consultar LSP, verificar se a informação válida já existe no índice. Reutilizar sessões por workspace/configuração e medir o custo de mantê-las.
6. **Distribuição em dois regimes.** Preservar modo básico autônomo. Modo enriquecido declara toolchains, indexadores, servidores e preparação; comparar com concorrentes em condições equivalentes. Importar SCIP não elimina o custo de produzi-lo.
7. **Memória separada de fatos de código.** Decisões têm autor, motivo, revisão e condição de reconsideração. Resumo inferido ou relato do agente não vira verdade semântica nem instrução autorizada.
8. **Suporte publicado por operação.** Rust/Go/JS/TS: linguagem e biblioteca padrão. Distinguir ECMAScript, tipos TS, Node e APIs de browser antes de fechar o corpus. Python: preservar funcionamento e limitar expansão às prioridades do usuário. Frameworks somente após escolha do usuário.

Esses pontos são recomendações para uma revisão prospectiva. Não mudam o escopo contratado de M0/M1/M2, os aceites históricos ou os gates existentes. A eventual antecipação de SCIP/LSP para um experimento de M0 precisa constar em decisão própria.

## 8. Próximas atividades para Arquiteto e Implementador

As atividades abaixo são preparadas para a retomada autorizada; não são novos cartões contabilizados nem autorização de gasto.

| ID | Responsável | Entrega e aceite |
|---|---|---|
| COMP-01 | Implementador, após retomada | Manifesto de finalistas: owner, URL, release/commit, licença dos componentes usados, SO, configuração, ferramentas/modelos externos, linguagens/operações. Separar release de `main`; marcar recursos indisponíveis. Nenhum resultado sem ambiente reproduzível. |
| COMP-02 | Arquiteto | Resolver Aided/agentmap quando houver link; definir fronteira std/runtime em JS/TS e recorte Python. Escolher finalistas por capacidade, sem ampliar frameworks. |
| COMP-03 | Arquiteto | Especificar experimento híbrido isolado em Rust, adaptadores mínimos, manifesto de fontes/configuração, tratamento de conflito e superfície MCP pequena. Registrar compatibilidade com Store e decisão prospectiva sobre prioridade SCIP/LSP. |
| COMP-04 | Implementador, após COMP-03 e retomada | Preparar smoketests de capacidades, sem campanha de modelos: mapa; leitura de três arquivos; definições/tipos; homônimos/reexports; std; alteração A→B; alteração apenas de dependência/configuração; servidor indisponível e timeout. Relatar capacidade ausente sem inventar resultado negativo completo. |
| COMP-05 | Arquiteto | Congelar comparação, orçamento e tarefas antes dos resultados. Avaliar os três braços xrai: sintaxe, sintaxe+SCIP, sintaxe+SCIP+LSP. Incluir pelo menos uma alternativa semântica forte no mesmo recorte e baseline textual competente. |
| COMP-06 | Implementador, após autorização da campanha | Medir tarefa inteira: êxito por testes/oracle independente, fatos incorretos, omissões, reaberturas, tokens reais, custo de índice/atualização e modelo, tempo frio/aquecido e pico de memória. Guardar configuração, respostas completas e falhas. |
| COMP-07 | Arquiteto | Decidir continuar, integrar um motor existente, reduzir escopo ou encerrar a hipótese. A vantagem precisa ser repetível no domínio escolhido; uma demo não libera v1 nem altera G0/G1/G2. |

### Regras da futura comparação

- Mesmo snapshot, tarefa, permissões, modelo/agente quando o fator testado for a ferramenta, e orçamento definido previamente. Não fornecer ao seletor a solução ou os arquivos-resposta do oracle.
- Separar ensaio de componente (três arquivos já definidos, mede enriquecimento) de tarefa completa (agente precisa descobri-los, mede seleção + semântica + resultado).
- Baselines podem aprofundar, ler fontes e corrigir escolhas. Contexto completo vs comprimido é configuração explícita, não impedimento artificial.
- Alterar A→B depois de construir o índice; incluir remoção/renomeação, símbolos homônimos, dependência e configuração. Um reindex completo antecipado não demonstra atualização incremental.
- Medir custo da árvore de processos e preparação, inclusive geração SCIP e inicialização LSP; informar latências frias e aquecidas separadamente.
- Contabilizar esquemas MCP, metadados, tentativas e expansões. “Tamanho dos arquivos menos tamanho da resposta” é uma estimativa contrafactual, não economia observada de uma sessão do agente.
- Publicar perdas e desconhecidos. Falha de instalação/configuração não prova baixa qualidade semântica; omissão silenciosa não equivale a resposta correta vazia.
- Nenhum limiar, denominador, quota ou aceite anterior é alterado por este levantamento. Usar o protocolo vigente e registrar formalmente qualquer revisão futura.

## 9. Registro da entrega

Consulta documental com links primários e revisão de identidades; sem benchmark, auditoria completa de código dos concorrentes ou nova revisão de C07. Foram preservados os documentos históricos. Handoff, retomada e estado receberam links para esta análise. Verificação aplicável: links relativos locais e `git diff --check`; resultados registrados no estado antes da publicação. Pendências substantivas estão em COMP-01 a COMP-07 e nas identidades acima.
