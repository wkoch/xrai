# ADR 027 — Contexto P3, comparação de revisões e expansão

12/10/2026. **Decisão do Arquiteto para M0-09. Primeira fatia experimental implementada em L5 e aceita na [revisão L5](../relatorios/REVISAO-L5.md); aceite integral pendente.** Complementa ADRs 007/015/025/026 e o [contrato](../contracts/m1.md). O Implementador concretiza schemas, código e provas. Promoção para domínio/CLI/MCP continua M1-23/M1-16/17/18 após G1.

## 1. Problema, decisão e alternativas

L4 fornece fontes capturadas, IR Rust inicial e medição offline. Falta provar que esses componentes selecionam evidência útil, preservam fatos removidos e permitem leitura adicional sob orçamento. O acerto de lookup de declaração não demonstra descoberta de todos os consumidores.

Motivação original em L4: o contrato permitia comparação base/head, porém `docs/contracts/verify.py` exigia que itens, afirmações e cobertura pertencessem ao único `response.snapshot`; o schema v2 não tinha descritor da comparação. L5 concretizou o perfil v3 separado, mantendo essa restrição em v2; o requisito deixou de ser apenas documental nessa primeira fatia.

**Decisão:** iniciar P3 com seleção determinística, fontes imutáveis, obrigações atribuídas e expansão por manifesto. Concretizar um perfil experimental v3 de comparação com dois snapshots explícitos; manter v2 e seus testes históricos. O mesmo motor atende uma revisão ou comparação. Não criar uma API de produção paralela nem fazer o verificador v2 aceitar mistura silenciosa.

Alternativas: usar somente head perde consumidores removidos; reconstruir base implicitamente a cada expansão quebra identidade; autorizar qualquer snapshot no envelope enfraquece o contrato; produzir seleção por LLM acrescenta custo e dificulta atribuir a contribuição de P2. Essas opções ficam fora da primeira prova. O algoritmo pode mudar após medição de perdas, com versão e hipótese registradas antes da rodada seguinte.

## 2. Perfil experimental de comparação

O Implementador acrescenta schemas, exemplos e verificador em `docs/contracts/experimental-p3/`, com `fixture_version:3` e `schema_version:3`. Trata-se de perfil documental/experimental, sem anúncio de capability pública. Campos comuns conservam o significado v2; exemplos/verificador v2 continuam executados. Atualizar a documentação de compatibilidade junto com essa implementação.

| Campo/regra | Definição a concretizar |
|---|---|
| `response.snapshot` | Snapshot principal; em comparação é exatamente head, inclusive configuração/produtor/worktree |
| `response.comparison` | `null` fora de comparação; caso contrário `{base: Snapshot, head: Snapshot}` com descritores completos, IDs distintos e ambos retidos |
| `params.base`/`params.head` | Ambos presentes ou ambos ausentes; somente IDs `snap_`; v3 inicial exige `revision.kind:fixed` e `revision.snapshot_id == head` em comparação |
| Itens/afirmações/cobertura | Snapshot obrigatoriamente igual ao principal, ou a base quando existe comparação explícita; evidências e alvos verificam os mesmos blobs/configuração da respectiva revisão |
| Relações | Cada relação semântica pertence a uma revisão. Correspondência base↔head é associação de comparação atribuída, nunca uma chamada/import causal entre tempos |
| `context_id` | Liga manifesto, par ordenado base/head (ou snapshot único), configuração, produtor, regras, seleção e retenção |
| `expand` | Seletor fixo aponta para o principal original; o par completo vem do manifesto, não de parâmetros substitutos |

`index` e `freshness` globais referem-se ao principal. Para comparação v3 inicial, usar `consistency.mode:snapshot`; registrar cobertura e limitações de base e head separadamente. Não anunciar validação do par a partir da validação de head. O pedido de modo ainda não suportado retorna indisponibilidade explícita. Primeira prova usa snapshots do mesmo workspace/worktree; comparação entre checkouts diferentes permanece fora do recorte.

Comparação é admitida somente em `context`/`expand`. Âncoras podem pertencer a qualquer lado explicitado; validar seu vínculo antes da recuperação, recusando terceira revisão com `anchor_revision_mismatch`. Contagens agregadas de cobertura contam unidades `(snapshot_id, file_id)` e relações de cada revisão, com partição por lado no recibo; não deduplicar denominadores históricos pelo path. `sufficiency` cobre obrigações dos dois lados e `support.producers` identifica os produtores usados em ambos.

Diff deve ser validado contra os blobs de base/head antes de gerar spans/obrigações: path, ranges e conteúdo removido/adicionado. Diff inconsistente retorna `invalid_request`. Diff sem base disponível pode sustentar investigação de head com limitação explícita em operação separada; pedido explícito de comparação com snapshot expirado retorna `snapshot_expired`, sem fallback silencioso. Rename por semelhança permanece candidato; não juntar identidades por nome. Não exigir acesso Git para consumir capturas já disponíveis.

