# Revisão L5-C04/C05 — provas aceitas e caminho para G0

13/10/2026, Arquiteto. Base `8b66cf6`, mudanças desde `f8881d4`. Três agentes revisaram dispatch/P3, TSJS/lexical e corpus/S02; a raiz revisou recursos e recompôs as provas retidas. Somente planejamento e evidências de revisão; implementação cabe à outra IA. Esta revisão substitui a ordem de execução da [revisão C03](REVISAO-L5-C03.md), preservando seus contratos ainda abertos.

## 1. Aceites e distância até v1.0

| Frente | Aceite desta revisão | O que continua aberto |
|---|---|---|
| E02 e eventos | Mapa v2/progresso derivados; quatro eventos operacionais, um por família | Zero novos dossiês de estado elegíveis; projeção multimódulo 19/20 |
| D01 | Compromisso v2, I/O fora do lock, preflight factual e factory de guarda de ferramentas | Defeito de identidade do pedido descrito abaixo; adoção, ABA, blobs e provider |
| P3 | Decoder de diff e reconstrução completa de HEAD como dados, incluindo presença e EOF | Consumo Rust/contexto e adapter P3 ainda pendentes |
| TSJS-A/B/C | 45 labels, 13/13 referências previamente resolvíveis; sessão A→B e rebuild integral | Perfil lexical ESM local exato, callable unknown; não é frontend geral nem nova tarefa D1 |
| Lexical | BM25/TF-IDF reais, segunda leitura posterior, 640 entregas com tokenizer fixado | Formulações defeituosas, conjunto independente, comparação P3 e sucesso de agente |
| Recursos | Equivalência de quatro modos e medição em Linux/macOS | Calibradores, instrumentação, classes ausentes e decisão de produção |
| S02 | Disponibilidade e contrato de inspeção offline | Zero aquisição; seleção/compilação/alcance desconhecidos; 55 alertas bloqueantes |

[Revalidação da raiz](logs/revisao-L5-C05/evidencias.json): cinco reconciliadores recompuseram **seis ZIPs e 2.737 arquivos**, com igualdade integral aos recibos retidos. São presença `38329111797`/`3463bdc` (53 arquivos), TSJS `38329944063`/`96b377c` (53), recursos `38332601334`/`e308c0f` (1.123 por host), tokens `38425062525`/`f7f9400` (361) e sessão TSJS `38425676814`/`15547ed` (24). Metadata/API provém da aquisição retida pelo Implementador; esta revisão não fez aquisição nova. Reconciliadores Python próprios trataram ELF/MachO como dados; nenhum binário retido, upstream, provider ou CI foi executado pela arquitetura.

**M0 permanece aberto:** oito tarefas individualmente elegíveis, D1 global 0/32, quatro eventos operacionais, 9 cartões concluídos/7 em andamento/25 não iniciados; G0/G1/G2 não avaliados. Faltam 24 tarefas para o conjunto, com déficits atuais de 11 complexas, dez históricas e 12 multimódulo; categorias se sobrepõem. A projeção 19/20 pertence ao plano, não à contagem das oito tarefas já elegíveis.

O avanço desde C03 é concreto em semântica, contexto e medição. O bloqueio principal passou a ser integração em tarefas completas: corpus, P3 consumindo contexto real, agentes/comparadores e condições de execução. Mais recibos isolados não substituem esses resultados. [Roteiro v1](../ROTEIRO-V1.md): G0 → confirmação M1-A/G1 → alpha M1-B/G2 → seis atividades de estabilização. Nenhum percentual ou prazo de release é inferido do número de testes/cartões.

## 2. D01 — corrigir identidade do pedido antes de adotar o factory

**Achado acionável:** `execution_dispatch_v2.py:283` reserva uma cópia de `request`; depois da barreira/compromisso, `:303` volta a copiar o objeto original para `_invoke`. Uma mutação concorrente entre esses pontos faz o transporte receber bytes diferentes dos registrados. A [contraprova fake](logs/revisao-L5-C05/pedido-divergente.json) alterou mensagem e `output_tokens` de 100 para 99999; adapter foi chamado uma vez e o replay ainda aceitou o registro antigo. Isso prova divergência de identidade no fake, não cobrança real nem que o limite foi efetivamente consumido por um modelo. Nenhum provider foi chamado.

