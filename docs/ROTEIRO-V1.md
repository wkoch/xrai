# Caminho até o v1.0 — ADR 028

13/10/2026. Avaliação arquitetural no corte `bd12a9a`, código `b5b9f8b`: [fechamento C06](relatorios/REVISAO-L5-C06-FECHAMENTO.md). **Decisão do Arquiteto para estabilização e lançamento; não aprova release nem antecipa M1-B.** Estado em [STATUS-IMPLEMENTACAO](STATUS-IMPLEMENTACAO.md).

## 1. Onde estamos

O projeto está em **M0, pesquisa aplicada e protótipos verificáveis**. A infraestrutura experimental avançou; o benefício para agentes e o produto integrado ainda não foram demonstrados. Os 41 cartões existentes têm 9 concluídos, 7 em andamento e 25 não iniciados: M0 tem 9/18 concluídos, 7 em andamento e 2 não iniciados; todos os 23 cartões M1 estão não iniciados. Esses cartões têm tamanhos muito diferentes e não cobrem a estabilização detalhada abaixo. Portanto **9/41 não é percentual de conclusão do v1.0**.

| Dimensão | Evidência atual | Distância até produto utilizável |
|---|---|---|
| Captura, armazenamento e parsing | Spikes de fontes/revisões/SQLite/FTS, sete dialetos e workers com provas nativas | Implementar integração de produção, atualização, recuperação e distribuição |
| Semântica | Rust R1/R2/R3; TSJS-A/B com 45 labels e 13/13 referências resolvíveis; sessão TSJS-C | Rust R4/lacunas, semântica Python/Go e relações úteis em tarefas; callable TSJS continua unknown |
| Contexto | P3/v3; BM25/TF-IDF em fontes reais, 640 entregas com tokens controlados; intake Rust e contexto por bytes provados | Integrar Store/P2 e consumer, comparação P3 sob orçamento de sessão, labels independentes e tarefas completas |
| Corpus | Oito dossiês individuais e quatro eventos operacionais comprovados; mapa E02 v2 | Faltam 24 tarefas/quotas; global 0/32. Candidato Django ainda não compensa 19/20; eventos não criam dossiês |
| Avaliação por agente | Harness/replay, dispatch v2, factory de tools, contenção Linux e oracles reais | Recibo público de transporte, adapter real, quatro smokes, comparadores fortes, D1/H1 e recursos |
| Produto público | `xrai --help` e `--version`; crates de domínio ainda sem capacidades da alpha | Indexar, consultar e atualizar pelo executável/CLI/MCP de produção |
| Distribuição | CI Linux x86_64/macOS arm64; recursos experimentais de workers nos dois hosts | Escolha de runtime/calibração, instalação do produto, piso macOS 15.0, licença e release auditável |

Avanço recente: C02 recomputa quatro novos dossiês elegíveis. Python/Go têm três requisitos falhos na base, três aprovados na referência e duas regressões por lado. São contratos controlados, não bugs históricos. Os probes deixaram de ser somente sintéticos. Rust reproduz os dois problemas esperados no baseline, passa referência 2/2 e 16 regressões; JS reproduz três requisitos falhos e passa referência 3/3, com duas regressões por lado. Isso valida tarefas/oracles; **não mede sucesso de um agente usando xrai**. Na amostra Tokio-test, 201 chamadas continuam unknown; o acerto 1/1 do subconjunto resolvível não é cobertura de 201 chamadas.

Os principais riscos são: semântica útil insuficiente fora das fixtures; seleção não melhorar tarefas completas; custo de sessão exceder tetos; esforço de qualificação/campanha e integração maior que o sugerido pelo scaffold. Tamanho da biblioteca necessária não é veto. Investir em biblioteca própria segue ADR 024 quando uma perda concreta a justificar.

## 2. O que significa v1.0

O plano anterior terminava M1-B em **alpha**, com M2–M5 como evolução por evidência; não definia uma passagem executável da alpha para 1.0. Esta decisão fecha essa lacuna.

