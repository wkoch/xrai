# Primeira vertical Rust: fonte capturada → Store → consumidor → tarefa

14/10/2026. Decisão do Arquiteto sobre `e30f54f`; nenhuma entrega nova do Implementador foi encontrada desde esse corte. Complementa o [fechamento C06](relatorios/REVISAO-L5-C06-FECHAMENTO.md), sem substituir seus aceites ou a ordem Store/Tokio, Django e transporte. Este arquivo especifica trabalho futuro; não afirma que a integração ou uma sessão real já existe.

## 1. Tarefa escolhida e alcance

Usar **Q1-Rust-8371, Tokio/FIFO**, como primeira tarefa natural inteira de desenvolvimento após os controles de integração. A [seleção capturada](../eval/qualification/vertical/selection.json) fixa BASE `2fb5757a97a94b3173f8fdd7b6280423b63da6e6` e referência `d241e4b5112ade7fa47310f39f81f59521ce988b`; o [pedido público](../eval/qualification/vertical/case-details.json) trata de FIFO sob esgotamento do orçamento cooperativo e preservação de permissões no cancelamento. O [oracle](../eval/qualification/vertical/oracles/tokio/oracle.json) e seus probes pertencem exclusivamente ao avaliador.

| Candidato já capturado | Decisão para esta vertical |
|---|---|
| Tokio/FIFO | Primeiro diagnóstico de tarefa inteira: origem histórica e oracle comportamental já preparados. Revalidar setup do domínio antes de executar; receipt antigo não comprova ambiente atual |
| rust-analyzer23422 | Preservar como tarefa elegível; não escolher primeiro para demonstrar P2 atual, pois a cadeia de tipos/métodos entre crates excede o recorte comprovado |
| Evento rand.rs | Controle operacional de configuração; não se transforma em correção natural nem em novo dossiê |
| Remoção cstr/Tokio | Regressão controlada de Store/P2 definida em C06; precede a tarefa natural e não a substitui |

A cadeia de Tokio envolve métodos, receptores e configuração além das relações P2 hoje comprovadas. Portanto o primeiro fluxo deve usar o Store/contexto conservador com **P2 desligado**, preservando extração estrutural Rust suportada e unknowns. Isso testa integração e disponibilidade de evidência; não comprova benefício semântico. P2 só ganha comparação específica depois de uma perda observada justificar uma fatia limitada, com rótulos independentes. Não desativar o Store e chamar uma execução puramente lexical de integração P3.

A tarefa já pertence ao conjunto conhecido de desenvolvimento. Reutilizá-la não aumenta oito elegíveis, não preenche quota novamente e não é confirmação reservada. O primeiro smoke Rust isolado não satisfaz o compromisso de quatro famílias/oito sessões do harness nem o piloto D1.

## 2. Entrada pública e início sem patch de solução

O agente recebe o pedido público e a captura ampla de BASE, com regras de edição e ferramentas declaradas. Não recebe `case-details.json` inteiro: esse arquivo também contém módulos/relações do avaliador. Materializar somente os campos públicos autorizados. Oracle, referência, patch de referência, mapa de módulos necessários, rótulos e relatórios ficam fora da raiz pesquisável, do índice e do prompt.

Fluxo inicial obrigatório:

1. Busca textual/estrutural a partir do enunciado, sobre o universo público congelado, sem restringir previamente aos arquivos do oracle.
2. Resultados de busca identificam fonte/revisão e spans verificáveis. O chamador escolhe âncoras desses resultados ou de leitura pública; o backend valida bytes e origem antes de preparar o contexto. Manter um rastro da consulta/resposta que originou cada âncora.
3. `context` e `expand` usam somente BASE enquanto não houver edição. A interface atual exige o slot técnico `head`; ele pode receber a única captura corrente somente com mapeamento explícito `role=initial_base`, sem inventar uma segunda revisão nem um patch. O envelope público deve dizer revisão única. Um novo HEAD distinto só surge da edição do agente.
4. Depois de uma edição pelo agente, capturar seu checkout candidato como HEAD. Só esse diff público BASE→candidato pode alimentar seleção/obrigações. O HEAD de referência nunca entra no backend do braço.
5. O avaliador aplica oracle privado ao patch candidato no domínio próprio e devolve o feedback permitido pelo protocolo, sem revelar o patch de referência.

Roteiro offline pode usar consultas públicas congeladas para exercitar a interface. Não recebe crédito de investigação ou sucesso do agente. Um teste que injeta anchors derivados da solução é contraprova de isolamento, não prova de descoberta.

## 3. Contrato da ponte Store–consumer

