# Revisão arquitetural L4 e atividades L5

12/10/2026, Arquiteto. Base documental `9a6b23f`; código examinado `1d2d40a221dad1a5ec9188158dbc624f329023c7`. Entrada: [L4](L4.md), relatórios por cartão e recibos locais. Esta entrega altera somente documentação e registros de revisão; código e experimentos novos cabem ao Implementador.

**Próxima execução: L5-01, primeira seleção/expansão P3, intercalando L5-03 e L5-04.** L5 continua cartões abertos e consome os componentes entregues em L4. Não reiniciar tokenizer/ledger fake, XRW2, captura ou R1/R2. [ADR 027](../decisoes/CONTEXTO-P3.md) resolve o contrato de comparação, obrigações, orçamento e expansão. Nenhum gate foi liberado.

## 1. Parecer e evidência verificada

| Entrega | Parecer | Limite do aceite |
|---|---|---|
| L4-01 / M0-04 | Aceitar medição offline com perfil fixado, sidecar verificável, ledger fake e readiness | Não há adapter real/smokes pagos, usage real nem custo competitivo |
| L4-02 / M0-06 | Aceitar XRW2 funcional, reaproveitamento de worker, cache/reset, falhas/retry e reservas retidas | CPU/RSS e comparação completa dos três modos continuam pendentes |
| L4-03 / M0-11 | Aceitar primeira IR e recorte Rust R1/R2 com evidência e invalidação conservadora | R3/R4, cobertura geral de referências e outras famílias permanecem abertos |
| CI nativa | Recibo do run38248278388 registra sucesso nos três jobs do SHA acima | Revalidação local dos recibos, sem nova consulta ou execução remota nesta revisão |

Reexecutei o [verificador entregue](logs/L4/verify-native.py), usando o ambiente Python fixado disponível. [Registro desta revisão](logs/revisao-L4/recibos-nativos.json): exit0, hashes das 28 fontes no commit, replay dos 20 legados e cinco medições por host, ledger, comparação XRW2 e matrizes semânticas conciliados. Por host: 29 equivalências diretas; Rust R1/R2 33/33, Tokio 4/4, contraprovas 6/6, nenhuma promoção indevida nessas matrizes. O script verifica os resultados registrados; não reexecuta os testes Rust nos hosts.

Fontes do parecer: [readiness](../../eval/reports/m0-agent-readiness.md), [workers persistentes](../../eval/reports/m0-workers-persistent.md), [semântica](../../eval/reports/m0-semantics.md), [dependências](dependencias-L4.md) e [CI](logs/L4/ci-native-run.json). O total de 50 testes de harness inclui skips; L4 discrimina 49+1 Linux e 45+5 macOS. Não apresentar os 50 como aprovados integralmente em cada host.

Os 1285/1286 tokens dos hosts correspondem a payloads originais diferentes. A propriedade exigida é replay dos mesmos bytes com o mesmo perfil; não normalizar históricos para forçar igualdade. A amostra Tokio captura um arquivo como raiz experimental, não uma crate completa; 4/4 não comprova call graph real completo. Não há nova conclusão M0: estados dos 41 cartões e gates permanecem.

## 2. Decisões e pendências resolvidas

| ID de revisão | Resolução | Aplicação |
|---|---|---|
| L4-P01 | Comparação v3 experimental explícita; v2 preservado. O verificador v2 hoje rejeita duas revisões | ADR 027 §2, L5-01 |
| L4-P02 | Obrigações atribuídas, status de insuficiência/lacuna, contagem do envelope inteiro e manifesto fixado com retenção | ADR 027 §§4–6, L5-01 |
| L4-M01 | **Quatro smokes pareados no total, uma tarefa por família**, conforme M0-04. A redação ambígua do ADR 026, reproduzida no readiness L4, não amplia para 16 tarefas | ADR 026 corrigido nesta revisão; conciliar readiness corrente no próximo incremento, preservando relato histórico. Dois braços significam oito sessões antes de retries; mais braços/repetições precisam entrar na projeção de recursos |

O Implementador não relatou nova decisão bloqueante. P01 foi identificado nesta revisão ao confrontar contrato, schema e verificador. P02 torna executável a próxima prova; não é defeito declarado de produto existente. M01 esclarece a unidade do aceite, sem autorizar despesas.

Continuam externos/operacionais: host literal macOS15.0, domínio macOS descartável, recurso/modelo/teto para sessões reais e licença do produto antes de distribuição. Não decidir licença em nome do mantenedor nem encerrar prova de SO por deployment target. Essas pendências não impedem o trabalho local abaixo.

## 3. L5-01 — Contexto e expansão com comparação verificável

**Continua:** L4-05 / M0-09. **Entrada já disponível:** captura, primeira IR Rust, medidor de L4. A integração inicial pode começar sem fechar todas as famílias de M0-11/M0-04; dependências do aceite integral permanecem. **Responsabilidade:** módulos/driver/testes em `crates/xrai-eval`, perfil em `docs/contracts/experimental-p3/`, fixtures em `eval/context/` e relatório `eval/reports/m0-context.md` (novos caminhos planejados).