**v1.0 é o produto estabilizado no escopo comprovado por G1/G2**, não a implementação integral de todo o backlog de pesquisa. Deve entregar:

- Um executável autônomo por alvo v1: Linux x86_64/glibc 2.39 e macOS arm64/piso 15.0, mantendo os compromissos do ADR020. Experiência básica sem Python/Node, serviço externo, credencial de modelo ou rede.
- Fluxo de indexação e atualização até `status`, `search`, `inspect`, `relations`, `context` e `expand`, pelos adapters CLI/MCP e domínio comum, com os comandos de administração previstos em M1. Configuração, exclusões, fontes/revisões, cancelamento e erros documentados.
- Navegação nas quatro famílias Rust, TS/JS, Python e Go. Semântica/contexto avançados anunciam recortes efetivamente provados; unknown/partial permanecem recursos corretos do contrato. Não prometer compilador completo ou profundidade igual nas quatro famílias.
- Evidência de maior sucesso dentro dos limites de custo do protocolo, preservada na integração e na release candidate. Nenhum novo limiar competitivo substitui G0/G1/G2.
- Interfaces públicas versionadas, instalação/atualização/recuperação testadas, limites operacionais medidos, documentação utilizável e licença definida pelo mantenedor.

M2/M3 entram antes de 1.0 somente nos recortes necessários para cumprir esse escopo e sustentar o ganho. M4/M5, bridges universais entre linguagens, memória/slicing avançados, embeddings e frontends mais profundos não são dependências automáticas de 1.0. Windows/Linux arm64/macOS Intel continuam posteriores ao v1. Não rebaixar requisito já escolhido e medido só para declarar release.

Alternativa descartada: condicionar 1.0 a todos os itens M2–M5. Isso criaria um destino móvel e confundiria experimentação com estabilidade. Também não basta renomear a alpha: as provas operacionais e de compatibilidade abaixo são obrigatórias para a decisão de release.

## 3. Caminho crítico e condições de passagem

```mermaid
flowchart LR
  A[Agora: M0 experimental] --> B[Fechar corpus, harness e P2/P3]
  B --> C[G0: piloto D1]
  C -->|favorável| D[M1-A: confirmação H1 / G1]
  D -->|favorável| E[M1-B: produto integrado / G2]
  E -->|favorável| F[Estabilização e release candidate]
  F --> G[v1.0 no escopo comprovado]
```

Resultado inconclusivo/negativo de G0/G1 requer a decisão prevista no protocolo: focar, revisar hipótese ou encerrar, respeitando limite de rodadas. Não iniciar automaticamente toda a engenharia para contornar a falta de ganho. G2 preserva o ganho na alpha; estabilização não substitui a validação competitiva.

| Etapa | Trabalho que falta | Saída que libera a seguinte |
|---|---|---|
| M0 técnico/experimental | Sete cartões em andamento: corpus R1, harness, contenção R1, autonomia, workers, P2, P3; mais M0-12 e M0-10 ainda não iniciados | Corpus 32 admitido, oracles/eventos, sessões reais/controladas, comparadores, provas técnicas e piloto; G0 favorável |
| M1-A | M1-01 e M1-22 | Contratos mínimos e confirmação reservada; G1 favorável. H1 é preparado no ambiente separado, tamanho congelado antes da campanha |
| M1-B | 21 cartões restantes: inventário/fontes, banco/workers, quatro frontends, índice/atualização, buscas/contexto, CLI/MCP, falhas e distribuição | Alpha integrada, recortes promovidos com evidência, G2 favorável |
| Estabilização v1 | Seis atividades condicionais V1 abaixo | Candidate pronta, interfaces e operação comprovadas; decisão explícita de publicação do mantenedor |

Recursos/modelo/teto precisam ser definidos antes do uso pago, e hardware comparável antes das campanhas. Host macOS 15.0 e domínio macOS descartável são pendências diferentes: o primeiro prova compatibilidade, o segundo execução arbitrária do harness. Licença é decisão do mantenedor antes de distribuição. Preparar estimativas/manifests concretos antes de pedir esses insumos; continuar o trabalho local independente.

