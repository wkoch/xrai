# Prova de diferenciação e decisão de investimento

Data: 11/10/2026. Estado: **protocolo proposto; nenhum experimento executado**.

Este protocolo antecipa a pergunta decisiva: **o agente com xrai resolve mais tarefas corretamente que alternativas fortes, com aumento de custo proporcional e limitado?** Por decisão do usuário, **qualidade é o objetivo primário; economia é secundária**. M0 procura um sinal; M1-A tenta confirmá-lo antes de financiar a alpha completa em M1-B. Uma ferramenta funcional, um grafo maior ou respostas menores não bastam para liberar M2/M3.

Os IDs e dependências estão no [plano de implementação](PLANO-DE-IMPLEMENTACAO.md). Invariantes, contabilidade e testes detalhados continuam no [plano de validação](PLANO-DE-VALIDACAO.md). Os limiares abaixo são decisões de produto propostas, não resultados nem previsões.

A orientação de qualidade e a separação arquiteto/implementador foram definidas pelo usuário. Os números de ganho/custo são parâmetros iniciais propostos pela arquitetura, a congelar antes da confirmação. A orientação anterior que permitia aprovar a tese somente por economia está substituída. [Instruções para a IA implementadora](../IMPLEMENTADOR.md).

**Plataformas do v1: Linux x86_64 e macOS arm64**, conforme [ADR 020](decisoes/PLATAFORMAS-V1.md). Fixar antes de cada campanha a plataforma primária, hardware e ambiente de todos os braços comparáveis. A confirmação estatística não precisa ser duplicada integralmente por SO: testes funcionais e de portabilidade são obrigatórios nos dois alvos; conclusões competitivas ficam limitadas ao ambiente medido. Comparador que exige outro ambiente recebe regime separado e limitação explícita, sem ser omitido por conveniência. Windows e outras arquiteturas não bloqueiam G0/G1/G2; limiares, amostras, comparadores e tetos de custo permanecem inalterados.

## 1. Investimento por etapas

| Etapa | Pergunta | Investimento autorizado pelo resultado |
|---|---|---|
| M0, decisão G0 | Existe sinal repetido de vantagem e um mecanismo plausível que o explique? | Somente a confirmação limitada de M1-A |
| M1-A, decisão G1 | A vantagem resiste a concorrentes fortes, dados reservados e custo completo? | Engenharia da alpha em M1-B e próximo pacote delimitado de M2/M3 |
| M1-B, decisão G2 | O produto integrado preserva o resultado e cumpre confiabilidade/distribuição? | Disponibilizar alpha e executar o pacote aprovado; expansão continua condicionada a evidência |

Passar nos spikes técnicos não implica passar em G0/G1. Falhar num experimento encerra ou redireciona aquela hipótese; não demonstra impossibilidade teórica de construir algo melhor.

Antes das execuções, registrar teto de dias-pessoa para M0 e M1-A, orçamento de uso de modelos, limite de runs e responsável pela decisão. Os valores monetários e de equipe dependem de recursos ainda não definidos; são campos obrigatórios do protocolo executável. Este plano não autoriza consumo ilimitado nem promete calendário. M0 permite no máximo duas versões experimentais por hipótese; M1-A permite uma campanha reservada e uma campanha adicional com dados novos. Exceder esses limites exige nova decisão explícita, com evidência do que mudou.

Dimensionar o custo da própria prova: `runs = tarefas × braços × repetições`. Por exemplo, 32 tarefas × sete braços (quatro variantes xrai, dois concorrentes e baseline) × duas repetições são 448 runs no piloto; 120 × quatro braços × duas repetições são 960 runs na confirmação principal. São exemplos de carga planejada, não execuções feitas. Segundo modelo, ablations reservadas, modos enriquecidos e triagem acrescentam runs e precisam caber no orçamento. Reduzir escopo antes de congelar o protocolo é preferível a omitir custos ou interromper seletivamente braços após observar perdas.

## 2. Dois protótipos que antecipam M2/M3

### P2 — Resolução semântica delimitada, de M2

Implementar regras gerais para os recortes abaixo. Não construir quatro type checkers completos. A representação comum carrega definição, uso, condição de configuração, evidência, candidatos e motivo de não resolução.

