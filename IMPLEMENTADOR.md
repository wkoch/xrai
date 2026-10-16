# Instruções para a IA implementadora do xrai

**Mudança de computador — 16/10/2026:** começar por [RETOMADA.md](RETOMADA.md). Publicação e conferência de clone sob responsabilidade do Implementador; consultar o inventário para o corte verificado e a entrega para o SHA final. O backup privado de objetos Git sem referência fica fora do checkout e precisa de cópia separada para outra máquina. Preservar a pausa até retomada autorizada.

**Diretriz posterior do usuário — 16/10/2026:** priorizar suporte mais completo a Rust, Go e JavaScript/TypeScript, concentrado na linguagem e biblioteca padrão. Preservar Python já funcional e limitar novos investimentos ao básico, IA e geração/manipulação de DOCX/XLSX e áreas semelhantes. Antes de escolher ou aprofundar qualquer framework, consultar o usuário. Esta instrução prevalece sobre prioridades anteriores conflitantes; decisões de arquitetura e ajustes de corpus/aceite ficam pendentes para o Arquiteto em [prioridades de linguagens](docs/relatorios/PRIORIDADES-LINGUAGENS-2026-10-16.md). O preparo Django existente é preservado, sem ampliação automática de foco em Django. A implementação continua no checkpoint de parada solicitado em14/10 até nova retomada.

Data: 13/10/2026. **Entrada vigente: [fechamento C06](docs/relatorios/REVISAO-L5-C06-FECHAMENTO.md).** Replay D01 v4, cápsula histórica/CI e prova nativa P3 por bytes aceitos no corte `bd12a9a`. Próximas entregas: integração Store/Tokio, oracle físico Django v2 e recibo público de transporte fake. Oito elegíveis, D1 global 0/32, quatro eventos e projeção multimódulo 19/20. [Estado](docs/STATUS-IMPLEMENTACAO.md) e [roteiro v1](docs/ROTEIRO-V1.md). Não repetir aceites históricos. Complemento de 14/10: [primeira vertical Rust](docs/INTEGRACAO-VERTICAL-RUST.md) fecha a ponte Store–consumer e seleciona Tokio/FIFO para diagnóstico de tarefa inteira, após os controles C06.

Atualização de 12/10/2026: repositório público e [CI confirmada nos três jobs](docs/relatorios/CI-PUBLICO.md). M0-02.R2/M0-07 concluídas; bloqueio anterior superado. [L3](docs/relatorios/L3.md) avançou contenção, workers, captura e quatro pilotos verticais. [L4](docs/relatorios/L4.md) entregou os recortes descritos acima; L5 organiza o restante dos mesmos cartões. Nenhum gate competitivo foi avaliado.

## 1. Papel e objetivo

O usuário definiu dois papéis:

- **Arquiteto:** o assistente da conversa de arquitetura mantém requisitos, decisões, plano, atividades e critérios de aceite. Não gera código do produto nem executa a implementação.
- **Implementador:** a outra IA que recebe este arquivo escreve código, configura ambiente/build, implementa testes, executa experimentos e registra evidências. Pode tomar decisões locais de engenharia dentro dos contratos; não precisa pedir aprovação para cada arquivo, biblioteca ou tarefa rotineira.

Construa um CLI em Rust para entregar a agentes de IA contexto de código correto, relevante e atualizado. Linguagens: Rust, TypeScript/JavaScript, Python e Go. **V1: Linux x86_64 e macOS arm64**, com um executável por alvo e nenhuma GUI. Windows, Linux arm64 e macOS Intel ficam para depois do v1. A experiência básica não requer runtimes auxiliares ou rede. O mesmo executável pode iniciar workers e criar banco/cache.

**Prioridade do usuário: maior sucesso em tarefas reais, aceitando custo adicional proporcional.** Redução de tokens é secundária. Não omita evidência necessária para produzir uma resposta menor. Use expansão, representações maiores ou diagnóstico de insuficiência dentro dos limites definidos.

As instruções diretas do usuário e as instruções de ambiente/AGENTS aplicáveis continuam válidas. Este handoff não substitui permissões da ferramenta nem autoriza ações externas, publicações ou envio de mensagens.

## 2. Leitura e fontes de decisão

Leia inicialmente este arquivo, o estado atual, a revisão vigente e os cartões do lote atual. Consulte o restante conforme a tarefa exigir; não é necessário reler toda a pesquisa a cada sessão.

