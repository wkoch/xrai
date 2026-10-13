# L5 — próxima execução concretizada

13/10/2026. **Ordem corrente na [revisão L5-C04/C05](relatorios/REVISAO-L5-C05.md), §8.** Este arquivo preserva o detalhamento original baseado em `a8f3764`; fake, quatro eventos e TSJS-A/B/C foram entregues posteriormente. Não recomeçar esses itens. Não cria lote L6, novo ADR, autorização de campanha ou cartões M0/M1.

Fontes: [revisão vigente e aceites](relatorios/REVISAO-L5-C05.md), [estado](STATUS-IMPLEMENTACAO.md), [semântica P2](decisoes/SEMANTICA-P2.md) e [caminho até v1.0](ROTEIRO-V1.md). Código/testes/experimentos são responsabilidade do Implementador. O Arquiteto escreve este roteiro; agentes auxiliares fizeram revisão somente leitura.

## 1. Entrega que deve vir primeiro

Corrigir a identidade do pedido no dispatch D01; em paralelo qualificar o candidato Django e integrar intake de diff/presença ao P3 Rust. A revisão corrente define evidências e ownership para essas frentes, avaliação lexical, recursos, comparadores/smoke e inspeção. As seções seguintes são contratos históricos; seus itens aceitos não voltam a ficar pendentes pela redação original. Fonte e expansão permanecem ligadas ao snapshot; corpus/eventos/provider têm condições distintas.

Se dividir entre agentes, atribuir módulos exclusivos e um integrador para schemas/entradas compartilhadas. Preservar alterações existentes e não executar campanhas por inferência dessa divisão.

## 2. C03: gate onde a chamada real acontece

`agent_ledger.readiness` (`crates/xrai-eval/harness/agent_ledger.py`) é um diagnóstico por flags; não prova admissão. `Ledger.send` pertence ao ledger/replay atual. `runner.execute` executa comandos em domínio descartável, inclusive probes de avaliação: **não é a chamada ao provedor**. Portanto não inserir requisito D1 indiscriminado nesses pontos.

### C03-A — Intenção explícita e decisão verificada

Definir entrada de execução real acima de reserva/ledger/adapter, com três intenções distintas:

| Intenção | O que exige | Relação com D1 |
|---|---|---|
| Replay/simulação offline | Entradas e recibos de replay válidos; sem chamada externa | Não exige D1 nem habilita provider |
| Smoke pareado D0/seed | Tarefa/conjunto smoke verificados, braços comparáveis, contenção, medição, modelo/configuração e recursos autorizados | Não exige corpus 32/32 ou quatro eventos reais; não é campanha D1 |
| Campanha D1 | Corpus global qualificado, quatro eventos requeridos executados/reconciliados e demais condições da campanha | Todos os requisitos consumidos pelo ponto efetivo de dispatch |

A escolha deve vincular IDs de tarefa, origem do dataset e configuração ao manifesto, não somente uma string de modo. D1 não vira smoke por mudar seu rótulo. Smoke pode usar tarefa cuja origem é o corpus, desde que declarado como smoke de desenvolvimento com protocolo próprio; seu resultado não passa a pontuar D1 por mudança posterior de etiqueta.

Produzir uma decisão verificável vinculada a hashes do manifesto, corpus/oracles aplicáveis, eventos, ferramentas, configuração/modelo/medição e controles. Registrar razões de recusa por dimensão. Nomes de tipos/arquivos são escolha do Implementador; um `ready=true` ou `admitted=32` fornecido pelo chamador não é autoridade.

**Aceite:** contraprovas para flags forjadas, dataset desconhecido, evidência ausente/trocada e mudança de intenção. Com provider fake, replay não chama rede; smoke válido não é bloqueado por falta de D1; campanha incompleta nunca alcança adapter. Testar o fluxo consumidor, além de unidades do verificador.

### C03-B — Snapshot de evidências e primeiro evento real

Reusar a materialização/captura existente. O inventário incremental de `crates/xrai-eval/harness/incremental.py` demonstra continuidade e comparação de fontes em seu recorte; não prova semântica nem substitui os novos eventos reais por si só.

Preparar os quatro descritores conforme C03 da revisão: uma tarefa natural e independente por família, hashes A/B/configuração, consultas, efeitos esperados e oracle. Implementar primeiro uma sessão experimental que mantenha o índice/processo entre A e B; comparar snapshot completo e respostas em B com rebuild independente. Registrar unknown/cobertura/diagnóstico, identidade de sessão, operações e encerramento. Rebuild conservador dentro da sessão é permitido como estratégia inicial de atualização, desde que declarado; não alegar ganho incremental/cache por manter o PID.

A recomposição custosa das provas pode ocorrer uma vez por snapshot imutável de campanha. Mudança de fonte/evidência/configuração invalida a decisão. Não verificar caminhos mutáveis uma vez e depois consumir bytes diferentes. Um hash em JSON não torna o diretório imutável: capturar/copiar ou conferir as entradas efetivamente usadas, com identidade de conteúdo.

