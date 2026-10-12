# xrai

CLI em Rust para entregar contexto de código relevante, verificável e atualizado a agentes de IA.

Estado: lote L0 concluído (M0-01 e M0-02). Workspace Rust mínimo compilável; `xrai --help` e `xrai --version` funcionam localmente. Parsing, consultas e MCP seguem nas tarefas posteriores. Não há resultados competitivos próprios.

Para executar o scaffold: `cargo build --workspace --locked`, depois `./target/debug/xrai --help` (Windows: `target/debug/xrai.exe`). Toolchain fixada em Rust 1.98.1. [Relatório e evidências L0](docs/relatorios/L0.md). A [revisão arquitetural](docs/relatorios/REVISAO-L0.md) confirmou a CI nos três hosts do scaffold e definiu o lote L1: retificar contrato, preparar corpus e automatizar sua validação; spike de armazenamento pode avançar independentemente.

Escopo inicial: Rust, TypeScript/JavaScript, Python e Go. Linux, macOS e Windows; um executável por plataforma/arquitetura; nenhuma GUI.

A prioridade é **resolver mais tarefas corretamente, com aumento de custo proporcional e limitado**. Economia de tokens é secundária; contabilizar exploração, indexação amortizada, chamadas de ferramentas e uso do modelo. O grafo é a infraestrutura para chegar lá.

**IA implementadora: consulte [IMPLEMENTADOR.md](IMPLEMENTADOR.md) e o estado atual antes de continuar.** O assistente de arquitetura planeja e define atividades; outra IA gera código, executa testes e registra evidências em [STATUS-IMPLEMENTACAO.md](docs/STATUS-IMPLEMENTACAO.md).

- [Proposta de arquitetura](docs/RFC-0001-ARQUITETURA.md)
- [Plano de implementação: tarefas, dependências e aceite de M0/M1](docs/PLANO-DE-IMPLEMENTACAO.md)
- [Prova de diferenciação: protótipos, concorrentes e decisão de investimento](docs/PROVA-DE-DIFERENCIACAO.md)
- [Estudo dos oito projetos de referência](docs/ESTUDO-COMPARATIVO.md)
- [Plano de validação e critérios de avanço](docs/PLANO-DE-VALIDACAO.md)

Direção proposta: núcleo local e determinístico; extração por Tree-sitter em workers isolados; resolução semântica por linguagem; grafo com evidências e revisões; navegação por propósito; seleção de contexto e testes por tarefa; CLI e MCP sobre o mesmo motor.

Referências estudadas: Graft, trace-mcp, codebase-memory-mcp, code-review-graph, jCodeMunch, tokensave, ProjectAtlas e codegraph-mcp. Recursos semelhantes já existem nesses projetos; a vantagem do xrai deverá ser demonstrada em precisão e custo total de tarefas reais.

Sequência de investimento: M0 procura sinal com protótipos de semântica e contexto; M1-A confirma contra concorrentes fortes em dados reservados; somente depois M1-B constrói a alpha completa. Sem vantagem demonstrada, focar, simplificar ou encerrar a tese atual.

Documentos preparados em 11/10/2026. Prioridade de qualidade e divisão de papéis definidas pelo usuário; decisões técnicas e limiares numéricos propostos pela arquitetura, sem compromisso de API estável.