| Documento | Autoridade no trabalho |
|---|---|
| [Estado da implementação](docs/STATUS-IMPLEMENTACAO.md) | Tarefas realmente executadas, evidências, impedimentos e próxima ação |
| [Plano de implementação](docs/PLANO-DE-IMPLEMENTACAO.md) | 35 tarefas principais e seis atividades complementares, dependências, entregáveis e aceite; IDs são estáveis |
| [Fechamento C06](docs/relatorios/REVISAO-L5-C06-FECHAMENTO.md) | Aceites D01/histórico/P3 e próximas fatias Store, Django e transporte |
| [Primeira vertical Rust](docs/INTEGRACAO-VERTICAL-RUST.md) | Binding/envelope/processo Store, entrada BASE pública e diagnóstico Tokio/FIFO; trabalho futuro |
| [Revisão L5-C06](docs/relatorios/REVISAO-L5-C06.md) | Histórico dos achados e contratos complementares preservados |
| [Revisão L5-C04/C05](docs/relatorios/REVISAO-L5-C05.md) | Aceites prévios e contratos de corpus, avaliação, recursos, ABA/blobs e inspeção ainda vigentes |
| [Revisão L5-C03](docs/relatorios/REVISAO-L5-C03.md) | Histórico da primeira prova Rust e origem de E02/D01/S02 |
| [Próxima execução L5](docs/L5-PROXIMA-EXECUCAO.md) | Fatias C03/dispatch e perfil TS/JS; considerar os aceites e ajustes posteriores da revisão L5-C05 |
| [Revisão L5-C02](docs/relatorios/REVISAO-L5-C02.md) | Aceite anterior dos quatro pares e origem dos requisitos de eventos/C03 e dependências/S01 |
| [Revisão da continuação L5](docs/relatorios/REVISAO-L5-CONTINUACAO.md) | Aceite anterior R3/pares Rust-JS e decisão C02 já concretizada |
| [Roteiro v1 / ADR028](docs/ROTEIRO-V1.md) | Avaliação do estágio, caminho crítico e seis atividades de estabilização após G2; não antecipar produção |
| [Revisão L5 / retomada](docs/relatorios/REVISAO-L5.md) | Critérios anteriores que permanecem abertos, incluindo controles P3/cache |
| [Revisão L4 / atividades L5](docs/relatorios/REVISAO-L4.md) | Critérios originais dos seis incrementos; continuam onde ainda não cumpridos |
| [Contexto P3 / ADR 027](docs/decisoes/CONTEXTO-P3.md) | Comparação experimental versionada, obrigações, orçamento, manifesto e expansão |
| [Revisão L3 / continuação L4](docs/relatorios/REVISAO-L3.md) | Histórico e critérios ainda abertos, retomados em L5 |
| [Semântica P2 / ADR 025](docs/decisoes/SEMANTICA-P2.md) | IR, primeira fatia Rust, incertezas, dependências negativas e equivalência incremental |
| [Workers e medição / ADR 026](docs/decisoes/WORKERS-E-MEDICAO.md) | XRW2 persistente, CPU/RSS, tokenizer, ledger e readiness sem alterar históricos |
| [Revisão L2 / lote L3](docs/relatorios/REVISAO-L2.md) | Histórico do lote anterior; itens abertos continuam nos incrementos vigentes |
| [Execução e captura / ADR 023](docs/decisoes/EXECUCAO-E-CAPTURA.md) | Contenção do harness, workers/IPC, captura por handles e Git adiado |
| [Bibliotecas próprias / ADR 024](docs/decisoes/BIBLIOTECAS-PROPRIAS.md) | Investimento próprio admitido, fronteiras Rust, experimentos e promoção |
| [Revisão L1 / lote L2](docs/relatorios/REVISAO-L1.md) | Parecer sobre corpus, resolução C01/S01/S02, próximos incrementos e impedimentos externos |
| [Corpus qualificado / ADR 021](docs/decisoes/CORPUS-QUALIFICADO.md) | Seed aceito para desenvolvimento; critérios e oracles obrigatórios para M0-03.R1/piloto |
| [Persistência e retenção / ADR 022](docs/decisoes/PERSISTENCIA-E-RETENCAO.md) | Dono/fencing, FTS, pins e GC; implementar apenas nos cartões M1 após G1 |
| [Plataformas do v1 / ADR 020](docs/decisoes/PLATAFORMAS-V1.md) | Dois alvos obrigatórios desde M0; Windows pós-v1; adaptação de CI em M0-02.R2 |
| [Revisão L0 / lote L1](docs/relatorios/REVISAO-L0.md) | Resposta às pendências A01/A02, nova A03, retificação do contrato, CI documental e trabalho imediato |
| [Prova de diferenciação](docs/PROVA-DE-DIFERENCIACAO.md) | Objetivo, concorrentes, corpus, contabilidade, limites e gates G0/G1/G2 |
| [RFC de arquitetura](docs/RFC-0001-ARQUITETURA.md) | Componentes, contratos fundamentais, trade-offs e ADRs |
| [Plano de validação](docs/PLANO-DE-VALIDACAO.md) | Invariantes, falhas, oracles e verificação por capacidade |
| [Estudo comparativo](docs/ESTUDO-COMPARATIVO.md) | Evidência histórica e inspirações; não é ranking medido pelo xrai |

