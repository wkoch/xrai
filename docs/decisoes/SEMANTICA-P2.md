# IR semântica e primeira fatia Rust — ADR 025

12/10/2026. Decisão do Arquiteto para M0-11/P2, detalhando ADRs 005/018/024. Entrada: [contrato de domínio v2](../contracts/m1.md), [recorte P2](../PROVA-DE-DIFERENCIACAO.md) e [revisão L3](../relatorios/REVISAO-L3.md). Especificação de experimento; não anuncia resolver implementado nem API estável.

## 1. Objetivo e fronteira

Entregar relações explicáveis que a busca textual não consegue distinguir: qual declaração uma referência usa, qual import/reexport a liga ao destino, qual configuração a ativa e quais mudanças invalidam a conclusão. Começar com uma fatia Rust completa, depois TS/JS, Python e Go. Um backend que apenas produz árvore/contagem de queries não atende esse objetivo.

Manter módulos experimentais em `xrai-eval`; o Implementador escolhe arquivos internos, sem criar crates vazias. Só promover tipos para `xrai-core` em M1-01 e módulos de produção para `xrai-index` em M1-23, após seus gates. Bytes capturados entram pelo contrato existente; oracles ficam fora da IR e do resolver. P2 pode iniciar com execução direta do parser para encurtar o ciclo de desenvolvimento; a prova do worker e sua integração continuam obrigações separadas.

## 2. Representação mínima, sem AST público

Os nomes da tabela são conceitos internos a concretizar pelo Implementador; não novos campos obrigatórios do schema público. Reutilizar IDs, spans, fingerprints e estados de `m1.md`. Se algum resultado não puder ser representado, registrar diferença de contrato antes de mudar o schema; não acrescentar um quinto estado informal.

| Conceito | Conteúdo necessário | Invariante |
|---|---|---|
| Unidade de análise | Snapshot, file version, bytes/hash, dialect/edition, produtor e configuração | Sempre uma versão de fonte; parser não reabre o path |
| Escopo | ID local, tipo, owner, pai lexical e intervalo aplicável | Escopo lexical não é automaticamente módulo, pacote ou intervalo de validade de um binding |
| Declaração | Nome original, categoria, namespace de linguagem, escopo/owner, span e visibilidade | Nome não identifica símbolo; homônimos, impls e construtores preservados |
| Binding | Nome introduzido, declaração/import associado, escopo e regra de visibilidade temporal | `let` e item de módulo não herdam a mesma regra de ordem textual |
| Referência | Ocorrência/span, papel (tipo/valor/import/callsite), escopo e path segmentado | Callsite sintático não comprova `calls` resolvido |
| Módulo/import/export | Origem, destino textual, alias, visibilidade, condição e arestas de lookup | Representar a cadeia que sustentou a resolução, inclusive reexports |
| Condição | Predicado original, entradas de configuração e resultado known true/false ou not_evaluated | Ausência de configuração fornecida não implica false |
| Resolução | Estado do contrato, alvo/candidatos permitidos, motivo e evidência | Mesmo um candidato único não vira resolved sem prova suficiente |
| Derivação | Chaves positivas/negativas, regras e versões usadas | Reuso de AST não autoriza reuso de resolução |
| Lacuna | Região/capability afetada, motivo e dependências que ela pode alterar | Lacuna no escopo de lookup acompanha resultado positivo e vazio |

Ownership Rust: um snapshot possui blobs imutáveis; fatos usam IDs/spans. Arenas/índices tipados são opção interna para escopos e declarações; IDs locais não escapam sem qualificação pela unidade/snapshot. Árvores e nós Tree-sitter ficam dentro do adapter. Evitar cópia de fonte por aresta e referências emprestadas que sobrevivam ao snapshot. Ordenação canônica torna comparação determinística; a ordem de hash map/worker não define resultado público.