1. Concretizar ADR 027 §2 com exemplos positivos/adversos: duas revisões explícitas válidas, mistura sem comparação, terceira revisão, hash/configuração errada, head divergente, diff inconsistente e expansão em nova geração. Preservar todos os testes v2.
2. Implementar fluxo pedido→fontes/IR→obrigações→alternativas→seleção→medição→manifesto→expansão. Primeiro fixture deve resolver definição com evidência real da IR e manter candidato/unknown sem promoção. Fazer controles com P2 desligado/ligado e head/base+head.
3. Demonstrar consumidor removido recuperado de base, função grande com hunk central, limitação por bytes e tokens, contexto expirado e expansão após publicação de outro snapshot. Verificador separado confronta fonte/span/hash e mede bytes finais.
4. Entregar resultados das curvas 2k/4k/8k/16k/32k quando a primeira fatia estiver estável, inclusive perdas e custos de expansão. Não usar o oracle para selecionar.

**Primeira entrega revisável:** perfil documental v3 + um contexto e duas expansões (sucesso e insuficiência/expiração), recibos de fonte/orçamento e controles equivalentes nas duas plataformas. Relatório distingue o que foi apenas fixture do que foi medido em fonte real. Fechar M0-09 exige restante do cartão, não somente essa vertical.

## 4. L5-02 — Rust R3, depois R4 e outras famílias

**Continua:** L4-03 / M0-11. **Responsabilidade:** IR/resolver experimental, `eval/semantics/`, verificador e relatório semântico. **Decisão:** ADR 025; não usar P3 como justificativa para promover lookup parcial a grafo completo.

Próxima fatia: ambientes locais/bindings/shadowing e configuração. Rotular antes das regras os casos resolvíveis e os conservadoramente desconhecidos; declarar suporte por forma sintática. Capturar configuração conhecida versus não avaliada e invalidar inclusive conclusões negativas. Parametrização/padrões ainda não suportados precisam marcar o escopo pertinente, sem resolver por nome global como fallback factual.

Preparar pares A→B: inserir binding que sombreia alvo, remover binding, trocar configuração, criar/remover export; comparar snapshot semântico completo com rebuild B. Ampliar a amostra real para pacote/módulos capturados com manifest explícito de inclusão/exclusão/configuração, sem executar build scripts ou inferir ambiente do host. Preservar a medição histórica do arquivo Tokio.

Depois implementar R4 com receptor demonstrável e contraprovas de interferência de traits/macros; avançar TS/JS, Python e Go pelos recortes próprios do protocolo. Reusar interface de evidência sem impor regras Rust às outras famílias. Critérios ≥80% dos pré-rotulados resolvíveis e zero promoção indevida nas fixtures permanecem; precisão/recall reais têm denominadores separados. Primeiro incremento R3 não conclui M0-11.

## 5. L5-03 — Encerrar medição de recursos dos workers

**Continua:** L4-02 / M0-06. **Responsabilidade:** drivers/medidor de recursos e relatório; alterar supervisor somente se a medição revelar necessidade. **Decisão:** ADR 026 §3. XRW1/XRW2 já funcionais são controles a preservar.

Congelar matriz antes de medir: direto/XRW1/XRW2, sete dialetos, fontes pequenas/médias/densas/grandes/com erro, repetidas/distintas, cold/warm; três sessões independentes por modo e pelo menos 30 pedidos por classe/sessão como desenho inicial do ADR 026. Registrar tamanho/hash, ordem, concorrência e falhas. Não escolher só entradas que beneficiem cache.

Medir CPU user/sys de pai+filhos e soma RSS em instantes comuns, com série bruta, intervalo de amostragem e custo do sampler separado. Accounting de filho persistente usa deltas ou total de sessão, nunca repetir cumulativo por pedido. Incluir resposta retida/consumidor lento na calibração de fila/reservas; cap lógico não é RSS. Reportar indisponibilidade como null e justificativa.

**Aceite:** comparação nativa dos dois alvos, análise das perdas, modo recomendado e limites calibrados com evidência. Não exigir percentual de ganho; uma conclusão desfavorável à persistência é válida. M0-06 só fecha com matriz/recursos completos, provas de falha e demais critérios do cartão. Não confundir esse fechamento com piso literal de M0-05.

## 6. L5-04 — Fazer o corpus avançar além dos quatro pilotos

**Continua:** L4-04 / M0-03.R1. **Responsabilidade:** `eval/qualification/`, oracles/materialização/probes e relatório. **Decisão:** ADR 021 e projeção da revisão L3, que permanece válida: quatro correções históricas, apenas Django complexo; D1 global 0/32 admitidos.

Entregar a matriz viável de 32 slots e **quatro dossiês novos** cobrindo lacunas de complexidade, tipos e JavaScript; não repetir apenas a curadoria dos quatro antigos. Selecionar repositórios/casos dentro dos pisos, máximo quatro primários por repo, duas tarefas JS e duas TS e quatro complexos por família distribuídos em dois projetos. A projeção condicional mantém 28 tarefas, 15 complexas e 12 históricas adicionais, sem somar categorias sobrepostas.

