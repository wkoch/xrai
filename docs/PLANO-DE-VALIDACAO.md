# Como demonstrar que o xrai ajuda

Data: 12/10/2026. Este documento contém **experimentos e metas propostas**, não resultados obtidos.

O [plano de implementação](PLANO-DE-IMPLEMENTACAO.md) antecipa a prova competitiva: M0 testa sinal e mecanismo; M1-A confirma em dados reservados antes da engenharia ampla; M1-B verifica se a alpha preserva a vantagem. O [protocolo de diferenciação](PROVA-DE-DIFERENCIACAO.md) é a referência para amostras, comparadores, limiares e decisões G0/G1/G2. Os spikes e dados de desenvolvimento não comprovam superioridade estatística.

**Matriz obrigatória do v1: Linux x86_64 e macOS arm64**, desde os spikes M0 até a distribuição. A [decisão do usuário / ADR 020](decisoes/PLATAFORMAS-V1.md) posterga Windows e outras arquiteturas. Ambos os alvos precisam de provas nativas de parsing/autonomia, SQLite, workers, filesystem e CLI/MCP nas tarefas correspondentes; cross-build não substitui execução. Falta de evidência em qualquer um dos dois mantém o critério pendente.

## 1. Hipótese principal

O agente com xrai resolve **mais tarefas corretamente**, com aumento de custo proporcional e limitado. Qualidade é a única rota primária, definida pelo usuário. Economia e menor latência são métricas secundárias; não substituem resultado primário negativo. A vantagem precisa sobreviver a consultas adicionais, erros, repetições e manutenção do índice. Os tetos numéricos são propostas iniciais da arquitetura.

Separar três perguntas:

1. O índice descreve corretamente o que foi analisado?
2. O seletor entregou as evidências relevantes, sem omissões disfarçadas?
3. O agente concluiu corretamente a tarefa com menor custo?

Melhorar uma não prova automaticamente as outras.

## 2. Corpus

Começar com D0: 20 tarefas de desenvolvimento para ajustar o harness, distribuídas por Rust, TS/JS, Python e Go. Acrescentar D1: 32 desafios reais, oito por família e pelo menos dois repositórios por família, incluindo correção, contrato, revisão, mudança de configuração/estado e controles simples. Não usar D0/D1 para anunciar vitória estatística.

A revisão L1 aceita as 32 propostas atuais como D1-seed para desenvolvimento. M0-03.R1 precisa cumprir a [admissão do ADR 021](decisoes/CORPUS-QUALIFICADO.md) antes de M0-12: porte/complexidade, proveniência, prompts sem pistas artificiais, testes independentes, revisão dos rótulos e eventos com índice aquecido. Seed e fixtures não aumentam a amostra primária. H1 herda pelo menos metade de casos complexos por família, com novidade em relação a todos os conjuntos de desenvolvimento.

Preparar H1 reservado **para M1-A**, inicialmente 120 tarefas, 30 por família, pelo menos três repos por família, dois ausentes de D0/D1. Dimensionar a amostra conforme variância, discordância pareada, agrupamento e hipótese pré-registrada; 120 não garante potência para confirmar ganho de sucesso e limites de custo. O protocolo propõe teto H1+H2 de 240 tarefas únicas e uma só campanha adicional, limitada por esforço/custo registrados antes de executar. Separar repositórios, linhagens de mudanças e patches semelhantes para reduzir vazamento.

| Classe | O que exige |
|---|---|
| Localização | Encontrar definição ou configuração sem abrir o projeto inteiro |
| Compreensão | Explicar comportamento com fontes corretas |
| Correção | Alterar implementação e passar testes relevantes sem regressão |
| Mudança de contrato | Encontrar consumidores, testes e adaptações necessárias |
| Revisão | Identificar defeitos reais e limitar falsos positivos |
| Fluxo entre linguagens | Relacionar cliente, contrato e implementação |
| Estado em edição | Responder corretamente depois de alteração, rename e checkout |
| Configuração | Interpretar features, aliases, build tags e manifests |
| Seleção de testes | Priorizar testes relevantes e reconhecer quando não pode justificar omissões |
| Continuidade | Retomar investigação após compactação ou mudança de worktree sem herdar fatos incompatíveis |