Qualidade como única rota primária substitui a proposta anterior de aprovar o projeto somente por economia. Essa alteração já está refletida nos documentos. Se encontrar divergência residual, preserve a decisão explícita mais recente do usuário, registre o conflito e corrija documentação sem mudar critérios de experimento após observar resultados.

As decisões técnicas propostas são a base de trabalho autorizada para iniciar; a palavra “Proposto” não exige uma nova aprovação a cada cartão. Mudanças materiais de escopo, arquitetura ou critérios merecem um registro com problema, alternativas, evidência e recomendação ao arquiteto. Continue tarefas independentes enquanto a decisão estiver pendente.

## 3. Como julgar qualidade e custo

O protocolo é a fonte completa. Os limites abaixo são **parâmetros iniciais propostos pela arquitetura**, não números explicitamente aprovados pelo usuário nem autorização de despesa.

| Momento | Qualidade exigida | Limites de custo simultâneos |
|---|---|---|
| G0, piloto de M0 | Ganho exploratório de sucesso ≥10 pontos percentuais, repetido em famílias/repos | Razões pontuais: por tentativa ≤1,25; por sucesso ≤1,15 |
| G1, confirmação em M1-A | Ganho pontual ≥8 pontos percentuais; limite inferior do intervalo de 95% da diferença acima de zero | Limites superiores dos intervalos das razões: por tentativa ≤1,25; por sucesso ≤1,15 |
| G2, produto integrado | Preservar o ganho e os critérios funcionais | Preservar tetos e demais guardrails após integração |

Comparar com cada finalista relevante e baseline textual competente, no regime previamente definido. Contar falhas, retries, expansões, instruções, indexação amortizada e todos os usos do modelo. Sem sucesso, custo por sucesso não é zero. Não usar apenas tokens da primeira resposta nem uma razão agregada para justificar perda de qualidade.

Configuração de maior qualidade do concorrente precisa ser representada, mesmo que seja cara. Economia sem ganho suficiente de sucesso é resultado secundário; maior sucesso com custo acima dos tetos também não libera automaticamente a próxima etapa. Documente ambos para eventual revisão de produto.

Gates dependem de evidência; não são uma fila de aprovações para trabalho rotineiro. O implementador registra resultado e decisão conforme o protocolo. Resultado inconclusivo ou negativo não libera engenharia ampla por conta própria. Não troque métricas, adversário, orçamento ou conjunto depois dos resultados para fabricar uma aprovação.

## 4. Primeiro lote executável — L0

**Roteiro de M0-01 e M0-02, já executado em L0.** Não comece pelo banco completo, resolvers de produção ou todos os comandos finais. Este lote estabelece contrato e base compilável para os experimentos.

