# Revisão L5-C02 — corpus nas quatro famílias e próximo incremento

12/10/2026, Arquiteto. Base `0c7064e`; entregas `e02370a` e `aadab48`. [Relato do Implementador](L5-C02.md), [estado](../STATUS-IMPLEMENTACAO.md) e [roteiro v1 / ADR 028](../ROTEIRO-V1.md). Revisão dirigida de arquitetura/evidências; nenhuma implementação de produto ou execução upstream nesta entrega.

## 1. Aceite e avanço real

**C02 aceita no escopo atual.** A derivação distingue curadoria, revisão, comportamento, preparo/execução de evento, elegibilidade individual e admissão global. A matriz factual é comparada à recomposição das evidências, não aceita apenas por possuir hashes consistentes. Python/Go completam os quatro novos dossiês; são contratos controlados em fontes reais, sem alegar bugs históricos dos upstreams.

| Dimensão | Parecer anterior | Agora |
|---|---|---|
| Novos pares comportamentais/revisados | 2/4, Rust e JS | 4/4, incluindo Python e Go |
| Novos dossiês individualmente elegíveis | Contabilização aguardava C02 | 4/4, recomputados |
| Total individualmente elegível, com pilotos | Projeção condicionada à conciliação | 8: cinco complexos, seis históricos, oito multimódulo |
| Restante condicional, mantendo os oito | 26 tarefas após eventual aceite dos dois pares | 24 tarefas, 11 complexas, 10 históricas, 12 multimódulo; categorias sobrepostas |
| Casos reais de estado requeridos | Nenhum selecionado/comprovado | 0/4 preparados e executados |
| Corpus global / gates | 0/32; nenhum gate avaliado | Inalterado |
| M0/M1 / estabilização | 9 concluídos, 7 em andamento, 25 não iniciados; seis V1 condicionais | Inalterado; M1 não iniciado |

Python: três falhas de contrato esperadas na base, três requisitos aprovados na referência e duas regressões aprovadas em cada lado. Go: a mesma contagem, com asserções nomeadas de contrato, não falhas de infraestrutura. CI dedicada `38294106923` e regular `38294095468` usam **`e02370a`**, não os commits posteriores de aceite/documentação. Oito domínios têm encerramento registrado. Go comprova fontes antes e locks antes/depois; não comprova inventário integral pós-probe. Hashes de runtimes/toolchains nos exports são relatos do produtor; seus bytes não estão retidos.

[Revalidação desta revisão](logs/revisao-L5-C02/evidencias.json): recomposição exata dos dois ZIPs originais e respectivos 13/14 arquivos, provas comportamentais, matriz C02 e slots aprovados. Gate global recusou por conjunto incompleto. Os dois manifests de publicação foram conferidos nos respectivos commits históricos. Nenhum teste comportamental, binário nativo, campanha paga ou CI foi reexecutado pelo Arquiteto. Metadados desses runs são os exports retidos.

O avanço fecha uma lacuna de **preparo da avaliação** nas quatro famílias. Não acrescenta semântica Python/Go ao xrai, nem demonstra melhora de sucesso dos agentes. O caminho continua M0/G0 → confirmação/G1 → alpha/G2 → seis atividades de estabilização. Não há base nova para data ou percentual do v1.0.

## 2. C03 — Da elegibilidade ao evento executado e à campanha

C02 pode registrar um caso de estado como individualmente preparado antes de executá-lo: `event_state` verifica a preparação para essa elegibilidade e mantém execução separada. Isso é aceitável para acompanhamento. Entretanto, `verify_qualified.validate` atualmente confere descritor/sequência/oracle e quotas; **não exige recibo de execução A→B**. A validação C02 de execução confere três booleanos de continuidade/igualdade, sem reconstruir a prova. Não são ainda o aceite operacional dos quatro eventos reais. Hoje não há liberação indevida: o conjunto continua incompleto e fechado.

**Decisão C03:** antes de uma campanha, exigir conjuntamente corpus completo qualificado, os quatro eventos requeridos executados/reconciliados e os demais critérios de readiness/orçamento. O gate/preflight efetivo consumido pelo executor deve impor isso, sem depender de leitura humana de relatório. É permitido manter comandos distintos para curadoria e readiness; nenhum resultado isolado pode liberar a campanha. Nenhuma flexibilização de G0/G1 ou da quota por família.

