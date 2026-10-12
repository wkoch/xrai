# Revisão arquitetural L3 e continuação L4

12/10/2026, Arquiteto. Base documental `98cca55`; código da CI examinada `21e9279a7502ed398e3b1d8321495142376e78af`. Entrada: [relatório L3](L3.md), relatórios por cartão e recibos locais. Planejamento solicitado pelo usuário; nenhum código/experimento de produto foi executado nesta revisão.

**Próxima execução: L4-01 local e primeira fatia L4-03 Rust, intercalando L4-02 e expansão L4-04.** L4 detalha a parte restante de L3. IDs M0/M1 permanecem; não reiniciar captura, corpus inicial ou supervisor entregues. ADRs [025 — semântica](../decisoes/SEMANTICA-P2.md) e [026 — workers/medição](../decisoes/WORKERS-E-MEDICAO.md) especificam as fronteiras seguintes. Não resta decisão do Arquiteto necessária para iniciar essas frentes locais.

## 1. Parecer sobre L3

| Entrega | Parecer | Limite preservado |
|---|---|---|
| M0-08 original e R1 | Manter concluídas no escopo do spike; recibos registram 35 testes Linux/34 macOS, drivers e quatro eventos por host | Confinamento e consistência continuam limitados pelo ADR 023; não é snapshot global atômico nem captura de produção já promovida |
| L3-01 / qualificação vertical | Aceitar quatro pilotos como incremento de curadoria: pares e revisão documentados | D1 global continua não admitido. Quatro candidatos não são 4/32 tarefas competitivas já aprovadas |
| L3-02 / contenção | Manter aceite do recorte Linux, com evidência externa nos casos em que o avaliador morreu | Mac local known-smoke não autoriza shell arbitrário; domínio descartável macOS continua pendente |
| L3-03 / workers | Aceitar framing/supervisão e equivalência nativa do primeiro recorte | 13 testes/18 comparações por host não fecham CPU/RSS ou persistência. O pool atual limita concorrência, mas cada tentativa inicia processo |
| CI L3 | Recibo local registra três jobs aprovados, run 38239765003, no SHA de código acima | Nesta revisão não houve nova consulta/reexecução de CI; preservar a primeira falha e correções |

Evidências examinadas: [CI](logs/L3/ci-native-run.json), [conferência nativa](logs/L3/native-receipts-final-verification.json), [workers](../../eval/reports/m0-workers.md), [corpus](../../eval/reports/m0-corpus-qualification.md) e [contenção](../../eval/reports/m0-harness-containment.md). O relato mostra macOS 15.7.9 e Ubuntu 24.04.5/glibc 2.39; literal macOS 15.0 permanece sem prova. Gates G0/G1/G2 não avaliados e CLI de produção ainda scaffold.

Não apareceu nova pendência arquitetural formal no relatório do Implementador. Esta revisão antecipa decisões necessárias à próxima implementação: conclusão de mensagens em conexão persistente, retenção de respostas, contabilidade de sessão e resolução semântica delimitada. Não converter lacunas conhecidas do spike em regressões imaginárias.

## 2. L4-01 — Tokenização, ledger e readiness local

**Continua:** L3-05 / M0-04. **Entrada:** replay v1/v2 e contenção L3. **Responsabilidade:** `crates/xrai-eval/harness/`, schemas/tests, `eval/reports/m0-agent-readiness.md` (planejado). **Decisão:** ADR 026 §§4–6.

Primeiro entregar medição offline derivada de transcript/projeção e fingerprint de tokenizer, sem editar históricos com null. Em seguida, adapter fake e schema de sessão real com eventos/attempts, usage/custo conhecidos ou desconhecidos. Só depois ligar provedor disponível dentro de recursos autorizados. Manter diferença entre texto entregue ao modelo, stdout binário e resposta pública do xrai.

