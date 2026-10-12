# Revisão L5 e retomada das atividades abertas

12/10/2026, Arquiteto. Base `f529bd2`; implementação `e4cd4d47090ca93715e82c4623a6a2463af3bdb4`. [L5](L5.md) entregou a primeira vertical P3, perfil documental v3, recursos sintéticos e alocação condicional do corpus. Esta revisão mantém os IDs L5-01…06 e os cartões M0/M1. Não cria outro lote para renomear trabalho pendente.

**Próxima execução: L5-04, quatro dossiês reais, intercalando L5-02, Rust R3.** L5-01 avança sobre fontes reais e recuperação lexical; L5-03 completa recursos com controles comparáveis. As atividades offline L5-05/06 continuam disponíveis. Planejamento e revisão somente; o Implementador escreve código e executa as próximas provas.

## 1. Parecer sobre a entrega

| Frente | Aceite desta revisão | O que permanece aberto |
|---|---|---|
| Perfil P3 v3 | Representação explícita de base/head, cobertura por revisão, obrigações e expansão; v2 preservado | Formatos de diff fora do recorte e adapter público; não anunciar produto pronto |
| Contexto Rust | Primeira seleção/expansão, fonte exata, medição, retenção/TTL/quota e isolamento de handles | Recuperação sem âncora, ranking/alternativas, qualidade de evidência em fontes reais e demais famílias |
| Workers | Calibração e comparação sintética nativa direto/XRW1/XRW2, CPU terminal e RSS amostrado | Fontes reais, concorrência, decomposição, controle de cache e calibração integral |
| Corpus | Alocação condicional de 32 slots consistente | **Zero dos quatro dossiês novos entregue; D1 global 0/32** |
| Smokes | Unidade corrigida: quatro tarefas pareadas, oito sessões mínimas | Adapter real e execução com recursos/teto/contenção pertinentes |

Reexecutei os verificadores existentes de contexto, recursos e slots, sem gerar novas medições ou alterar recibos anteriores. [Evidência desta revisão](logs/revisao-L5/evidencias.json): **59 hashes de fontes** confrontados com o commit publicado, **199 hashes de artefatos**, quatro provas de contexto e duas matrizes sintéticas de **18.900 pedidos cada**, todos aprovados. O verificador de slots confirmou planejamento, não admissão. Os binários nativos não estão nos artefatos; seus hashes declarados não puderam ser recomputados a partir dos bytes.

