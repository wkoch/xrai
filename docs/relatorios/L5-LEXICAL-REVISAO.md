# L5-01 — segunda leitura dos rótulos lexicais congelados

Os 16 rótulos receberam segunda leitura **depois de existirem resultados**. Os 12 caminhos/anchors positivos correspondem aos bytes capturados e as quatro negativas têm seu identificador ausente nas respectivas capturas. A leitura de pertinência textual encontrou dez positivos sustentados, uma ressalva de formulação em RS-03 e uma cláusula não sustentada em GO-02. Os originais e as métricas foram preservados.

O revisor `implementer/d01_commitment` não escreveu as queries/rótulos congelados, o benchmark nem o recuperador lexical. Integra a mesma equipe de implementação e escreveu o adapter que usa a API lexical. A independência é limitada à autoria desses ativos; os resultados e o relatório L5-LEXICAL estavam visíveis. Esta revisão não foi cega, externa, prospectiva ou anterior à medição e não transforma o conjunto em holdout independente. O marker original `independent_second_reader: pending` permanece no arquivo congelado como histórico; o registro desta leitura fica separado.

## Evidência e alcance

[`review-independent.json`](logs/L5-C04/lexical/review-independent.json) registra hashes de queries, labels, manifesto, protocolo, matriz, freeze e resultados existentes, mais os 82 arquivos capturados (819.020 bytes). Foram lidos e conferidos bytes/SHA de cada arquivo, limites/tipos e fronteiras UTF-8 de cada anchor e sua igualdade com o hash congelado. Para os positivos, a leitura manual usou declaração, corpo e contexto pertinente; o JSON registra witnesses com texto, offsets, linha e SHA. Para as negativas, a checagem percorreu corpo integral e caminho de todos os arquivos da família, inclusive casefold. A closure permaneceu idêntica antes/depois.

São verificações próprias de bytes e leitura de fonte como dados: nenhuma execução/importação upstream, build nativo, rede, provider ou rerun de ranking. A relação textual abaixo é julgamento de pertinência do revisor; não é prova de resolução semântica, comportamento em runtime, acerto de agente ou vantagem de um método.