**Decisão:** capturar o pedido validado uma única vez na entrada, em representação privada/canônica, e derivar reserva, compromisso, transporte e transcript desse mesmo conteúdo. Não reler um objeto mutável do caller. A regra de captura exige ausência de escrita concorrente durante a própria cópia ou entrada de bytes imutáveis; uma cópia não torna múltiplas leituras atômicas. Vincular hash/versão do pedido, task/arm/call/attempt, limites e autorização no novo registro prospectivo. Adapter não pode modificar a representação autoritativa; entregar bytes imutáveis ou uma cópia descartável e registrar exatamente o payload enviado. Preservar replay/fixtures antigos como históricos.

**Aceite prioritário:** barreiras determinísticas antes/depois do compromisso; mutar mensagem, limites e listas aninhadas do caller. Pedido observado pelo espião deve coincidir com o reservado/registrado, ou ser recusado antes do envio. Adulterar o vínculo no replay deve falhar. Preservar D01: reserva não é envio, cancelamento anterior impede invocação e posterior mantém incerteza/recibo tardio idempotente.

Depois dessa correção, fazer a entrada CLI/scripted prospectiva consumir `make_guarded_fake_session`; provar com um único fluxo real offline dispatch→recover→expand→finalize/replay, inclusive resultado delegado retido e recusado. Não editar os sete transcritos históricos para aparentar adoção. O factory disponível é avanço; disponibilidade de API não prova uso pelo executor.

**ABA e blobs:** hashes antes/depois detectam divergência observada, não A→B→A externo. Escolher fonte/manifest/configuração de execução como captura imutável por sessão; mudanças externas só chegam mediante novo snapshot explícito. Autoridade/revogação controlada pelo executor usa geração monotônica não reutilizável, comparada no compromisso e na aceitação de resultados. Callbacks de autoridade externos sem geração deixam essa garantia indisponível. Guard mantém lock curto e não serializa I/O pelo lock contábil. Para resultados grandes, novo perfil referencia blob por hash/tamanho/tipo/encoding e owner; verificar bytes na entrega, controlar retenção/limite agregado e erro por ausência. Referência sozinha não foi entregue ao modelo: projeção efetivamente enviada entra na contagem. Sem store global ou banco M1 exigido; arquivo privado por sessão basta. Não ampliar teto de frame para esconder duplicação.

## 3. P3 — consumir diff validado em Rust e medir uma tarefa inteira

A próxima fatia L5-01 integra o intake C05 ao protótipo Rust existente, sem criar CLI/índice de produção. Contrato tipado preserva `absent` versus arquivo presente vazio, bytes exatos, identidade base/head, paths, EOF e origem dos hunks. Decoder limitado continua recusando formato não suportado; não recorrer silenciosamente ao diretório corrente ou a patch aproximado.

O consumidor Rust recebe mudanças tipadas com kind, base/head `Absent|Present`, bytes/hashes e hunks, além dos manifests completos. Reconstrói HEAD e confere inclusive arquivos não citados; não confia apenas em `validated=true` nem precisa reimplementar todos os formatos Git. SHA-256 do intake e BLAKE3 interno têm algoritmos explícitos ligados aos mesmos bytes. Publicação de B é atômica: falha preserva A e não mistura evidência de ambas. Criação gera obrigação em HEAD, remoção em BASE e arquivo vazio tem obrigação de presença sem inventar span semântico. Ausência conhecida difere de fonte indisponível; expansão usa a revisão retida.