**Aceite:** um caso real com A aquecido → evento → B no mesmo índice e B reconstruído em outra sessão; saída completa recomputada, controle de resultado obsoleto e contraprovas de cold B/reinício/troca de caso/flags sem provas. Os outros três podem continuar preparados, explicitamente não executados; campanha continua bloqueada até quatro comprovados.

### C03-C — Consumo por dispatch e retries

Antes de cada chamada real, incluindo retry, conferir intenção/plano e decisão vinculada, autorização vigente, contenção exigida, reserva de orçamento e ausência de incidente que tenha invalidado a sessão. Adquirir a reserva atomicamente antes de chamar o adapter. Alteração de plano/configuração/evidência exige novo preflight; não repetir leitura pesada de todo o corpus por chamada se o snapshot é de fato fixo.

O adapter não pode ser invocado por uma rota pública que contorne a entrada verificada. A autorização/teto pertencem à sessão autorizada; o preflight não os inventa. Preservar a distinção entre custo reservado, confirmado, estimado e desconhecido, inclusive falha após envio. Cancelamento/timeout não demonstram que nenhuma cobrança ocorreu.

**Aceite:** teste de integração com adapter espião/fake que conta chamadas; recusa resulta em zero chamadas. Cobrir retry sem saldo, corrida de reservas, configuração alterada, recibo substituído, cancelamento e resposta/usage ausentes. Implementação offline pode ser concluída sem credencial ou gasto. Provedor/modelo/preços reais só entram após escolha e verificação pertinentes, sem valores fictícios neste plano.

## 3. TS/JS: primeira fatia P2 com limites explícitos

O código atual está em `crates/xrai-eval/src/semantics_spike.rs`, com edição/módulos/lookup Rust; `semantics_spike/mod.rs` não é seu caminho. Reutilizar os envelopes/conceitos `Evidence`, `Resolution`, `Scope`, `Reference`, spans em bytes e IDs por snapshot. As regras de `::`, visibilidade Rust e edição não são resolução universal. `parsing_spike::grammar` e `worker_spike::producer` já cobrem os dialetos; isso não implica semântica pronta. Preservar formatos/recibos Rust e introduzir perfil experimental explícito para TS/JS.

### TSJS-A — Relações ESM locais por caminho exato

Fixar o perfil inicial **`captured-relative-exact-v1`**, experimental: imports relativos com caminho e extensão explícitos identificam exatamente uma fonte capturada dentro da raiz. Resolver por mapa de fontes do snapshot; nenhuma descoberta no host, tentativa por basename, substituição `.js`→`.ts`, fallback `index.*`, alias tsconfig, package exports ou resolução Node/bundler. É um recorte declarado, não conformidade geral com o compilador.

Entrada identifica dialeto por arquivo, fontes/configuração e perfil. Módulos são declarados como ESM pelo perfil; arquivo ambíguo não vira módulo por suposição. Suporte inicial: funções declaradas em módulo, named imports com alias, named exports de função e lista de exportação local. Relação de uso de função importada precisa evidenciar ocorrência → import → export → declaração. AST Tree-sitter permanece interna ao adapter. Identidade lexical de declaração não promete alvo de chamada em qualquer execução: reatribuição do binding exportado ou interferência não analisada impede promover alvo chamável; explicitar essa distinção já em TSJS-A.

Default/namespace imports, reexports externos ao módulo, `export *`, CommonJS, import dinâmico e pacotes externos ficam explicitamente fora. Em TS, construções de tipos/namespaces/merging não implementadas não entram no namespace de valores; não ignorar sintaxe que possa alterar o ambiente e então promover alvo externo. Bare specifier não vira fato `external` apenas pelo texto. Ciclos/limites de trabalho podem produzir unknown, sem exigir SCC completo nesta fatia.