## 4. Atividades de estabilização após G2

Estes **seis cartões novos são condicionais e ainda não iniciados**, separados dos 41 cartões M0/M1. Planejamento agora; implementação após suas dependências. Não muda IDs/estados nem libera produto amplo antes de G1. Responsável de execução: Implementador; escopo/compatibilidade: Arquiteto; licença e publicação 1.0: mantenedor.

### V1-01 — Congelar escopo e interfaces públicas

**Depende de:** M1-21/G2 favorável. **Entrega:** manifesto de capacidades da release, matriz de compatibilidade e referência CLI/JSON/MCP/configuração/erros.

Escolher o schema público a promover a partir dos perfis comprovados; v2/v3 documentais não viram estáveis por terem número. Distinguir interface estável de experimental, política de depreciação/versões, protocolo MCP fixado e migração de configuração. IDs de snapshot/item mantêm seus limites de validade, sem promessa de estabilidade entre snapshots. Crates internas e ASTs não recebem ABI pública acidentalmente.

**Aceite:** exemplos e clientes de referência reproduzem o contrato publicado; mudanças incompatíveis são detectadas por fixtures de compatibilidade. Toda capability anunciada tem implementação/prova e todas as indisponíveis têm diagnóstico.

### V1-02 — Fixar envelope operacional e medir a candidate

**Depende de:** V1-01, M0-05, M0-06, M1-19, M1-20. **Entrega:** orçamento de CPU/RSS/disco/latência e limites por operação/classe de projeto, com hardware/ambiente declarados.

Derivar valores da alpha, congelá-los antes da medição de release e medir carga sustentada com concorrência, respostas retidas, cancelamento, rotatividade de snapshots e reinício. Não inventar SLO agora sem hardware/carga. Separar tamanho de fonte, índice/cache e artefato. Medir mediana/cauda, falhas e overhead do observador; fonte indisponível não vira zero.

**Aceite:** todos os limites publicados têm prova nos dois alvos; pressão de recurso termina com comportamento limitado/explicável, sem morte silenciosa ou loop de retries. Desvio é corrigido ou explicitamente revisto antes de recongelar a candidate.

### V1-03 — Comprovar atualização, migração e recuperação

**Depende de:** V1-01, M1-04, M1-12, M1-19. **Entrega:** política de schemas de cache/configuração, testes de atualização/rollback e guia de recuperação.

Testar instalação limpa, atualização a partir da alpha suportada, banco antigo/futuro, interrupção durante migração/indexação, lock concorrente e restauração após corrupção do cache. Fontes e notas humanas não são descartáveis; regenerar somente dados derivados permitidos. Se rollback de banco não for suportado, recusar de forma recuperável e documentar reinstalação/rebuild sem destruir dados do usuário. Não prometer downgrade universal.

**Aceite:** fluxo reproduzível preserva dados autoritativos e evita mistura de gerações. Migração/backup/rebuild têm prova e instrução; incompatibilidade nunca altera arquivo desconhecido silenciosamente.

### V1-04 — Verificar uso completo pelo artefato distribuído

**Depende de:** V1-01, V1-02, V1-03. **Entrega:** walkthrough automatizado e revisão do fluxo por agentes/clientes, exclusivamente com os pacotes que serão distribuídos.

Instalar em host limpo, indexar, consultar pelas seis operações, aplicar alteração, consultar novamente, expandir contexto antigo retido e verificar expiração. Cobrir as quatro famílias, paths nativos e falhas documentadas. A experiência básica não pode recorrer aos binários de `xrai-eval`, Python/Node ou rede como dependência implícita.

**Aceite:** CLI e MCP observam as mesmas revisões/estados/fonte; custos e resultados de regressão da integração continuam dentro do recorte G2. Alteração material de semântica/seleção após G2 exige revalidação pertinente; não abrir holdout já contaminado como nova confirmação.