| Família | Primeiro recorte autônomo | Limite explícito |
|---|---|---|
| Rust | Módulos, `use`/`pub use`, shadowing, `cfg` conhecido e método inerente com receptor concreto demonstrável | Macro não expandida, dispatch por trait e inferência insuficiente permanecem desconhecidos/candidatos |
| TS/JS | Imports, aliases, reexports/barrels, escopo lexical e resolução de caminhos para configurações contratadas | Mistura CJS/ESM não suportada, export condicional ambíguo, objetos dinâmicos e inferência ampla não viram fatos |
| Python | Imports estáticos absolutos/relativos, aliases e bindings locais; receptor quando explicitamente demonstrável | Não importar módulos; decorators, monkey patching e import dinâmico preservam lacunas |
| Go | Packages/imports, seletores, métodos de tipo nomeado conhecido e build tags fornecidas | Interface dinâmica, reflection e cgo não são reduzidos a alvo único |

Entrada: bytes e configuração capturados, sem executar o projeto. Mudança de configuração ou novo export deve reavaliar também resoluções antes ausentes. Compilador/LSP/SCIP pode ajudar o **avaliador** a conferir o oracle; seu resultado não entra clandestinamente no braço autônomo.

Aceite técnico: zero promoção indevida de candidato/unknown a fato nas fixtures contratadas; resolução correta de pelo menos 80% dos casos rotulados como resolvíveis dentro desse recorte. Reportar separadamente cobertura no universo completo e precisão/recall em projetos reais, para impedir que abstenção generalizada pareça precisão útil. Nenhuma regra usa nomes de tarefas, paths de referência ou patches esperados.

### P3 — Contexto orientado à tarefa, de M3

Consumir léxico, fatos de P2 e dois snapshots fornecidos pelo harness. Prototipar:

1. Obrigações derivadas da tarefa e das relações disponíveis: implementação, contrato, consumidor afetado e teste pertinente quando identificável.
2. Base/head para recuperar consumidores de contratos removidos; os dois estados podem ser diretórios capturados, sem implementar toda a integração Git.
3. Seleção conjunta de assinatura/trecho/símbolo/arquivo com deduplicação, orçamento, omissões explícitas e expansão sob demanda pelo agente.

Medir a curva de qualidade com orçamentos de 2 mil, 4 mil, 8 mil, 16 mil e 32 mil tokens, além de extremos técnicos. A configuração candidata pode usar mais contexto e expansões quando isso aumenta sucesso dentro dos limites de sessão/custo; 4 mil tokens não é um teto universal do produto. Comparar com ranking lexical/estrutural de mesmo orçamento e, separadamente, com uso natural do agente. O oracle de evidência necessária fica exclusivamente no avaliador: obrigações inferidas pelo produto não equivalem ao conjunto completo de necessidades reais.

Aceite técnico: bytes/revisões corretos, resposta inteira contabilizada e insuficiência explícita quando obrigações identificadas não cabem. Medir também necessidades que o seletor **não identificou**. Recomendação de testes pode entregar evidência; o protótipo não autoriza dispensar a suíte de validação da tarefa.

Ficam fora da prova inicial: parser próprio, type checker universal, embeddings obrigatórios, memória de investigação, recibos de sessão, slicing profundo e catálogo extenso de frameworks. Só antecipar outro componente se um erro medido bloquear a hipótese principal e uma ablation justificar o investimento.

## 3. Corpus e isolamento da avaliação

| Conjunto | Tamanho inicial | Uso |
|---|---|---|
| D0 — desenvolvimento | 20 tarefas, cinco por família | Contratos, smoke, replay e triagem de ferramentas |
| D1 — desafios de desenvolvimento | 32 tarefas, oito por família; pelo menos dois repositórios por família | Ajustar protótipos, comparar finalistas e decidir G0; nunca alegar confirmação estatística |
| H1 — confirmação reservada | Proposta inicial de 120 tarefas, 30 por família | Decidir G1; tamanho final fixado antes de abrir resultados |
| H2 — campanha adicional | Até o teto total pré-registrado | Uma única extensão/replicação com tarefas novas, se necessária; sem ajuste retroativo de H1 |

