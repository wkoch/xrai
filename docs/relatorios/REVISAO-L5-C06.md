# Revisão L5-C06 — completude do replay e passagem à tarefa real

13/10/2026, Arquiteto. Corte inicial publicado `bc874f4`, após `1d40e52`; revisão anterior `b065e33`/[C05](REVISAO-L5-C05.md). Implementador ativo no mesmo checkout. Os pareceres sobre D01/consumer/Django e correção P3 referem-se aos hashes locais registrados, não a um futuro commit ou CI. Três agentes trabalharam somente em leitura e verificações próprias offline. Este documento mantém os mesmos cartões L5/M0 e as frentes independentes da revisão C05.

Durante a revisão, o Implementador publicou `fbf1e53`. Os 43 registros de paths hashados nas três frentes coincidem com os bytes desse commit; os aceites locais abaixo podem ser vinculados a ele. Isso não atribui sucesso à sua CI nem elimina as pendências de replay, tarefa ou prova nativa.

## 1. Avanço verificado e limites

| Frente | Aceite nesta revisão | Próximo resultado necessário |
|---|---|---|
| E02 | Inventário fechado recomposto: 384 pares, 12 compatíveis, zero compensações nesse universo; 37 testes | Qualificar novo candidato; repetir pares antigos não resolve 19/20 |
| D01 | Captura privada do pedido corrige a contraprova C05 no caminho novo; consumer adota factory | Corrigir omissão de tentativas recusadas no replay; recibo público do transporte |
| Django | Preparação do cenário/rubrica/fontes e modelo declarativo | Materialização isolada e oracle CreateModel/SQLite real; necessidade multimódulo substantiva |
| P3 | Typed intake/HEAD/presença e contexto por bytes preparados em Rust | Prova nativa autenticada e integração com Store/obrigações; não é ainda a vertical P3 completa |

A primeira CI dedicada P3 `38440152422` falhou em Clippy antes da coleta; a correção local do iterador não constitui prova nativa. Não repetir ou ampliar o experimento para ocultar esse resultado. Os quatro eventos, TSJS e provas lexicais/recursos aceitos anteriormente continuam aceitos nos seus recortes.

**CI regular também requer correção:** o passo de contratos executa `eval/adapters/experimental-v1/verify.py`, cuja closure C04 inclui `docs/PLANO-DE-IMPLEMENTACAO.md`. O recibo antigo exige os bytes antigos; a evolução legítima desse plano fez a verificação falhar em `b065e33`/`1d40e52`. Não declarar CI verde com base apenas nos testes locais desta revisão.

Decisão: entrada histórica explícita em cápsula privada, com o plano original extraído de `f8881d4` e SHA exatamente igual ao recibo C04. A única substituição documental permitida é esse path identificado; verificador, métodos, fontes, fixtures e recibos históricos continuam com seus hashes originais. O plano corrente permanece documento vivo e não é retroativamente rehashado no recibo. Novo entry verifica sua própria origem/closure e rejeita original adulterado, doc corrente no lugar do original, substituição extra, receipt reancorado e symlink/escape. Registrar claramente qual revisão foi reproduzida. Só conectar o entry à CI após essas contraprovas e confirmar novo run regular; cápsula que apenas ignora mismatch ou retorna resultado cacheado não satisfaz o aceite. Isso resolve a dependência histórica sem relaxar a prova nem exigir congelar para sempre o planejamento atual.

[Revalidação da raiz](logs/revisao-L5-C06/evidencias.json) e [pareceres/hashes](logs/revisao-L5-C06/agentes.json) distinguem execução de testes próprios, leitura de código e resultado apenas relatado. Nenhuma execução native/upstream/provider ou aquisição nova foi feita pela arquitetura. Trabalho ainda em andamento não recebe aceite global por existir no disco.

**Até v1.0:** M0, oito tarefas individualmente elegíveis, D1 global 0/32, quatro eventos operacionais e projeção multimódulo 19/20. Permanecem 9 cartões concluídos/7 em andamento/25 não iniciados, G0/G1/G2 não avaliados e seis atividades V1 condicionais. O progresso desta rodada está na integração e no candidato preparado; ainda não há medida de sucesso de agente nem base para percentual/data de 1.0.