**Aceite local:** vetores de tokenização/serializer fixados, hashes, replay das duas versões antigas, falsificação de medição recusada, fake com timeout/stream parcial/cobrança ausente/retry/duplicata e limite concorrente. Manifest de readiness distingue smoke D0/seed de campanha D1. Quatro smokes reais continuam pendentes até modelo/teto/permissão de uso e contenção pertinentes; não bloquear desenvolvimento local por isso.

**Primeira entrega revisável:** um transcript existente medido offline com sidecar verificável + uma sessão fake completa e uma falha com cobrança desconhecida. Nada disso é sucesso de agente ou custo competitivo observado.

## 3. L4-02 — Pool persistente e recursos

**Continua:** L3-03 / M0-06. **Entrada:** XRW1 e provas nativas existentes. **Responsabilidade:** `crates/xrai-eval/src/worker_spike.rs`, binário/testes e relatório de workers; reorganizar internamente se necessário. **Decisão:** ADR 026 §§1–3.

Antes de editar, mapear callers/consumidores do codec e supervisor, incluindo drivers/fixtures; preservar XRW1 como controle. Implementar XRW2 com handshake/encarnação, framing por mensagem, um pedido em voo por worker e conclusão sem EOF. Testar persistência, falhas e retenção de tickets antes de medir ganhos. O primeiro cache reutiliza gramática/query; AST/cache incremental não é exigido.

**Aceite:** mesmo PID/encarnação processa sequência saudável de pedidos/dialetos/configurações; erro/timeout/cancelamento substitui worker sem bloquear outro; resposta de tentativa antiga não publica; consumidor lento não libera reserva cedo. Provas dos dois alvos, cold/warm separados, fontes reais, CPU pai+filhos e RSS simultâneo amostrado com limitações. Comparação direta/processo por tentativa/persistente tem amostras e falhas brutas.

**Primeira entrega revisável:** dois pedidos e depois uma falha no mesmo worker, substituição e pedido saudável; XRW1 ainda passa. Fechar M0-06 exige restante da matriz/recursos, não ganho percentual arbitrário. Se pool persistente não compensar, documentar escolha fundamentada preservando contenção.

## 4. L4-03 — IR e resolver Rust vertical

**Continua:** L3-06 / M0-11. **Entrada:** captura/parsing/contrato e harness local. **Responsabilidade:** módulos experimentais em `crates/xrai-eval`, fixtures rotuladas e `eval/reports/m0-semantics.md` (planejado). **Decisão:** ADR 025.

Entregar R1/R2 (módulos, namespaces, imports e reexports) com consulta local e evidências; depois R3/R4 (shadowing, cfg, método inerente demonstrável). A primeira consulta deve separar dois símbolos homônimos em módulos distintos, seguir alias/reexport e retornar a fonte exata do destino com cadeia de evidência. Uma segunda consulta com módulo/configuração ausente deve preservar a lacuna, sem inventar alvo.

Adicionar atualização no mesmo índice experimental: consulta em A sem export → criar export B → invalidar lookup negativo → consulta em B igual a rebuild B. Incluir remoção e nova configuração. Invalidar pacote inteiro é aceitável inicialmente; não implementar fine-grained engine antes de provar correção.

**Aceite:** matriz do ADR 025 com positivos/negativos/ambíguos e comparações incremental/rebuild. Casos resolvíveis rotulados antes das regras; critério ≥80% e nenhuma promoção indevida nas fixtures permanecem. Relatório diferencia erro de parser, extração, ambiente de nomes, resolução e invalidação. Produção, quatro type checkers universais e H1 não entram nesta fatia.

**Primeira entrega revisável:** R1/R2 Rust, consulta com evidência, caso unknown e evento negativo→resolved demonstrados em fixtures e uma amostra real de desenvolvimento. Não concluir M0-11 só com Rust: TS/JS, Python e Go continuam obrigatórios no recorte do protocolo; estendê-los após estabilizar a interface mínima, sem congelar abstração que force semânticas iguais.