1. Confira o checkout e o estado local antes de editar. Preserve arquivos e alterações existentes. Se já houver implementação de outra sessão, retome da evidência encontrada; não recrie o projeto cegamente. Registre presença/ausência de Git, sem depender de um remoto para começar.
2. Em **M0-01**, produza `docs/contracts/m1.md` e exemplos de request/response. Defina IDs, paths nativos, spans em bytes, revisão, cobertura, capabilities, erros e distinção entre fato/candidato/unknown. Inclua resultado vazio completo, capacidade ausente, parse parcial, snapshot expirado e orçamento insuficiente. Contrato não pode anunciar capacidade ainda inexistente.
3. Em **M0-02**, crie o workspace mínimo com `xrai-core`, `xrai-index`, `xrai-query`, `xrai` e `xrai-eval`; fixe toolchain, edição, dependências e lockfile após verificar compatibilidade e licenças nas fontes oficiais. Versões ainda não estão decididas. Evite implementar subsistemas para preencher diretórios vazios.
4. Entregue `xrai --help` e `xrai --version` funcionando localmente; a matriz obrigatória vigente é Linux x86_64 e macOS arm64. L0 incluiu Windows no escopo anterior; M0-02.R2 adapta essa CI. A comprovação nativa de autonomia dos dois alvos pertence a M0-05 e não bloqueia o início local dos protótipos.
5. Rode as verificações previstas para o esqueleto: `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets --locked -- -D warnings` e `cargo test --workspace --locked`, além dos dois smokes da CLI. Registre ambiente, comandos, código de saída e resultado real. Runner ausente é não verificado; cross-build não prova execução nativa.
6. Entregue `docs/relatorios/L0.md` e atualize o [estado](docs/STATUS-IMPLEMENTACAO.md). Registre escolhas técnicas, arquivos alterados, critérios demonstrados, pendências e próxima tarefa. Só marque concluído o que cumprir aceite. A elaboração deste handoff não conclui M0-01.

L0 não precisa de API paga, corpus reservado pronto ou confirmação de métricas competitivas. Esses itens não bloqueiam começar. Ao concluir o lote, comunique seu resultado na conversa de implementação e mantenha o relatório local disponível ao arquiteto; não envie mensagens a outra conversa sem autorização do usuário.

## 5. Ordem após L0

| Etapa | Atividades | Condição |
|---|---|---|
| Plataforma do v1 | M0-02.R2 e M0-07 concluídas com CI nativa | Preservar checks documentais e históricos; próximos spikes seguem seus próprios critérios |
| Corpus e medição | M0-03 inicial aceito; M0-03.R1 qualifica D1; M0-04 usa D0/seed no harness/replay | Começar localmente; piloto depende de R1; smoke pago exige teto autorizado |
| Spikes técnicos | M0-05/06/07/08: gramáticas, workers, snapshots e filesystem | Seguir dependências dos cartões; registrar limitações nativas |
| Prova semântica P2 | M0-11: recortes de imports/bindings/alvos/configuração nas quatro famílias | Extração mínima local; não esperar todos os runners ou índice de produção |
| Prova de contexto P3 | M0-09: obrigações, base/head, representações e expansão | Usar snapshots capturados e evidências de P2; medir qualidade de 2 mil a 32 mil tokens |
| Piloto competitivo | M0-12: oito triados, finalistas fortes, variantes A/B/C/D e sessões reais | Configurações e despesas limitadas; não escolher só modos fracos dos rivais |
| G0 | M0-10: sinal de qualidade, tetos e viabilidade técnica | Favorável libera apenas M1-A; duas versões experimentais por hipótese no máximo |
| Confirmação | M1-01 e M1-22: contratos mínimos e H1 reservado | G0 favorável; proposta inicial 120 tarefas, teto H1+H2 240, uma campanha adicional |
| Alpha | M1-02 a M1-20, com M1-23 antes de M1-16 | G1 favorável; promover somente componentes e recortes justificados |
| G2 | M1-21: preservar ganho, confiabilidade e distribuição | Autoriza alpha no domínio comprovado e próximo pacote delimitado |

Esta tabela orienta a sequência; os cartões contêm todas as dependências. ID numérico não é ordem de execução: M0-11 precede M0-09 e M1-22 precede a engenharia ampla de M1. Não avance M2/M3 completos só porque há tarefas listadas.

## 6. Limites de arquitetura a preservar