## 2. D01 — preservar todas as tentativas, inclusive recusas

**Achado P2:** o replay v3 confere que as tentativas do ledger aparecem no wrapper, mas isso não cobre uma operação recusada pela guarda antes da reserva. A [contraprova](logs/revisao-L5-C06/omissao-replay.json) mantém journal com `dispatch:one` e `dispatch:two`, remove somente a linha imutável `two` e obtém `verified=true`, com uma tentativa em vez de duas. É falha de completude do recibo; não é bypass de execução nem cobrança real. Não reabre a correção do pedido mutável, que passou nos testes do novo caminho.

**Decisão imediata:** exigir bijeção entre registros do wrapper e todos os begin/end de dispatch da guarda, inclusive precheck recusado e operação não delegada. Continuar verificando ledger para as tentativas reservadas, sem tratá-lo como denominador completo. Correlacionar ID/ordem/argumentos/resultado e estado terminal; recover/expand não são tentativas de dispatch. Erro de captura anterior à entrada na guarda tem categoria própria e não inventa begin/end inexistente. Expor contagens distintas de pedidos, reservas, compromissos e invocações observadas; nenhuma recusa desaparece por falta de cobrança.

**Aceite:** contraprova atual passa a recusar; omissão, extra, duplicação, troca de ID/recusa, ordem incompatível e resposta de outra tentativa também recusadas. Precheck recusado permanece zero I/O/zero reserva; recibo tardio e retries mantêm contabilidade idempotente. Preservar fixtures antigas e registrar o conserto prospectivo; não converter a projeção privada em prova de transporte.

### Próxima interface de transporte

Depois dessa correção, um dono de sessão compõe captura, guarda e transporte público; evitar uma cadeia indefinida de wrappers. A entrada do adapter recebe bytes imutáveis, hash/tamanho, versão de serializer, task/arm/run/call/attempt e vínculo ao compromisso. Se o formato de transporte difere do pedido lógico, produzir e limitar os bytes finais antes do envio, com ligação explícita à origem/configuração. Não reler dict do caller nem serializar conteúdo mutável depois do compromisso.

O adapter produz recibo da entrada que efetivamente consumiu, pelo próprio ponto público. Distinguir: não invocado comprovado, invocado com resultado incerto, resposta observada. Recibo local de entrada não prova aceite remoto, execução do modelo ou cobrança zero. `transport_projection` permanece projeção quando não há observação. Cada retry tem seus próprios bytes/recibos; ausência de prova após compromisso mantém reserva/estado incerto conforme D01.

**Primeira prova ainda fake/offline:** um fluxo consumer completo compara bytes reservados, recebidos e replay; cobre serializer divergente, truncamento, recibo de outra tentativa, omissão/duplicação, falha antes da invocação, timeout e receipt tardio. Sem profiler no executor e sem provider/modelo/credencial necessários para esse contrato. Adoção offline não fecha M0-04 nem os quatro smokes reais. ABA/gerações, blobs e orçamento agregado permanecem como definidos na revisão C05.

## 3. Django — oracle físico e crédito multimódulo condicionado

O candidato no slot `L5-SLOT-Python-state_config-1` está preparado: universo amplo, pin/licenças, configuração A/B, oito casos centrais e dez controles declarativos, fontes e segunda leitura. Esse redutor próprio não executa Django e não prova criação de tabela. A falta desse resultado continua bloqueando elegibilidade/crédito; não substituir a medição física por uma tabela calculada pelo mesmo algoritmo.

**Risco de quota decorativa:** inverter os dois routers e resolver os oito casos centrais pode ser deduzido da política pública e de `ConnectionRouter`. Exigir três paths na rubrica CHAIN, sozinho, não demonstra que três módulos são necessários. A compensação só é válida se um requisito substantivo do cenário exigir também o comportamento de migração/modelo, não apenas citar a cadeia por conveniência do avaliador.