### Próximo aceite L5-04: quatro casos de estado

1. Selecionar quatro tarefas independentes nos slots `state_config`, uma por família; congelar fonte A/B, configuração, input natural, evento, oracle e relações antes do resultado. Os targets atuais são sugestões, não aprovação de uma tarefa. Não duplicar correção/contrato ou contar o exercício suplementar Rust como outra amostra.
2. Cada evento deve alterar um fato observável relevante à tarefa: fonte, disponibilidade, binding/relação ou configuração declarada. Reescrever os mesmos bytes só para gerar um evento não basta. Definir consultas aquecidas em A, expectativas em B e contraprova para resultado obsoleto; não exigir resolução integral do upstream.
3. Manter processo/sessão/índice ao aplicar B; registrar identidade e continuidade, revisões/fontes/configuração, invalidação e respostas completas. Comparar incremental B com rebuild B independente no recorte inteiro anunciado, incluindo unknown, cobertura, diagnósticos e relações. Normalizar apenas diferenças operacionais declaradas; não remover campos divergentes após observar o resultado.
4. Vincular recibo a task/slot/família/linhagem, descriptor e hashes A/B, consultas/oracles, executável/configuração, ambiente, sequência, saídas e encerramento. Recomputar comparação a partir dos artefatos; três flags `true` não substituem os resultados. Hash de PID sozinho não prova continuidade. Usar o adapter experimental necessário, sem antecipar banco/índice de produção M1.
5. Adicionar contraprovas: recibo ausente; cold B ou processo reiniciado; evento suplementar; recibo de outro caso/binário/configuração; remoção de unknown/diagnóstico divergente; saída truncada; simples mudança de flags/hash da saída. Casos preparados podem continuar contados como preparados, mas não como evento executado nem campanha pronta.

Primeira entrega revisável: quatro descritores, um evento integral de ponta a ponta e contraprovas; depois completar os outros três. Para TS/JS, alinhar o evento à primeira fatia semântica implementada. Enquanto isso, fonte/estado podem ser medidos com capacidade explicitamente limitada; não anunciar invalidação semântica ainda inexistente.

## 3. S01 — Dependências do corpus congelado

A pendência `C02-DEPENDABOT-TRIAGE` foi investigada por consulta autenticada somente leitura em 12/10/2026. [Snapshot com os 55 alertas e fontes](logs/revisao-L5-C02/dependencias.json): todos abertos, 9 críticos, 14 altos, 25 médios e 7 baixos, **todos em `eval/qualification/l5-real/go/setup/go.mod`**. Classificação de propriedade resolvida: são dependências do setup congelado do Gitea, não evidência de que essas mesmas dependências compõem o executável Rust. Isso não prova ausência de outras vulnerabilidades nem elimina exposição do harness/setup.

**Decisão:** preservar os pins e recibos da prova histórica/controlada. Não atualizar o `go.mod` congelado silenciosamente, apagar alertas em lote, desativar o scanner ou declarar falso positivo por pertencer a teste. Código vulnerável pode ser compilado/executado nos probes. Atualizações de dependências do produto e das ferramentas ativas seguem correção normal com testes; corpus requer outra decisão de tratamento por exposição.

**Próxima atividade do Implementador, antes de nova execução afetada:** para cada alerta, registrar GHSA/versão/faixa/correção indicada, componente realmente compilado/executado, entrada que poderia alcançá-lo, exposição em download/build/teste e eficácia/limites dos controles. Priorizar críticos/altos e caminhos envolvendo filesystem, subprocessos, autenticação e rede; agrupar avaliações somente quando compartilharem a mesma evidência. O snapshot já fornece IDs e versões corrigidas informadas pelo GitHub, sem prescrever upgrade automático.

Se a prova puder continuar com risco delimitado, registrar justificativa por alerta e execução descartável, sem segredos/acesso do agente ao host, rede desabilitada durante probes e saída limitada. Se precisar corrigir dependência para executar, preservar o baseline original, criar variante de setup explicitamente identificada e revalidar os dois lados/regressões antes de reutilizar resultados. Se o controle necessário não existir, suspender somente aquela execução e continuar curadoria/semântica/contexto independentes. Nenhum alerta foi fechado nesta revisão; classificação por manifesto está concluída, aplicabilidade/remediação por advisory ainda pendente. Fechamento remoto exige evidência individual e decisão explícita de tratamento, não é necessário para trabalhar localmente.

