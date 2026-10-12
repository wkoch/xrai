# Plataformas do v1 — ADR 020

Data: 11/10/2026. **Decisão definida pelo usuário:** focar Linux x86_64 e macOS arm64 no v1; pensar em Windows depois. O arquiteto atualiza plano/aceite; o implementador adapta CI/código e registra provas.

## Escopo vigente

| Alvo | Target Rust inicial | Compromisso |
|---|---|---|
| Linux x86_64 | `x86_64-unknown-linux-gnu` | Obrigatório desde M0 até a alpha/v1 |
| macOS arm64 / Apple Silicon | `aarch64-apple-darwin` | Obrigatório desde M0 até a alpha/v1 |
| Windows, Linux arm64, macOS Intel | A definir após v1 | Fora dos gates e dos artefatos obrigatórios do v1 |

“V1” significa aqui a primeira versão do produto, incluindo a alpha planejada em M1-B; não altera a numeração do schema documental. Musl pode ser avaliado futuramente, sem acrescentar agora outro artefato obrigatório.

### Baseline definido pelo Arquiteto na revisão L1

- **Linux:** Ubuntu 24.04 LTS x86_64, glibc 2.39, como ambiente inicial de fabricação e aceite. Outras distribuições GNU/Linux com ABI compatível podem funcionar, mas só entram na lista de ambientes verificados após smoke próprio. Não prometer todas as distribuições apenas pelo target Rust. A versão de glibc dessa baseline consta no [pacote oficial Ubuntu](https://packages.ubuntu.com/noble/amd64/libc6).
- **macOS:** piso inicial 15.0 em arm64, com `MACOSX_DEPLOYMENT_TARGET=15.0` aplicado a Rust e componentes C. Testar nativamente no piso e registrar SDK/flags/dependências. Execução em versão posterior não comprova o piso. O mecanismo de deployment target é documentado pelo [Rust](https://doc.rust-lang.org/stable/rustc/platform-support/apple-darwin.html); o piso 15.0 é uma escolha do xrai, não uma limitação universal do Rust.
- M0-05 inspeciona ABI/dependências e comprova autonomia nesses ambientes; M1-20 repete com o artefato distribuído. Não aceitar dependência de biblioteca de desenvolvimento instalada só no runner. SDK/compilador são ferramentas de build, não requisitos do usuário.

O objetivo é começar com os ambientes de referência já previstos na CI e uma promessa verificável. Não aumentar o piso silenciosamente se uma dependência falhar; corrigir a dependência ou registrar proposta fundamentada. Versões mais antigas e musl ficam fora do compromisso inicial, sem demandar trabalho de compatibilidade antecipado. Estes pisos fecham a escolha arquitetural, mas não declaram os testes executados.

A decisão concentra trabalho nos dois alvos sem reduzir qualidade, linguagens ou autonomia. Rust, TS/JS, Python e Go permanecem no escopo. Um executável por alvo, CLI/MCP, uso básico offline e sem runtimes auxiliares continuam obrigatórios. Amostras, limiares e tetos de G0/G1/G2 permanecem os mesmos.

## Impactos no trabalho

| Atividade | Alteração de aceite ou próxima ação |
|---|---|
| M0-02.R2, nova atividade | Adequar CI: dois hosts Rust e check documental; retirar Windows da matriz obrigatória; observar evidências e eventual configuração de checks exigidos |
| M0-05/06 | Parsing incorporado, autonomia e workers comprovados nativamente nos dois alvos |
| M0-07 | SQLite/FTS5, leitores e interrupção precisam de evidências do spike em Linux x86_64/macOS arm64; retirar somente a exigência Windows |
| M0-08, M1-01/02 | Paths e filesystem Linux/macOS sem perda; reparse points e adapter Windows ficam pós-v1 |
| M0-10 / G0 | Consolidar viabilidade nativa dos dois alvos e conclusão de M0-02.R2 |
| M1-19/20/21 | Confiabilidade, artefatos, ambiente limpo, CLI/MCP e saída G2 nos mesmos dois alvos |
| Campanhas competitivas | Ambiente primário pré-definido e comparável; testes funcionais nos dois alvos, sem duplicação automática de toda campanha paga |

Detalhes, dependências e critérios estão no [plano](../PLANO-DE-IMPLEMENTACAO.md); execução e impedimentos no [estado](../STATUS-IMPLEMENTACAO.md). M0-02.R2 depende de M0-02.R1 e é requisito de M0-10. Pode ser executada sem aguardar corpus ou retomar entregas concluídas.

O implementador continua responsável por alterações de workflow e código. Remover Windows do aceite não comprova execução nos outros alvos. Se billing, runner ou infraestrutura impedir a prova Linux/macOS, preservar a pendência e continuar trabalho independente; não mascarar falha, dispensar check ou usar smokes antigos como prova do spike novo. A elegibilidade do corpus foi resolvida separadamente no [ADR 021](CORPUS-QUALIFICADO.md); o bloqueio anterior de CI foi [superado em 12/10](../relatorios/CI-PUBLICO.md), concluindo R2/M0-07 sem concluir os demais cartões.

## Contratos e histórico

- Preservar CRLF, Unicode, bytes nativos, espaços, symlinks e case sensitivity. Esses cenários também existem nos dois alvos; a mudança não autoriza identidade com conversão de path com perda.
- Preservar `windows_u16` e fixtures documentais já produzidas como extensão futura. Não exigir adapter Windows de produção no v1, não anunciar execução Windows e não inferir portabilidade de bancos entre SOs.
- Resultados anteriores no Windows continuam evidência histórica. Referências a três SOs/cinco alvos em relatórios anteriores não definem o aceite vigente. Esta decisão substitui esses requisitos de plataforma, sem reescrever logs ou declarar tarefas concluídas.
- Evitar dependências gratuitas de um SO no núcleo; abstrações existentes podem ser preservadas. Não financiar antecipadamente suporte Windows, instaladores ou testes específicos para cumprir v1.

## Depois do v1

Reabrir Windows por demanda e custo de manutenção, com escopo próprio: paths UTF-16/reparse points, filesystem/locking/SQLite, subprocessos/IPC/cancelamento, gramáticas incorporadas e pacote autônomo em máquina limpa. Disponibilizar runner nativo e medir antes de anunciar suporte. Linux arm64/macOS Intel seguem o mesmo princípio. A expansão não tem prazo nem dependência automática com M2/M3.

## Verificação desta atualização

A entrega do arquiteto é documental: plano, RFC, contrato, validação, protocolo e handoff foram alinhados. O [registro de verificações](../relatorios/logs/plataformas-v1/documentacao.json) confere referências locais, cartões/dependências e o recorte dos critérios. Resultados de implementação permanecem atribuídos aos relatórios do implementador; a publicação desta decisão só é declarada após commit/push confirmado.