- Monólito Rust modular; CLI e MCP compartilham domínio. `xrai-eval` é ferramenta de desenvolvimento, não requisito da máquina de uso.
- Tree-sitter e gramáticas incorporados inicialmente; biblioteca própria de qualquer porte é opção legítima quando necessária. Lacuna reproduzível ligada ao objetivo permite experimento vertical antes de ganho competitivo completo; expansão/produção seguem ADR 024 e gates. Complexidade sozinha não impede investimento.
- Pai captura bytes/hash e workers do mesmo executável analisam esses bytes; protocolos, filas, respostas e retries limitados. Isolamento de processo não é promessa de sandbox ou proteção contra OOM global.
- Fonte, fatos e configuração pertencem à revisão declarada. SQLite publica gerações completas; nunca juntar grafo antigo com arquivo novo para aparentar frescor.
- Produção de persistência segue ADR 022: posse por lock/epoch, fontes e FTS deduplicados, pins contra GC. Não antecipar esse trabalho para substituir o spike M0-07 antes da prova competitiva.
- Cobertura sintática não comprova precisão semântica. Unknown/candidato não vira fato por nome parecido ou score alto; ausência de resultado com cobertura parcial não prova ausência no programa.
- Mudanças de configuração e dependências positivas/negativas invalidam resoluções; incremental precisa equivaler a rebuild das mesmas entradas.
- Indexar não executa imports, macros, scripts ou builds do projeto. O harness pode executar testes/builds como parte da avaliação, em ambiente separado e com entradas declaradas.
- Base/head permanece identificável; worktrees não compartilham estado gravável por acidente. Cache regenerável não contém a única cópia de notas humanas.
- Contexto inclui fonte exata e omissões explícitas; orçamento cobre a resposta serializada. Expansão permanece possível; recibos de sessão, memória, embeddings e seleção que dispensa testes seguem seus marcos.

## 7. Medição e orçamento sem bloquear o início

Há smokes e medições técnicas locais; não há resultados competitivos próprios, teto monetário da campanha nem hardware/runner completo definido. Versões já fixadas permanecem nos relatórios. O implementador deve converter as lacunas em registros concretos, sem inventar medições ou preços.

- Trabalho local de L5 continua os cartões abertos após L4, conforme critérios da revisão vigente. Não aguardar nova decisão arquitetural sobre H01/F01/GIT01; smokes pagos/infraestrutura indisponível mantêm seus limites próprios.
- Antes de uma campanha com modelos pagos, preencher limites de uso/runs e orçamento do protocolo a partir dos recursos autorizados. A preferência por qualidade não é autorização de gasto ilimitado. Se o valor necessário não estiver definido, apresentar uma estimativa concreta e continuar as frentes locais independentes.
- Estimar a carga da prova, não só uma chamada: a matriz ilustrativa do protocolo chega a 448 runs no piloto e 960 na confirmação principal, antes dos complementos. Não iniciar esses lotes automaticamente com orçamento ausente.
- Manter D0/seed/D1 qualificado para ajuste; congelar candidata, prompts, adversários e critérios antes de H1. Não colocar patches/oracles ocultos no contexto do agente ou nas entradas do seletor. Se dados de H1 forem expostos durante ajuste, registrar contaminação e não tratá-los como confirmação independente.
- Os percentuais de custo de G1 comparam operação entre ferramentas. Registrar separadamente esforço de implementar e manter cada frontend e o custo total da campanha de pesquisa.

## 8. Relato ao arquiteto e continuidade

Ao terminar um lote ou encontrar decisão material, atualize o estado e deixe relatório local com:

1. IDs trabalhados e situação real; o que o usuário/agente já consegue fazer.
2. Arquivos alterados e escolhas relevantes, com motivo e alternativa descartada quando necessário.
3. Critérios de aceite verificados, comandos/resultados e localização das evidências; separado do que não foi executado.
4. Custos observados, defeitos conhecidos e limites de cobertura/plataforma.
5. Decisão necessária, se houver, com recomendação concreta e tarefas que podem continuar.
6. Próxima tarefa pronta pelas dependências.

Instrução posterior do usuário: ao finalizar uma entrega e suas verificações, faça commit e push para `origin` (`https://github.com/wkoch/xrai.git`), conforme [AGENTS.md](AGENTS.md). Registre falhas de publicação explicitamente; não substitua histórico remoto por force push.

Não marque sucesso experimental por acerto de fixture, economia de payload ou benchmark publicado por concorrente. Um relatório de experimento negativo é uma entrega válida e pode economizar investimento futuro. Mantenha falhas visíveis e não reescreva critérios para acomodar o resultado.

**Próxima execução: [fechamento C06](docs/relatorios/REVISAO-L5-C06-FECHAMENTO.md), §§2–5.** Integrar intake ao Store com presença/IR opcional e regressão Tokio; preparar/executar oracle físico Django v2 no domínio permitido; observar bytes na interface pública de transporte fake. Correção do replay, cápsula histórica e prova nativa byte-only estão aceitas. Continuar demais frentes C05. Nenhum crédito multimódulo por lista de paths nem tarefa natural por fixture. Atualizar evidências e commit/push após checks conforme AGENTS.md.