Na próxima alteração do executor Go, acrescentar inventários antes/depois das fontes, oracle e ferramentas que deveriam permanecer imutáveis; declarar separadamente cache de build/scratch graváveis. Uma alteração entre fase de requisito e regressão deve ser detectada. Preservar os recibos aceitos e seu limite; não reexecutar CI apenas para trocar a redação histórica.

## 4. Continuidade por família e atividade

Mantendo as oito tarefas elegíveis e os pisos atuais:

| Família | Tarefas adicionais até oito | Complexas adicionais até quatro | Históricas adicionais até quatro |
|---|---:|---:|---:|
| Rust | 6 | 3 | 2 |
| TS/JS | 6 | 3 | 2 |
| Python | 6 | 2 | 3 |
| Go | 6 | 3 | 3 |

Cada família ainda exige dois repositórios com pelo menos duas tarefas complexas em cada; a contagem agregada não satisfaz essa distribuição. Preservar estratos, teto por repo, limites de controlados e pisos TS/JS. Os quatro casos de estado fazem parte das 24 tarefas restantes, não são 28 novas. O aceite dos contratos controlados Python/Go não reduz o déficit de origem histórica.

| Ordem da próxima entrega | ID existente | Trabalho e aceite |
|---|---|---|
| 1 | L5-04, com L5-05 para o preflight | C03: descritores/quatro eventos, prova recomputável e bloqueio de campanha sem execução; adaptar matriz/readiness aos demais tipos de tarefa |
| 2 | L5-02 | Primeira fatia TS/JS de imports/exports/bindings; escopos e homônimos, configuração/resolução explícita, labels externos e relação útil em fonte real; manter R3 e delimitar R4 por perdas |
| 3 | L5-01/05 | Recuperação lexical sem âncora, alternativas e custo integral; adapter real com replay offline, ledger e estimativa dos quatro smokes pareados. Recursos pagos somente com teto autorizado |
| 4 | L5-04 | Mais tarefas históricas/revisão/controles, respeitando a matriz por família/repo; converter dossiês elegíveis para o schema/materializador de admissão com mapa de IDs e proveniência, sem rebatizar seed |
| 5 | L5-03/06 | Controle `direct_cached`, recursos reais/concorrência/calibração e comparadores/preflight conforme critérios anteriores |

S01 acompanha qualquer execução afetada e não exige parar o restante. Em C02, a derivação atual cobre oito correções/contratos específicos; ao ampliar para estado/revisão/controle, aplicar aceite próprio de cada tipo. Não impor par baseline/reference de correção a toda pergunta/controle, nem generalizar elegibilidade sem oracles adequados. Não existe lote L6 novo nem alteração de estados dos 41 cartões.

**Higiene de status:** `case.json` e READMEs Python/Go ainda descrevem o preparo com comportamento pendente; a matriz C02 e seus recibos são a visão vigente. Adicionar ponte explícita nos READMEs para essa visão derivada, identificando o checkpoint histórico; preservar bytes congelados usados nos hashes. Consumidores devem usar a derivação corrente, não flags antigas nem números copiados manualmente. Isso é manutenção de clareza, sem exigir repetir probes já aceitos.

## 5. Verificação e limites da revisão

Graft localizou os verificadores; codebase-memory Tier 2, geração `2026-10-12T19:18:26Z`, search/trace/snippet de `event_state` e cobertura de 17 paths sem lacuna registrada, com ressalva best-effort. Leitura dirigida dos gates, runners e workflow confirmou as fronteiras descritas. Não houve auditoria exaustiva do runtime nem confirmação de explorabilidade dos advisories.

[Evidências](logs/revisao-L5-C02/evidencias.json), [dependências](logs/revisao-L5-C02/dependencias.json) e [checks documentais](logs/revisao-L5-C02/documentacao.json) registram o recorte. Estados e dependências dos 41 cartões, seis V1 condicionais e gates preservados. Publicação da revisão somente após commit/push confirmado, conforme AGENTS.md.
