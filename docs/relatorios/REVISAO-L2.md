# Revisão arquitetural L2 e lote L3

12/10/2026, Arquiteto. Base: `db0e754` (commit completo no recibo documental). Entrega de planejamento solicitada pelo usuário; nenhum código, dependência, workflow ou experimento de produto foi alterado/executado. L3 é continuação dos cartões abertos, não reinício de L2 nem liberação de M1-B.

**Próxima ação do Implementador:** começar L3-01 e os incrementos locais independentes L3-02/03/04. P2/P3 seguem os critérios de entrada abaixo. Os ADRs 023/024 resolvem as decisões de arquitetura; falta implementar e comprovar. A lista não solicita criar agentes ou enviar mensagens a outras conversas.

## 1. Parecer sobre o que existe

| Evidência consultada | Parecer e limite |
|---|---|
| L2 e recibo `ci-native-validation.json`, run 38200959849, commit 1e09318 | Aceitar como evidência registrada pelo Implementador: parsing de 14 fixtures/7 dialetos, 20 replays e quatro eventos por host, filesystem e SQLite nativos. Não reexecutados nesta revisão. A correção posterior db0e754 não herda automaticamente uma nova execução dessa CI. |
| M0-03.R1 e `admission-status.json` | Gate fechado corretamente; zero tarefas qualificadas. Nove testes corretivos e revisão foram relatados em L2; não equivalem a qualificação de dados reais. |
| Harness local | Bytes/replay/isolamento demonstrados no recorte; uso de modelo/tokenizer/custo continua desconhecido. Baseline roteirizada não é agente competente medido. |
| M0-05 | Autonomia comprovada nos hosts registrados; literal macOS 15.0 pendente. Não baixar o piso nem concluir o cartão por deployment target. |
| M0-08 | Escopo estático demonstrado; corrida de ancestral fora do spike. Decisão Git agora definida; recibo final do cartão e prova adicional continuam separados. |

Os pareceres usam relatórios e logs locais, sem nova consulta de status da CI. Estado de produção permanece scaffold: consultas e MCP ainda não entregues; G0/G1/G2 não avaliados.

## 2. Decisões fechadas

| Pendência | Decisão | Atividade de execução |
|---|---|---|
| L2-H01 | Domínio descartável controlado externamente para comandos de agentes; Linux primário; macOS arbitrário em VM/runner dedicado; killpg é auxiliar | L3-02 / M0-04.R1, [ADR 023](../decisoes/EXECUCAO-E-CAPTURA.md) |
| M0-08.F01 | Captura/enumeração ancoradas em handles, sem symlinks; bytes imutáveis identificados e limitações de árvore viva explícitas | L3-04 / M0-08.R1; promoção M1-02/03, ADR 023 |
| L2-GIT01 | Adiar Git incorporado/histórico/diff até consumidor; base/head do harness bastam para P3 | Fechamento documental M0-08 em L3-04; ADR 023 |
| Bibliotecas complexas próprias | Admitidas por necessidade concreta; experimento vertical pode preceder prova competitiva, produção ampla mantém gates | L3-06 registra lacunas; [ADR 024](../decisoes/BIBLIOTECAS-PROPRIAS.md) organiza B01–B08 |
| Início de M0-06/P2 com cartões parciais | Usar os critérios pertinentes já verificados; recursos pagos/piso literal não bloqueiam código experimental local | L3-03/06; não equivale a concluir as dependências inteiras |

L2-E01 (host 15.0), L2-E02 (recursos de modelo/campanha) e L0-A01 (licença de distribuição) continuam externos. Preparar configuração/estimativa concreta com recursos disponíveis; solicitar ao usuário somente o item necessário quando for executar algo não autorizado. Não exigir nova confirmação do Arquiteto para escolhas previstas.

## 3. Cartões executáveis L3

IDs L3 são incrementos dos cartões M0 indicados. Marcar ambos separadamente: concluir um incremento não conclui automaticamente M0. Arquivos abaixo são destinos planejados quando ainda não existem.

### L3-01 — Qualificação vertical e depois matriz D1

