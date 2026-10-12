# Revisão arquitetural de L0 e próximas atividades

**Atualização de escopo posterior:** o [ADR 020](../decisoes/PLATAFORMAS-V1.md) define Linux x86_64 e macOS arm64 para v1, com Windows pós-v1. Referências abaixo a três SOs/cinco alvos registram o escopo da revisão original; os requisitos vigentes estão no plano atualizado. Evidências históricas permanecem válidas para o que foi executado.

Data: 11/10/2026, America/Sao_Paulo. Arquiteto. Commit revisado: `10d9bf95490d405ea2d8014e95065295b32727c4`. Verificações desta revisão em 12/10/2026 UTC, ainda 11/10 no fuso do projeto. Nenhum código de produto, teste, schema ou verificador foi alterado pelo arquiteto.

## 1. Parecer de aceite

**Aceito L0 no escopo entregue:** M0-01 como especificação e exemplos documentais; M0-02 como scaffold compilável com ajuda/versão. Os 25 exemplos existentes e os checks do workspace foram reexecutados com sucesso. Isso não aprova parser, semântica, índice, MCP ou vantagem competitiva.

**O contrato ainda requer a retificação M0-01.R1 antes de seu congelamento para o harness e M1.** A lacuna é a representação e a política de snapshot fixo versus seleção da revisão mais recente. Não é um defeito observado em uma API de produto: essa API ainda não existe. Os casos atuais de snapshots fixos continuam válidos no escopo documentado.

| Critério | Evidência conferida | Conclusão |
|---|---|---|
| M0-01: vazio válido, parcial, excluído, parser ausente e capacidade indisponível | Contrato, fixtures 01–06, schema e verificador | Atendido nos exemplos; não é cobertura completa do domínio |
| M0-01: estados, orçamento, expiração, fonte/hash/spans e separação de afirmações | Fixtures 07–16 e nove casos inválidos; execução documental | Atendido no recorte; exceção de admissão recebe decisão L0-A02 abaixo |
| M0-01: snapshot/validated/strict e limites de atomicidade | Contrato §§4–5 e sondagem de geração | Conceitos descritos; falta explicitar seletor e transição para geração nova, tratada em M0-01.R1 |
| M0-01: promessas rastreáveis a tarefas | Matriz sintática e rastreabilidade §§7–8 | Atendido; capacidades futuras corretamente indisponíveis |
| M0-02: cinco crates, direção de dependências e separação do harness | Cargo metadata/lock/manifests e fontes das bibliotecas | Atendido; core sem dependências, query sem index concreto, eval fora do executável |
| M0-02: ajuda/versão e recusa de operações não implementadas | Fonte da CLI, três testes de processo e smokes | Atendido; não encontrei defeito pendente na superfície examinada |
| M0-02: fmt, clippy, test, build e lockfile | Reexecução local offline e CI do commit | Atendido |
| M0-02: matriz nativa inicial | CI Linux x86_64, macOS arm64 e Windows x86_64 | Agora executada com sucesso; não apenas configurada |

M0-01/M0-02 permanecem concluídas **no escopo de L0**. As duas atividades derivadas desta revisão têm IDs próprios e estado não iniciado; não converter sua especificação em trabalho implementado. G0/G1/G2 permanecem não avaliados.

## 2. Evidências atuais

