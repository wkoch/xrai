# Fechamento C06 — aceites e próxima integração

13/10/2026, Arquiteto. Corte `bd12a9a`, código final `b5b9f8b`; entrega histórica/P3 em `282f885`. Esta revisão sucede a [C06](REVISAO-L5-C06.md) nos itens explicitamente encerrados abaixo; os demais contratos C06 e [C05](REVISAO-L5-C05.md) continuam. Três agentes fizeram revisão de escopos distintos. Apenas documentação/evidências são entregues pela arquitetura.

## 1. Entregas verificadas

| Entrega | Evidência e aceite | Limite preservado |
|---|---|---|
| D01 v4 e consumer v3 | 38 + 33 testes fake; a omissão de recusa sem reserva é rejeitada. Admissão de ID/capacidade ocorre atomicamente; captura pendente impede snapshot incompleto; wrapper e guarda usam o mesmo snapshot e ordem | Captura privada e projeção continuam sem observação pública do transporte; nenhum provider foi chamado |
| Adapter histórico C04 | Cápsula de 30 inputs, sete replays, oito comparadores; 16 testes refeitos; snapshot do plano igual a `git show f8881d4` | Reproduz a prova histórica; não vincula o plano atual nem qualifica tarefa nova |
| P3 nativo | Run `38441971210` / `fbf1e53`: ZIP/API/export retidos conferidos; recomposição integral igual ao recibo, 225 comandos e 42 pares; 47 testes locais sem skips | Intake tipado e contexto por bytes; Store/IR/P2, tokens e sucesso de agente ainda não demonstrados |
| CI regular | APIs retidas de `38446119525` / `b5b9f8b`: contratos, Linux x86_64 e macOS arm64 aprovados | Dois jobs comportamentais upstream permaneceram skipped; não são nova prova. O commit documental posterior não herda uma execução própria de CI |

[Revalidação da raiz](logs/revisao-L5-C06-fechamento/evidencias.json), [revisões dos agentes](logs/revisao-L5-C06-fechamento/agentes.json) e [verificação documental](logs/revisao-L5-C06-fechamento/documentacao.json) registram escopos, comandos e hashes. Os 134 testes refeitos nesta rodada são próprios, offline ou sobre dados retidos. A arquitetura não executou ELF retido, analisador do produto, projeto upstream ou provider. A conferência de API/ZIP usa a aquisição histórica registrada; não houve nova aquisição autenticada, e JSON não é assinatura.

**Encerrados:** achado de omissão do replay C06, entrada histórica/CI e falta de prova nativa do consumidor de bytes. Não recolocar esses itens no primeiro lote. A cápsula executa somente método próprio fixado; seu limite de stdout/stderr é conferido depois da captura e não é promessa de contenção para execução upstream.

## 2. Próxima fatia P3: Store existente, presença e Tokio

Dono: L5-01, nos módulos de avaliação de contexto existentes. Entregar uma ponte interna reutilizável do intake validado para `context_spike::Store`, preservando o driver histórico de bytes e seus recibos. Evitar um terceiro planejador paralelo. O Implementador escolhe nomes/arquivos; o contrato é o seguinte:

1. Separar revisão capturada/presença de IR opcional. O tipo validado tem construção privada; desserializar DTO externo não dispensa validação nativa. Cada lado mantém identidade, bytes e perfil; representar `Absent`, `Present(empty)` e indisponibilidade separadamente. O `ValidatedDiff` só nasce depois de validar ambos os lados, spans, identidade e reconstrução integral de HEAD. Validar identidade externa sobre os mesmos bytes ou declará-la apenas proveniência externa; SHA Python não vira SHA nativo.
2. `p2=false` hoje desliga consultas, mas `prepare` ainda constrói semântica e candidatos usam parser Rust. Corrigir essa fronteira: um contexto React de bytes não pode executar análise Rust nem anunciar P2. Reusar Store/seleção/expansão com IR ausente e diagnósticos explícitos. Não exige implementar frontend universal.
3. Traduzir hunks em obrigações por lado: conteúdo criado em HEAD, removido em BASE, presente vazio com evidência de presença sem span falso. Não preencher ausência com arquivo vazio. Expansão referencia snapshot e lado retidos; ausência conhecida não é falha de captura.
4. Tornar a publicação do contexto transacional dentro do Store experimental: calcular vítimas e concluir operações falíveis antes de aplicar evicções/publicar. Relógio determinístico e pressão de memória devem demonstrar que timeout ou limite da operação B não remove A ainda válido. TTL vencido continua expiração legítima; não alterar contratos históricos para fazer a prova passar.
5. Congelar a regressão Tokio já decidida: pin `2fb5757a97a94b3173f8fdd7b6280423b63da6e6`, `tokio/src/io/uring/utils.rs`, edição 2021, perfil `rust-r1-r2-v1`. B remove somente a declaração `cstr`; derivar pedido dos hunks/ocorrências reais. BASE mantém definição/expansão; HEAD indica unknown para a consulta derivada a cstr, sem inventar ocorrência após remover sua declaração; ArcFd/UringFd permanecem resolvidos e OwnedFd unknown. Comparar respostas completas com rebuild independente.
6. Aplicar orçamento à resposta serializada e à sessão inteira, incluindo expansões/retries/recusas conforme contrato vigente. Um limite em bytes não é medição de tokens. Separar prova funcional da posterior curva medida; respeitar o limite efetivo atual de 512 KiB do meter e limites mais restritivos. Não usar quota maior para esconder obrigação omitida. Tentativa admitida de expansão continua consumindo o contador mesmo se falhar; atomicidade de publicação não devolve custo já incorrido.