Corpus sintético cobre cantos difíceis; corpus real mede utilidade. Incluir funções grandes, arquivos pequenos, código incompleto, monorepos, nomes homônimos, callbacks, traits/interfaces, macros, decorators, módulos condicionais e dependências externas ausentes.

Nem todas as classes da tabela entram como compromisso de produto em M0/M1: continuidade, fluxo entre linguagens e seleção que permite omitir testes continuam posteriores. Os protótipos antecipam semântica delimitada e contexto base/head nas tarefas de correção/revisão. O agente pode executar testes para resolver a tarefa; o indexador continua sem executar código do projeto.

Candidatos a repositórios serão selecionados por licença, diversidade e facilidade de reproduzir testes. Congelar commits. Preferir mudanças posteriores aos dados usados para ajustar o ranker quando possível. Não fornecer patch de referência, arquivos alterados pelo autor ou testes ocultos ao agente, exceto quando fazem parte natural da tarefa e estão disponíveis igualmente em todos os braços.

## 3. Bases de comparação

| Braço | Objetivo |
|---|---|
| Agente com busca textual e leitura seletiva | Base principal: comportamento competente sem índice |
| Diff + arquivos completos | Referência simples para volume; não representa toda exploração real |
| Graft, versão fixada | Comparar experiência/configuração documentada |
| trace-mcp, versão fixada | Comparar recuperação composta e semântica disponível |
| codebase-memory-mcp | Cobertura declarada, impacto e seleção de testes; modos separados |
| code-review-graph | Contexto de revisão, mudanças, fluxos e incerteza |
| jCodeMunch | Navegação progressiva, fonte por símbolo e custo entre chamadas |
| tokensave | Núcleo Rust, contexto, robustez de extração e operação contínua |
| ProjectAtlas | Navegação por propósito e continuidade entre worktrees |
| codegraph-mcp | Sessões de investigação, compactação e memória atribuída |
| xrai estrutural | Medir valor sem resolvers avançados |
| xrai com semântica | Medir ganho dos resolvers e das evidências |
| xrai com seleção avançada | Medir custo/qualidade do planner |

Comparar em dois regimes: local com fontes/configuração comuns, sem enriquecimento externo, e melhor configuração documentada/enriquecida. No segundo, registrar LSP, SCIP, modelos e dependências disponíveis, oferecendo os mesmos artefatos aos braços capazes de usá-los. Dependência runtime de um concorrente é custo operacional, não motivo automático para removê-lo da comparação de qualidade. A autonomia de binário é requisito da entrega xrai. Não comparar modos diferentes sem informar a assimetria e limitar a conclusão.

Mesmo agente, modelo e versão, prompt, limites, checkout e ferramentas de edição/teste em cada par. Alternar ordem, separar sessões e executar repetições conforme variância. Registrar falhas de instalação e setup, sem apagá-las dos resultados operacionais.

Testar integração real por CLI/MCP, incluindo descoberta e follow-ups. Contexto pré-montado é um experimento útil, mas não substitui avaliar a escolha de ferramentas pelo agente.

Triar os oito já em M0, escolhendo finalistas por qualidade/custo observado em D0/D1 e capacidade pertinente. Incluir a configuração com maior sucesso observado e outra forte na fronteira de qualidade/custo quando distinta; não excluir a melhor qualidade por preço alto. Não presumir que um projeto é o melhor por sua descrição. Fixar finalistas por domínio/regime antes de H1; empate sem resolução pede inclusão ou conclusão mais restrita. O protocolo define ajuste limitado, exclusões justificadas e comparação com cada finalista, sem escolher o vencedor por tarefa depois de conhecer a solução. Modos fortes e enriquecidos relevantes entram na campanha; um modo rápido fraco não representa todo o concorrente.

Usar as integrações documentadas de cada produto e registrar seu tamanho/custo. Separar uma execução com política de ferramentas controlada de outra com uso natural pelo agente. Isso identifica se o ganho vem do índice, da montagem de contexto ou da orientação que evita chamadas desnecessárias. O estudo dos concorrentes não substitui executar esse harness.

## 4. Métricas