Em D1, cada família contribui com duas correções que exigem seguir relações, duas mudanças de contrato, duas tarefas após alteração/configuração, uma revisão por diff e um controle simples. Revisão recebe orçamento de falsos positivos e oracle próprio. TS e JS têm tarefas reais; TSX/JSX também aparecem nas fixtures. Tarefas pequenas continuam no relatório para revelar overhead.

H1 mantém estratos de linguagem e tarefa definidos antes dos resultados, com pelo menos três repositórios por família, dois deles ausentes de D0/D1. Separar também linhagens de mudanças e patches semelhantes. Se não houver dados suficientes, reduzir explicitamente o domínio da conclusão; não preencher o conjunto com duplicatas sintéticas. Fixtures não contam como tarefas reais independentes.

Usar D1 para estimar variância, discordância pareada e efeito de agrupamento por repositório. Simular o tamanho necessário para detectar ganho de sucesso e verificar os limites de custo. **120 tarefas não garantem potência suficiente para confirmar a vantagem.** O teto proposto de H1 + H2 é 240 tarefas únicas; se a potência necessária exceder o teto ou o orçamento financeiro, reformular o experimento antes de abrir H1 ou registrar que a confirmação não é viável neste ciclo. A dimensão da amostra não deve ser escolhida após observar um resultado favorável.

Congelar commit/configuração do xrai, concorrentes, modelos, prompts, budgets, política de retries, pesos dos estratos, análise e critérios antes de H1. Os avaliadores mantêm patches, testes ocultos e rótulos fora das entradas. Avaliar todos os braços em checkouts e sessões isolados; executar builds/testes para julgar a tarefa é função do harness, distinta da indexação autônoma.

## 4. Selecionar adversários fortes, sem presumir um vencedor

Triar os oito projetos do [estudo comparativo](ESTUDO-COMPARATIVO.md): Graft, trace-mcp, codebase-memory-mcp, code-review-graph, jCodeMunch, tokensave, ProjectAtlas e codegraph-mcp. Os snapshots estudados são referências; fixar versões efetivamente disponíveis na campanha e revalidar suas capacidades. Não há ranking próprio medido hoje.

| Necessidade | Candidatos a examinar primeiro, sem exclusividade |
|---|---|
| Navegação, semântica e contexto de alteração | Graft, trace-mcp, codebase-memory-mcp, tokensave |
| Contexto de revisão e impacto | code-review-graph, trace-mcp, codebase-memory-mcp |
| Recuperação econômica e progressiva | jCodeMunch, tokensave, Graft |
| Propósito e continuidade | ProjectAtlas, codegraph-mcp; manter no inventário e testar se houver capacidade pertinente ao recorte |

Procedimento:

1. Registrar instalação, modo, capacidades e limitações dos oito. Dar oportunidade de configuração conforme documentação, com esforço de ajuste limitado e registrado para todos, inclusive xrai.
2. Rodar D0 nas capacidades relevantes. Falta de suporte é registrada; não inventar suporte nem descartar um produto forte em uma só família por não cobrir as demais.
3. Comparar candidatos viáveis em D1 com agente real. Levar até duas configurações finalistas por domínio/regime para H1: incluir a de maior sucesso observado e outra forte na fronteira de qualidade/custo, quando distinta. Não excluir a melhor em qualidade apenas por ser mais cara. Fixar desempates antes da triagem, registrar exclusões e, se houver empate não resolvido, incluir o empatado ou restringir a conclusão.
4. Manter agente com `rg` + leitura seletiva como baseline competente em toda campanha. Diff + arquivos completos é somente referência de volume.

Cada configuração é um braço fixo. Se diferentes ferramentas forem usadas por classe, publicar uma política de escolha aplicável antes de conhecer a solução. Não usar o melhor resultado de cada concorrente em cada tarefa como se fosse uma ferramenta real. Comparar xrai contra cada finalista, além da baseline textual; uma vitória contra um finalista fraco não compensa derrota contra outro forte.

Dois regimes separados:

- **Local com entradas comuns:** mesmos fontes, configs e documentação; sem enriquecimento semântico externo. Dependências de instalação dos concorrentes são registradas, não motivo automático para excluí-los. A exigência de executável autônomo aplica-se à entrega do xrai.
- **Melhor configuração documentada:** permitir o enriquecimento que a ferramenta usa, incluindo LSP/SCIP/modelos. Oferecer os mesmos artefatos de entrada aos braços capazes de consumi-los, atribuir custos completos e identificar assimetrias remanescentes. Ganho nesse regime não prova a mesma capacidade no núcleo autônomo.

Escolher o regime primário antes de H1. Incluir em M1-A um desafio separado contra a melhor configuração enriquecida relevante e reportar seu resultado, mesmo quando o primário for autônomo. Se ela vencer, explicitar que a liderança de qualidade geral não foi demonstrada. Conveniência/eficiência local, sozinha, não libera a tese atual; um domínio com ganho de qualidade confirmado ainda pode justificar foco. Não anunciar liderança geral comparando só modos rápidos dos adversários.

## 5. Atribuir o ganho ao componente correto

| Variante xrai | Semântica P2 | Seleção P3 |
|---|---|---|
| A | Não | Não: recuperação lexical/estrutural competente |
| B | Sim | Não |
| C | Não | Sim, usando relações estruturais disponíveis |
| D | Sim | Sim |

Mesmos fontes, candidatos iniciais, limites e interfaces onde aplicável. Primeiro medir relações e evidências em replay; depois executar tarefas com agente e follow-ups. Uma comparação adicional mantém o orçamento de resposta igual para isolar qualidade; a principal permite escolhas naturais do agente e mede a sessão completa.

Executar as quatro variantes em D1; antes de H1 congelar a variante candidata. Pré-selecionar em H1 um subconjunto estratificado para ablations, sem escolhê-lo pelos erros ou vitórias observados. Remover P2/P3 deve permitir observar se o ganho depende deles; se A já produzir o mesmo resultado, adotar a solução mais simples e retirar a justificativa de investimento no componente mais caro.

Pelo menos duas execuções independentes por tarefa e braço na campanha principal, com seeds quando disponíveis. Repetições medem variabilidade do agente; não multiplicam o número de tarefas independentes. Usar mesmo modelo, versão, prompt de tarefa, permissões, ferramentas de edição/teste, limites de tempo e retries. As orientações próprias de uso das ferramentas permanecem documentadas e entram no custo. Não compartilhar transcript/cache de resposta de um braço com outro.

## 6. Métricas e limiares de decisão

Definir sucesso por tarefa antes da execução: comportamento correto, testes independentes e ausência de regressão relevante; em revisão, defeitos reais e falsos positivos avaliados de forma cega. Compilação isolada ou parecer de outro LLM não basta. Falha de ferramenta e timeout durante uma tarefa contam; pane comum do ambiente só permite invalidar o bloco pareado inteiro segundo regra prévia.

- `S`: fração de tarefas concluídas corretamente, agregando repetições sem inflar a amostra.
- `C`: custo total de **todas** as tentativas, inclusive falhas, dividido pelo número de sucessos; se não houver sucesso, não é zero.
- `A`: custo médio por tentativa; ajuda a interpretar ganho de qualidade sem esconder maior gasto.
- `T`: tempo total até conclusão e suas caudas; separar instalação/indexação fria e uso quente.

Ordem de decisão: cumprir invariantes de correção; aumentar `S` com evidência; manter `A` e `C` dentro dos limites; depois otimizar latência, chamadas e tokens. Não maximizar apenas `S/C`, pois essa razão pode favorecer uma variante barata que resolve menos tarefas. Entre variantes de qualidade indistinguível, preferir a mais simples/barata; variante mais cara precisa de ganho adicional medido e relevante. Publicar também custo e ganho marginais entre variantes xrai, para não justificar grande gasto por diferença pequena só porque ambas vencem a baseline. Otimização de tokens que reduz sucesso não é melhoria por si só.