**Aceite mínimo:** atualização válida A→B; atualização inválida preserva A; criação/remoção/presente vazio nos controles React sem P2; Tokio com BASE/HEAD e expansão correta; pressão/deadline e handle retido; comparação integral com rebuild; mesma chamada pública de Store usada pelo consumer. Rebuild compara captura/IR, candidatos, obrigações, conteúdo, unknown e cobertura. Epochs/handles podem diferir entre processos: congelar previamente o mapeamento de identidades operacionais e conferir seus vínculos, sem excluir revisões/configuração/evidências para acomodar diferenças. Native receipt novo informa plataforma, configuração e método reais; não reancorar o receipt do binário C06 para atribuir a ele a integração futura.

Depois, selecionar tarefa Rust natural compatível com as capacidades efetivas e comparar Store+consumer com controle lexical no mesmo universo/orçamento. A regressão cstr é desenvolvimento controlado, sem crédito histórico, D1 ou sucesso de agente. Lacuna semântica material pode justificar biblioteca/extensão própria conforme ADR024; criar complexidade sem uma perda observada não aproxima o gate.

## 3. Django v2: comportamento físico e acesso separado

Dono: L5-04, candidato `django-router`, sem alterar receipts v1. Não houve nova implementação desse candidato desde `fbf1e53`. Preservar pin `8abacfc36d755d8e762a4d2074601b8dc412bfee`, arquivo completo/licenças e proveniência; as duas policies A/B existentes permanecem identificadas por bytes. Criar variante pública v2 com `ledger.LegacyEntry`, modelo legado `managed=False`, cuja tabela a migração não deve criar mesmo onde o router permitiria.

A condição deve constar no enunciado/material do agente antes da execução, com estados e expectativas congelados. Não adicionar critério oculto para transformar a tarefa artificialmente em multimódulo. A rubrica avalia relações necessárias e aceita evidência equivalente; três paths citados não são prova de necessidade.

Estado inicial: tabelas dos três modelos ausentes nas duas bases; sentinelas separadas são fixtures do avaliador. Apenas a ordem dos componentes da configuração é editável pelo agente. O resultado físico esperado fica congelado:

| Estado / alias | ledger.Entry | catalog.Item | ledger.LegacyEntry |
|---|---|---|---|
| A: primary, scoped / default | presente | presente | ausente |
| A: primary, scoped / reporting | ausente | ausente | ausente |
| B: scoped, primary / default | ausente | presente | ausente |
| B: scoped, primary / reporting | presente | ausente | ausente |

**Oracle físico mínimo:** duas execuções frescas A/B, cada uma com dois bancos SQLite scratch e três modelos, total de 12 células. Usar `CreateModel`, estado histórico produzido pela operação, `database_forwards` e schema editor reais do Django capturado. Conferir tabelas físicas nos dois aliases e preservação de sentinelas fora do alvo. Para LegacyEntry, exigir ausência de nova tabela e demonstrar que o veto do modelo ocorre antes da consulta ao router; instrumentação observa a chamada real, não substitui sua decisão. A autorização isolada do router serve como controle de que o veto vem do modelo.

Os oito resultados dos modelos managed cobrem ordem, True/False e abstenção. Acrescentar dois controles físicos nos dois aliases (quatro resultados): all-None permite; componente sem método seguido de False recusa. Os dez controles declarativos v1 conservam sua natureza; não alegar prova física dos que não forem executados. Fazer baseline/referência divergirem nos requisitos públicos esperados; execução do oracle apenas sobre a referência ou tabela-verdade Python não basta. Se o fixture precisar de modelo unmanaged já existente, preparar uma tabela legada com sentinela e provar preservação, distinguindo essa preparação da criação pela operação testada.