| Camada | Métricas |
|---|---|
| Indexação | Arquivos elegíveis, processados, ignorados, erros, duração, RSS máximo e tamanho em disco |
| Semântica | Precisão/recall por relação e linguagem; candidatos ambíguos; referência externa versus não resolvida |
| Atualização | Tempo até visibilidade, escopo invalidado e equivalência com rebuild completo |
| Recuperação | Recall de evidência relevante, ruído, cobertura das obrigações, perda por truncamento e custo por representação |
| Agente | Tarefas resolvidas, regressões, explicações corretas, defeitos detectados e falsos positivos |
| Operação | Tokens por sessão, custo, chamadas, latência p50/p95, tempo de instalação e manutenção do índice |
| Testes | Recall dos testes que revelam regressões, suíte ampliada por incerteza e omissões injustificadas |
| Worktrees | Reuso de extração, custo de hidratação e mistura indevida de fatos/recibos entre checkouts |

Precisão exige rotulagem ou oracle adequado; contagem de arestas não basta. Compiladores/SCIP/LSP servem como referências dentro das configurações suportadas, com amostragem manual para discrepâncias. A solução oficial de uma issue não é o único patch correto, nem todos os seus arquivos são obrigatórios numa solução alternativa.

Qualidade funcional: testes existentes, testes independentes para o comportamento esperado e avaliação cega quando apropriada. Julgamento por modelo é sinal auxiliar, com protocolo fixo e inspeção humana de amostra; não é a única definição de acerto.

Medir separadamente: símbolo localizado, assinatura entregue, trecho entregue e corpo completo entregue. Medir também pertinência e desempenho final: um corpo completo desnecessário pode ser desperdício, enquanto um contrato curto pode ser indispensável.

## 5. Contabilidade honesta

```text
custo operacional por tarefa =
  uso medido do modelo em todas as rodadas
  + enriquecimento opcional
  + parcela declarada de indexação/manutenção

custo por sucesso = custo de todas as tentativas / tarefas resolvidas
```

Reportar custo de infraestrutura separadamente quando não houver conversão monetária defensável. Não misturar segundos de CPU com tokens numa unidade inventada.

Publicar cold start e índice quente. Amortizar por quantidade explícita de tarefas e mostrar a curva de ponto de equilíbrio; um índice caro pode não se pagar em uso pontual.

Para G1, o cenário primário proposto é 100 tarefas por checkout, com sensibilidade em 1, 10 e 1.000. Congelar esse cenário antes dos resultados. Contar todos os runs, inclusive falhas; reportar também custo por tentativa para separar aumento de qualidade de aumento de gasto. Repetições do mesmo problema não são novas tarefas independentes.

Incluir schema MCP, snippets de integração, prompts de ferramenta, resultados repetidos, follow-ups e saída do modelo. Registrar tokens de cache e seus preços separadamente. Contagem exata usa tokenizer identificado; modelos sem tokenizer local entram como estimativa, confrontada com usage real quando disponível.

Comparar JSON compacto, texto estruturado e eventuais codecs especializados no mesmo conteúdo. Publicar bytes e tokens separadamente, mais acerto de interpretação e rodadas adicionais. O percentual contra leitura integral de arquivos não deve ser tratado como economia faturada observada.

## 6. Testes que protegem a tese