### V1-05 — Preparar distribuição auditável e documentação de operação

**Depende de:** V1-01, M1-20; licença definida. **Entrega:** artefatos dos dois alvos, hashes, proveniência de build, dependências/licenças, instruções e notas de release.

Verificar piso de SO/ABI real, linkage, conteúdo offline e gramáticas incorporadas; guardar os bytes da candidate e metadata recuperável por uma política de retenção que cubra seu suporte, sem depender somente de artefato CI que expira. Declarar o método de instalação e verificação de integridade. Se distribuição macOS exigir assinatura/notarização pelo canal escolhido, concretizar credenciais/identidade e provar instalação; não alegar assinatura inexistente.

Fazer revisão dirigida dos limites de confiança: paths/repositório não confiável, IPC/parser, corrupção do banco, recursos e logs sem segredos. Dependências e licenças têm inventário atribuído. Manual cobre setup, uso, limites, partial/unknown, diagnóstico, atualização e recuperação. Sem auditoria meramente cerimonial para substituir as provas de M1-19.

**Aceite:** instalação limpa verificável, artefatos correspondem ao commit/tag candidato e os avisos/licenças estão completos; provenance identifica entradas e ferramentas. Reprodutibilidade bit a bit só é afirmada se medida; ausência não é escondida atrás de hash de um único build.

### V1-06 — Qualificar a release candidate e decidir 1.0

**Depende de:** V1-01, V1-02, V1-03, V1-04, V1-05; G2 preservado. **Entrega:** checklist de release, inventário de defeitos, resultados congelados e decisão do mantenedor.

Congelar commit/configuração/pacotes, executar matriz de aceite, comparar resultados com a alpha e documentar diferenças. Não exige um prazo fictício de beta. Qualificação é por evidência de uso completo, limites e recuperação; bug fix material gera nova candidate e reexecuta o que foi afetado.

**Aceite:** zero defeito conhecido que viole os invariantes declarados (corrupção/perda de dados, fonte/revisão falsa, promoção semântica indevida no recorte, escape do escopo de acesso prometido, instalação ou operação central quebrada). Limitações fora do recorte são explicitadas, não renomeadas para esconder violação. Revisão de comportamento/custo passa, documentação bate com o executável e o mantenedor autoriza tag/publicação 1.0. Commit/push de código ou documentação não equivale a esse lançamento.

## 5. Como acompanhar sem percentual fictício

Medir cinco eixos separadamente: capacidades reais por linguagem; tarefas do corpus prontas/admitidas; sessões reais completas e gates; operações do produto distribuído; critérios de estabilidade/release. Quantidade de testes/linhas/ADRs não é proxy de utilidade.

Antes de estimar uma data, registrar esforço ativo e espera externa de pelo menos dois incrementos representativos (um dossiê completo e uma fatia de frontend/contexto), custos dos probes/campanhas e largura real de trabalho do Implementador. Só então apresentar faixa condicionada a G0/G1 e recursos, revisada quando surgir dependência nova. Hoje não há base para prometer semanas, meses ou percentual de 1.0; a maior incerteza é a eficácia ainda não medida.

Próximas entregas observáveis: integração Store/P2 via regressão Tokio, oracle físico/isolamento Django v2 e recibo público de transporte fake. Replay, cápsula histórica/CI e prova nativa por bytes foram encerrados; elegibilidade/gates não mudaram. Conjunto lexical independente, contratos ABA/blobs, comparadores/smoke, recursos v2 e coletor S02 continuam em paralelo. [Fechamento corrente](relatorios/REVISAO-L5-C06-FECHAMENTO.md), §5, define os próximos resultados.

O avanço técnico reduz incertezas do protótipo, mas ainda não há sessão real de agente demonstrando ganho, corpus32 admitido ou gate avaliado. O próximo marco de produto continua G0; não há base para percentual/data de v1.0. As [fatias históricas](L5-PROXIMA-EXECUCAO.md) preservam contratos que a revisão não substituiu.
