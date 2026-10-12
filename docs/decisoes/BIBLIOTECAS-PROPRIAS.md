# Bibliotecas próprias e evolução do motor — ADR 024

12/10/2026. Diretriz do usuário: complexidade não impede construir bibliotecas do porte de Tree-sitter ou maiores quando necessárias ao objetivo do xrai. O Arquiteto define escopo/aceite; o Implementador escreve código e mede. Esta decisão detalha ADRs 002/005/007/018; não muda gates, linguagens ou plataformas.

## 1. Política de investimento

Escolher componentes pelo sucesso em tarefas reais, integridade e custo total. Reutilização é opção inicial, não limite de ambição. Biblioteca própria, fork mantido ou frontend incorporado podem ser a melhor solução. Nenhuma opção é rejeitada apenas por exigir muito código. Também não começar uma reescrita sem identificar a capacidade que ela entrega.

Tree-sitter permanece o parser inicial porque o spike já prova os dialetos necessários nos hosts executados. Não há neste levantamento evidência de que substituí-lo resolva uma perda observada. A falta de resolução de tipos/imports, isoladamente, é trabalho semântico; não prova defeito do parser. A substituição pode ocorrer por linguagem, preservando o restante do pipeline.

O critério anterior de esperar um ganho competitivo completo antes de investigar parser próprio fica refinado: **uma lacuna reproduzível ligada a tarefa-alvo basta para abrir um experimento delimitado de viabilidade**. Não exigir que uma implementação inexistente já vença G1. Produção ampla continua condicionada à prova adequada do componente e aos gates do produto. Complexidade do experimento deve ser proporcional à pergunta que precisa responder; o plano pode expandi-lo quando os resultados justificarem.

## 2. Fronteiras do desenho Rust

Manter o workspace atual. Os nomes abaixo descrevem módulos/responsabilidades; criar crates novas somente quando isolamento de dependências, ciclo de build, testes ou uso independente justificar. Não criar interfaces vazias para preencher arquitetura.

| Responsabilidade | Contrato conceitual | Dono inicial |
|---|---|---|
| Captura | Entrada nativa → bytes imutáveis, hash, diagnóstico de inventário | xrai-index; spike em xrai-eval |
| Frontend sintático | Bytes + dialect + producer fingerprint → declarações/escopos/referências/spans + lacunas | xrai-index; workers isolados |
| Resolução | Fatos sintáticos + configuração + dependências → fatos/candidatos/unknowns com evidência | xrai-index, módulos por linguagem |
| Incremental | Chaves de derivação e dependências positivas/negativas → conjunto afetado | xrai-index |
| Domínio | IDs tipados, spans validados, revisão, cobertura, erros, capabilities | xrai-core |
| Consulta/seleção | Snapshot fixado + pergunta + orçamento → itens/obrigações/omissões/expansão | xrai-query |
| Interfaces | CLI/MCP → mesma API de domínio, sem regras semânticas duplicadas | xrai |
| Avaliação | Oracles, comparadores, falhas, custo, ablations e promoção | xrai-eval + eval |

AST/CST e handles do parser ficam privados ao frontend; schema público e persistência não contêm IDs de nós Tree-sitter. O domínio usa estruturas próprias com proveniência. Parser novo pode produzir sintaxe distinta, mas precisa preservar o contrato de evidência. Métricas e capacidades identificam produtor/versão; mudança de parser/query invalida derivações afetadas. Cache nunca depende só do hash da fonte: incluir configuração, linguagem e fingerprint do produtor.

Ownership: snapshot possui bytes, fatos apontam IDs/spans; referências emprestadas ficam dentro da operação, sem atravessar IPC ou sobreviver ao snapshot. Usar compartilhamento imutável quando necessário; evitar clones de fonte por fato e mutex global como modelo de concorrência. Erros de domínio tipados, cancelamento e limites explícitos. Novos IDs internos não significam estabilidade universal entre renames/versões.

Preservar Rust seguro no workspace. Se uma biblioteca própria exigir unsafe/FFI, o Implementador registra a operação sem wrapper seguro, contrato de memória/lifetime/thread-safety, alternativas e plano de fuzz/sanitizers/Miri onde aplicáveis. O Arquiteto decide uma fronteira mínima e auditável; não retirar forbid globalmente. FFI já encapsulado numa dependência não é evidência de que todo o programa seja memory-safe.

## 3. Programa de trabalho próprio