| Cenário | Invariante esperada |
|---|---|
| Mesmo nome em escopos/pacotes distintos | Resolução segue bindings; nome único no repo não basta |
| Rust `flush`/`take` em receptores diferentes | Métodos homônimos não são promovidos de candidatos a chamadas confirmadas sem evidência de receptor |
| Go `make` e helper TS `make` | Não criar chamada entre linguagens sem mecanismo real |
| Alias/barrel/reexport | Uso aponta para definição compatível ou candidatos explícitos |
| Trait Rust, interface Go, callback JS | Dispatch dinâmico não vira único alvo arbitrário |
| Decorator/import Python dinâmico | Lacuna identificada; nenhum código do projeto executado |
| Conteúdo muda com tamanho/mtime preservados | Validação dos bytes detecta diferença no modo pertinente |
| Só muda manifest/feature/build tag | Invalidar resolução afetada mesmo sem mudança no source |
| Novo export satisfaz referência antes ausente | Dependência negativa provoca reavaliação |
| Arquivo removido ou renomeado | Remover fatos atuais; recibos antigos tornam-se inválidos |
| Remoção de API/contrato no head | Comparação base/head encontra consumidores do estado anterior |
| Atualização incremental aleatória | Mesmo grafo normalizado que rebuild completo da mesma entrada |
| Dois clientes e escritor simultâneo | Cada resposta usa geração e fontes coerentes |
| Watcher perde eventos ou há checkout | Reconciliação recupera; nunca afirmar atualidade global sem evidência |
| SCIP produzido para revisão/configuração diferente | Recusar promoção a fato verificado |
| Hunks após centenas de linhas | Incluir trecho relevante; não retornar somente início da função |
| Classe/módulo e membros sobrepostos | Bytes não são cobrados/enviados em duplicidade |
| Orçamento menor que requisitos identificados | Estado `insufficient_budget`, omissões e continuação explícitos |
| Resultado vazio com cobertura parcial | Não traduzir ausência no índice em ausência no programa |
| Resultado positivo com parte dos callsites não resolvida | Preservar lacunas pertinentes; não afirmar enumeração completa |
| Arquivo sem símbolos ou capacidade de chamadas | Distinguir parse válido vazio, exclusão e capacidade ausente; fallback textual rotulado |
| Parser aborta, trava ou excede recursos | Pai continua; retry limitado; arquivo aparece como falha/parcial, nunca sucesso silencioso |
| IPC entrega hash, produtor ou comprimento incompatível | Rejeitar resposta; não publicar geração como válida |
| Um cliente cancela trabalho compartilhado | Outros consumidores mantêm trabalho necessário e publicação coerente |
| JSON final, metadados e marcadores | Custo serializado respeita limite no tokenizer declarado |
| Tokenizer desconhecido | Resultado diz estimativa; não promete limite exato |
| Duas chamadas concorrentes usam orçamento da tarefa | Reservas impedem dupla alocação; sessões diferentes não compartilham saldo implicitamente |
| Compactação ou troca de agente | Não ocultar código somente porque já foi enviado |
| Fonte com instrução maliciosa | Tratar como dado; não executar nem mudar política do agente |
| Cache interrompido/corrompido | Recuperar/reindexar sem perda de notas humanas |
| Propósito ou nota de investigação fica obsoleto | Manter autoria e conteúdo; marcar revisão necessária sem promover anotação a fato |
| Worktrees com mesmo path relativo e bytes diferentes | Isolar respostas, resoluções e recibos por identidade/revisão |
| Hidratação recebe gramática/configuração diferente | Invalidar dados incompatíveis; resultado final equivale a indexação normal |
| Coverage de teste vem de revisão/configuração distinta | Não usar para justificar omissão; ampliar seleção e explicar |
| Diff/inventário de testes incompleto ou dispatch desconhecido | Recomendar suíte mais ampla; vazio não significa dispensar testes |
| CRLF, Unicode, caminhos longos, case e symlinks | Mesmo source correto e identidades não colididas |

Testes metamórficos: comparar índice incremental versus completo após sequências de operações; repetir com renames, erros sintáticos, mudanças de configuração e concorrência. Comparar o significado dos fatos, sem exigir IDs internos ou timestamps idênticos.

Persistência segue o [ADR 022](decisoes/PERSISTENCIA-E-RETENCAO.md): testar posse/epoch, dono pausado e PID reciclado, commit sem confirmação, disputa GC/pin, base/head retidos, quota com tudo pinado, FTS sem corpo duplicado por geração e ranking de A estável quando B entra/sai. Sessão ociosa e transporte lento não mantêm transação WAL indefinida. A matriz especifica quais provas pertencem a M1-04/15/16/19; decisões documentadas não equivalem à execução desses testes.

Fuzzing nos parsers/adapters, leitores de índice externo e limites de saída. Testes de integração em ambientes limpos de Linux x86_64 e macOS arm64. Não depender exclusivamente de mocks para provar filesystem, SQLite, protocolos e comportamento de processo. Unicode, CRLF, espaços, bytes nativos e case sensitivity continuam no aceite; documentar filesystem/configuração efetivamente testados. Paths UTF-16/reparse points e particularidades de processos Windows ficam pós-v1; fixtures documentais existentes não anunciam suporte runtime.