**Primeiro aceite:** fixtures positivas/negativas existentes como regressão e uma tarefa capturada com criação/remoção real; A→B, HEAD integral e rebuild conferidos, cobrindo UTF-8/CRLF/EOF sem newline e mudança omitida. Fonte React serve para equivalência de bytes; a tarefa de obrigações P2/P3 deve ser compatível com o frontend efetivamente usado. Em seguida adapter P3 sobre o mesmo dataset/budgets do lexical, sem rubrica/oracle na seleção. Comparar lexical, estrutura sem P2 e P3 com P2 disponível; capacidade ausente em Python/Go deve permanecer explícita, não virar semântica emprestada. Provar `insufficient_budget` quando obrigação não cabe e expansão vinculada ao snapshot correto. Registrar custos de todo o fluxo, inclusive recusas; não atribuir sucesso de agente a cobertura de spans.

## 4. Lexical e semântica — próxima evidência útil

**Labels:** preservar GO-02/RS-03 e todos os resultados antigos. Nova regressão com IDs e `derived_from`: GO-02 pede extração de path de file URL/erro para scheme diferente, sem alegar validação de authority; RS-03 pede drenagem dos pipes até EOF ou inclui também a função que aguarda o filho se exigir exit status. Corrigir texto já visto não cria holdout. Os anchors antigos comprovam localização, não satisfação das cláusulas incorretas.

**Conjunto independente de desenvolvimento:** congelar 24 consultas novas, seis por família: três positivas, duas negativas naturais e uma ambígua/multialvo. TSJS inclui três TS e três JS; pelo menos duas positivas por família omitem nome/path da solução e uma requer evidência além de declaração curta. Aproveitar fontes já capturadas compatíveis; registrar lacuna se não bastarem. Negativas usam termos plausíveis presentes e ausência limitada ao universo capturado. Autor e segundo leitor fecham rótulos/rubricas/alternativas antes de observar saídas dos métodos. Não usar H1 reservado nem contar consultas como tarefas D1; conjunto deixa de ser independente para confirmação após tuning. Rodada inicial usa rankings/hiperparâmetros atuais, com resultados pareados e denominadores por consulta distinta, sem novo gate estatístico.

**Expansão:** preservar a curva adaptativa antiga. Próximo diagnóstico fixa o mesmo pedido entre cotas, por regra sem oracle, e compara expansão da união com pedidos por handle, deduplicados. Congelar orçamento agregado busca+expansões, número de chamadas e teto de bytes antes da medição; respostas recusadas e projeções também contam. A queda observada ao aumentar cota não demonstra defeito do tokenizer: o conjunto de handles/arquivos mudou e a expansão é integral. Eventual expansão por range exige perfil próprio com offsets/hash/cobertura, nunca fingir arquivo completo. Não eleger BM25 ou TF-IDF vencedor geral pelos 12 positivos anteriores.

**P2:** TSJS-A/B/C aceitos no recorte atual; conservar callable unknown. Próximo incremento é uma relação necessária a dossiê natural. Se essa tarefa exigir named reexport local exato, permitir fatia acíclica limitada com cadeia import→reexport→declaração, alias, ausência/ambiguidade/ciclo/gap como unknown e invalidação do intermediário. Novo produtor/labels; B integral igual a rebuild. Não ampliar sintaxe por catálogo nem exigir reexport para tarefas que já cabem no perfil. Rust R4 e primeiras fatias Python/Go seguem pendentes de M0-11; escolher cada recorte por perda concreta e conservar fontes upstream inertes.

## 5. E02 — compensação concreta e qualificação dos eventos

**Candidato escolhido para investigar:** `L5-SLOT-Python-state_config-1`, Django, tarefa controlada de política de migração com duas bases e ordem de `DATABASE_ROUTERS`. Fontes locais mostram a cadeia `CreateModel.database_forwards` → `Operation.allow_migrate_model` → `ConnectionRouter.allow_migrate`. Isso oferece hipótese verificável de relação necessária entre módulos. Não cria quinto slot/repo, histórico fictício ou obrigação nova no evento scikit-learn.

