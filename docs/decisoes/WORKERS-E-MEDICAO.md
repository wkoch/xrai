# Workers persistentes e medição reproduzível — ADR 026

12/10/2026. Decisão do Arquiteto para a continuação de M0-04/M0-06 e preparação M0-09/12. Concretiza ADR 023; preserva os limites e gates. Entrada: [workers L3](../../eval/reports/m0-workers.md), replay local v1/v2 e [revisão L3](../relatorios/REVISAO-L3.md). Nada aqui declara implementação ou despesa realizada.

## 1. Decisão sobre o próximo worker

Comparar três modos com o mesmo corpus: parsing direto, subprocesso por tentativa já entregue e dois workers persistentes com um pedido ativo em cada um. Não retirar contenção para escolher o modo de produção só por latência do modo direto. O primeiro pool persistente reutiliza processo e recursos de gramática/query compatíveis; **não precisa guardar AST de todos os arquivos nem cache de respostas**.

O protocolo XRW1 atual é de pedido único, resposta e EOF/exit. Preservá-lo como controle/replay. Criar protocolo experimental XRW2 discriminado por magic/versão e mensagens tipadas; não reinterpretar EOF do XRW1 como término de pedido numa conexão reutilizada. Iniciar o próprio executável com modo explícito, sem autodetecção ambígua de protocolo.

Handshake registra versão, encarnação aleatória do worker, produtores/dialetos aceitos e limites. Tipos mínimos: Hello/Ready, Parse, Result e Shutdown; rejeitar tipo/estado inesperado. Cada frame tem teto validado antes de alocar. O pai atribui request/attempt e associa o canal a uma encarnação; identidades de fonte, produtor e configuração permanecem obrigatórias. Não confiar só no PID, que pode ser reutilizado.

Máquina de estados do pai: Starting → Idle → Busy → Idle; qualquer timeout/cancelamento/violação grave passa por Retiring → Reaped antes de substituição. Um único Parse em voo por worker simplifica correlação e cancelamento. Sem multiplexar dois clientes no mesmo parser no primeiro recorte. Worker só sinaliza Ready inicial após handshake válido; o Result terminal de um pedido libera a próxima admissão naquele canal.

**Conclusão por mensagem:** Result contém payload completo, estado e identidades; frame validado conclui o pedido, sem esperar EOF ou exit0. Emitir somente depois de terminar a computação/validação e liberar recursos temporários que não pertencem ao cache permitido. Pai valida estado, spans e consistência entre envelope e payload antes de aceitar. Evitar duas fontes de verdade: se campos forem repetidos no JSON interno, exigir igualdade. Result duplicado/tardio ou de outra encarnação é erro de protocolo, nunca segunda publicação.

Crash após Result já validado não revoga retroativamente aquela resposta imutável; invalida a saúde do worker e afeta trabalho em voo posterior. Frame incompleto, hash incorreto ou morte antes de completar Result não conclui pedido. Essa distinção substitui a exigência exit0 por resposta **somente no XRW2**; XRW1 e seus testes permanecem com semântica original.

## 2. Cancelamento, retenção e caches

Ao cancelar/estourar deadline em Busy, retirar o worker e encerrar/recolher seu processo; descartar frame parcial. Não tentar recuperar alinhamento do stream após interrupção. Outro worker deve continuar. Retry continua no máximo um em processo novo e dentro do deadline total, somente para falha transitória de transporte/crash; erro de protocolo/identidade/limite/linguagem é definitivo. Cancelamento não provoca retry. Resultado pronto para entrega ainda verifica cancelamento/validade da tentativa.

Manter valores de referência: 2 workers, fila 8, fonte 8 MiB, resposta 16 MiB, payload reservado 64 MiB, deadline total 5 s, stderr retido 64 KiB. O relatório atual limita fila/processamento; a continuação deve também controlar respostas concluídas **ainda retidas pelo pool/ticket**, para que consumidor lento não esvazie a contabilidade sem liberar memória. Transferência ao consumidor externo tem limite/ownership documentado. Tokens de reserva pertencem a objetos RAII; cancelamento, drop, erro e shutdown os liberam exatamente uma vez. Temporários de codec, parser nativo e overhead não são RSS coberto pelo cap lógico.

Cache permitido inicialmente: gramática/query por fingerprint/dialect e estado reutilizável do parser com reset comprovado. Erros, configuração, linguagem, ranges e cancelamento de um pedido não vazam para o seguinte. AST/cache incremental é outro experimento: depende de fonte anterior, edição validada e owner; não pertence automaticamente ao pool persistente.