Cada dossiê inclui commits/fontes/hashes, justificativa real, porte conservador, configuração/setup, solução de referência/probes/regressões fora dos inputs do agente e revisão independente. Registros provisórios não viram admitidos porque os testes do gate passaram. Eventuais eventos de estado A→B usam processo/índice preservado; não apenas indexar B do zero. Concluir posteriormente a matriz global e os eventos A→B nas quatro famílias conforme cartões/ADR, preservando controles suplementares.

**Aceite do incremento:** novos dossiês reproduzíveis, lacunas restantes quantificadas e gate global ainda fechado se faltar critério. ENOSPC/setup custam infraestrutura e não são derrota semântica. Não transformar ausência de runner em resultado de probe.

## 7. L5-05 — Adapter real pronto e quatro smokes condicionados

**Continua:** L4-01 / M0-04 e M0-04.R1. **Responsabilidade:** harness/adapters/tests/readiness/relatório. Reutilizar tokenizer/serializer e ledger L4, preservando `fake-offline-v1` como controle.

Implementar um adapter real configurável para o provedor/modelo efetivamente disponível, após conferir sua documentação e recibos; construir fixtures de protocolo sem chamadas pagas antes de conectar. Fixar modelo/versão/configuração e tabela de preço/unidade/validade, distinguir usage observado de estimativa, validar terminal/stream/retry/duplicata, reserva conservadora e teto. Não declarar `real_run_ready` apenas porque existe classe de adapter: exigir recurso, credencial, limite financeiro/runs e contenção do domínio.

Manifesto separa configuração do smoke pareado D0/seed e campanha D1. Preparar estimativa concreta de oito sessões mínimas, retries máximos, tokens/tempo/armazenamento e reserva; não executar sem recursos/teto autorizado. Corrigir a unidade dos quatro smokes em M01. Uma tarefa real por família, dois braços declarados e sessões isoladas; resultado não comprova vantagem. macOS local conhecido não se torna ambiente para shell arbitrário por esse adapter.

**Aceite local:** replay de fixtures do adapter, falhas/cobrança desconhecida e readiness com causas acionáveis. **Aceite completo M0-04:** quatro smokes reais e demais critérios, preservando pendências separadas quando faltarem recursos. Trabalho local não precisa aguardar orçamento pago.

## 8. L5-06 — Preflight e preparação competitiva

**Continua:** L4-06 / M0-12 e M0-10. **Responsabilidade:** comparadores, manifestos e relatórios de impedimentos. Preparar triagem dos oito concorrentes/configurações fortes, versões verificadas e scripts/receipts de setup dentro do ambiente disponível. Registrar indisponível/excluído e motivo, sem substituir configuração forte por modo fácil só para vencer.

Preparar matriz tarefa×braço×repetição, seeds/ordem, prompts congelados e amortização de setup/indexação antes dos resultados. D1 só entra após qualificação global; smokes não exigem D1. Readiness aponta separadamente corpus, P2/P3, harness, contenção, orçamento/modelo e prova nativa. Host15.0 exige execução real; mac descartável exige teardown demonstrado. Teto/licença são decisões nos momentos próprios, não bloqueio genérico ao lote.

**Aceite:** manifest/configuração verificáveis, projeção de recursos e motivos específicos de não execução; campanha apenas quando suas condições estiverem satisfeitas. G0/G1/G2 continuam exatamente os do protocolo, sem flexibilização por esta revisão.

## 9. Ordem, entrega e limites da revisão

Iniciar L5-01; intercalar L5-03/L5-04 e ampliar semântica em L5-02. L5-05/06 podem preparar trabalho offline enquanto recursos reais faltarem. O lote organiza responsabilidade e não solicita subagentes nem novas conversas. Não deixar todo avanço de corpus/contexto para depois de tornar a infraestrutura universal.

Ao entregar: relatório L5 com critérios por incremento, comandos/exits/ambiente, fontes/hashes, failures/skips, limitações e decisão arquitetural necessária se surgir. Atualizar estado somente por aceite efetivo. Verificações pertinentes e commit/push conforme AGENTS.md; não declarar publicação antes de confirmar.

Exploração: graft e codebase-memory Tier2, descoberta na geração `2026-10-12T12:26:27Z` e cobertura final na geração `2026-10-12T12:48:34Z`; discovery/trace/snippet do lookup e inspeção de readiness/worker. Cobertura dos paths de código sem lacunas registradas; candidatos JSONL sem freshness rastreada foram lidos diretamente. O trace incluiu ligações aparentes a helpers homônimos de outros arquivos e não foi usado como prova de integração. Fonte exata/recibos sustentam as conclusões. Verificador/schema documental lidos diretamente; revisão dirigida, sem auditoria exaustiva de segurança ou reexecução dos testes nativos.

[Recibo documental](logs/revisao-L4/documentacao.json) registra links, IDs/dependências/estados/gates preservados e hashes. [Revalidação dos recibos L4](logs/revisao-L4/recibos-nativos.json) é execução local de verificação offline, não campanha ou nova CI. Nenhum código do produto foi alterado pelo Arquiteto.