**Pai:** M0-03.R1. **Entrada:** seed/triagem e ADR 021 existentes. **Responsabilidade:** `eval/qualification/`, tarefas/oracles/fontes e relatório `eval/reports/m0-corpus-qualification.md`.

Primeiro produzir quatro casos candidatos completos, um por família, preferindo casos históricos complexos entre os projetos triados. Para cada um: árvore completa elegível, proveniência, prompt natural, módulos/relações necessários, baseline falhando, referência passando, regressões relevantes e recibo independente ligado por hashes. Para revisão/configuração usar a rubrica própria do ADR 021. Corrigir materialização e build antes de rotular os outros 28. Não adulterar o gate global de 32 para admitir um lote pequeno: validação parcial tem nome e saída separados, sem permissão competitiva.

Depois preencher matriz de 32 com oito por família, tipos originais, dois repos/família, máximo quatro casos/repo, ao menos 20 relações entre módulos, 16 complexos e 16 históricos; TS e JS representados. Manter seed e descartes. Reutilizar os quatro pilotos somente se cumprirem todos os critérios finais. Um evento A→B por família preserva processo/índice; solução e oracles permanecem no avaliador.

**Aceite do primeiro incremento:** quatro dossiês reprodutíveis e revisados, build/probe real e tabela de lacunas; admissão global ainda recusada. **Aceite R1:** todos os pisos do ADR 021, 32 oracles/revisões, testes negativos e admissão positiva do dataset congelado. Não inventar revisão independente nem reaproveitar recibo sobre hash antigo.

### L3-02 — Contenção do harness

**Pai:** nova M0-04.R1; complementa M0-04. **Entrada:** harness L2 e ADR 023 §1. **Responsabilidade:** `crates/xrai-eval/harness/`, testes e `eval/reports/m0-harness-containment.md`.

Separar adapter de execução e supervisor de domínio; preservar replay v1 e versionar registros novos. Implementar Linux primeiro com testes de descendentes/teardown/cancelamento; definir adapter macOS descartável sem fingir disponibilidade de VM. Registrar `containment`, `cleanup_status`, ID do domínio e evidência de término. Teardown incompleto não é sucesso, mesmo com patch correto. Manter política comum entre braços e teste positivo de execução dentro do isolamento.

**Aceite:** matriz do ADR 023, repetida em Linux; implementação macOS só é aceita com prova no ambiente escolhido. Plataformas indisponíveis ficam explícitas. O incremento Linux pode liberar smokes Linux após L3-05 e recursos autorizados; não liberar shell de agente no macOS local por analogia. Não acoplar esse supervisor ao runtime obrigatório do produto.

### L3-03 — Workers e IPC

**Pai:** M0-06. **Entrada:** contrato e provas locais/nativas pertinentes de M0-05. **Responsabilidade:** spike/binário/testes em `crates/xrai-eval/`, `eval/reports/m0-workers.md` e contrato IPC do experimento.

Executar ADR 023 §2 em três incrementos: framing/identidade e roundtrip → supervisão/falhas/limites → pool e comparação direta. O primeiro inclui request/source/producer/configuration IDs, spans e erro parcial; o segundo garante recusa antes de alocar e progresso de pedido independente; o terceiro mede desempenho e recursos. Não transportar árvores nativas ou reabrir paths. Reusar gramáticas/queries e fingerprints existentes, sem promover a CLI final.

**Aceite:** casos adversos, retry finito, shutdown, equivalência direta/pool e prova nativa dos dois alvos disponíveis. Logs distinguem piso literal ainda não executado. Fixar limites de experimento antes do benchmark; incluir versão/build/configuração e bytes efetivos de IPC.

### L3-04 — Captura ancorada e fechamento do recorte filesystem

**Pais:** M0-08 e nova M0-08.R1. **Entrada:** spike/tests e ADR 023 §§3–4. **Responsabilidade:** `crates/xrai-eval/src/filesystem_spike.rs`, testes/driver; relatório `eval/reports/m0-filesystem.md` com adendo novo.

Primeiro registrar a decisão Git e conciliar evidências nativas/critério do escopo original; M0-08 pode encerrar esse escopo deixando R1 explícita. Depois implementar abertura e enumeração ancoradas nos dois alvos, limites de leitura e diagnósticos de corrida. Escolher wrapper seguro após verificar versões/licenças. Escrever testes determinísticos com barreiras nos pontos de troca; acrescentar stress com seeds registrados como complemento. Não depender de sleeps para demonstrar a corrida.