| Query | Anchor/caminho | Leitura de pertinência e limite |
|---|---|---|
| RS-01 | `pub fn shuffle`, `crates/stdx/src/rand.rs:6` | Sustentada: slice mutável, callback `rand_index` e swap aparecem no corpo. Nome exato já vem na query. |
| RS-02 | `pub fn enter`, `crates/stdx/src/panic_context.rs:18` | Sustentada: `enter` instala hook uma vez, empilha frame e retorna guard com Drop que remove frame. Associação textual do arquivo; lifetimes não executados. |
| RS-03 | `pub fn streaming_output`, `crates/stdx/src/process.rs:13` | Caminho/anchor pertinentes com ressalva: função recebe stdout/stderr e lê até EOF. `child.wait()` está em `spawn_with_streaming_output`, linha75. “Until the child exits” mistura o lifetime dos pipes com a espera do filho e não descreve literalmente o contrato do anchor. |
| JS-01 | `function resolveDispatcher`, `packages/react/src/ReactHooks.js:24` | Sustentada: nome e mensagem Invalid hook call presentes; em DEV usa console.error e comenta que não lança erro próprio. Error na query é pertinente como diagnóstico; não se prova configuração Flow/build/runtime. |
| JS-02 | `export function cloneElement`, `packages/react/src/ReactElement.js:470` | Sustentada: overrides de ref/key e transferência de children no corpo. Anchor de declaração não exige por si só cobertura de todos os branches na entrega. |
| JS-03 | `function lazyInitializer`, `packages/react/src/ReactLazy.js:51` | Sustentada: transitions Pending/Resolved/Rejected e payload no corpo. Não comprova comportamento assíncrono real. |
| PY-01 | `def roc_auc_score`, `sklearn/metrics/_ranking.py:420` | Sustentada: recebe scores/max_fpr, documenta e trata restrição multiclass, delegando AUC binária. Não recalcula AUC nem valida resultado numérico. |
| PY-02 | `def precision_recall_fscore_support`, `sklearn/metrics/_classification.py:1614` | Sustentada: average/beta/zero_division aparecem na assinatura e tratamento do corpo. Outros trechos da mesma fonte também contêm termos; não se afirma relevância única. |
| PY-03 | `def mean_squared_error`, `sklearn/metrics/_regression.py:426` | Sustentada: regression loss e média ponderada por sample_weight. Biblioteca, execução NumPy e compatibilidade de versão não avaliadas. |
| GO-01 | `func SanitizeURL`, `modules/util/url.go:43` | Sustentada: parse de URL e `u.User = nil`. Não certifica sanitização de todos os componentes/formatos URL. |
| GO-02 | `func FileURLToPath`, `modules/util/path.go:228` | **Pertinência parcial da query**: target de conversão file URL correto, mas “rejecting invalid authorities” não tem suporte. A função rejeita scheme não-file, extrai `u.Path` e ajusta drive Windows; não lê `u.Host`/authority. O comentário linha227 declara erro somente quando a URL não é file. Recebe URL já parseada. |
| GO-03 | `func ShellEscape`, `modules/util/shellquote.go:55` | Sustentada: seleciona escapes e quotes para caracteres; preserva expansão inicial de tilde conforme política textual. Não é certificação de segurança entre shells. |
| Rust-ABSENT | Sem anchor; 13 arquivos /76.529 bytes | Identificador `qzvksndpwbf467901` ausente em corpo/caminhos capturados. |
| TSJS-ABSENT | Sem anchor; 28 arquivos /112.122 bytes | Mesmo identificador ausente nesta captura JavaScript/Flow; não cobre TypeScript geral. |
| Python-ABSENT | Sem anchor; 19 arquivos /576.337 bytes | Mesmo identificador ausente na captura metrics. |
| Go-ABSENT | Sem anchor; 22 arquivos /54.032 bytes | Mesmo identificador ausente na captura util. |

As quatro negativas compartilham **uma única string artificial**, sem pergunta natural. Elas sustentam ausência lexical por família capturada, sem provar que uma tarefa real é impossível de responder, que algo não existe no repositório inteiro ou que um modelo entende ausência. A maioria dos positivos já entrega nome exato do símbolo; busca lexical competente pode ser suficiente sem inferência. As três queries por família e anchors curtos de declaração não constituem anotação exaustiva de todos os arquivos/trechos relevantes nem dificuldade representativa de tarefas reais.

## Pendências para o Arquiteto

1. GO-02 exige decisão prospectiva: reformular a cláusula incorreta ou selecionar target que realmente documente validação de authority em um **novo conjunto congelado antes da execução**. Não corrigir o label/query original para reescrever resultados. O acerto de arquivo atual não comprova aquela cláusula.
2. RS-03 deve esclarecer EOF de pipes versus espera por child quando virar tarefa de comportamento. Os labels atuais continuam anchors de localização lexical.
3. A segunda leitura pós-resultado está registrada com ressalvas. Independência prospectiva, cegamento/holdout, tarefas naturais mais exigentes, negativas diversas e política de múltiplos alvos/ambiguidades continuam pendentes. Esta leitura não fecha retroativamente esses requisitos.
4. Scores, denominadores e falhas do benchmark original permanecem como medidos. GO-02 não foi removida dos denominadores, RS-03 não recebeu anchor novo e nenhum ranking/hyperparâmetro foi ajustado. Qualquer avaliação corrigida futura precisa de identidade e evidências próprias.

Estado: revisão de autoria separada, pós-resultado, concluída para16/16 com integridade12/12 e ausência lexical4/4; pertinência da formulação não tem aceite irrestrito em duas queries. Não há promoção a holdout, agent_run, semântica, D1 ou gate global.