## 5. L4-04 — Completar corpus por lacunas mensuráveis

**Continua:** L3-01 / M0-03.R1. **Entrada:** quatro pilotos verticais aceitos localmente e ADR 021. **Responsabilidade:** `eval/qualification/`, fontes/oracles, verificadores/materializador e relatório de admissão.

Os quatro pilotos são correções históricas, um por família. Somente Django está marcado complexo; Tokio, TypeScript e Prometheus não estão. TS/JS só tem TypeScript entre os quatro. Não promover flags com base no tamanho bruto ou na conveniência da matriz.

Se todos os pilotos cumprirem o gate final e forem reaproveitados, a lacuna provisória é:

| Família | Correções restantes | Contratos | Estado/configuração | Revisão | Controle | Complexos adicionais mínimos | Históricos adicionais mínimos |
|---|---:|---:|---:|---:|---:|---:|---:|
| Rust | 1 | 2 | 2 | 1 | 1 | 4 | 3 |
| TS/JS | 1 | 2 | 2 | 1 | 1 | 4 | 3 |
| Python | 1 | 2 | 2 | 1 | 1 | 3 | 3 |
| Go | 1 | 2 | 2 | 1 | 1 | 4 | 3 |

São 28 tarefas faltantes por tipo, pelo menos 15 complexas e 12 históricas adicionais; as categorias se sobrepõem. Dos quatro pilotos, todos têm ao menos dois módulos de produção declarados; caso essa necessidade seja confirmada no gate final, faltam ao menos 16 casos para o piso de 20 relações entre módulos. Não somar esses pisos como tarefas extras. O verificador final, e não esta projeção, decide admissão.

Preparar uma matriz de **slots** por família/tipo/repo/linguagem antes de produzir todos os oracles. Cada família precisa de quatro complexos distribuídos em dois projetos com dois por projeto; máximo quatro tarefas primárias por repo. Se um piloto não complexo ocupar um slot de correção, escolher os complexos nos outros tipos, sem relabeling oportunista. TS/JS exige pelo menos duas tarefas JS e duas TS; acrescentar candidato JS elegível se os projetos triados não oferecerem necessidades reais em JS. Repositórios adicionais são permitidos desde que os pisos/cap se mantenham.

**Porte Rust:** até excluir testes inline, manter Tokio não complexo. O Implementador pode escolher outro projeto/caso que cumpra o piso por arquivos de produção verificados, ou produzir medição conservadora revisada. Uma primeira prova conservadora pode excluir arquivos/linhas de classificação duvidosa e só aceitar o piso se o limite inferior ainda bastar. Método por ranges deve registrar exclusões de itens test-only, casos mistos e hashes, com revisão independente e versão nova; nunca alterar a contagem antiga em silêncio. Não executar build script para classificar produção. O método do gate precisa corresponder ao método efetivamente medido.

Entregar em lotes pequenos com gate parcial distinto do global. Próximo incremento: matriz de 32 slots viável + quatro novos dossiês que ataquem lacunas de complexidade/linguagem/tipo, sem obrigar número por característica impossível numa só tarefa. Depois completar 32, controles negativos de revisão suplementares requeridos pelo desenho e eventos A→B em cada família. Linhagem não duplica patch como amostra independente.

**Aceite final:** todos os pisos do ADR 021, oracles/probes baseline/referência/regressões, revisão por segundo leitor com hash e política de adjudicação cega; gate rejeita dataset incompleto e aceita somente conjunto final congelado. Custos de compilação/setup e tentativas ENOSPC preservados como infraestrutura. Preflight de espaço/caches isolados antes de rodadas longas; remover apenas artefatos regeneráveis pertencentes ao run conforme política explícita, preservando fontes/recibos. Esta revisão não autoriza limpeza de dados do usuário.

## 6. L4-05 — Consumidor P3 sobre a primeira semântica