Contar modelo de entrada/saída/cache, schemas e instruções, ferramentas, expansões, novas leituras, retries e enriquecimento. Publicar recursos de indexação/manutenção e monetizar somente com taxa defensável. Congelar como cenário primário a amortização por 100 tarefas por checkout; mostrar também 1, 10 e 1.000. Se a frequência real prevista for diferente, alterá-la **antes** da campanha. Eficiência de tokens sozinha não equivale a economia financeira.

Os limites propostos são relativos a cada comparador: até **25% mais custo por tentativa** e até **15% mais custo por sucesso**, além do ganho mínimo de qualidade. São tetos simultâneos, não metas de gasto. Separar custos operacionais de esforço de desenvolvimento/manutenção; os percentuais não autorizam despesas nem aumento ilimitado da equipe.

Exemplos aritméticos hipotéticos, sem constituir resultados: sucesso de 60% para 68% com custo por tentativa +20% produz custo por sucesso aproximadamente +5,9% e atende aos limites pontuais de G1. De 60% para 62% com o mesmo gasto não atende ao ganho mínimo e aumenta custo por sucesso em cerca de 16,1%. De 60% para 72% com custo por tentativa +50% também ultrapassa os tetos, apesar do ganho de qualidade. Intervalos, replicação e demais critérios ainda precisam ser cumpridos no primeiro exemplo.

### G0 — sinal suficiente para financiar M1-A

Nas 32 tarefas D1, contra os finalistas relevantes e a baseline textual, cumprir simultaneamente:

| Medida | Sinal exploratório exigido |
|---|---|
| Qualidade | Pelo menos +10 pontos percentuais em `S` |
| Custo proporcional | Razão pontual de `A` ≤1,25 e de `C` ≤1,15 |

Além da média: benefício presente em pelo menos duas famílias e em dois repositórios de cada uma; falhas e dispersão publicados; ablation explica o mecanismo; nenhuma falha crítica pendente. Ganho só em controles fáceis, só em fixtures, só contra leitura integral ou só no payload não passa. Se apenas um domínio estreito mostrar sinal, a decisão é **focar**, com nova hipótese explícita, sem liberar expansão ampla.

G0 é uma decisão exploratória, sem alegação de significância. Cumpridos o sinal e os spikes técnicos, preparar H1 com **qualidade como única rota primária**. Economia sem melhora de sucesso é achado secundário e não satisfaz G0/G1. Não mudar a tese após olhar o resultado reservado para converter uma falha de qualidade em vitória de custo.

### G1 — confirmação antes da engenharia ampla

Intervalos de confiança de 95% conforme análise pré-registrada, respeitando pares, repetições e agrupamento por repositório. Ajustar comparações/olhadas múltiplas; validação por simulação é necessária com poucos repositórios. Bootstrap degenerado com todos os resultados iguais não pode produzir falsa certeza. Publicar resultados por família, classe, repo e configuração, além do agregado ponderado fixado antes da execução.

| Critério simultâneo | Exigência proposta contra cada finalista relevante e a baseline competente |
|---|---|
| Sucesso | Ganho pontual de `S` de pelo menos **8 pp**, com limite inferior do intervalo da diferença acima de zero |
| Custo por tentativa | Limite superior do intervalo da razão de `A` no máximo **1,25** |
| Custo por sucesso | Limite superior do intervalo da razão de `C` no máximo **1,15** |

Esses critérios confirmam uma vantagem de qualidade e exigem tamanho de efeito pontual relevante; não afirmam que todo o intervalo assegura ganho de 8 pp. Uma alegação desse tamanho mínimo exigiria intervalo inteiramente acima de 8 pp. Queda de custo não compensa falha no critério de sucesso. Mesmo +8 pp com custo muito maior não libera expansão; registrar a fronteira observada para uma eventual nova decisão de produto, sem afrouxar o protocolo após os resultados.

Guardrails adicionais: nenhum erro crítico conhecido de fonte/revisão, execução indevida na indexação ou omissão disfarçada; nenhum estrato de linguagem com queda pontual maior que 5 pp em `S`; tempo p95 total no máximo 20% maior no cenário primário. Nas tarefas de revisão, teto proposto de aumento pontual de 0,1 falso positivo por tarefa, com intervalos reportados e definição congelada antes de H1. Intervalos amplos por linguagem limitam a conclusão: média favorável não comprova liderança nas quatro famílias.