A fixture de métodos homônimos é motivada pela [checagem exploratória com codebase-memory](evidencias/CBM-TOKENSAVE-FAST.md). Usá-la como caso de regressão; não ajustar o sistema somente a esse exemplo nem extrapolar um erro para a qualidade global do concorrente.

Para seleção de testes, comparar com suíte de referência executada em mudanças com regressões conhecidas e, separadamente, mutações controladas. Medir testes que efetivamente revelam a falha e tempo da suíte; proximidade no grafo não é oracle. Omissões injustificadas em casos críticos bloqueiam promoção a modo que autoriza seleção reduzida.

## 7. Metas iniciais, sujeitas ao spike

Hardware de referência proposto: 8 núcleos lógicos, 16 GiB RAM e SSD local, com CPU/SO/temperatura de cache registrados. Conjunto de rotina de aproximadamente 1 milhão de linhas/10 mil arquivos e conjunto de stress de aproximadamente 10 milhões/100 mil arquivos. Bytes e distribuição de tamanhos também devem ser publicados.

| Alvo proposto | Condição |
|---|---|
| Lookup/inspect p95 abaixo de 100 ms | Índice quente; snapshot já publicado; símbolo de tamanho limitado |
| Busca p95 abaixo de 250 ms | Escopo de rotina e limites documentados |
| Contexto p95 abaixo de 500 ms | Sem LLM/LSP remoto; revisão pronta; orçamento de 4 mil tokens |
| Edição isolada visível em até 1 s p95 | Alteração de corpo sem grande invalidação; modo duradouro |
| Reduzir custo de contexto onde não há perda de qualidade | Métrica secundária, sem percentual mínimo obrigatório; sucesso e tetos de custo decidem o investimento |
| Nenhuma omissão obrigatória silenciosa | Invariante funcional, não média estatística |
| Nenhuma fonte servida com hash incorreto | Invariante funcional |

Esses valores orientam experimentos. Não são garantias. Publicar também latência incluindo validação/reindexação, cold start, consulta pontual e pior cauda; números de índice quente não descrevem todo o produto.

Metas de RSS, tamanho do executável e throughput de indexação serão fixadas após medir o spike das gramáticas. Medir supervisor e conjunto de workers, custo de IPC e respawn, não só RSS do pai. A execução precisa respeitar limites configuráveis; não basta obter um pico baixo numa base pequena.

Gates de investimento propostos, detalhados no protocolo:

| Gate | Evidência mínima |
|---|---|
| G0, fim de M0 | Em D1 qualificado, +10 pp em sucesso, razões pontuais de custo por tentativa ≤1,25 e por sucesso ≤1,15; sinal em duas famílias e dois repos de cada uma; ablations e invariantes; recorte complexo melhora sucesso em duas famílias dentro dos tetos |
| G1, M1-A, qualidade obrigatória | Ganho pontual ≥8 pp em sucesso, limite inferior do intervalo da diferença acima de zero |
| G1, M1-A, custo limitado simultaneamente | Limites superiores dos intervalos das razões: custo por tentativa ≤1,25 e por sucesso ≤1,15 |
| G2, fim de M1-B | Produto integrado preserva ganho pontual de sucesso e tetos/guardrails de G1, com invariantes e distribuição cumpridas |

Usar intervalos de 95%, pares e agrupamento por repo, com tratamento pré-registrado de múltiplos comparadores/olhadas. O limiar pontual de 8 pp não significa que todo o intervalo assegure esse tamanho de efeito. Validar o método em poucos clusters; não aceitar intervalo degenerado como certeza de superioridade. Economia isolada não libera investimento; tampouco melhora de qualidade com custo acima dos tetos.

Guardrails: zero falha crítica conhecida de fonte/revisão ou capacidade enganosa; nenhum estrato de linguagem com perda pontual >5 pp; p95 total até +20%; teto proposto de +0,1 falso positivo por tarefa de revisão. Reportar intervalos por estrato e restringir afirmações quando amplos. Benefício precisa reaparecer em famílias/repos novos e passar pela verificação de direção com segundo modelo/agente.