A [CI38259048931](https://github.com/wkoch/xrai/actions/runs/38259048931) é comprovada pelo recibo local, sem nova consulta remota nesta revisão. Resultados registrados: Rust112 Linux/111 macOS, sem falhas/ignorados; harness49+1 skip Linux/45+5 skips macOS; contexto18+9 por alvo. O job documental omite um teste de tokenizer, coberto nos jobs Python3.13.13. A execução macOS15.7.9 não comprova o piso literal15.0.

XRW2 perdeu para direto em 5/35 células Linux e 8/35 macOS nos artefatos nativos; o resultado não justifica escolher modo de produção. Valores locais do macOS27 e da CI15.7.9 são experimentos distintos. O relatório de workers contém um trecho anterior à CI dizendo faltar prova nativa: a fatia **sintética** agora tem os dois alvos comprovados; fontes reais e demais critérios continuam faltando. Não reexecutar a matriz sintética só por esse texto histórico.

## 2. Decisões de arquitetura para a retomada

Não surgiu decisão bloqueante formal no relato do Implementador. As concretizações abaixo fecham escolhas de execução dentro dos ADRs existentes; nenhum gate ou critério competitivo muda.

| ID | Decisão | Consequência |
|---|---|---|
| L5-C01 | Os repositórios dos slots são candidatos substituíveis. Aprovação da forma da matriz não fixa React/Tokio nem prova porte/módulos | Rejeitar candidato inadequado com evidência e realocar preservando estratos/pisos; sem pedir decisão de arquitetura por cada troca |
| L5-P01 | O ponto de 2k que rejeita admissão é resultado válido da implementação atual, não promessa de limite mínimo universal | Mantê-lo nas curvas; medir custo do envelope e perdas antes de alterar representação. Não ocultar metadados nem aumentar teto |
| L5-P02 | P2 desligado em L5 é ablação, não baseline lexical competente: ainda constrói IR e suprime recuperação de consumidores | Implementar controle lexical/estrutural explícito; separar seus custos e os efeitos de disponibilidade de base |
| L5-R01 | Comparação atual mistura custo de IPC com políticas diferentes de compilação/cache | Acrescentar controle direto com reutilização equivalente de parser/query, preservando os três modos históricos; decisão de produção espera evidência completa |
| L5-E01 | Novas provas nativas devem permitir conferir os executáveis medidos | Reter binários por alvo e seus hashes junto ao run, ou referência de artefato recuperável; ausência continua explícita nos históricos |

As implementações de P01/P02/R01 continuam experimentais em `xrai-eval`. Não abrir nova camada de produção, trocar parser ou implementar GC universal para cumprir esses incrementos. Biblioteca própria maior continua autorizada quando uma perda reproduzível exigir, conforme ADR024.

## 3. L5-04 — Quatro dossiês, agora com evidência factual

**Responsabilidade:** `eval/qualification/`, materialização/probes/oracles e relatório de corpus. A [alocação existente](../../eval/qualification/l5-slot-plan.json) é ponto de partida; seu verificador continua sendo verificador de plano. Não transformar `target:true` em evidência.

| Slot vigente | Candidato / tipo | Trabalho que deve produzir evidência |
|---|---|---|
| `L5-SLOT-Rust-correction-2` | rust-lang/rust-analyzer / correção histórica | Fixar origem e par real; provar porte, necessidade entre módulos e referência/probes |
| `L5-SLOT-TSJS-contract_change-2` | facebook/react / contrato histórico JavaScript | Primeiro provar produção JS elegível, porte e setup; depois origem/par e relações necessárias |
| `L5-SLOT-Python-contract_change-2` | scikit-learn/scikit-learn / contrato | Instanciar desafio natural conforme ADR021, referência e probes independentes; não inventar histórico público para um slot que não o exige |
| `L5-SLOT-Go-contract_change-2` | go-gitea/gitea / contrato | Mesmas provas de porte, módulos, referência e regressões, com configuração reproduzível |

Esses nomes não significam candidatos qualificados. Para cada um: fixar SHA/fontes/licença/setup; medir porte de produção conservador com exclusões; demonstrar pelo menos três módulos/dois subsistemas e caminho de duas arestas para o alvo complexo conforme ADR021; registrar por que a tarefa exige essas relações, não somente que os arquivos existem. Preparar entrada natural sem solução e manter patch/probes/oracles fora do alcance do agente.

Executar baseline/referência/regressões no domínio autorizado do harness, registrar comandos/ambiente/exits e revisão independente conforme o protocolo. Não usar macOS local conhecido para comandos arbitrários de dependências/projetos. Se faltar ambiente, avançar curadoria/oracles/setup e declarar os probes pendentes; não chamar isso de dossiê aceito. Priorizar uma primeira entrega Rust+JS e completar Python+Go para fechar o incremento de quatro.

Se React não cumprir os pisos, substituir por outro projeto JS elegível, registrando a rejeição e recomputando slots. Se Tokio não atingir porte conservador após excluir testes inline, realocar somente os slots complexos condicionais; preservar o piloto não complexo. Não flexibilizar pisos para salvar nomes escolhidos. Evitar gastar todo o incremento em novo schema/validator sem materializar caso algum.

**Aceite:** quatro novos dossiês reproduzíveis e revisados, lacunas restantes atualizadas e gate global fechado até cumprir tudo. Rejeição fundamentada de candidato é progresso, mas não conta como dossiê aceito. Déficits atuais condicionais: 28 tarefas, 15 complexas, 12 históricas e 16 provas multimódulo adicionais; categorias se sobrepõem. Registrar separadamente quatro eventos A→B, um por família, com índice/processo preservado. Nenhum resultado aqui é vantagem de agente.

## 4. L5-02 — Rust R3 como próxima fatia semântica

**Responsabilidade:** `crates/xrai-eval/src/semantics_spike.rs` ou módulos experimentais extraídos, matrizes/verificador e relatório semântico. Contrato: ADR025; R1/R2 e suas contraprovas ficam preservados.

Congelar antes de implementar as regras a matriz por forma de binding, parâmetros, escopos e configuração conhecida/desconhecida. Incluir homônimo local versus import, introdução/remoção de shadowing e limites de escopo; as formas ainda não suportadas produzem lacuna conservadora. Definir o recorte resolvível previamente, sem retirar falhas do denominador. Consultar as fontes oficiais fixadas de Rust ao concretizar regras; não executar Cargo/build scripts/macros do projeto para indexar.

Entregar evento A→B que cria binding/export e outro que muda configuração, ambos iguais a rebuild B em estados/alvos/evidências/lacunas, não apenas contagem. A captura real deve identificar pacote/módulos, entradas excluídas e configuração; o arquivo Tokio de L4 permanece amostra de arquivo. Primeiro consumidor P3 deve mostrar que o alvo antes sugerido lexicalmente muda com a resolução, preservando a evidência que permite auditar a escolha.

**Aceite do incremento:** matriz R3 positiva/adversa, comparação incremental/rebuild e uma amostra real capturada; ≥80% dos pré-rotulados resolvíveis e nenhuma promoção indevida nas fixtures. Não fechar M0-11: R4 e TS/JS, Python, Go permanecem no cartão. Sem motor incremental fino ou type checker completo como pré-requisito.

## 5. L5-01 — Relevância real, busca e custo de representação

**Responsabilidade:** módulos/driver P3, `eval/context/`, verificador e relatório. Consumir fontes de desenvolvimento e interfaces P2 disponíveis; não aguardar quatro resolvers completos para medir a primeira fatia real.

1. Acrescentar recuperação lexical/estrutural sem âncora: mesmo pedido/escopo/limites, resultados com fonte/span e incerteza, sem orçamento de trabalho ilimitado. Pedido sem pista suficiente admite `not_assessed`; não inventar obrigação resolvida.
2. Acrescentar alternativas ponteiro/assinatura/trecho/símbolo/arquivo e seleção por ganho marginal com prioridades determinísticas. Testar conteúdo mínimo exigido, homônimos, função grande/hunk central, classes e arquivo pequeno conforme linguagens disponíveis. Não confundir ordem por path com relevância.
3. Preparar labels externos que enumerem evidência necessária e distratores, incluindo a que o planner não encontrou. Usar fontes reais de desenvolvimento; não incorporar probes/soluções à seleção. O avaliador julga descoberta e entrega separadamente de obrigações autoidentificadas.
4. Rodar curvas 2k/4k/8k/16k/32k, extremos e expansão, com bytes/tokens completos. Para 2k rejeitado, decompor bytes de metadados/fonte e medir variantes de serialização de forma reproduzível. Tokens de segmentos isolados não são aditivos: qualquer atribuição por campo declara método e o total exato continua medido no wire inteiro.
5. Estender diff para criação/remoção integral de arquivo e último trecho sem newline antes de afirmar suporte a revisão geral. Preservar restrições explícitas de formatos ainda não implementados e provas de byte offsets. Typed-hunk e exemplo de diff unificado só são equivalentes quando um teste demonstra a mesma reconstrução, não por compartilhar nomes.

**Controles:** baseline lexical/estrutural; ablação P2 off/on com os mesmos candidatos/entradas quando se quer isolar resolução; ablação de recuperação semântica quando ela também muda candidatos; comparação head/base+head identificada como mudança na informação disponível. Declarar cada braço e o custo de construir IR mesmo quando o lookup está desligado. Não chamar controles internos de baseline `rg` competitivo ou atribuir todo ganho de base à seleção.

**Aceite do incremento:** casos reais com oracle externo, recall/precisão/perdas por camada e orçamento, uma perda reproduzível e seu diagnóstico; fonte/revisão/retention intactas e v2/v3 continuam válidos. Configurar as alternativas antes de ver resultados, mantendo limite de versões experimentais do protocolo. Não transformar envelope compacto em nova promessa de sucesso ou exigir caber em 2k removendo evidência obrigatória. M0-09 continua aberto até o aceite integral.

## 6. L5-03 — Fechar a comparação que ainda falta

**Responsabilidade:** driver/medidor/verificador de workers, fontes capturadas e relatório. Primeiro corrigir o texto corrente que ainda indica falta da comparação sintética nativa, referenciando os dois runs já aceitos; preservar números históricos e proveniência.

O controle adicional de L5-R01 deve reutilizar parser/query por dialeto/configuração sob a mesma política de reset do XRW2, dentro do processo de benchmark. Denominá-lo explicitamente, por exemplo `direct_cached`; o direto histórico permanece. Provar equivalência integral antes de comparar tempo. Esse controle mede cache/IPC; sua falta de isolamento não o torna recomendação de arquitetura do produto. Se schema/verificador fechado em três modos precisar evoluir, versionar o novo desenho e manter replay da matriz v1 histórica.

Usar fontes reais pequenas/médias/grandes densas/erro e sequências repetidas/distintas dos sete dialetos, com manifest/hashes e classificação anterior aos resultados. Manter large-comments como controle, sem usá-lo como único arquivo grande. Cobrir carga sequencial e concorrência declarada em tabelas distintas; medir queue/codec/roundtrip/end-to-end e bytes IPC/stderr, sem somar percentis. Cache/compilação e startup têm tempos separados onde observáveis.

Calibrar baseline idle sincronizado antes do trabalho; guardar timestamps, CPU pai/filhos inclusiva sem duplicação, sampler/overhead, série RSS simultânea e processos curtos perdidos. Comparar reservas/tickets com RSS sem equiparar as unidades. Retenção de binários medidos por alvo resolve L5-E01 apenas para os novos runs. Preservar `null` quando indisponível e justificar o impacto na conclusão.

**Aceite:** matriz congelada, ambos os alvos, fontes reais e concorrência, perdas por classe/configuração e limites fundamentados. Recomendar modo somente com evidência de confiabilidade/custo; não exigir vitória percentual da persistência. Prova literal macOS15.0 continua em M0-05 e não é substituída por deployment target. Não reabrir retenção funcional do contexto/workers sem falha nova.

## 7. L5-05/06 — Continuidade offline e condições externas

Permanecem os critérios da [revisão L4 §§7–8](REVISAO-L4.md): adapter real com fixtures/replay/ledger, readiness acionável, estimativa das oito sessões mínimas, quatro smokes pareados condicionados e triagem dos oito comparadores em configurações fortes. Verificar versões/protocolos nas fontes oficiais no momento de implementar; não congelar aqui preço/modelo sem evidência.

Preparar estimativa e configuração concretas antes de solicitar recurso faltante. Orçamento/modelo/contenção são condições do run correspondente, não impedimentos para corpus curado, R3, P3 ou medição técnica. Campanha M0-12 continua exigindo D1 qualificado e demais dependências. Licença do produto segue com mantenedor antes de distribuição; nenhuma licença de projeto de terceiro a substitui.

## 8. Próxima entrega e verificação desta revisão

Entregar relatório da **continuação L5**, identificando quais dos seis IDs avançaram e quais critérios restam. A próxima entrega prioritária deve conter evidência de dossiês novos e/ou R3, não somente mais validação estrutural de planos. Registrar fracassos, bloqueios específicos e trabalho independente; não aguardar parecer novo para decisões locais já cobertas por esses contratos. Este roteiro não solicita novos chats ou subagentes.

Atualizar estado por execução, rodar checks pertinentes e commit/push conforme AGENTS.md. Arquitetura conserva os 41 IDs/dependências e todos os estados encontrados em `f529bd2`; M0-09 já estava em andamento. Nenhum gate G0/G1/G2 é avaliado nesta revisão.

Exploração dirigida com graft e codebase-memory Tier2, geração `2026-10-12T14:06:52Z`, cobertura de 18 paths sem lacuna registrada. Search/trace/snippet de `Store::expand` conferiram vínculo de manifesto, quota de tentativas e deadline cooperativo. Ligações do grafo a helpers homônimos de outros arquivos não foram consideradas prova de integração; fonte exata sustenta a conclusão. Não é auditoria exaustiva de segurança nem reexecução de Rust/benchmarks nos hosts.

[Verificação documental](logs/revisao-L5/documentacao.json) e [replay independente dos artefatos](logs/revisao-L5/evidencias.json) registram os checks, fontes e limitações. A publicação será comunicada após confirmação de commit/push.
