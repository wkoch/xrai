# xrai

CLI em Rust para entregar contexto de código relevante, verificável e atualizado a agentes de IA.

Estado: protótipos em M0. L5-C04/C05 acrescentou quatro eventos operacionais, semântica lexical e sessão TS/JS, recuperação BM25/TF-IDF com contagem integral de tokens e medição de workers em Linux/macOS. Oito tarefas individualmente elegíveis; admissão D1 global 0/32, sem resultado competitivo próprio. A [revisão corrente](docs/relatorios/REVISAO-L5-C05.md) define correções e próximas entregas; o [roteiro até 1.0](docs/ROTEIRO-V1.md) separa M0, confirmação, alpha e estabilização. `xrai --help` e `--version` funcionam; capacidades do produto seguem nas tarefas posteriores. [Estado e evidências](docs/STATUS-IMPLEMENTACAO.md).

Para executar o scaffold: `cargo build --workspace --locked`, depois `./target/debug/xrai --help`. Toolchain fixada em Rust 1.98.1. [Relatório e evidências L0](docs/relatorios/L0.md). A atividade M0-02.R2 cobre a adaptação da CI ao [escopo do v1](docs/decisoes/PLATAFORMAS-V1.md); o estado distingue configuração e execução comprovada.

Escopo inicial: Rust, TypeScript/JavaScript, Python e Go. **V1 em Linux x86_64 e macOS arm64 (Apple Silicon)**; um executável por alvo; nenhuma GUI. Windows e outras arquiteturas serão reavaliados após v1.

A prioridade é **resolver mais tarefas corretamente, com aumento de custo proporcional e limitado**. Economia de tokens é secundária; contabilizar exploração, indexação amortizada, chamadas de ferramentas e uso do modelo. O grafo é a infraestrutura para chegar lá.

**IA implementadora: consulte [IMPLEMENTADOR.md](IMPLEMENTADOR.md) e o estado atual antes de continuar.** O assistente de arquitetura planeja e define atividades; outra IA gera código, executa testes e registra evidências em [STATUS-IMPLEMENTACAO.md](docs/STATUS-IMPLEMENTACAO.md).

- [Proposta de arquitetura](docs/RFC-0001-ARQUITETURA.md)
- [Plano de implementação: tarefas, dependências e aceite de M0/M1](docs/PLANO-DE-IMPLEMENTACAO.md)
- [Prova de diferenciação: protótipos, concorrentes e decisão de investimento](docs/PROVA-DE-DIFERENCIACAO.md)
- [Estudo dos oito projetos de referência](docs/ESTUDO-COMPARATIVO.md)
- [Plano de validação e critérios de avanço](docs/PLANO-DE-VALIDACAO.md)

Bibliotecas próprias, inclusive parsers e frontends complexos, são opções admitidas quando necessárias. O [ADR 024](docs/decisoes/BIBLIOTECAS-PROPRIAS.md) define fronteiras Rust, experimentos e promoção; complexidade sozinha não é veto.

Direção proposta: núcleo local e determinístico; extração por Tree-sitter em workers isolados; resolução semântica por linguagem; grafo com evidências e revisões; navegação por propósito; seleção de contexto e testes por tarefa; CLI e MCP sobre o mesmo motor.

Referências estudadas: Graft, trace-mcp, codebase-memory-mcp, code-review-graph, jCodeMunch, tokensave, ProjectAtlas e codegraph-mcp. Recursos semelhantes já existem nesses projetos; a vantagem do xrai deverá ser demonstrada em precisão e custo total de tarefas reais.

Sequência de investimento: M0 procura sinal com protótipos de semântica e contexto; M1-A confirma contra concorrentes fortes em dados reservados; somente depois M1-B constrói a alpha completa. Sem vantagem demonstrada, focar, simplificar ou encerrar a tese atual.

Documentos preparados em 11/10/2026. Prioridade de qualidade e divisão de papéis definidas pelo usuário; decisões técnicas e limiares numéricos propostos pela arquitetura, sem compromisso de API estável.