**Aceite R1:** matriz do ADR 023 e nenhuma promoção como fonte atual de binding invalidado. Hash corresponde aos bytes entregues; nenhum symlink redireciona captura ao arquivo sentinela externo; árvore instável retorna limitação. Limites sobre hard links/mounts/renames de handles e escritores concorrentes estão documentados. M1-02/03 só promovem o mecanismo comprovado.

### L3-05 — Medição real e adapters sem campanha automática

**Pai:** M0-04. **Entrada:** replay/schema L2; L3-02 é requisito apenas para rodar comandos arbitrários de agente. **Responsabilidade:** harness/adapters, schema versionado e `eval/reports/m0-agent-readiness.md`.

Separar bytes observados, tokens do payload por tokenizer fixado, usage reportado pelo provedor e cobrança. Replay histórico com null continua válido. Não usar tokenizer do payload para inventar tokens ocultos/faturados. Registrar modelo/versão, esforço, prompts, definições de ferramentas, cache, rodadas, erros, retries, setup/indexação e política de amortização. Preços entram com fonte/data/unidade no momento da campanha; custo ausente permanece desconhecido. Implementar adapter fake/replay para cancelamento, erro, uso parcial e limite antes de chamar modelo.

Criar manifest de readiness com hardware/SO, provedor/modelo disponível, orçamento por run e campanha, concorrência, deadlines, teto financeiro e política de parada. Valores não autorizados ficam ausentes e bloqueiam somente o run pago. Estimativa inclui braços, tarefas, repetições e overhead, sem escolher preço arbitrário. Baseline real permite busca/leitura/edição/testes ao agente; roteiro de palavras-chave L2 é smoke, não substituto competitivo.

**Aceite local:** replay exato do novo schema, tokenizer identificado e custos não fabricados, manifest que recusa execução sem recursos/tetos. **Aceite M0-04 restante:** quatro smokes pareados reais (um/família), sessão auditada, mesma tarefa/modelo/permissões, contenção e orçamento autorizados; nenhum ganho competitivo inferido desses smokes.

### L3-06 — P2 em quatro recortes, com fronteira estável

**Pai:** M0-11. **Entrada:** contrato/fonte capturada, parsing pertinente e harness local/replay. Pode começar sem API paga ou banco de produção. **Responsabilidade:** módulos experimentais de semântica em `xrai-eval`, fixtures/labels no avaliador, `eval/reports/m0-semantics.md`.

Primeiro definir IR mínimo de escopos, declarações, refs, imports e configuração sem tipos Tree-sitter públicos. Implementar uma fatia completa Rust: módulos/use/pub use, shadowing, cfg fornecido e método inerente com receptor concreto. Em seguida repetir o contrato em TS/JS (imports/exports e resolução estática conforme protocolo), Python (imports estáticos/aliases/bindings) e Go (packages/seletores/tipo nomeado/build tags). Restrições detalhadas continuam no protocolo; não ampliar recortes silenciosamente.

Para cada fato: regra produtora, fonte/hash/span, configuração, dependências positivas e negativas; candidatos/unknowns quando faltar prova. Testar homônimos, reexport cíclico, shadowing, import externo ausente, export criado após primeira consulta, configuração alterada e edição A→B. Não executar imports, macros ou build scripts do projeto. Oracle de compilador, quando houver, só no avaliador.

**Aceite:** pelo menos 80% corretos entre casos rotulados resolvíveis, zero promoção indevida nas fixtures contratadas; precisão/recall/cobertura separados nos casos reais. Incremental igual a rebuild nas mesmas entradas. Controle lexical/estrutural participa. Registrar perdas por camada e dossiê B05/B06 apenas quando necessário; biblioteca grande própria não é bloqueada por complexidade.

### L3-07 — P3 e expansão por revisão

**Pai:** M0-09. **Entrada:** contratos, harness/tokenizer pertinente e primeira fatia P2 para desenvolver; aceite final depende do recorte P2 contratado. **Responsabilidade:** seletor experimental e `eval/reports/m0-context.md`.