## 3. Fronteiras em Rust e entradas do experimento

Implementar em módulos experimentais de `xrai-eval`; reaproveitar captura/IR/worker existentes. Separar responsabilidades, sem criar crates vazios: fonte imutável e consulta → recuperação de candidatos → obrigações → alternativas de representação → seleção/dedup → serialização/medição → manifesto/expansão. O domínio de seleção recebe dados tipados e não executa código do repositório.

Pedido contém intenção, descrição, âncoras, escopo, revisão/par e limites. Rótulos de relevância, patch de referência, resposta esperada, probes e relatório do avaliador não entram nessas entradas, na IR ou na pontuação. O processo avaliador pode confrontar a saída depois. Fixtures devem demonstrar essa separação por interfaces/arquivos, não apenas comentário.

Coleções têm ordem determinística; desempate por snapshot, path nativo codificado de forma estável, início do span e identidade. Fixar versão/pesos do seletor. Cache é derivado de blobs/configuração/produtor; mudança de pedido ou regra gera outro manifesto. Rebuild do mesmo input deve reproduzir seleção e hashes, salvo IDs/instantes explicitamente normalizados no recibo.

Uma interface de medição do spike pode chamar o helper offline fixado de L4 pelo harness. Isso é dependência de desenvolvimento, não prova de tokenizer incorporado/autonomia do produto. Medição participa da seleção final, não apenas da avaliação posterior de uma resposta que já excedeu o teto. Registrar chamadas/tempo do medidor no custo técnico.

## 4. Obrigações e estados

Obrigação interna tem identidade, motivo/regra, origem verificável (pedido/âncora/hunk/relação), revisão, prioridade, requisito mínimo de representação e itens que a satisfazem. O manifesto registra `satisfied`, `omitted_budget`, `unavailable` ou `not_assessed` e motivo; não importar obrigações ocultas do oracle. A contagem do envelope reflete esse conjunto, sem alegar que ele contém tudo de que a tarefa precisará.

| Intenção | Obrigações iniciais, quando identificáveis |
|---|---|
| `locate` | Localização e identidade da âncora; ponteiro pode bastar ao pedido de localização |
| `understand` | Definição/assinatura e trecho da âncora com contexto estrutural; dependências demonstradas pertinentes |
| `fix` | Trecho do diagnóstico/âncora, contrato relacionado e condições conhecidas relevantes; candidatos a teste atribuídos |
| `review` | Hunks válidos nos lados existentes, contêiner e contratos/consumidores demonstrados nas respectivas revisões |
| `impact` | Origem da alteração e caminhos de relação demonstrados; buracos de cobertura explícitos |

As regras só geram obrigações cujo objeto consigam identificar; domínio não analisado gera gap. Pedido sem âncora útil pode fazer busca lexical e informar `not_assessed`. Não converter termo coincidente em alvo resolvido. Candidato/unknown pode priorizar investigação e gerar fonte contextual, mas mantém estado e motivo originais.

L4 cobre sobretudo lookup Rust de módulos/declarações. A amostra Tokio é um arquivo tratado como unidade experimental. P3 não pode inferir dessa prova cobertura de crate, todos os callers ou impacto completo. Uma definição resolvida permite recuperar sua evidência; chamada só vira fato quando a ocorrência e sua resolução forem demonstradas. Se não existir relação suficiente, entregar fonte/candidato e lacuna.

Precedência preservada: erro operacional/request inválido → `error`; evidência obrigatória identificada que não cabe → `insufficient_budget`; lacuna de fonte/capacidade/trabalho → `partial`; `ok` somente no recorte declarado sem esses impedimentos. `sufficiency:satisfied` significa apenas obrigações identificadas satisfeitas. Não atribuir `insufficient_budget` a fonte que nunca foi capturada; ela é indisponível. Se coexistirem ambas, preservar os dois motivos, com o status de orçamento prioritário conforme contrato.

## 5. Representações, seleção e limites

1. Aplicar exclusões, revisão, capacidade e limites de trabalho antes do ranking. Limitar candidatos/arquivos/fonte/expansões/deadline. Resultados interrompidos mantêm gap, sem cobertura completa.
2. Gerar alternativas por objeto: ponteiro, assinatura, trechos AST centrados no hunk/âncora, símbolo inteiro, arquivo inteiro. Ponteiro não satisfaz obrigação de conteúdo; assinatura não substitui corpo quando o requisito pede comportamento. Não selecionar apenas o prefixo de função grande.
3. Alocar primeiro representações que satisfazem obrigações obrigatórias. Depois, ganho marginal por custo serializado e diversidade de evidência; sem quotas fixas por categoria. Heurística inicial não promete ótimo global nem monotonicidade de ranking ao ampliar orçamento.
4. Deduplicar intervalos sobrepostos da mesma revisão/file/hash. Membros já cobertos pelo contêiner mantêm seus motivos/identidades associados ao trecho único. Trechos descontínuos têm spans próprios, nunca fonte artificial concatenada. Base e head mantêm atribuição própria mesmo quando bytes iguais.
5. Medir o JSON final compacto completo, inclusive comparação, IDs, motivos, omissões, diagnósticos e contadores. Recalcular após toda modificação; publicar somente se bytes e teto exato solicitado forem respeitados. Registrar projeção/escopo/fingerprint e SHA dos bytes emitidos.