Dono L5-01 implementa o backend Store; dono L5-05 implementa o handler e a entrada consumidora. Um integrador é responsável pelo envelope e pelo vínculo das revisões. Reusar guarda, ledger e autorização de sessão; não criar outra máquina de estados.

A entrada histórica [guarded-smoke-v1](../eval/adapters/guarded-smoke-v1/README.md) é lexical/fake e exclui subprocesso/analisador. Preservar seus inputs, limites e receipts. A ponte nativa precisa de perfil experimental novo, com método, executável, configuração, entradas, limites e autorização de execução identificados; `fake_transport` não significa backend simulado. O fornecedor pode ser fake enquanto o handler chama o Store real.

Hoje `crates/xrai-eval/src/bin/context-spike.rs` gera um relatório one-shot, enquanto `context-diff-spike` conserva um contexto próprio de bytes. Nenhum dos dois demonstra a sessão necessária. Acrescentar uma entrada mínima de sessão, preferencialmente um modo do driver existente, que chame a biblioteca `crates/xrai-eval/src/context_spike.rs` integrada. O handler deve demonstrar chamadas efetivas no mesmo processo retido para contexto/expansão; não criar outro planejador. Respostas pré-gravadas ou reconstruídas por Python a partir do resultado esperado não encerram esse aceite. A validação de source bytes pelo consumidor é adicional à prova do produtor.

O envelope lexical atual exige um `ToolSnapshot` SHA-256 único e `lexical-delivery.v1`; o Store usa envelopes v3, descritores BLAKE3 e context/item handles. A guarda verifica tipos exatos. Portanto a ligação não se resolve passando um handler diferente ao factory antigo. Criar binding/verificador prospectivos e generalizar somente a composição necessária; preservar algoritmos, cobertura e bytes do Store sem conversão que perca informação. Identidade SHA e BLAKE3 não são intercambiáveis.

### Decisões de interface

- **Revisões:** vincular cada item a snapshot, lado quando houver comparação, arquivo e span. A identidade da sessão e a identidade da captura são distintas. Não rotular bytes BASE com identidade HEAD para caber no envelope antigo.
- **Presença:** criação/remoção/presente vazio precisam de representação explícita. Ausência não vira snippet vazio; resultado válido sem fonte recuperável não vira fonte observada. Preservar omissões, unknown e suporte declarado pelo Store.
- **Handles:** manter ligação exata entre handle do Store, contexto retido, produtor/configuração e referência externa. A expansão resolve a origem retida, inclusive BASE removida; nunca relê automaticamente o checkout atual. Expiração/evicção retorna diagnóstico próprio.
- **Formato e orçamento:** usar versão prospectiva quando o envelope antigo não conseguir expressar o resultado sem perdas. Medir os bytes finais entregues ao consumidor, incluindo envelope, representação de fontes, metadados e recusas. Se a ponte acrescentar overhead, incluir isso antes de prometer o limite; truncar depois da seleção é proibido. Limites mais estreitos de frame, guard, retenção e meter prevalecem.
- **Processo:** serializar uma requisição por processo, sem segurar o lock da guarda durante I/O. O helper batch atual `Process.call` escreve/flush antes de iniciar o deadline e só registra resposta JSON completa; não basta reusá-lo sem adaptar essas condições. O limite de tempo deve incluir escrita bloqueada, leitura e cancelamento. Usar framing limitado, ID/correlação de comando e leitura limitada antes de alocar frame completo. Registrar resposta parcial, EOF, stderr e encerramento. Cancelamento/timeout não permite atribuir ao próximo comando uma resposta atrasada. Reinício invalida identidades operacionais; não restaurar handles por semelhança de texto. EOF, frame inválido, timeout ou resposta não solicitada encerra essa instância; não fazer retry/reuso implícito. Uma operação pode ter sido aplicada antes do cancelamento: matar o processo não comprova rollback, e resposta tardia não pode escapar após recusa da guarda. O processo pertence à sessão, com encerramento e coleta dos filhos.

**Mudança de revisão e orçamento:** a edição legítima invalida o binding da captura antiga; não reler fontes novas sob o `ToolSnapshot` anterior. Fechar admissão desse binding, capturar/validar o candidato e emitir decisão prospectiva vinculada ao par, ao patch público e à mesma execução. Preservar o Store quando for necessário expandir BASE retida, mediante validação explícita de contexto/handle.

A transição não renova autorização nem teto: preservar custos, reservas incertas, tentativas, expansões e recusas acumulados pela tarefa. O dono da execução serializa a mudança e aplica o limite agregado entre bindings. Recibos antigos ficam imutáveis e eventos tardios permanecem associados à tentativa original, sem dupla contagem. Se a implementação exigir novo objeto de ledger, sua composição deve provar esse limite comum antes da admissão; criar ledger vazio por revisão não é aceite. Contraprovar patch repetido/reabertura, mudança com reserva incerta e resultado tardio após transição. Essa regra concretiza o orçamento de sessão já vigente e não pede nova máquina de estados genérica.

