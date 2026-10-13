# Revisão L5-C03 — evento Rust, dispatch e continuidade

12/10/2026, Arquiteto. Base `d9c3c87`; implementação `5191baa`/`4972f02`. [Entrega C03](L5-C03.md), [entrega S01](L5-S01.md), [fatias vigentes](../L5-PROXIMA-EXECUCAO.md). Três agentes revisaram dispatch, eventos/alocação e dependências. Somente documentos e evidências de revisão foram produzidos pelo Arquiteto.

## 1. Aceite e avanço até v1.0

| Entrega | Aceite desta revisão | Limite |
|---|---|---|
| C03-A/C | Snapshot de bytes, decisão recomposta, consumidor fake, reservas/retries/replay e recusa D1 | Offline/sintético; provider, smoke real, contenção e campanha não comprovados |
| C03-B | Quatro descritores congelados e primeiro evento operacional Rust reconciliado | 1/4 executado; alocação exige E02; não equivale a novo dossiê elegível |
| Evento Rust | Mesmo `Index`/processo A→B e rebuild B independente, três queries e snapshot completos iguais | Unidade stdx/rand.rs, configuração experimental 2018→2024, rebuild conservador; sem alegação de cache ou semântica integral |
| S01 | 55 decisões bloqueantes, 54 advisories retidos, guard consumido no workflow Go atual | Alcance ainda desconhecido; nenhuma remediação/liberação de execução |

O evento muda a configuração do analisador, não os bytes da fonte. Duas queries passam de unknown para resolved e uma ausência permanece unknown. É prova legítima de atualização de configuração nesse recorte, não demonstra que a fonte upstream seja inválida em edição 2018. Aceitar a prova operacional sem promover precisão, desempenho, complexidade ou elegibilidade da tarefa.

[Revalidação local](logs/revisao-L5-C03/evidencias.json): **275 arquivos** do manifesto final conferidos, ZIP original e seus **23 arquivos** recompostos, incluindo hash dos bytes do executável retido; recibo nativo reproduzido integralmente. CI `38309739709`, código `4972f0285915a37d044d0d2bee30a32eecaffb30`, passou 30 checks. A primeira tentativa falhou na preparação de contraprova e continua histórica, sem substituir a prova final. A revisão não executou o binário retido, upstreams, CI ou provider. Metadata é a aquisição API já retida pelo Implementador.

Preparo dos quatro descritores, CLI fake e inventário S01 foram revalidados; os guards de download/build/probe retornaram a recusa esperada. Não repetir probes C02 nem todas as provas antigas para implementar a próxima fatia.

**Estágio permanece M0:** oito tarefas individualmente elegíveis, D1 global 0/32, 9 cartões concluídos/7 em andamento/25 não iniciados, G0/G1/G2 não avaliados. O ganho desta rodada é uma prova operacional antes inexistente. TS/JS semântico, recuperação real, adapter, comparadores e ganho competitivo continuam pendentes. [Roteiro v1](../ROTEIRO-V1.md) mantém seis atividades de estabilização somente após G2.

## 2. E02 — Conciliar tarefa congelada e slot de admissão

Os quatro descritores usam `state_config-1`, mas pertencem ao segundo repositório de cada família, reservado no plano para `state_config-2`. Rust/TSJS/Go slot-1 têm meta complexa; Python slot-1 é simples, mas no Django. TSJS slot-1 exige TypeScript, enquanto o descritor novo usa React/JavaScript. Substituir os repositórios desses slots silenciosamente deixaria cinco tarefas no segundo repo, acima do teto quatro.

**Decisão E02:** criar mapa externo versionado de atribuição, preservando bytes/hashes/IDs dos descritores, oracles e recibos históricos. A identidade da tarefa continua a mesma; `slot_id` congelado é a referência original, e o mapa aponta sua alocação prospectiva para admissão. Não criar uma segunda tarefa ou modificar o recibo nativo para esconder a divergência.

| Caso preparado | Slot prospectivo | Meta que deve permanecer no primeiro repo |
|---|---|---|
| Rust rust-analyzer / configuração rand.rs | `L5-SLOT-Rust-state_config-2` | slot-1 Tokio complexo |
| TSJS React / disponibilidade JS | `L5-SLOT-TSJS-state_config-2` | slot-1 TypeScript complexo |
| Python scikit-learn / disponibilidade | `L5-SLOT-Python-state_config-2` | slot-1 Django |
| Go Gitea / disponibilidade | `L5-SLOT-Go-state_config-2` | slot-1 Prometheus complexo |