Inconclusivo permite uma campanha adicional dentro dos tetos, com finalidade/método definidos antes de abri-la. Sem confirmação suficiente, não liberar engenharia ampla. Não significância não prova equivalência; parar por orçamento/evidência insuficiente é uma decisão de investimento, não um teorema de impossibilidade. Falhas críticas conhecidas bloqueiam avanço mesmo com média favorável.

## 8. Experimentos para cada inovação

| Hipótese | Comparação que a pode refutar |
|---|---|
| Semântica própria melhora o acerto | Léxico + sintaxe versus resolução adicional, mesmos candidatos/tokens |
| Grafo melhora seleção | Léxico puro versus léxico + grafo, sem mudar tamanho do pacote |
| Obrigações evitam perda importante | Top-k/percentuais versus cobertura conjunta, em vários orçamentos |
| Slicing oferece ganho | Símbolo inteiro versus trecho AST versus slice, avaliando acerto e follow-ups |
| Embeddings ajudam conceitos | Canal desativado versus ativado, com perguntas bilíngues e aliases |
| Resumos ajudam navegação | Sem resumo versus resumo atribuído, incluindo custo e casos obsoletos |
| Recibos reduzem repetição | Sessão sem delta versus delta, com compactação forçada |
| Hash/derivação melhoram confiabilidade | Mesma tarefa após sequência de edições e mudanças de ambiente |
| Propósito ajuda a localizar responsabilidade | Mapa estrutural versus propósito atribuído, incluindo notas obsoletas e custo de curadoria |
| Grafo base/head recupera impactos perdidos | Mesmo diff consultado só no head versus ambos os estados |
| Seleção de testes reduz esforço sem perda indevida | Suíte ampla versus seleção com evidências, incluindo relações desconhecidas |
| Workers contêm falhas com custo aceitável | Pool de processos versus threads, falhas injetadas, latência e memória agregada |
| Hidratação ajuda worktrees | Índice frio por checkout versus snapshot compatível + reconciliação |
| Memória de investigação evita repetição | Sessões sem memória versus notas atribuídas, incluindo resultados incorretos e código alterado |

Em M0/M1-A, priorizar A: estrutural; B: +P2; C: +P3; D: P2+P3. Fixar a candidata antes de H1 e o subconjunto reservado de ablations antes de ver seus resultados. Antecipar essas provas não exige completar todos os recursos desta tabela.

Publicar curvas qualidade × tokens × latência. Quando a leitura de um arquivo pequeno ganhar, o seletor deve poder escolhê-la. Não tentar forçar um ganho de compressão em toda consulta.

## 9. Artefatos de um resultado reproduzível

Manifest com commits, versões, configurações, hardware, modelos, tokenizers e seeds; descrição das tarefas; orçamento e política de retries; resultados por tarefa; uso completo; falhas; scripts de execução; testes; saídas rotuladas; hashes dos pacotes entregues e critérios definidos antes da avaliação.

Uma linha de resultado deve permitir investigar: o agente errou por relação falsa, ausência de evidência, truncamento, leitura incorreta ou implementação ruim? Sem essa classificação, melhorar o ranker pode mascarar um defeito no resolver.

Relatórios G0/G1/G2 distinguem conclusão experimental, liberação de investimento e declaração pública. Relatório negativo também é entrega válida; não satisfaz um gate de avanço. Dados de H1 vistos na integração da alpha viram regressão e nunca são reapresentados como nova confirmação independente.

Só anunciar superioridade no domínio que os dados sustentarem. O objetivo de longo prazo é amplo; a evidência precisa continuar específica.


## 10. Provas acrescentadas pela revisão L2

[ADR 023](decisoes/EXECUCAO-E-CAPTURA.md) define os contratos; [L3](relatorios/REVISAO-L2.md) define incrementos. Estas provas são planejadas, sem resultados novos nesta revisão.