Na medição exata, usar o perfil fixado de L4 e vetores de prova, sem equiparar tokens locais a usage faturado. Cobrir Unicode, CRLF, escapes, tokens especiais como texto e fronteiras de dígitos dos contadores. A estabilização dos contadores tem limite de iterações e detecta ciclos; convergência não pode ser presumida para qualquer tokenizador. Se a serialização autoconsistente falhar, o spike registra falha operacional e não emite resposta normal com contagem falsa; esse caso integra as contraprovas. A política de erro de produto será concretizada no adapter, sem relaxar o teto.

Envelopes mínimos e exceção de admissão seguem contrato §5/A02: rejeitar orçamento impraticável antes de recuperar fonte; diagnóstico limitado, sem JSON truncado e sem aumentar orçamento automaticamente. Reduzir detalhes opcionais de omissões de forma explícita quando necessário: totais exatos por motivo e referência ao manifesto completo retido; não transformar contagem truncada em zero nem ocultar obrigação obrigatória omitida. `next` e seus bytes também contam. Não presumir que o cap de 4096 do diagnóstico seja teto universal de framing externo.

## 6. Manifesto e expansão

O manifesto imutável contém pedido normalizado, inputs/hashes, par/revisão, regras, conjunto de candidatos limitado e sua cobertura, obrigações, alternativas, seleção inicial e omissões. Não armazena labels do avaliador. Snapshot(s) e fontes ficam retidos antes de devolver `context_id`; no spike, mapa em memória/arquivos capturados com limite explícito basta. Expiração ou pressão de memória encerra o contexto com erro tipado, nunca o migra para geração mais recente.

`item_id` identifica objeto da seleção no manifesto; representação entregue pode crescer sem trocar objeto/revisão. IDs desconhecidos, pertencentes a outro contexto ou duplicados são recusados como `invalid_request`. Expansão deve obedecer aos novos limites e fornecer representação mais completa disponível para os IDs solicitados, ou insuficiência/motivo explícito. Não executa nova busca global nem adiciona fatos de snapshots recentes. Mesmo pedido/limites e manifesto produz mesmo conteúdo.

É permitido expandir item conhecido omitido por orçamento. Itens inteiramente não descobertos exigem novo pedido `context`, com novos limites/escopo; expansão não promete reparar descoberta truncada. Manifesto de duas revisões retém ambas; liberação de qualquer uma impede expansão do contexto inteiro com `context_expired`, evitando resposta silenciosamente reduzida a head.

Não suprimir fonte por ter sido entregue em chamada anterior. `context_id` não é recibo de memória do agente. Expansão conta integralmente no custo da sessão e o harness registra repetição. Limites do protótipo: contextos retidos, bytes totais retidos, TTL explícito e número de expansões; documentar valores iniciais e provas de exaustão. Sem implementar agora GC/pins de produção do ADR 022.

## 7. Avaliação e aceite

Primeiro incremento: contrato v3 experimental e um fluxo Rust de duas capturas, seleção/expansão e controles lexical/estrutural versus P2. Demonstrar contrato removido e consumidor conhecido de base, ausência de base, hunk no meio de função grande, obrigação que não cabe, contexto expirado e snapshot novo entre seleção e expansão. A fixture de consumidor pode ser sintética rotulada de desenvolvimento; não apresentá-la como cobertura já comprovada em Tokio.

Depois: curvas de 2k/4k/8k/16k/32k tokens e extremos, sempre com teto de bytes identificado; casos reais de desenvolvimento, classes, arquivos pequenos e relações das quatro famílias conforme P2 as disponibilizar. Controle e P3 usam mesmas fontes/pedido/tokenizer/limites e mesmo envelope comparável. Separar ablations de P2, seleção e base/head; não atribuir ganho a mecanismo cuja ativação mudou também inputs/custo oculto.

O avaliador mede evidência relevante encontrada, entregue e perdida; obrigações relevantes que o planner não descobriu; falsa evidência, excesso de bytes/tokens, expansões, repetição e custo técnico. Labels/probes versionados antes de ajuste; negativos permanecem nos denominadores. Nenhuma promoção indevida a fato ou mistura de revisão é tolerada nas fixtures. Payload menor e recall do oracle são diagnósticos, não sucesso do agente.

Manter verificações v2 e adicionar positivos/adversos v3, replay, fonte/hash/span exatos e limites nas duas plataformas. O primeiro incremento não encerra M0-09: conclusão exige o aceite integral do cartão; ganho em tarefas completas pertence a M0-12. Biblioteca maior necessária segue ADR 024 com perda reproduzível, sem bloqueio por complexidade.