O TypeScript possui regras de resolução que incluem substituição de extensões; essa é uma razão para declarar a exclusão, não para aplicar a regra Rust ou inventar fallback. Antes de congelar labels de cada capacidade, registrar a referência oficial e configuração pertinentes. [Referência oficial de módulos TypeScript](https://www.typescriptlang.org/docs/handbook/modules/reference.html), consultada em 12/10/2026.

**Aceite:** matrizes JS e TS rotuladas antes do resolver, cadeia com alias, homônimos em módulos distintos, export ausente, arquivo ausente, path inválido/fora da raiz, binding duplicado e parse parcial. Evidências incluem todos os arquivos da cadeia. Uma relação útil em fonte real congelada compatível com o perfil, com denominador e perdas; não forçar React ao perfil se ele não couber. JSX/TSX semânticos não são requisito desse primeiro incremento.

### TSJS-B — Escopos e bindings sem confundir referência e chamada

Parâmetros simples e `const` simples em função/bloco; escopo e posição explícitos. Identificar a declaração do parâmetro não prova qual função seria chamada através dele. Alias imutável só recebe alvo chamável quando inicialização, escopo e ausência de interferência estiverem demonstrados; de outro modo, manter referência ao binding e chamada unknown.

Não copiar visibilidade temporal do Rust: um binding local não pode desaparecer antes da declaração e revelar um import externo. Tratar acesso antes de inicialização como desconhecido/diagnóstico no recorte até haver regra comprovada. A especificação cria bindings lexicais antes da avaliação da inicialização, mas restringe seu acesso nesse intervalo. [ECMAScript 2024, declarações lexicais](https://tc39.es/ecma262/2024/multipage/ecmascript-language-statements-and-declarations.html#sec-let-and-const-declarations).

`let`, `var`, destructuring, closures capturadas, `eval` e demais formas não tratadas exigem lacuna no alcance pertinente quando puderem interferir. Não basta pular o nó. Se o alcance não puder ser limitado com precisão, conservar unknown em bloco/função mais amplo.

**Aceite:** parâmetro sombreando import, bloco irmão, uso anterior à declaração, autoinicialização, alias não demonstrado, duplicidade e binding introduzido por forma não suportada. Separar precisão de referências e chamadas. Aplicar critérios P2 existentes, incluindo pelo menos 80% no subconjunto previamente rotulado resolvível e zero promoção indevida nas contraprovas; não mudar rótulos após resultados para atingir meta.

### TSJS-C — Sessão experimental ligada a C03

Operações conceituais: abrir A, consultar, atualizar com revisão esperada para B, consultar e fechar. API interna e layout são escolhas do Implementador. O `Index::update` Rust já reconstrói e publica após sucesso; reaproveitar a disciplina de ownership, não suas regras de linguagem. Na primeira versão TS/JS, rebuild conservador completo é permitido. Falha de update preserva A explicitamente; não marcar B disponível com dados antigos.

Fingerprints abrangem fontes/paths, configuração, dialetos, gramáticas/queries/produtor, versão do resolver e perfil. Primeiro evento sugerido: export antes ausente passa a existir, alterando consulta negativa aquecida; alternativa é introduzir shadowing. A escolha final precisa da tarefa real independente e do descritor, sem gerar tarefa apenas para acomodar o teste.

Comparar B integral com rebuild independente: estados, alvos, evidências, dependências, cobertura/unknown e diagnóstico. Contraprovas incluem B sem update, revisão esperada incorreta, processo reiniciado, troca de fonte/configuração/produtor e remoção de divergências na normalização. Fixture sintética é regressão técnica; só fonte/caso real congelado e recibo C03 correspondente cumprem a quota do corpus.

## 4. S01: registro que permita decidir a próxima execução

Usar o [snapshot dos alertas](relatorios/logs/revisao-L5-C02/dependencias.json) como inventário datado, não como prova de que cada falha é alcançável. Não repetir a classificação já feita: os 55 apontavam para o setup congelado Go. Nesta rodada não houve nova consulta de alertas nem análise por advisory.

Produzir um registro por alerta, com: ID/GHSA e revisão/data da fonte oficial, package/versão resolvida e cadeia de dependência, fase afetada (download/build/probe), entrada exposta, evidência de alcance ou limite da investigação, controles efetivamente presentes, decisão e motivo, hashes do setup e responsável. Resultado desconhecido deve continuar desconhecido. Ausência de rede não prova ausência de exposição a arquivos, subprocessos ou entradas locais.

Os nove críticos do snapshot se distribuem em sete `x/crypto`, um gRPC e um go-git; isso orienta leitura inicial, sem dispensar os outros 46. Se agrupar, enumerar os IDs e a evidência comum, mantendo decisão por alerta. Bloqueio de execução afetada não bloqueia curadoria data-only, C03 offline ou frontend TS/JS.

**Aceite:** cada uma das 55 entradas tem decisão fundamentada ou pendência explícita que impede a execução afetada; nenhuma dispensa por etiqueta “teste”. Upgrade necessário gera variante de setup e revalidação dos dois lados, preservando a prova original. Na alteração do runner Go, guardar inventários imutáveis entre fases e separar caches/scratch permitidos. Não fechar alertas remotos apenas para limpar o painel.

## 5. Integração, aceite e próxima revisão

O Implementador pode escolher layout interno, nomes de tipos e organização de testes dentro destes limites. Extração de tipos P2 comuns só quando houver consumidor real; não criar framework genérico nem reescrever R3 para acomodar placeholders. Biblioteca própria maior permanece permitida pelo ADR024 quando a perda concreta justificar.

Relatório do próximo incremento deve informar: fatia implementada, operação que passou a funcionar, arquivos/interfaces, contraprovas e comando/resultados, limites ainda desconhecidos, estado dos eventos por família e gate realmente consumido. Manter oito tarefas elegíveis/0 admitidas até nova prova; não editar contadores para refletir este planejamento. Revalidar apenas o que a mudança afetar, além dos checks obrigatórios; não repetir todos os probes aceitos sem motivo.

Avanço até 1.0 continua: M0/G0 → M1-A/G1 → M1-B/G2 → V1-01…06. Os 41 cartões mantêm 9 concluídos, 7 em andamento e 25 não iniciados. Este checkpoint de planejamento não representou progresso de código; entregas posteriores e seus limites estão na revisão L5-C03. [Verificação documental e recorte dos agentes](relatorios/logs/proxima-execucao/checks.json).