Transferir a obrigação de evento requerido para esses slots na nova versão de alocação, mantendo pelo menos um por família. Mapa precisa vincular tarefa, descritor/hash, família, repo, slot original/canônico e versão do plano; validar uma tarefa por slot e um slot por tarefa, sem alias duplicado. O consumidor da admissão aplica e verifica esse mapa explicitamente; o reconciliador histórico continua verificando os dados originais.

**Déficit adicional de planejamento:** rand.rs é unitário, embora o slot Rust-2 previsse multimódulo. Corrigir essa meta reduz a projeção de 20 para **19 tarefas multimódulo**; o piso continua 20. Selecionar mais uma tarefa com relação necessária entre módulos em slot compatível, ou rever a alocação com evidência equivalente, sem duplicar linhagem. A presença de dois arquivos nos outros eventos não prova relação multimódulo. As metas de 16 complexas/16 históricas e quatro tarefas por repo permanecem possíveis após o mapa. [Cálculo reproduzível da projeção](logs/revisao-L5-C03/alocacao.json).

Não somar os quatro descritores aos oito elegíveis. Para admissão, preparar tarefa natural com universo de busca e contexto pertinentes, rubrica, segundo leitor e demais critérios. O recorte de uma/duas unidades pode provar protocolo sem qualificar o dossiê inteiro. Se futuramente os quatro casos simples forem individualmente elegíveis, a projeção passa a 20 tarefas restantes, 11 complexas, dez históricas e 12 multimódulo; hoje continua 24/11/10/12. Categorias se sobrepõem.

**Aceite E02:** novo mapa/plano e verificadores rejeitam conflito de repo/linguagem, slot duplicado, caso sem hash, cinco tarefas por repo e projeção multimódulo 19. O planejamento pode registrar explicitamente déficit enquanto a tarefa compensatória não foi escolhida; não declarar matriz global satisfatória nesse estado. Um registro derivado de progresso distingue preparo 4/4, prova operacional 1/4, novos dossiês de estado elegíveis 0/4 e admissão 0/32. Retornos históricos `executed=0` do preparador não são a contagem atual de execuções.

## 3. D01 — Tornar explícito o compromisso de envio

[Contraprova fake](logs/revisao-L5-C03/cancelamento.json): cancelamento ativado na última checagem antes de `_invoke` resultou em uma chamada ao adapter e status cancelled. **O `Ledger.send` já havia sido registrado.** Portanto a prova mostra a janela e a ambiguidade do compromisso, não demonstra violação de uma promessa de cancelar envio já comprometido. Nenhuma chamada externa ocorreu.

**Decisão D01, antes de transporte real:** reserva não é envio. Depois da reserva, uma seção crítica verifica cancelamento, autorização/expiração e incidente; registra o compromisso de envio como ponto de linearização. Cancelamento/revogação linearizados antes desse ponto recusam sem invocação e liberam a reserva. Depois dele, registrar solicitação de cancelamento/aborto, sem prometer zero chamadas ou zero cobrança; incerteza mantém reserva até reconciliação. Resposta/usage tardios precisam de tratamento idempotente.

O lock hoje cobre `_invoke`; é aceitável no fake instantâneo, mas não deve impedir revogação/invalidação durante I/O bloqueante. Liberar o lock após compromisso e antes do transporte, mantendo transições contábeis protegidas. Não reescrever eventos/recibos históricos: versão nova do protocolo distingue estados e migração do replay se necessário.

**Aceite:** espião/barreiras determinísticas antes/depois do compromisso; antes, zero chamadas/reserva liberada; depois, cancelamento e cobrança incerta registrados. Cobrir autorização expirada, revogação, retry e corrida de reservas. Definir ordem para erro comprovadamente anterior ao transporte versus resultado incerto. Evitar teste baseado apenas em sleep. Não prometer desfazer operação que já foi enviada.

A CLI atual só aceita fixture offline e os metadados do ledger usam a primeira tarefa do manifesto. Antes do smoke real, tornar task/arm/call/attempt explícitos, vincular tokenizer/serializer/modelo/configuração e autorização, e testar o protocolo por replay. **Não liberar D1:** integrar diagnósticos factuais do corpus/eventos ao snapshot consumido, mantendo razões de bloqueio para requisitos ausentes e provider/teto. Smoke D0/seed continua com critérios próprios.

## 4. S02 — Avançar a análise sem desativar o bloqueio S01

S01 v1 exige estados unknown/bloqueados e recusa todas as três fases. Isso está correto para o checkpoint; não oferece ainda uma transição comprovada para permitir execução. Não alterar o JSON para `allow` nem inserir bypass no runner bloqueado.

**Decisão S02:** separar inspeção de dados e execução do setup. Preservar inventário/recibos v1 e acrescentar política/artefatos prospectivos:

1. **Disponibilidade, agora e offline:** cruzar go.mod/go.sum, fontes e manifestos históricos. Há manifesto de 36.892 arquivos do cache, cerca de 1,08 GB declarados; os bytes dos módulos não estão no ZIP histórico de 14 recibos/logs/manifests. Separar requisito, versão presente, selecionada e compilada; enumerar bytes ausentes. Nenhuma compilação ou `go list` é necessária para esse inventário.
2. **Perfil de aquisição/inspeção de dados:** coletor separado, com verificador próprio, ferramentas fixadas e destino descartável. Reutilizar bytes autenticados disponíveis; aquisição ausente somente por destinos permitidos, limites e hashes, sem credenciais de projeto. Não executar hooks, geração, imports upstream, compilação ou testes. Não reusar `--require-execution` como dispensa geral nem instalar flag `--allow-inspection` no runner bloqueado. O Implementador prepara contrato e testes offline antes de qualquer aquisição nova.
3. **Closure e alcance por contexto:** metadados e fontes condicionais com plataforma/tags/CGO/oracle. Registrar arestas não demonstradas e alcance de inicializadores/TestMain, subprocessos e entradas locais. Análise estática não vira “versão compilada”; imports por regexp não provam ausência. Começar críticos/altos, manter decisão para cada um dos 55 IDs.
4. **Política de execução prospectiva:** só com evidência por fase/contexto, aceitar exclusão demonstrada, contenção específica ou variante remediada. Exposição ao adquirir dados é distinta de executar bibliotecas; não exigir closure runtime concluída para toda aquisição restrita, mas verificar os riscos próprios do leitor/aquisição. Antes de build/probe permitido, controlar inventários imutáveis entre fases e scratch separado. Variante exige revalidar os dois lados e preservar baseline histórico.

**Próxima entrega S02:** inventário de disponibilidade mais contrato/contraprovas offline do perfil de inspeção. Zero downloads/builds/probes necessários para esse aceite. Os 55 alertas permanecem bloqueantes; nenhuma permissão remota de dismiss é criada. Ler fontes Go como dados para o evento de presença não executa o setup vulnerável e não depende de liberar o probe Gitea.

## 5. Próximas atividades por resultado

| Ordem / ID existente | Entrega revisável | O que evita |
|---|---|---|
| 1 / L5-04 | E02, progresso derivado e tarefa compensatória multimódulo a qualificar | Prova de protocolo contada como tarefa complexa ou slot incorreto |
| 2 / L5-05 | D01 com barreiras fake; diagnóstico de corpus/eventos consumido pelo preflight | Ambiguidade de cancelamento e futura liberação por flags |
| 3 / L5-02 | TSJS-A do perfil ESM exato, labels e uma relação em fonte real | Mais ciclos de infraestrutura sem ampliar semântica útil |
| 4 / L5-04 | Executar três eventos `captured-source-presence-v1` restantes | Confundir presença de fonte com parse/semântica TSJS/Python/Go |
| 5 / L5-01/05 | Recuperação lexical real/alternativas e protocolo de smoke com task/arm; orçamento concreto | Fake técnico apresentado como tarefa completa de agente |
| 6 / S01 em L5-04 | S02 disponibilidade e inspeção offline | Impasse circular de pedir execução vulnerável para poder avaliá-la |
| 7 / L5-03/06 | Recursos `direct_cached` e comparadores/preflight | Manter lacunas já identificadas fora do balanço |

A ordem não proíbe trabalho independente. Para os três eventos de presença: mesma sessão, consulta negativa aquecida, restauração de fonte, fonte preservada e ausência não relacionada; B completo igual a rebuild independente, revisão errada recusada. Cobertura é de fontes; parse/semântica permanecem unknown. React/Flow nesse evento não demonstra TSJS-A. Concluir essas provas não exige antecipar frontends completos ou índice M1.

Sem novos cartões ou lote L6. Preservar os critérios das [fatias](../L5-PROXIMA-EXECUCAO.md) quando não concretizados por esta revisão; não recomeçar o fake, os quatro descritores ou o protocolo Rust já aceitos. Implementador escolhe detalhes internos e pode usar agentes com ownership de arquivos; o Arquiteto não implementou nenhuma dessas correções.

## 6. Verificação

Três revisões Tier 2, codebase-memory geração `2026-10-12T21:27:13Z`, com cobertura e leitura dirigida; ressalva best-effort e ZIPs inspecionados como dados quando não indexados. Achados e recortes consolidados acima. [Evidências](logs/revisao-L5-C03/evidencias.json), [contraprova](logs/revisao-L5-C03/cancelamento.json) e [checks documentais](logs/revisao-L5-C03/documentacao.json). Commit/push conforme AGENTS.md depois da verificação, sem equivaler a release ou aprovação de campanha.