**Decisão sobre a próxima variante, antes de executar:** explicitar no contexto público um modelo legado não gerenciado, cuja tabela não deve ser criada por migração mesmo quando o router permite, junto à correção de roteamento das duas bases. Fixar estado/modelo/configuração e expectativa antes dos resultados, com nova versão/linhagem da preparação quando alterar o cenário. O pedido descreve o objetivo operacional; não revela paths/métodos de solução. Usar condição de domínio realmente sustentada no checkout, não inventar bug upstream. Aceitar evidências equivalentes válidas: mínimo é relação necessária entre unidades, não uma lista obrigatória de três arquivos.

Oracle próprio chama o `CreateModel` capturado com modelo histórico e schema editor real em duas bases SQLite descartáveis. Conferir tabelas reais e alias físico após cada cenário, preservar base não alvo e aplicativos não envolvidos. Cobrir ordem, None/False/True e veto do modelo; instrumentação do observador pode registrar consultas ao router sem substituir sua implementação. O caso vetado deve demonstrar ausência de criação e, onde o contrato capturado assim define, ausência de consulta ao router. Uma resposta baseada apenas na tabela dos routers precisa falhar nesse requisito independente para sustentar o crédito adicional.

**Setup e visibilidade:** reaproveitar pin/arquivo/fontes/licenças e inventário do piloto Django como entradas; não reaproveitar recibo JSONField como execução deste oracle. Preparar runtime/lock/proveniência próprios e fases de aquisição, import e execução em domínio descartável permitido. Checkout/inputs autoritativos somente leitura; SQLite, caches, pycache e temporários em scratch separado; rede/segredos/ambiente do host fora do processo de teste. Fixar timeout, limites de processos/saída/bytes e observar encerramento. Materializar agente e avaliador em universos separados: tarefa/configuração e checkout amplo no lado público; reference/oracle/rubrica privados. Provar por ferramentas reais do domínio que o agente não lê arquivos do avaliador; nomes de diretórios não são isolamento.

**Aceite para a próxima entrega:** receipts originais do oracle físico, resultados A/B e controles, materialização/limites verificados e segunda leitura da necessidade entre módulos. Se o novo requisito for artificial, estiver só no oracle oculto ou todos os casos físicos repetirem a decisão de router, manter `multimodule=false` e 19/20; uma tarefa eventualmente elegível não recebe esse crédito automaticamente. Variante/recusa não apaga a preparação existente nem os eventos scikit-learn.

Quando os critérios factuais forem cumpridos, o Implementador pode produzir plano/consumer prospectivo v3 que derive o crédito e mantenha bijeção/linhagem, quatro slots por repo e pisos, sem outra aprovação de detalhe. Estado corrente continua oito elegíveis/0 admitidos; projeção 20/20 futura também não equivale a vinte tarefas qualificadas. Não editar mapas/recibos v2 para acomodar o candidato.

## 4. P3 — terminar a prova atual e conectar ao planejador

O novo `context-diff-spike` ainda é um consumidor por bytes. Não chama `context_spike::Store`, não cria obrigações IR/P2 e não demonstra qualidade de tarefa. Isso é um passo verificável, mas não encerra o pedido de integração da revisão C05. Primeiro concluir build/coleta/reconciliação da versão corrigida, com os mesmos pares congelados e 182 comandos vivos/43 rebuild; preservar a tentativa de lint e não contar testes skipped como prova.

A próxima fatia deve extrair/reusar a validação tipada de forma que **o Store existente a consuma**, sem criar outro caminho paralelo de produto. `Absent` difere de `Present(empty)` e de fonte indisponível. O Store antigo exige path nos dois lados; não preencher criação/remoção com arquivo vazio para fazê-lo aceitar. Publicar apenas snapshot completo validado; update inválido preserva a revisão anterior. Identidade SHA-256 do intake e BLAKE3 interno permanecem declaradas separadamente: SHA conferido só no verificador Python não vira verificação nativa. A fronteira que aceitar uma identidade externa como autoridade deve checá-la sobre os mesmos bytes; evitar novo parser universal de diff só para obter esse vínculo.