Shutdown: fechar admissão, cancelar ou drenar conforme política fixa/deadline, enviar Shutdown a Idle, recolher todos os filhos e reunir leitores/escritores. Processo morto durante handshake/Idle/Busy é detectado. Não deixar reader bloqueado em pipe ao destruir pool. Testes devem provar PID/encarnação repetidos em múltiplos pedidos saudáveis, substituição após falha e resposta correta depois de alternar dialect/configuração.

## 3. Benchmark e recursos: metodologia antes dos resultados

Congelar manifesto com binário/commit, host/SO, corpus, fontes/hashes, produtor, configuração, modo, workers, número de rodadas, ordem e método de observação. Proposta inicial: três sessões independentes por modo, pelo menos 30 pedidos medidos por classe/sessão; warm-up separado e explicitado. Os números são desenho inicial, não garantia estatística. Se custo operacional inviabilizar a matriz, registrar ajuste antes de obter comparações; seis observações antigas continuam exploratórias.

Classes: fontes pequenas reais, médias reais, grandes com alta densidade sintática, incompletas/erros, repetição de mesma fonte e sequência de fontes distintas; cobrir os sete dialetos. Manter large-comments antigo como controle, sem tratá-lo como representante de projeto grande. Arquivos escolhidos por tamanho/sintaxe, sem oracle de tarefa ou resultado xrai. Incluir pelo menos uma sequência de configurações/dialetos alternados para detectar contaminação.

Separar cold (startup/handshake) de warm; cold de processo não implica page cache do SO frio. Comparar primeiro latência com um pedido por vez nos três modos; medir throughput com a concorrência declarada em tabela separada, sem atribuir ao IPC um ganho causado por mais CPUs. Fixar carga por modo e alternar ordem entre sessões para reduzir viés. Medir tempo de fila, codec, roundtrip e end-to-end sem somar percentis de componentes. Publicar amostras cruas, p50/p95 por sessão, throughput, falhas, retries, bytes IPC/stderr e tempo de shutdown. Diferença de desempenho não pode ocultar divergência lógica.

**CPU:** segundos user/system do pai e filhos do experimento, com identidade/lifetime e origem dos contadores; somar deltas sem contar o mesmo filho duas vezes por agregação do pai. Filhos curtos exigem contabilização de saída ou mecanismo equivalente; amostragem que os perdeu não equivale a zero. Observador pertence a outro domínio de medição, com overhead separado. Não usar CPU de todos os filhos históricos do processo como se fosse a deste run.

**Memória:** série temporal da soma de RSS dos processos simultaneamente vivos (pai+workers) e máximo dessa série; registrar intervalo e lacunas do sampler, processo/encarnação, mínimo de processos observados e baseline ocioso. Chamar o valor de `sampled_peak_sum_rss`, não pico físico exato: páginas compartilhadas podem aparecer em mais de um RSS e picos entre amostras podem ser perdidos. Soma dos máximos individuais não é pico simultâneo; ru_maxrss de um único filho não é memória do pool. Dados impossíveis de coletar ficam null com causa.

Não inventar porcentagem obrigatória de ganho. Concluir comparação mesmo se persistência não melhorar a carga: registrar se startup, recursos, confiabilidade e manutenção justificam escolha. M0-06 fecha quando comparação e critérios funcionais estiverem comprovados; o modo final é decisão fundamentada, não obrigação de declarar persistência vencedora. M1-05 preserva isolamento e só promove o recorte verificado.

## 4. Três contabilidades, sem mudar registros históricos

Replay `xrai.eval.local.v1/v2` continua aceitando somente o que realmente foi registrado, com modelo/tokenizer/usage/custo null nos históricos. Não preencher esses campos retroativamente para aparentar sessão de agente. Acrescentar artefato de medição offline versionado, ligado por hash ao transcript/projeção, e um schema próprio de sessão real (`xrai.eval.agent.v1`, nome proposto a concretizar). Roteador de replay/validação seleciona schema pela versão; versão desconhecida falha claramente.

| Camada | Fonte de verdade | Limite |
|---|---|---|
| Bytes do processo | stdout/stderr originais, hashes, observado/capturado/truncado | Não são necessariamente o texto enviado ao modelo |
| Tokens do conteúdo controlado | Bytes/texto efetivamente entregue, serializer, tokenizer e configuração fixados | Contagem exata só para esse perfil/payload; binário bruto não é texto sem projeção explícita |
| Uso/custo do provedor | Resposta/recibo do provedor, categorias e preço/data/unidade | Não inferir tokens ocultos/faturados usando tokenizer local; ausente não vira zero |