**Materialização e execução:** agente recebe somente checkout capturado e tarefa pública; avaliador recebe oracle/rubrica/referência privados. Testar a visibilidade efetiva das ferramentas e paths, inclusive tentativa de ler os privados. Runtime/dependências Python/SQLite devem ter versão, hash/proveniência, licença e lock registrados antes da execução; não herdar pacotes do host sem inventário. Instalação e execução são fases distintas. Checkout só leitura, scratch próprio para bancos/cache/pycache/temp; sem rede/segredos; limites de tempo/processos/bytes/output e encerramento coletados no domínio descartável. Orçamento inicial do oracle: execução serial, 60 s por processo, 300 s no lote, 1 MiB por stream; fixar memória, processos e disco conforme mecanismos realmente aplicados pelo executor, antes do run. Conferir que os dois aliases não apontam ao mesmo banco e que imports vêm do snapshot. Separar `oracle_executed` de `requirement_satisfied`: baseline pode executar corretamente e reproduzir a falha esperada. Reusar o runner permitido; indisponibilidade do domínio impede a prova física, mas não as outras frentes.

**Saída:** oracle físico reproduzível, baseline/referência, contraprovas de políticas e isolamento, fontes/lineage congeladas e parecer sobre necessidade multimódulo. Só então atualizar prospectivamente E02/consumer com fatos. Sem necessidade demonstrada, `multimodule=false` e projeção 19/20; elegibilidade individual eventual não concede automaticamente esse crédito. Não há necessidade de nova aprovação arquitetural rotineira se esses critérios forem cumpridos.

## 4. D01: observar a fronteira pública do transporte

Dono: L5-05, mesmo dono da sessão/consumer. Não refazer ledger, guarda ou máquina de estados. A próxima entrega é fake e local; ela prepara a interface do adapter real sem chamar provider.

**Primeiro incremento:** preparar uma única representação imutável final antes de reservar/comprometer. Se o adapter exige serialização diferente, produzir seus bytes limitados nessa fase; registrar separadamente hash lógico e hash/size/versão do formato wire. O consumidor público do transporte recebe esses mesmos bytes e emite recibo de entrada com task/arm/run/call/attempt/commit e identidade do payload. Não reler dict do chamador nem inferir o recibo pela projeção privada do ledger.

**Segundo incremento:** correlacionar lifecycle e replay completos por tentativa. Distinguir entrada local, envio incerto e resposta recebida; entrada local não prova aceitação remota, execução do modelo, tokens ou cobrança. Ausência só é provada pelo caminho que sabe que a entrada não ocorreu. Timeout/erro depois do compromisso conserva reserva enquanto o resultado for incerto. Retry tem identidade/recibo próprios; evento tardio é idempotente. Consumer consome o mesmo owner de sessão, sem novo wrapper que duplique autoridade.

**Aceite fake:** payload serializado difere do lógico; mutação do chamador; truncamento; serializer/attempt incorretos; recusa antes de entrada; entrada seguida de exceção/timeout; retorno ausente; recibo omitido/duplicado; retry e resultado tardio; snapshot durante execução. Replay recusa lacunas e metadados fabricados, mantendo contagens separadas de pedidos, reservas, compromissos, entradas e respostas. ABA e blobs continuam contratos C05: geração monotônica própria/fencing e captura/retensão limitada; referências de blobs não são conteúdo entregue ao modelo.

## 5. Ordem, avanço ao v1 e critério de parada

| Prioridade / cartão existente | Resultado que o Implementador deve entregar | Dependência |
|---|---|---|
| 1 / L5-01 | Store consome diff tipado e prova Tokio/React/retensão | Prova nativa C06 já aceita; não esperar Django |
| 1 paralelo / L5-04 | Variante Django v2 pública + oracle físico/visibilidade | Runtime/domínio contidos; preparação está pronta |
| 2 paralelo / L5-05 | Recibo na interface pública do transporte fake | D01 v4/consumer v3 aceitos; não exige provider |
| Continuidade / L5-01/02/03/06, S02 | Lexical24/expansão, semântica por perda útil, recursos v2, comparadores/smoke, coletor limitado | Contratos C05; sem depender de banco/produção M1 |
| Depois / M0-12 e M0-10 | Piloto competitivo e decisão G0 | Corpus/qualificação, candidatos/comparadores fortes, sessão completa e recursos autorizados |

Distribuir módulos exclusivos entre agentes. Integrador coordena Store/consumer/schemas; registrar cada mudança de formato prospectivamente. A próxima unidade de progresso deve ser integração executável ou tarefa/oracle real. Encerrar os controles de uma fatia quando os critérios estiverem demonstrados; ampliar testes/recibos somente por mudança, falha ou lacuna concreta. Não criar novos lotes de documentação para adiar essas entregas.

**Até v1.0:** 9 cartões concluídos, 7 em andamento, 25 não iniciados; todos os 23 M1 ainda não iniciados; seis V1 condicionais intactos. Oito dossiês individualmente elegíveis, D1 global 0/32, quatro eventos operacionais; faltam 24 tarefas, 11 complexas, 10 históricas e 12 multimódulo no balanço qualificado (categorias sobrepostas). A projeção do plano continua 19/20, distinta desse balanço. G0/G1/G2 não avaliados. Esses fechamentos reduzem risco experimental, mas não medem ganho de agente. O caminho segue M0/G0 → confirmação M1-A/G1 → integração alpha/G2 → estabilização V1. Sem percentual ou data justificável hoje.