| Cartão | Oráculo e falhas obrigatórias | Limite da conclusão |
|---|---|---|
| M0-04.R1 | Setsid/double fork, pipes, morte do pai, dois braços e teardown; sentinela/controle positivo; falha impede reutilização | Timeout do avaliador não prova encerramento de descendentes. Linux e macOS têm mecanismos distintos; VM/runner é só avaliação. |
| M0-06 | Roundtrip direto/pool, identidade de tentativa/hash/configuração, framing/overflow/limites, abort/hang/resposta tardia, progresso independente | Mesmo binário e contenção de falhas; não prometer sandbox completo ou limite rígido de RSS sem prova do SO. |
| M0-08.R1 | Captura e enumeração por handles; barreiras nas trocas de ancestrais/raiz, symlink externo, crescimento e reconciliação | Hash dos bytes não prova árvore global atômica. Binding alterado não publica fonte como atual; modelo de rename/hard link/mount documentado. |
| B05/B06 condicionais | Reproduções reais, alternativas, testes diferenciais, recuperação, fuzz e incremental/rebuild | [ADR 024](decisoes/BIBLIOTECAS-PROPRIAS.md): complexidade não impede experimento; promoção depende de evidência e gates do produto. |

Preservar logs históricos e os estados parciais de L2. Antes de campanha, readiness inclui contenção, corpus qualificado, tokenizer/modelo e orçamento; falta de um deles bloqueia a execução correspondente e permite continuar preparação independente.


## 11. Continuação L4: semântica, persistência e contabilidade

[Revisão L3](relatorios/REVISAO-L3.md) preserva os aceites de L3 e detalha provas planejadas nos ADRs [025](decisoes/SEMANTICA-P2.md)/[026](decisoes/WORKERS-E-MEDICAO.md).

| Frente | Verificação adicional | O que não concluir pela prova |
|---|---|---|
| P2 Rust | Namespaces/escopos, alias/reexport, cfg conhecido/desconhecido, método com interferência de trait e macro; export criado invalida ausência; B incremental = rebuild B | Acerto de Rust não encerra quatro famílias; cobertura sintática não resolve chamadas; oracle não entra na IR |
| Workers | Vários pedidos na mesma encarnação, handshake, término por Result, falha Idle/Busy, consumidor lento e cancelamento; XRW1 preservado | Persistência não herda teste de EOF por pedido; cap lógico não é teto de RSS |
| Recursos | Cold/warm, fontes reais por dialeto, CPU de pai/filhos sem duplicação, série de soma RSS simultânea e sampler separado | Soma de picos individuais não é pico simultâneo; amostragem não é pico físico exato |
| Sessões | Tokenizer/serializer e projeção fixados, replay legado, fake com receipt duplicado/cache subset/cobrança desconhecida e teto concorrente | Tokens locais não são usage faturado; timeout não comprova chamada gratuita |
| Corpus | Slots por família/tipo/repo/JS/TS/complexidade; medição conservadora de produção e revisão; quatro eventos A→B | Piloto vertical aceito não é admissão global ou resultado competitivo |

Critérios numéricos de qualidade/custo e gates permanecem os do protocolo. Configurações de novos benchmarks são congeladas antes dos resultados. Testes/campanhas não foram executados por esta atualização documental.

## 12. L5: contexto/expansão e fechamento das provas restantes

[Revisão L4](relatorios/REVISAO-L4.md) e [ADR 027](decisoes/CONTEXTO-P3.md) definem as provas seguintes. Recibos L4 foram revalidados; a tabela abaixo é trabalho planejado.

| Frente | Prova exigida | Limite |
|---|---|---|
| Comparação experimental v3 | Base/head explícitos, snapshot principal=head; rejeitar terceira revisão, diff inválido, hash/config errada e expansão que troca geração; manter v2 | Verificador v2 atual não comprova comparação |
| Seleção e orçamento | Fonte/spans exatos, hunk central, alternativas/dedup, obrigações omitidas e envelope completo em bytes/tokens; metadados extensos e contadores | Obrigações próprias satisfeitas não significam todas as evidências relevantes encontradas |
| Expansão | Manifesto imutável, duas revisões retidas, item omitido expansível, item de outro contexto rejeitado, expiração e pressão de memória | Entrega anterior não prova memória atual do agente |
| Qualidade P3 | Mesmo pedido/fontes/perfil/limites nos controles; oracle isolado mede também omissões não identificadas; curvas 2k–32k | Recall de evidência não é sucesso de tarefa real |
| Rust seguinte | R3/configuração e R4, contraprovas e incremental=rebuild; amostra real com escopo de captura | Arquivo Tokio de L4 não prova crate completa |
| Recursos e corpus | Matriz direto/XRW1/XRW2, CPU/RSS dos dois alvos; quatro dossiês novos com revisão e slots globais | Persistência funcional não fecha recursos; dossiê vertical não abre D1 global |
| Adapter/smokes | Protocolo/ledger testado offline; quatro smokes pareados totais, um por família, quando houver recursos/teto | Fake e readiness não substituem uso real; oito sessões mínimas não autorizam despesa |