| Pacote | Problema/saída | Primeiro aceite | Dependência/momento |
|---|---|---|---|
| B01 — Evidência | ID/revisão/hash/span, estado de fato e derivação verificáveis | Rejeitar span inválido, configuração errada e mistura base/head | Já contratado M1-01/03; protótipos reutilizam contrato documental |
| B02 — Escopos e bindings | Regras por linguagem e representação comum de resolução | Homônimos/shadowing/imports/configuração; nenhum fato sem prova | M0-11/P2; produção em M1-23 após G1 |
| B03 — Dependências incrementais | Registrar dependência presente e ausente, configuração e produtor | Criar export antes ausente/alterar cfg invalida; resultado igual a rebuild | P2 experimental; M1-12 em produção |
| B04 — Seleção de contexto | Obrigações, representações, dedup e expansão fixada | Fonte exata, cap serializado, omissão explícita e base/head | M0-09/P3; M1-16 após G1 |
| B05 — Parser/frontend próprio | Corrigir lacuna sintática/autonomia/recursos comprovada | Experimento diferencial do recorte, erros recuperáveis e custo medido | Condicional ao dossiê abaixo; sem criar crate agora |
| B06 — Semântica profunda | Tipos, generics, dispatch ou macros declarativas em recorte escolhido | Alvo demonstrado ou unknown; configurações/dependências explícitas | M2, priorizado por perdas de P2/G2 |
| B07 — Contratos entre linguagens | Identidade de rotas/esquemas/configuração e consumidores | Duas linguagens, positivo/negativo/homônimos e invalidação | M4, após semântica suficiente |
| B08 — Slicing/memória | Dependências causais e recibos atribuídos por revisão | Ablation em tarefas novas; retenção/expiração sem fonte misturada | M5; não antecipar promessa de omitir testes |

B01–B08 organizam investimento; não duplicam tarefas M0/M1 nem autorizam toda a lista como execução imediata. Uma necessidade concreta pode motivar revisão da ordem. Estimar esforço após o primeiro recorte executado, separando engenharia, manutenção, recursos e operação.

## 4. Roteiro de decisão para B05/B06

1. **Dossiê:** tarefa real afetada, menor reprodução, linguagem/versão/configuração, falha do componente vigente, magnitude observada e capacidade necessária. Classificar parsing, extração, resolução, invalidação ou seleção; não atribuir todo erro ao parser.
2. **Alternativas:** medir configuração/query, patch upstream/fork, frontend incorporado e implementação própria no mesmo caso. Não é necessário desenvolver todas: documentar restrição objetiva que elimina opção e esforço estimado. Registrar licença/proveniência e fabricação offline nos dois alvos.
3. **Experimento vertical:** uma capacidade e corpus de desenvolvimento congelado; entrada/saída do adapter, diagnósticos, limites, recuperação, fonte exata e comparação diferencial. Reservar casos inéditos antes de ajustar. Critérios numéricos específicos são definidos antes dos resultados, com base no defeito; não usar o holdout competitivo H1 para depurar.
4. **Aceite do componente:** sem regressão crítica de evidência; cobertura/perdas por construção; fuzz de entrada arbitrária e edição incremental versus parse completo; recursos/latência; estabilidade de serialização e descarte de cache. Divergência com compilador é investigada, não automaticamente tratada como erro dele ou verdade do xrai.
5. **Migração limitada:** dual-run só no avaliador, switch por capability/dialect com fingerprints novos, rebuild versionado e rollback para produtor anterior. Não misturar fatos dos dois produtores como se fossem uma prova única. Comparar tarefas completas e custo adicional.
6. **Decisão:** incorporar, manter experimental, ampliar um recorte ou encerrar abordagem com evidências. Manter registro de manutenção/compatibilidade futura. G1/G2 continuam decidindo o produto, não o número de linhas da biblioteca.

Se o experimento mostrar necessidade de um parser geral próprio, decompor em especificação/versionamento da gramática → lexer Unicode/bytes → algoritmo de parsing/ambiguidade → árvore lossless e erros → edição/reuso incremental → consultas/extração → geração e empacotamento → fuzz/diferenciais → migração por dialect. Escolher algoritmo após requisitos de gramática/recuperação; não fixar LR/GLR/PEG por preferência abstrata. A primeira entrega é uma linguagem/recorte completo e verificável; as demais entram com tarefas e testes próprios.

Para type checker/resolver mais amplo: primeiro grafo de módulos/configuração, depois bindings, representação de tipos necessária, restrições/inferência do recorte, seleção de membros/dispatch e explicação do resultado. Não executar proc macros/build scripts/imports do projeto para preencher lacunas do indexador. Importar um artefato semântico produzido externamente exige regime explícito, proveniência e hash das entradas; permanece opcional, sem transformar runtime externo em requisito básico.

## 5. Próxima decisão e comunicação

Agora: executar P2/P3 e registrar perdas por camada. Não há pedido de aprovação por biblioteca rotineira dentro dos contratos. Mudança de arquitetura ou capacidade exige relatório local com dossiê, recomendação e cartões; continuar tarefas independentes. O usuário receberá uma decisão concreta, não uma pergunta genérica sobre permitir complexidade.

Esta política substitui qualquer interpretação de que tamanho/complexidade, sozinho, proibiria desenvolvimento próprio. Não representa autorização de despesa, mudança de licença do produto, ampliação de plataformas ou execução de código nesta conversa de arquitetura.