Entregar primeiro um dossiê dessa tarefa: pedido sem pistas de resposta, fontes/configuração/pin, política desejada, rubrica e oracle independente, par A/B e controles de alias/ordem/retorno de router. Demonstrar que consultar apenas um módulo deixa uma obrigação sem evidência; quantidade de arquivos sozinha não é multimódulo. Se não houver tarefa natural sustentada ou oracle independente, rejeitar o candidato e registrar alternativa dentro do mesmo teto, sem marcar a quota como resolvida.

**Plano permanece 19/20 até revisão factual da compensação.** Novo plano prospectivo versionado só promove a meta comprovada, com bijeção, quatro tarefas/repo, complexas/históricas e map v2 preservados. Não alterar descritores/ZIPs de estado para ganhar quota.

Os quatro eventos operacionais são insumos, não quatro dossiês prontos. Para cada um: objetivo útil no repositório, universo de busca não limitado ao anchor, entrada do agente sem oracle, alternativas aceitas, obrigações/controles, rubrica, segundo leitor e relação com prova operacional. Rust rand.rs continua simples/unitário; JS/Flow, Python e Go provam presença de fontes, não semântica. Se um evento não sustentar tarefa natural independente, conservar a prova operacional e preparar caso elegível substituto com mapeamento/linhagem explícitos; não duplicar a tarefa nem recontar o mesmo evento como vários desafios.

## 6. Recursos — fechar lacunas sem escolher pelo menor tempo

Aceitar o desenho/medição real-v1: 80 unidades, 52 arquivos integrais, 24 sessões e 57.600 consultas por host. `direct_cached` teve throughput mediano maior que XRW2 nos quatro cenários observados; isso não autoriza remover isolamento. RSS menor de XRW1 não prova vantagem: o sampler perdeu muitos processos curtos. Sem recomendação final de produção nesta revisão.

Próxima fatia L5-03 tem duas partes verificáveis, preservando protocolo/resultados v1:

1. Instrumentação privada do próprio pool: filas, codec, roundtrip, IPC/stderr e shutdown por pedido/encarnação, com ledger de recursos sem dupla contagem. Provar drop/ticket/consumidor lento, reservas retidas, deadline/retry, worker afetado retirado e vizinho saudável. Artefatos medidos e respostas precisam corresponder ao mesmo produtor/configuração; probes não executam upstream.
2. Protocolo v2 congelado antes de medir: distinguir processo frio, warmup de todas as gramáticas por lane e execução aquecida; alternar A/B dentro de cada lane, inclusive concorrência2. Incluir sequência de 30 arquivos distintos por dialeto quando disponíveis, sem chamar duas fontes repetidas de 30 amostras independentes; registrar insuficiência. Selecionar TSX dense/large e incompletos originais apenas quando fontes reais satisfizerem critérios predefinidos; controle sintético não preenche ausência.

Aceite usa testes funcionais dos dois alvos, equivalência completa antes de medir e resultados por regime/sessão; null com causa para métricas ainda indisponíveis, sem somar percentis ou misturar CPU de observador. Ao terminar, recomendar modo com evidências de isolamento, falhas, manutenção e custo observado. M0-06 depende dos aceites existentes; não há obrigação de XRW2 vencer nem motivo para reescrever Tree-sitter sem perda demonstrada.

## 7. S02, comparadores e preparação de smoke

**S02:** inventário/contrato offline aceitos; preservar guard S01. Próxima entrega pode avançar sem download: coletor separado com transporte fake, verificando limites de destino, redirects, bytes, hashes, timeout, symlink e quarentena. Primeira tranche: somente `.mod/.info` dos módulos críticos/altos com hash/tamanho esperados já presentes no manifesto histórico; enumerar os demais como indisponíveis. ZIP/expansão ficam para perfil posterior. Usar destinos exatos da política, sem redirects/proxy/credenciais herdados, runtime fixado e domínio descartável; teto por objeto 32 MiB, agregado 256 MiB, 128 objetos e deadline total inicial de 30 s, sem ampliar silenciosamente. Streaming conta bytes mesmo sem Content-Length e verifica hash/tamanho antes de publicar. Não confundir JSON válido com contenção observada: aquisição efetiva requer recibo de ambiente/coletor/requests/status/bytes e limites. Mudança de escopo requer novo perfil prospectivo; não usar `go mod download` como fallback.