O benefício deve reaparecer em pelo menos duas famílias e dois repositórios novos de cada uma. Repetir um subconjunto congelado de pelo menos 20 tarefas, cinco por família, com um segundo modelo/agente e os mesmos adversários; é verificação de direção e integração, não uma segunda prova estatística. Se houver inversão material, restringir a tese ao cliente/modelo validado ou usar H2 para investigar.

### G2 — produto preserva a vantagem

M1-B reexecuta os testes e cenários congelados no produto integrado. Dados já vistos agora são regressão, não novo holdout. A candidata precisa manter os critérios funcionais, o ganho pontual de sucesso e os tetos/guardrails de G1; diferenças de custo/qualidade em relação ao protótipo recebem relatório próprio. Se a integração perder o ganho, não liberar automaticamente M2/M3. Mudança material no algoritmo/modelo exige nova confirmação em dados ainda reservados.

## 7. Continuar, focar, estender ou encerrar

| Decisão | Condição | Ação |
|---|---|---|
| Continuar | G1 confirmado no domínio primário, mecanismo explicado e guardrails cumpridos | M1-B e pacote limitado dos componentes que geraram ganho; definir custo de manutenção por frontend |
| Focar | Vantagem concentrada em linguagem/tarefa/regime | Reduzir investimento semântico ao domínio; achado pós-hoc exige H2 novo antes de ser tratado como confirmação |
| Simplificar/redirecionar | Seletor ganha, resolver não; índice externo equivale; variante simples vence | Priorizar seletor, integração ou frontend específico; adiar componente sem ganho marginal |
| Não aprovar pela tese atual | Só há economia, ganho de sucesso abaixo do mínimo ou custo acima dos tetos | Registrar utilidade e fronteira observada; não liberar M1-B sem nova decisão de produto e confirmação pertinente |
| Inconclusivo | Intervalo não decide, instalação de adversário importante falhou ou orçamento de confirmação não cabe | Uma extensão dentro do teto, com método sequencial previamente definido; caso contrário encerrar o ciclo sem liberar engenharia ampla |
| Encerrar a tese atual | Nas duas versões de M0 não há sinal repetido; ou H1/H2 exclui ganho útil/mostra dominância dos concorrentes; ou invariantes seguem violadas após correção limitada | Arquivar o resultado reproduzível; não financiar a sequência completa sob a mesma hipótese |

“Não significativo” não demonstra equivalência. Para concluir ausência de ganho material, observar se os intervalos excluem o limiar economicamente útil, junto das demais métricas. Ainda assim, o investimento pode ser encerrado por evidência insuficiente dentro do orçamento; a conclusão deve dizer exatamente isso, sem alegar impossibilidade técnica.

H2 tem finalidade escolhida e registrada antes de abrir seus dados: extensão de hipótese congelada, confirmação de um foco descoberto ou replicação. Não usá-lo sucessivamente para todos esses fins. Se a análise sequencial não tiver sido pré-registrada, H2 é confirmação independente com controle de multiplicidade, não soma oportunista até obter significância.

## 8. Entregáveis da decisão

- `eval/protocol.toml`: escopo, rota, estratos/pesos, comparadores, commits, custos, teto de esforço/runs, amostra, análise e política de continuação.
- `eval/competitors/`: instalação/configuração, modos tentados, resultados da triagem e motivos de inclusão/exclusão.
- `eval/results/`: registros por tarefa/braço/run, pacotes e usage; dados ausentes explicitamente marcados.
- `eval/reports/m0-exit.md`, `m1-proof.md` e `m1-exit.md`: critérios, intervalos quando aplicáveis, perdas, ablations e decisão G0/G1/G2.
- Backlog revisado: componentes que ganharam, custo incremental de mantê-los, lacunas ainda não comprovadas e próximo experimento capaz de refutar a aposta.

Esses caminhos são entregáveis futuros. O resultado desejado deste ciclo é uma decisão justificável, inclusive se for não continuar construindo o xrai na forma originalmente proposta.