Separar namespaces com regras por linguagem, sem impor os de Rust aos outros frontends. O contexto da referência determina o namespace consultado; um import pode introduzir nomes em mais de um. Fundamento: [Rust Reference — namespaces](https://doc.rust-lang.org/reference/names/namespaces.html). Implementar somente os namespaces necessários ao recorte e registrar os demais como capacidade ausente, sem fundir macro/tipo/valor por string.

## 3. Algoritmo de resolução delimitado

1. Validar manifesto, configuração e identidade das fontes. Registrar entradas ausentes e arquivos fora do recorte, sem executar Cargo, builds ou código do projeto.
2. Extrair escopos/declarações/referências/imports/condições e lacunas. Validar spans; sintaxe com erro não produz automaticamente semântica completa. Nós íntegros fora da região danificada podem ser úteis se as premissas de lookup também estiverem íntegras.
3. Construir módulos e ambiente de nomes; resolver imports/reexports por componentes fortemente conexos ou outra iteração determinística equivalente. Ciclos convergem sobre conjunto finito de fatos; limitar trabalho e retornar diagnóstico quando excedido, nunca promover o estado intermediário a completo.
4. Resolver referências por namespace, escopo, visibilidade, condições e regra da linguagem. Registrar os caminhos consultados, inclusive buscas sem resultado. Lookup que depende de macro/arquivo/configuração não analisada conserva a lacuna.
5. Produzir relações distintas para import, referência e chamada; converter para resolved somente quando existe alvo único demonstrado **e** as alternativas pertinentes foram examinadas. Candidato não é afirmação de completude da lista.
6. Validar referências cruzadas de snapshot/configuração/produtor e publicar o resultado experimental com cobertura. Falha de uma unidade não pode aparecer como ausência comprovada de relação.

Motivos internos mínimos: módulo/arquivo ausente, pacote externo não capturado, configuração não avaliada, edição não suportada, parse parcial, lookup ambíguo, macro não expandida, receptor/tipo não demonstrado, resolução de trait não suportada e limite de trabalho. Projetar esses motivos nos diagnósticos/capabilities do contrato, sem inventar alvos locais para dependências externas. `external` exige identidade verificável; reconhecer apenas o texto de um path não basta.

## 4. Rust: recorte contratado em etapas

Primeira fatia declara editions 2021 e 2024 em fixtures fixadas; outras editions retornam limitação até teste próprio. Isso delimita o experimento, sem mudar as quatro famílias do produto. A edição deve vir do manifesto/configuração capturados; nunca do toolchain do host por suposição. Ao implementar, registrar a versão da referência de linguagem usada junto ao toolchain de oracle; links oficiais consultados nesta revisão não substituem esse pin.

| Etapa | Entrega | Limite que deve continuar visível |
|---|---|---|
| R1 — módulos e nomes | Módulos inline/em arquivos convencionais; crate/self/super; funções, tipos e escopos locais; chamada direta de função conhecida | Caminho de módulo por atributo, include ou árvore gerada fora do recorte vira lacuna; não tentar executar gerador |
| R2 — imports e visibilidade | `use`/`pub use`, alias, grupos, reexports, visibilidade privada/pub/pub(crate); ciclos finitos | Globs, visibilidade restrita mais ampla e regras não implementadas bloqueiam conclusão dependente; não procurar por basename global |
| R3 — bindings e configuração | Parâmetros, bindings locais e shadowing; `cfg` conhecido; dependências negativas | Destructuring/closures/patterns só com regra testada; forms fora do recorte não são ignoradas se puderem introduzir binding |
| R4 — método inerente demonstrável | Tipo nominal local concreto e método inerente conforme regras de lookup pertinentes | Sem inferência ampla, dispatch dinâmico, Deref arbitrário ou resolução genérica de traits; lacunas impedem alvo indevidamente único |

Separar `cfg` do Rust, que é avaliado com configuração definida, do estado de conhecimento do xrai. No xrai, uma entrada não fornecida é not_evaluated. Só tratar feature/custom cfg ausente como false quando o manifesto declarar conjunto fechado pertinente; herdar target/features do host é incorreto. `cfg_attr` não suportado que possa mudar módulos/declarações precisa propagar lacuna. Regras reais de predicados: [Rust Reference — conditional compilation](https://doc.rust-lang.org/reference/conditional-compilation.html).

Para R4, saber o tipo e encontrar um método inerente homônimo ainda pode ser insuficiente. Rust considera uma sequência de receptores e métodos visíveis, com empréstimos/dereferências; um trait pode ser selecionado antes de um método inerente em outro receptor. [Rust Reference — method calls](https://doc.rust-lang.org/reference/expressions/method-call-expr.html). O experimento deve provar a escolha no recorte suportado ou emitir candidate/unknown. Chamada qualificada também precisa validar tipo, owner e configuração; não contornar ambiguidade pelo texto do método.

Macros não expandidas podem introduzir bindings/métodos/módulos. Registrar alcance conservador da lacuna: quando não se consegue delimitá-la, invalidar a unidade ou ambiente de nomes consumidor pertinente. Não reduzir a lacuna ao span da macro e afirmar completude ao redor sem justificativa. Arquivo com sintaxe válida também pode ter ambiente semântico incompleto.

## 5. Dependências negativas e atualização

Representar lookup como uma consulta versionada: escopo/módulo/pacote, namespace, nome/path, configuração, regras e resultado. Uma busca vazia depende da versão do ambiente consultado; não depende de um símbolo inexistente. A primeira implementação pode invalidar o pacote inteiro e seus consumidores. Granularidade maior é otimização posterior, não condição para começar.

| Mudança A→B | Invalidação mínima conservadora |
|---|---|
| Criar export ou módulo antes ausente | Lookups positivos/negativos do ambiente, imports/reexports e consumidores transitivos |
| Inserir binding que sombreia outro | Referências no alcance do binding; se alcance incerto, unidade completa |
| Remover/renomear arquivo | Grafo de módulos e todos os consumidores, inclusive consultas sem alvo anterior |
| Trocar target/features/manifest | Condições e resultados semânticos afetados; invalidar pacote se não houver mapa fino |
| Trocar gramática/query/resolver | Derivações com fingerprint antigo; sem reuso semântico por hash de fonte isolado |
| Mudar path/pacote sem mudar bytes | Reavaliar lookup relativo, visibilidade e configuração; cache sintático pode ser reutilizado se compatível |

Capturar versões das dependências e comparar antes de publicar. Trabalho calculado para A nunca se anexa a B só porque terminou depois. Durante atualização servir A explicitamente ou aguardar B; não misturar. Base/head são snapshots independentes, com removed/added do avaliador; não exigir histórico Git.

Oráculo incremental: normalizar os resultados de B incremental e rebuild de B pelos mesmos IDs determinísticos de unidade/declaração/ocorrência, ou por mapeamento explícito dessas identidades quando a implementação exigir; comparar estados, alvos, evidências, configuração, cobertura e lacunas. Não remover esses campos da comparação para esconder divergência. Spans/IDs de A não têm estabilidade prometida em B.

## 6. Matriz de aceite da primeira fatia

O Implementador escreve fixtures e rótulos independentes da saída do resolver antes de ajustar regras. Não usar H1. Todo grupo abaixo precisa de positivo, negativo/ambíguo e mudança incremental quando aplicável; contagem vem dos casos reais preparados, não de duplicação artificial.

| Grupo | Pergunta que o teste precisa decidir |
|---|---|
| Namespaces e homônimos | Tipo/valor/macro iguais colidem indevidamente? |
| Escopos | Binding local, parâmetro e declaração de item obedecem às regras de visibilidade e ordem? |
| Imports/reexports | Alias, grupo, cadeia e ciclo levam à definição correta sem inventar alvo? |
| Módulos/visibilidade | Dois arquivos homônimos em pacotes diferentes, privado e pub(crate) preservam acesso? |
| Configuração | True/false/not_evaluated e troca de features alteram conclusão/cobertura corretamente? |
| Método | Receptor concreto, método de outro tipo e interferência de trait não são confundidos? |
| Incompletude | Macro, módulo ausente, parse error e dependência externa conservam unknown/lacuna? |
| Derivação | Export criado, shadowing novo, rename, query nova e alteração de config equivalem a rebuild? |
| Fonte | CRLF, Unicode, arquivo vazio, spans e mistura de revisões são tratados pelo contrato? |

Aceite M0-11 permanece: pelo menos 80% dos casos **pré-rotulados como resolvíveis no recorte** corretos, nenhuma promoção indevida a fato nas fixtures contratadas; precisão, recall e cobertura nos casos reais em separado, com denominadores. Não reclassificar casos fracassados como fora do recorte após observar resultado. Ampliar o conjunto com contraprovas e versionar mudanças de escopo antes da próxima rodada.

Primeiro relatório entrega R1/R2 Rust, matriz e perdas; fechamento do cartão exige R3/R4 e recortes TS/JS, Python e Go do protocolo. Cada família usa suas próprias regras sobre a IR comum. Lacuna que realmente exigir biblioteca maior abre dossiê do ADR 024; não bloquear implementação por tamanho nem financiar substituição de parser sem causa.

## 7. Integração posterior com P3

P3 recebe fatos/candidatos/unknowns junto com revisão, evidência e coverage; usa isso para sugerir obrigações e expandir. Candidato serve como caminho de investigação, não como afirmação de causalidade. Comparar controle lexical/estrutural e P2 com os mesmos blobs/configuração. A avaliação de sucesso de tarefa continua M0-12; acerto de relações não é sucesso de agente.

## Concretização TS/JS de L5-02

O [roteiro da próxima execução](../L5-PROXIMA-EXECUCAO.md) fixa `captured-relative-exact-v1` como perfil experimental inicial, com ESM local, evidências por ocorrência, bindings e sessão A→B em três incrementos. Preservar semântica/recibos Rust; gramática compartilhada não implica resolução compartilhada. Regras de módulo e shadowing têm limites próprios, labels prévios e fontes oficiais vinculadas no roteiro. Esta decisão detalha P2, sem promover o perfil a API pública nem concluir a implementação.