Produzir manifesto exato dos módulos/versões e contexto alvo, preservando requisito/presente/selecionado/compilado. Metadados permitem iniciar relações de requisitos, mas não provam seleção nem alcance; imports por regexp não demonstram exclusão. Aquisição restrita não habilita geração/import/build/test/probe. Liberação futura é por fase/contexto e evidência específica, nunca um allow em lote. Evento Go de presença não exige executar setup Gitea.

**Comparadores L5-06:** o manifesto dos oito continua `planning_only`, com pins/configurações/instalação null. Próximo resultado é inventário versionado para todos os oito, com fonte oficial, versão/pin, capacidades, modo local e melhor configuração enriquecida, dependências, licença e requisitos. Depois obter receipts de instalação/probe em domínio apropriado para os selecionados, sem importar código upstream no host da arquitetura. Seleção de finalistas usa capacidades/tarefas e mantém modos fortes; impossibilidade observada justifica exclusão, preferência pelo baseline fraco não. Não esperar 32/32 para preparar essa triagem.

**Smoke L5-05:** preparar manifesto concreto de quatro tarefas, uma por família, dois braços/oito sessões antes de retries, task/arm/attempt explícitos, política de ferramentas, snapshots isolados e replay. Vincular modelo/versão/esforço/tokenizer/serializer, timeout, concorrência e retenção. Estimar custo máximo com preços oficiais verificados quando a proposta estiver pronta, incluindo chamadas/retries/expansões/saída e uso incerto; ausência de autorização/teto/provider permanece bloqueante. Esta revisão não inventa escolha de modelo nem autoriza gasto. Smoke de desenvolvimento não exige D1 global, mas exige contenção e demais condições próprias. Falta de recursos externos não bloqueia dossiê, P3, fake, comparadores documentais ou outras frentes offline.

## 8. Ordem, divisão e aceite da próxima entrega

| Ordem / ID existente | Responsável sugerido | Resultado a entregar |
|---|---|---|
| 1 / L5-05 | Dono de dispatch/adapter | Corrigir pedido mutável; contraprova falha antes/passa depois; adoção do factory no fluxo offline |
| 2 / L5-04 | Dono de corpus | Primeiro dossiê Django candidato e quadro dos quatro casos de estado; plano ainda bloqueia até evidência |
| 3 / L5-01 | Dono de contexto Rust | Intake tipado consumido por P3 e uma tarefa integral comparável ao lexical |
| 4 / L5-01/02 | Dono de avaliação/semântica | Regressões GO-02/RS-03, conjunto24 congelado, diagnóstico de expansão; relação útil por dossiê |
| 5 / L5-05/06 | Dono da integração | Contratos ABA/blobs, manifesto smoke e triagem dos oito comparadores |
| 6 / L5-03 | Dono de runtime | Calibradores/instrumentação e protocolo de recursos v2; medir só depois do freeze |
| 7 / S02 em L5-04 | Dono de inspeção | Collector limitado com provas fake e lista exata de aquisição; manter bloqueio afetado |

A ordem expressa prioridade, não dependência artificial entre frentes independentes. Com agentes, fixar ownership de módulos e um integrador para schemas/shared APIs; não editar o mesmo módulo em paralelo. Próxima entrega deve conter correção do pedido e avanço de tarefa/P3, além dos testes relevantes, não somente outra camada genérica de recibos. Não reexecutar provas aceitas sem mudança/falha que justifique; não criar L6 ou novos cartões para esconder critérios pendentes.

Relatar por critério: implementado, verificado no recorte, pendente e limitação; atualizar estado e commit/push após checks. Caminho v1 e limiares permanecem os mesmos. A revisão Tier 2 é dirigida, não auditoria exaustiva; [pareceres dos agentes](logs/revisao-L5-C05/agentes.json) registram paths/cobertura e limites, e [checks documentais](logs/revisao-L5-C05/documentacao.json) verificam links/estados/escopo.