Não importar os limites de 128 KiB de fontes do consumer histórico como cobertura do checkout Tokio completo. Fixar prospectivamente limites do corpus público/materialização, entrada por chamada e saída. Fonte que exceda um limite deve produzir lacuna explícita; uma fatia selecionada não passa a representar cobertura integral do repositório.

## 4. Execução em três entregas delimitadas

| Entrega / responsabilidade | Conteúdo | Evidência que encerra |
|---|---|---|
| Ponte nativa / L5-01 + L5-05 | Novo perfil, handler Store real e tradução sem perda | Chamadas públicas context/expand, snapshots/presença/handles, bytes e orçamento verificados; contraprovas de troca/omissão/framing |
| Ensaio offline Tokio / integrador | BASE ampla, consultas públicas, captura do patch controlado próprio e evaluator separado | Rastro busca→âncora→contexto→expansão→HEAD; ausência de entrada privada; processo e custos controlados; sem alegar agent_run |
| Smoke real Rust / L5-05 | Uma tarefa, dois braços isolados: baseline textual competente e Store conservador | Agente produz patch, oracle julga ambos, sessão completa/custos/falhas preservados; modelo/configuração/recursos/teto autorizados antes da chamada |

A primeira linha depende da integração Store C06; Django e transporte podem continuar em paralelo. O recibo público do transporte é necessário antes do envio real, mas não bloqueia a ponte com fornecedor fake. A preparação do smoke pode avançar sem credencial; sua execução real exige as condições de contenção, medição e recursos já previstas em C05.

Os dois braços usam o mesmo enunciado, fonte pública, permissões de edição, testes públicos, modelo/esforço e tetos da sessão. Busca/leitura de fallback têm a mesma política de acesso, e suas chamadas/custos aparecem nos resultados. A baseline não perde acesso a fonte necessária para favorecer o Store. Os backends diferem de forma declarada; não compartilhar patches, memória ou saídas entre braços. Congelar ordem/seeds quando aplicáveis e critérios antes de observar os resultados.

Registrar separadamente: execução de infraestrutura, patch entregue, oracle satisfeito, regressões, evidência recuperada, unknown/omissões e custo. Não escolher o vencedor por pacote menor nem inferir sucesso por cumprir obrigações derivadas pelo próprio seletor. Recibo sem uso/cobrança conhecido conserva incerteza e reserva; sucesso ausente não produz custo por sucesso zero.

## 5. Contraprovas e condições de parada

Cobrir somente as fronteiras novas ou alteradas, preservando os testes já aceitos:

- Acesso ao patch/oracle/módulos privados por path absoluto, traversal, symlink, busca e índice; a chamada deve recusar antes de expor conteúdo.
- Âncora forjada, terceira revisão, spans/bytes trocados, BASE rotulada HEAD e candidato criado sem evento de edição público.
- Handle de outro contexto/sessão; handle expirado; restart; expansão após remoção em HEAD; retenção/evicção conforme o Store.
- Envelope incompleto ou alterado, erro convertido em sucesso vazio, overhead acima do orçamento, truncamento de frame e resposta tardia confundida com comando seguinte.
- Resultado sem chamada do backend real, entrada do corpus reduzida silenciosamente ou referência usada como resposta do fornecedor fake.

Se o perfil ainda não suporta a tarefa inteira sob seus limites, registrar a dimensão faltante e manter o resultado como ensaio parcial. Não estreitar o universo para os arquivos da solução nem promover unknown a resolved. Se a perda observada for localização de método, a primeira opção é extrair declaração e owner sintático de impl como candidato estrutural pesquisável, sem alegar receiver/trait dispatch resolvido. Uma extensão semântica só entra quando houver relação específica necessária que o controle textual/estrutural não entregou de forma adequada; o objetivo não exige um frontend completo antecipadamente.

A unidade seguinte de progresso é a ponte executável seguida da tarefa, não outro inventário de receipts. O Implementador pode resolver escolhas locais dentro destes contratos sem nova aprovação arquitetural. [Plano v1](ROTEIRO-V1.md) e gates permanecem: D0 tem 20 tarefas de desenvolvimento; G0 usa D1 global qualificado de 32. Este ensaio não reduz esses denominadores.

[Revisões e fontes desta decisão](relatorios/logs/vertical-Rust-planejamento/revisao.json) registram os dois pareceres, hashes e limites. Somente leitura e planejamento nesta rodada; nenhuma suíte anterior, projeto upstream, analisador nativo ou provider foi executado.