Implementar pipeline pedido → obrigações inferidas → candidatos léxicos/estruturais/semânticos → representação → dedup → empacotamento → expansão. Registrar motivos das escolhas e omissões. Obrigações inferidas não acessam rótulos do oracle. Receber base/head explícitos, incluindo remoções; não exigir Git incorporado. Guardar IDs de revisão e budget total serializado em todas as respostas.

**Aceite:** curvas 2k/4k/8k/16k/32k tokens e limites extremos, fonte exata, contêiner/membro sem duplicação indevida, obrigação conhecida que não cabe gera insuficiência e expansão não muda snapshot. Comparar com/sem P2, head/base+head e representações. O avaliador mede também obrigações que o seletor não percebeu. Não prometer suficiência universal ou autorizar omissão da suíte.

### L3-08 — Preparar piloto, sem pular admissão

**Pais:** preparação M0-12 e consolidação M0-10. **Entrada para preparação:** harness local; **para execução:** R1 qualificada, M0-04/09/11 e recursos autorizados. **Responsabilidade:** `eval/competitors/`, manifest de campanha e relatórios dos cartões.

Triar os oito comparadores do protocolo, versões e modos fortes; registrar indisponibilidades por evidência. Congelar finalistas/baseline/variantes A/B/C/D, recursos, prompts, seeds/repetições, amortização, corpus e análise antes de runs comparativos. Rodar ao menos duas repetições por tarefa/braço principal quando liberado. Contabilizar falhas, custos completos e recorte complexo; reproduzir uma vitória/perda. Não contratar modelos/runners nesta preparação.

**Aceite da preparação:** manifest reprodutível e preflight que explica dependências faltantes. **Aceite da execução/G0:** somente critérios integrais dos cartões/protocolo, incluindo spikes técnicos e piso de SO. G0 positivo libera M1-A; G1 libera M1-B; G2 libera alpha no escopo comprovado. Gates negativos/inconclusivos produzem relatório e decisão, nunca avanço por quantidade de código escrito.

## 4. Sequência e evidências

Sequência prática: quatro casos verticais de L3-01 → expandir corpus; L3-02/03/04 independentes podem intercalar builds. L3-05 local e L3-06 começam com os artefatos disponíveis; L3-07 consome as fatias estáveis; L3-08 prepara comparadores enquanto dependências fecham. Não esperar o cartão de modelo pago para escrever o resolver. Não esperar o resolver completo para qualificar dados.

Cada incremento: atualizar estado, relatório e hashes; registrar comando, commit base, ambiente/versão, exit code, falhas e limitações; executar checks pertinentes e preservar os anteriores; commit/push para origin sem force. Código Rust requer fmt/clippy/tests aplicáveis; corpus/harness exigem seus verificadores e adversos; mecanismos de plataforma exigem execução nativa. Nenhum teste novo foi executado por este parecer.

O roadmap M1–M5 do plano continua vigente. ADR 024 detalha como ampliar infraestrutura própria sem criar obrigação de construir tudo agora. Não definir cronograma fictício: após cada primeiro incremento, o Implementador informa esforço observado, riscos e estimativa do próximo recorte.

## 5. Verificação desta entrega documental

Exploração: graft localizou o parsing/harness; codebase-memory Tier 2 consultou índice e cobertura. Geração `2026-10-12T01:50:21Z` não rastreava fontes novas L2 e marcou manifest alterado; leitura direta das fontes pertinentes e relatórios supriu a lacuna. Consulta documental posterior já retornou geração `2026-10-12T09:29:51Z`, com metadata correspondente nos 15 paths consultados; isso não substitui a leitura direta usada nos achados. Não é auditoria exaustiva de código nem certificação de segurança. Os números de CI são atribuídos aos recibos do Implementador.

Verificação documental em [documentacao.json](logs/revisao-L2/documentacao.json): referências locais, correspondência dos IDs plano/estado, dependências sem ciclos, arquivos alterados e fontes com hashes. Checks de produto/campanhas não foram repetidos para alteração somente documental. Publicação desta entrega só será comunicada após commit/push confirmado.