Verificação de produto cabe ao Implementador. Não alterar limiares dos gates, denominadores ou dados reservados para acomodar resultados.

## 13. Retomada após a primeira fatia L5

[Revisão L5](relatorios/REVISAO-L5.md) preserva as provas sintéticas e prioriza evidência real. Contratos v2/v3 e retenção já verificados são regressões a preservar, sem refazer seu desenho.

| Frente | Próxima prova | Interpretação correta |
|---|---|---|
| Corpus | Quatro dossiês com porte/módulos/setup, baseline/referência/probes e revisão | Verificador de 32 slots só comprova alocação condicional; quatro novos continuam 0/4 |
| P2 Rust | R3 com labels anteriores às regras, shadowing/configuração, eventos e rebuild B | Amostra de arquivo não é pacote; R3 não encerra quatro famílias |
| P3 | Lexical sem âncora, ranking/alternativas, oracle externo e curvas em fontes reais | Ablação P2 off não é baseline lexical; rejeição em 2k fica no resultado |
| Contagem | Total de wire exato, metadados/fonte e custo de expansão separados por método explícito | Tokens por campo não se somam necessariamente; não retirar metadados do orçamento |
| Workers | Direto com cache equivalente, fontes reais, concorrência, fases e novos binários recuperáveis | Ganho misto de cache/IPC não isola mecanismo; controle direto não prova contenção |

Usar o escopo/recorte congelado antes dos resultados; conservar falhas, perdas, indisponibilidades e histórico de schemas. Nenhuma alteração dos limiares G0/G1/G2 nesta revisão.

## 14. Continuação L5 e estabilização v1

[Revisão corrente](relatorios/REVISAO-L5-CONTINUACAO.md) preserva as provas R3/pares históricos e concretiza C02. Validar separadamente status de dossiê, evento por família e admissão global; uma correção histórica não recebe obrigação automática de A→B suplementar. Baseline/reference/probes continuam obrigatórios no seu recorte. Denominadores de cobertura real incluem unknowns e não podem ser substituídos pelo subconjunto resolvível.

[ADR028](ROTEIRO-V1.md) especifica as provas condicionais V1-01…06: compatibilidade pública, recursos medidos, atualização/recuperação, fluxo completo pelos artefatos CLI/MCP, distribuição nos pisos nativos e qualificação da candidate. Executar após G2; não alterar H1 ou limiares para acomodar resultados. A documentação de release só anuncia capacidades, estabilidade e reprodutibilidade efetivamente comprovadas.

## 15. Aceite L5-C02 e próximos controles

[Revisão L5-C02](relatorios/REVISAO-L5-C02.md): pares Python/Go aceitos no recorte e matriz recomposta. C03 exige recibos vinculados a task/descriptor/fontes A/B/executável/configuração, continuidade de índice/processo, saídas completas e comparação recomputável com rebuild B; quota preparada não libera campanha. Contraprovas cobrem cold B, reinício, troca de recibo, evento suplementar, flags sem provas e divergências de cobertura/unknown.

S01 exige avaliação dos alertas observados no setup congelado antes de nova execução afetada, preservando o baseline. Mudança de setup que afete prova requer variante identificada e revalidação. No próximo incremento do executor Go, separar inventários imutáveis de caches graváveis e conferir mudanças entre fases; não atribuir retroativamente essa prova ao run aceito. Continuidade de documentação usa a matriz C02 derivada, mantendo checkpoints congelados explicitamente históricos.