- [Checks locais desta revisão](logs/revisao-L0/checks.json): fmt; clippy sem warnings; build; três testes da CLI; help/version; metadata; 16 exemplos válidos aceitos e nove inválidos rejeitados, zero falhas.
- [CI observada](logs/revisao-L0/ci.json), [run Rust workspace](https://github.com/wkoch/xrai/actions/runs/38190368368): commit exato revisado; três jobs concluídos com sucesso, incluindo verificação do host, fmt, clippy, test, build e smokes.
- [Sondagens do contrato](logs/revisao-L0/sondagens-contrato.json): transformação em memória, sem editar fixtures. Resposta coerente numa geração nova é recusada pela igualdade incondicional com o snapshot solicitado; `latest` literal não pertence ao schema atual. Isso identifica uma forma ainda não representada, não prova falha de runtime nem autoriza simplesmente remover a checagem de revisão.
- [Verificação dos registros desta revisão](logs/revisao-L0/documentacao.json): 35 cartões principais e duas atividades de revisão, 105 dependências sem ciclos, estado coerente, links/fences válidos; nenhuma mudança em fontes de implementação. `git diff --check` também passou.

Método: a skill codebase-memory foi consultada em Tier 2. O projeto estava indexado na geração `2026-10-11T22:57:19Z`; a busca não trouxe funções e a cobertura dos 16 caminhos consultados informou `not_tracked`. Não derivei ausência de implementação desse resultado. Usei leitura das fontes/configs/contrato, metadata Cargo e checks executados. Graft localizou verificador e testes; o grafo antigo não foi tratado como prova de completude.

Os relatórios originais de L0 descrevem corretamente seu momento anterior à criação do Git, mas suas frases “CI não executada” e “nenhum Git/remoto” deixaram de descrever o estado atual. Este adendo e o quadro de estado são a atualização; logs históricos não foram reescritos. O commit L0 existe em `origin/main` e sua CI foi observada.

O sucesso dessa CI comprova somente o scaffold. **M0-05 continua não iniciada:** ainda faltam gramáticas incorporadas, parsing, erros sintáticos e execução limpa sem runtimes/rede. Os cinco alvos da alpha também não estão comprovados por esses três jobs.

## 3. Pendências e decisões

| ID | Prioridade e estado | Decisão / responsável | Efeito nas próximas tarefas |
|---|---|---|---|
| L0-A01 | P2, pendente do mantenedor | Licença do produto permanece sem escolha; não atribuir SPDX ou LICENSE em nome do usuário. Implementador preserva `publish=false` e inventário de licenças de dependências | Não bloqueia M0; resolver antes de distribuir/publicar pacotes em M1-20 |
| L0-A02 | Decisão arquitetural tomada; concretização pendente | Aprovar rejeição de admissão com diagnóstico separado, limites e contabilidade definidos abaixo | Consolidar em M0-01.R1; adapters/medição real nos cartões M0-09, M1-16/17/18 |
| L0-A03 | P2, nova lacuna de contrato | Separar explicitamente snapshot fixo e seletor `latest`; nunca relaxar proteção contra mistura de revisão | M0-01.R1 antes de congelar entradas/saídas do harness e tipos de M1 |
| L0-V01 | P2, proteção de regressão pendente | Os exemplos só têm execução local registrada; workflow atual verifica Rust, mas não `verify.py` | M0-02.R1 acrescenta validação documental automatizada, sem dependência Python no produto |
| L0-O01 | Encerrada no escopo do scaffold | Git e CI dos três hosts confirmados | Retirar “CI ainda não executada” das pendências correntes; manter lacunas reais de M0-05 |
| L0-O02 | P2, operacional aberta | Hardware de referência, esforço e orçamento de campanhas ainda não definidos | Impede campanha paga sem limites; não impede corpus, replay ou spikes locais |
| L0-O03 | P3, ferramenta auxiliar | Índice codebase-memory anterior ao scaffold | Implementador atualiza/verifica cobertura antes de depender do grafo; leitura direta continua permitida |

### L0-A02 — admissão quando o envelope não cabe

Decisão para concretizar o ADR 007:

1. `max_bytes` e, quando exato, `max_tokens` limitam a resposta normal. Uma solicitação cujo orçamento não comporta o envelope mínimo é recusada antes da recuperação de fonte; não emitir JSON truncado nem resposta normal acima do limite.
2. O diagnóstico de admissão usa um canal separado e **não finge cumprir o orçamento pedido**. CLI: stdout vazio, exit 2, stderr com diagnóstico. MCP: erro de execução da ferramenta para a restrição de orçamento, preservando JSON-RPC; argumentos malformados seguem erro de protocolo. A distinção é compatível com a [especificação MCP consultada](https://modelcontextprotocol.io/specification/2025-06-18/server/tools#error-handling); a versão efetivamente usada deve ser fixada no spike do adapter.
3. O cap de **4096 bytes** vale para o diagnóstico serializado controlado pela aplicação: bytes de stderr na CLI; objeto `result` da ferramenta no MCP, incluindo `content`, `structuredContent` se presente, escapes e metadados. Não duplicar representação sem contabilizá-la. O framing JSON-RPC e o ID ecoado entram na medição total, mas não se promete limite universal de 4096 para o wire inteiro com IDs arbitrários do cliente. Limites de transporte/entrada pertencem ao adapter e devem ser declarados.
4. O diagnóstico permanece limitado mesmo com entradas longas: usar mensagem curta e campos limitados, sem fonte, sem reproduzir paths/descrições extensos. Se o detalhe não couber, retornar diagnóstico mínimo ainda válido. Registrar mínimo exato ou limite estimado como tal; não chamar estimativa de contagem exata.
5. Não executar retry automático com o mesmo orçamento impossível nem expandi-lo silenciosamente. Consumidor decide nova solicitação. Custo desse erro e de eventual repetição entra na sessão e no experimento; a exceção não oculta tokens.

É uma exceção explícita para comunicar rejeição, com custo limitado, não uma autorização de ultrapassar o orçamento em respostas de contexto. A fixture14 cobre apenas o objeto documental atual; não comprova serialização, contagem de tokens ou MCP real.

### L0-A03 — seletor de revisão e frescor

Direção normativa para R1; o implementador deve concretizar schema, exemplos e nomes de campos coerentemente, sem anunciar API implementada:

- A entrada distingue uma **revisão fixada por ID** de uma **seleção explícita `latest`**. `latest` não é um `snapshot_id` fictício. `status` antes da primeira geração mantém o caso legítimo sem snapshot.
- Com ID fixado, a resposta não troca de revisão. Se `validated`/`strict` detectar que aquela geração não corresponde ao estado exigido, recusar com erro tipado de revisão desatualizada e orientar nova consulta; não chamar isso de expiração nem atualizar silenciosamente. Falta de validação conserva diagnóstico e ausência de completude.
- Com `latest` + `snapshot`, resolver a geração publicada disponível e informar seu ID, sem afirmar frescor do filesystem. Com `latest` + `validated/strict`, reconciliar o escopo necessário antes de fixar a geração da resposta; uma geração nova é permitida e deve ser explícita. A resposta continua internamente coerente e o working tree não ganha atomicidade global.
- IDs de símbolo/ocorrência, cursores e contextos vinculados a uma revisão não migram para outra por coincidência de nome. Âncora incompatível exige erro/relocação explícita. `expand` e paginação permanecem presos às revisões do manifesto original.
- A igualdade request/response do verificador deve depender do seletor. Manter testes que rejeitam rebind com ID fixo, mistura de fontes e expansão em revisão diferente. Acrescentar caso positivo para avanço de geração solicitado por `latest`.

Esse ponto precisa ficar explícito antes da promoção do contrato a domínio de produção. As fixtures atuais cobrem requests fixados; não são uma especificação exaustiva da futura seleção `latest` ou de base/head.

## 4. Próximo lote L1

O implementador pode iniciar as frentes abaixo, respeitando dependências e sem refazer L0. O arquiteto definiu o trabalho; correções em schema/verificador/CI e os novos testes pertencem ao implementador.

| Ordem | Atividade | Entrega e aceite |
|---|---|---|
| 1A | **M0-01.R1**, retificar contrato | Consolidar A02/A03 em contrato/schema/examples/verificador. Casos positivos/negativos de snapshot fixo, `latest` que avança, revisão desatualizada, expiração, âncora incompatível e orçamento abaixo do envelope. Preservar checks de bytes/hash/revisão. Log distingue exemplos de testes de runtime futuros |
| 1B | **M0-03**, corpus D0/D1 | 20 tarefas D0 e 32 D1 com todos os campos/oracles, quatro famílias, ao menos dois repos por família em D1; TS e JS reais; commits/licenças/procedimentos reproduzíveis; patches ocultos fora da entrada do agente. Sem campanha paga para apenas preparar corpus |
| 1C | **M0-07**, spike de snapshots/SQLite | Dois leitores e escritor, publicação A/B, interrupção antes de commit, FTS5 e revisão dos bytes; reusar contratos estáveis de snapshots. Essa frente não depende de corpus. Incorporar R1 se expuser a seleção dinâmica de revisão |
| 2 | **M0-02.R1**, CI dos contratos | Após R1 e M0-02, executar checks documentais numa job de desenvolvimento com versões fixadas. Testemunhar um caso inválido sendo rejeitado e a suíte passando. Dependências Python não entram na closure do binário |
| Após corpus e R1 | **M0-04**, harness/replay | Mesmo modelo/tarefa/condições por braço, custos e resultados separados, replay reproduzível; campanha paga só com limites definidos |
| Após corpus | **M0-05** e **M0-08** | Gramáticas/autonomia e filesystem/caminhos conforme cartões. M0-08 depende de M0-03; não tratá-la como inteiramente liberada só pelo scaffold |

M0-06 depende de M0-05. M0-11/P2 vem após contratos, workspace, corpus e harness; M0-09/P3 usa P2. M0-12 mede o piloto. A prioridade continua provar ganho de sucesso antes de engenharia ampla; não iniciar M1-B por extrapolação dos smokes de L0.

Relatório esperado: `docs/relatorios/L1.md`, com IDs realmente concluídos, comandos/ambientes, oracles preparados, custos observados, lacunas e próxima atividade. Atualizar o estado antes do commit e push. Se uma frente não terminar, registrar seu estado real sem encerrar o cartão inteiro.

## 5. Limites do parecer

Não auditei cada combinação possível do schema nem certifiquei correção de domínio inexistente. A documentação já declara que o verificador cobre as formas dos exemplos. Paths Windows adversos, prefixos de IDs por tipo, cobertura integral, base/head e produtores ainda exigem testes de domínio nas tarefas responsáveis; não extrapolar “25 casos passaram” para esses cenários.

Não foi escolhida licença, contratado serviço, iniciada campanha de modelos, implementado recurso ou alterado critério competitivo. A entrega desta revisão consiste em decisões, atividades, estado e evidências; a publicação Git só é declarada após push confirmado.