**Continua:** L3-07 / M0-09. **Entrada:** L4-01 tokenização pertinente e primeira IR/consulta estável de L4-03; aceite integral exige os recortes de M0-11. **Responsabilidade:** seletor experimental e `eval/reports/m0-context.md` (planejado).

Primeiro fluxo: pedido + snapshot → busca lexical/estrutural → relações com evidência → obrigações inferidas → representação/dedup → resposta limitada + expansão fixada. Demonstrar a mesma tarefa com P2 desabilitado/habilitado e base/head explícitos. A lista de obrigações do avaliador não entra no planner. Candidato/unknown pode motivar leitura adicional, nunca virar relação causal afirmada.

**Aceite do primeiro incremento:** fonte exata, orçamento serializado, obrigação conhecida não cabe → insuficiência explícita, expansão em mesma revisão, item removido em head ainda recuperável em base. Tabela registra também evidência relevante não identificada pelo planner. Depois curvas 2k/4k/8k/16k/32k e casos função grande/classe/arquivo pequeno. Ganho do payload não substitui julgamento de tarefa com agente.

## 7. L4-06 — Preparação competitiva e encerramento das provas

**Continua:** L3-08 / M0-12, M0-10. **Responsabilidade:** comparadores, manifest de readiness, relatórios dos cartões. Preparar triagem dos oito comparadores em versões verificadas e modos fortes; não eleger adversário por facilidade de instalação. Não executar campanha sem D1 qualificado, P2/P3/harness pertinentes e recursos autorizados.

Distinguir pendências no preflight: host macOS literal 15.0 (M0-05/G0), adapter macOS descartável (recorte M0-04.R1), modelo/tetos (smokes reais/campanha), licença do produto (distribuição). Cada pendência tem artefato/comando/configuração esperada e trabalho independente disponível. Não pedir ao usuário confirmação genérica para continuar todo o lote; preparar o pedido concreto somente quando necessário.

**Aceite da preparação:** manifesto que recusa execução por motivo específico, comparadores/configs/versões documentados, ordem/repetições/amortização fixadas antes dos resultados e projeção de recursos. Smoke pareado D0/seed não exige D1 global pronto; campanha M0-12 exige. G0 permanece condicionado a todos os critérios técnicos e competitivos, G1 a confirmação reservada e G2 à integração. Nenhuma revisão de arquitetura aprova esses gates por antecipação.

## 8. Ordem e conclusão de incrementos

L4-01 local e L4-03 são a próxima entrega de valor: medição verificável e relações úteis. L4-02 e L4-04 avançam independentemente; L4-05 consome suas dependências pertinentes; L4-06 prepara comparadores enquanto aguarda resultados. A lista não solicita subagentes/conversas; o Implementador organiza seu trabalho dentro das instruções aplicáveis.

Ao concluir incremento, atualizar relatório/estado com comando, fonte/hash, base commit, ambiente, saída/exit code, critérios comprovados e limitações. Executar checks pertinentes, commit e push conforme AGENTS.md; não inventar duração ou evidência. M0-04/06/11/09/12 só fecham com aceite integral. APIs públicas, banco e MCP de produção continuam após G1.

## 9. Evidência desta revisão

Graft localizou as fronteiras do worker/captura. Codebase-memory Tier 2, geração `2026-10-12T11:08:47Z`: worker consultado por search/trace/snippet, chamador de entrada e cinco callees diretos. Cobertura sem lacuna registrada nos paths de código consultados; candidatos JSONL sem freshness rastreada foram lidos diretamente. Inspeção de runner/schema e relatórios complementou o grafo. Não é auditoria exaustiva de segurança ou reexecução dos testes.

[Recibo documental](logs/revisao-L3/documentacao.json): links, IDs/dependências, estados anteriores preservados, seis incrementos L4, projeção do corpus e hashes das evidências consultadas. Fontes oficiais de Rust sustentam os pontos de linguagem no ADR 025. Publicação só será comunicada após commit/push confirmado.