Obrigações por presença: criação em HEAD, remoção em BASE, arquivo vazio sem span semântico inventado. P2 acrescenta somente relações demonstradas por frontend compatível. Expansão de arquivo removido consulta BASE retida; prova integral B deve coincidir com rebuild independente. Fonte React da matriz continua controle de bytes e não vira semântica Rust.

**Primeiro commit de integração concreto:** captura Tokio `2fb5757a97a94b3173f8fdd7b6280423b63da6e6`, unidade `tokio/src/io/uring/utils.rs` em `eval/semantics/tokio-development.json`, edição 2021/perfil Rust R1/R2. Congelar regressão derivada removendo somente a declaração `cstr`: BASE conserva definição e expansão, HEAD informa unknown, ArcFd/UringFd permanecem resolvidos e OwnedFd unknown no recorte já rotulado. O seletor deriva ocorrências dos hunks/fontes; o oracle não fornece anchors de solução. É transformação controlada para ligar o Store, não bug histórico, tarefa natural ou dossiê novo. Create/delete de arquivo continua separado nos controles React já congelados, com P2 indisponível.

**Retenção em falha:** a leitura de `Store::context` identificou evicção por pressão antes de uma nova checagem de deadline. Não houve reprodução nativa nesta revisão; acrescentar contraprova determinística dessa janela na integração. Planejar vítimas/bytes e concluir operações falíveis antes de um compromisso único que aplica evicções e publica o novo contexto. Falha por timeout/limite não remove A ainda válido; expiração legítima por TTL permanece regra própria. Cobrir também handle retido e orçamento insuficiente, sem fingir preservação de contexto já expirado.

**Aceite da vertical seguinte:** selecionar tarefa Rust natural compatível, usar contexto completo pelo Store e consumer guardado, contra controle lexical no mesmo universo e orçamento de sessão. Rubrica/oracle ficam no avaliador; registrar perdas/unknown e obrigações que não cabem. Não prometer suporte ao dossiê rust-analyzer23422 com o perfil atual: métodos/tipos entre crates podem exigir extensão específica. Igualdade de bytes, sucesso do oracle e cobertura de evidência são resultados distintos; a regressão Tokio não substitui esse aceite de tarefa inteira.

## 5. Ordem e frentes independentes

| Ordem / ID existente | Próxima entrega concreta | Condição de encerramento |
|---|---|---|
| Imediato / L5-05 | Entrada histórica C04 com plano original | Hashes preservados, substituição explícita/limitada e CI regular novamente comprovada |
| 1 / L5-05 | Bijeção do replay de dispatch | Contraprova de omissão recusada e denominadores completos |
| 2 / L5-04 | Variante Django com requisito de modelo + oracle físico/visibilidade | Comportamento medido e necessidade multimódulo revisada; caso contrário sem crédito |
| 3 / L5-01 | Prova nativa P3 atual; intake consumido pelo Store | Rebuild/retensão/obrigações e uma vertical compatível, sem atalho por arquivo vazio |
| 4 / L5-05 | Interface pública de transporte com recibo próprio | Bytes efetivamente consumidos e tentativas completas no fake |
| Paralelo / L5-01/02/03/06 e S02 | Conjunto lexical24, expansão, semântica por perda útil, recursos v2, triagem/smoke e coletor | Critérios da revisão C05 continuam, sem repetição das provas aceitas |

Dono de integração coordena schemas/Store/consumer compartilhados; agentes recebem ownership exclusivo de módulos. A próxima entrega prioriza tarefa completa e correções demonstradas. Não adiar essas frentes para construir banco M1, frontend integral, parser próprio ou wrappers genéricos. Bibliotecas novas continuam permitidas quando uma perda concreta justificar seu investimento.

[Checks documentais](logs/revisao-L5-C06/documentacao.json) preservam cartões/gates e verificam links/escopo. Commit/push desta revisão inclui somente arquivos da arquitetura; trabalho simultâneo do Implementador é preservado e recebe revisão própria quando houver evidência estável.