Escolher primeiro tokenizer disponível e reproduzível, fixando implementação/versão, hashes do vocabulário/merges/config, normalização e special-token policy. Comparar vetores de referência, Unicode/CRLF, conteúdo vazio, delimitadores, ferramentas e casos binários projetados. Fonte original permanece preservada; projeção ao modelo tem bytes/hash próprios e regra de escaping/truncamento. Sem perfil identificado, declarar estimativa e usar teto independente de bytes. O contrato público de orçamento de `m1.md` continua autoridade para resposta serializada.

## 5. Ledger de sessão, falhas e orçamento

Sessão real identifica task/dataset hash, braço, modelo/versão/esforço, policy/config, run ID, todas as chamadas e tentativas com sequência. Cada chamada liga bytes de request/response, tool definitions, orientação, ferramenta, expansões, edição/testes, timing e recibo de uso. Distinguir rejeição antes de envio, enviada sem resposta, resposta parcial, timeout, cancelamento e conclusão. Nenhuma delas pode desaparecer do custo ou denominador por conveniência.

Uso cacheado, tokens de raciocínio e categorias semelhantes podem ser subconjuntos dos totais do provedor. O adapter explicita a semântica de cada categoria e não soma subconjunto ao total novamente. ID do provedor e ID local evitam duplicar um recibo; retries são tentativas próprias, inclusive quando cobrança anterior é desconhecida. Preços versionados com fonte/data e unidade; registrar estimativa calculada e cobrança observada separadamente. Credenciais nunca entram no transcript publicado.

Reservar o máximo previsto antes de despachar cada chamada, considerando concorrência, limites de entrada/saída e preços conhecidos. Parar novas admissões quando teto não puder ser garantido pela política autorizada; reserva só é liberada conforme recibo/política de incerteza, não por timeout local. Uma chamada já enviada pode ter sido cobrada. Teto de orçamento do harness não é garantia universal de cobrança exata do provedor. Sem limite monetário definido, adapter pago permanece desabilitado; fake/replay e estimativa continuam possíveis.

Custo agregado tem flags de completude: qualquer cobrança desconhecida conserva lacuna/intervalo sustentado por evidência; não imputar zero nem aprovar gate de custo com subcontagem. Amortização de setup/indexação precisa ser definida antes da campanha; reportar também valor bruto, número de usos e regime. Sucesso continua resultado do julgador; tokenização exata não prova acerto.

## 6. Testes de aceite e readiness

| Frente | Aceite mínimo |
|---|---|
| XRW2 | Múltiplos pedidos no mesmo PID/encarnação; handshake inválido; frame parcial/excessivo; duplicata; morte Idle/Busy; resposta de tentativa antiga; cancelamento e worker saudável independente |
| Memória lógica | Consumidor lento/abandona ticket; fila cheia; resposta entregue/liberada; erro de codec; reservas voltam ao esperado e não extrapolam cap lógico |
| Isolamento de estado | Alternar sete dialetos/configs e entradas incompletas; repetir pedido anterior e comparar resultado integral com modo direto |
| Medição | CPU controlada com contador de saída; pai+dois filhos sobrepostos; observador separado; processo curto perdido registrado como lacuna; amostras/hashes reproduzíveis |
| Ledger | Fake streaming parcial, cobrança ausente, cache subset, retry, duplicata de receipt, cancelamento com cobrança possível e concorrência no teto |
| Replay | Históricos v1/v2 intactos; artefato offline adulterado rejeitado; sessão real usa schema próprio; tokenizer/serializer trocados invalidam a medição derivada |

Readiness produz razões específicas: recursos/modelo/credencial, orçamento, contenção por plataforma, corpus e perfil de medição. Diferenciar smoke pareado em D0/seed (permitido pelo cartão M0-04 com recursos autorizados) de campanha M0-12 (exige D1 admitido). Preparação do adapter e P2 não aguardam chamada paga. Não instalar configurações globais nem contratar recursos nesta etapa.

Os quatro smokes reais por família continuam necessários ao aceite M0-04; somente Linux contido pode recebê-los enquanto o macOS descartável estiver indisponível. Produto continua obrigado aos dois alvos. Levar a configuração existente a um modelo disponível é escolha de execução dentro dos recursos autorizados, sem fixar neste ADR um provedor ou preço não verificado.
