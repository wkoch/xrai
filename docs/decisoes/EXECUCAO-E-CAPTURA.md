# Execução, captura e integração Git — ADR 023

12/10/2026. Decisão do Arquiteto para L3, em resposta a L2-H01, M0-08.F01 e L2-GIT01. Define trabalho; não atesta implementação. Evidência de entrada: [L2](../relatorios/L2.md). Mantém ADRs 013, 017, 020 e 022.

## 1. Separar dois supervisores

O worker do produto analisa bytes fornecidos pelo pai; não executa comandos do projeto nem precisa criar descendentes. O harness executa ferramentas, builds e testes, inclusive programas que criam processos. A contenção exigida para um não comprova a do outro.

**L2-H01 resolvida em arquitetura:** agentes reais usam um domínio de execução descartável por braço/run, cujo encerramento seja controlado fora dele. Encerrar um process group é limpeza auxiliar, não a fronteira de contenção. O implementador prova a fronteira antes dos smokes reais; não há exigência de VM na máquina do usuário do xrai.

| Ambiente do harness | Direção de implementação | Prova exigida |
|---|---|---|
| Linux, ambiente primário inicial | Namespace PID privado com bubblewrap, além de isolamento de FS/rede já existente; supervisor externo controla a vida do namespace | Encerrar seu init elimina descendentes, inclusive após setsid/double fork; verificar comportamento real do wrapper e morte do avaliador |
| macOS, testes com comandos arbitrários | VM/runner descartável dedicado ao run, controlado externamente; destruir o ambiente quando termina/falha | Sem reutilização enquanto a destruição não estiver confirmada; descendente não escreve sentinela após teardown; controle positivo prova que ele chegou a executar |
| macOS local atual | Manter replay e smokes de programas conhecidos e limitados | Não declarar contenção de daemon arbitrário; não iniciar agente real capaz de executar shell nesse modo |

Linux pode receber os primeiros smokes de agentes. Isso não substitui provas funcionais do produto nos dois alvos nem muda o piso macOS. Não contratar infraestrutura automaticamente: implementar adapter/configuração e registrar indisponibilidade quando não houver recurso autorizado.

O orquestrador confiável guarda credenciais e conversa com o provedor; executor de comandos recebe apenas operações limitadas e dados públicos da tarefa. Não montar tokens, home do avaliador, oracles ou diretórios de outros braços no domínio. Rede para modelos, se necessária, usa canal controlado pelo orquestrador; não liberar rede irrestrita no executor como atalho. Builds usam dependências pré-materializadas/fixadas e a mesma política em todos os braços. Julgamento oculto ocorre depois, em outro ambiente; logs dos testes ocultos não retornam ao agente.

Contrato conceitual do adapter: criar domínio → executar com deadline → coletar resultado parcial → encerrar → obter recibo de destruição. Timeout, limite de saída, cancelamento, falha de spawn, morte do pai e falha no teardown são estados distintos. Cleanup inconclusivo invalida a elegibilidade do run e impede reutilizar o domínio; preservar resultado e custo como falha, sem excluir a tentativa do denominador. Não prometer que uma enumeração de PIDs fecha corridas de fork/reuso de PID.

Testes mínimos: setsid, double fork, descendente com pipes abertos, saída sem limite, fork limitado, pai encerrado, encerramento normal deixando filho, timeout e falha de teardown. Usar sentinelas e controles positivos; o teste também deve possuir cleanup externo finito. Não provocar fork bomb/OOM global. Dois braços simultâneos comprovam isolamento de leitura/escrita e cancelamento independente.

Fundamento: a documentação de [PID namespaces do Linux](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html) especifica a morte dos processos quando o init termina. [setsid da Apple](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/setsid.2.html) cria nova sessão/grupo; por isso killpg do grupo original não prova encerramento de todos os descendentes. São fundamentos do desenho, não provas dos adapters futuros.

## 2. Worker de parsing: contrato do spike M0-06

Implementar em `xrai-eval` primeiro. O executável do spike inicia a si mesmo em modo worker; M1-05 transportará a solução comprovada para o binário de produto. Pai controla admissão, filas, bytes em trânsito, tentativa, deadline e associação do resultado. Worker não recebe um path para reler a fonte.

Envelope versionado contém request ID, attempt ID, dialect, hash dos bytes, fingerprint de parser/query, configuração, comprimento e payload. Resposta ecoa identidades, estado complete/partial/error, spans e diagnósticos. Sem AST/pointer nativo no IPC. Decoder verifica comprimento antes da alocação, overflow, enum/versão, bytes extras e limites agregados; stdout é protocolo e stderr tem captura limitada. Antes de aceitar, validar spans contra comprimento da fonte e identidade contra a tentativa ainda ativa. Resultado atrasado/cancelado não publica fatos.

Valores iniciais **do experimento**, a registrar antes das medições: 2 workers, fila de 8 pedidos, 8 MiB por fonte, 16 MiB por resposta, 64 MiB de payload agregado reservado entre fila e processamento, 5 s por tentativa e no máximo 1 retry em worker novo. A reserva inclui entrada e teto de resposta até liberação. São limites configuráveis propostos; não metas de RSS nem limites finais do produto. Em M0-10, calibrar com dados e congelar. Parser/query inválido ou limite excedido não merece retry; crash/pipe quebrado admite uma tentativa nova dentro do deadline total. Não aumentar limites após falha sem registrar nova configuração experimental.

Fila cheia retorna sobrecarga, não crescimento sem limite. Deadline cobre espera e execução; se não houver tempo restante, não recomeçar. Cancelamento descarta a tentativa e, no spike, pode reciclar seu worker exclusivo. Leitura/escrita de pipes não bloqueia indefinidamente o supervisor. Recolher filhos para evitar zombies. Workers ociosos, reinício e shutdown têm estado explícito; uma falha não perde trabalhos concluídos de outros workers.

Aceite: mesmo resultado lógico no parsing direto/pool; abort/travamento/truncamento/hash errado/versão errada/resposta excessiva contidos; outro arquivo completa; pai sobrevive; nenhuma fonte é relida pelo worker; filhos terminam no shutdown normal e caminho de falha testado. Comparar startup, throughput, p50/p95, CPU, RSS agregado e custo de serialização com entradas pequenas, grandes e incompletas. Recursos compartilhados de queries/gramáticas precisam ter dono e fingerprint; caches entre pedidos não podem misturar configuração. Hook de falha fica somente no experimento/testes.

Os critérios locais de M0-05 já permitem iniciar esse spike. A falta do host literal macOS 15.0 não impede desenvolvimento em Linux/macOS disponível; permanece pendência para conclusão integral de M0-05 e G0. Não marcar M0-06 concluída sem sua matriz nativa.

## 3. Captura por handles e limite de consistência

**M0-08.F01 resolvida em arquitetura:** substituir verificação seguida de abertura por path por resolução ancorada em handle da raiz, sem seguir symlinks em componente algum. Primeiro spike M0-08.R1; promover somente após os testes. A raiz explicitamente escolhida pode ser resolvida na admissão; depois, sua identidade/handle ficam fixados. Paths relativos rejeitam raiz, `..`, NUL e componentes inválidos; bytes nativos permanecem sem normalização.

Linux: avaliar wrapper seguro de openat2 com BENEATH/NO_SYMLINKS e política explícita para mounts; suporte ausente ou erro de corrida não causa fallback silencioso para abertura insegura. macOS: caminhada componente a componente com handles de diretório, nofollow e validação de tipo/identidade. Preferir APIs seguras de crates existentes; verificar compatibilidade, licença e semântica na versão escolhida. Nenhuma crate está selecionada por este ADR. Preservar `unsafe_code = forbid`; necessidade de FFI próprio requer decisão isolada do ADR 024, não remoção global do lint.

Enumeração e abertura usam o mesmo mecanismo ancorado. Não proteger apenas o arquivo final e deixar read_dir reabrir um ancestral por string. Recusar symlinks, arquivos especiais e caminhos de estado interno com diagnóstico; impor teto durante a leitura, inclusive quando o arquivo cresce. Renome/removal/substituição detectados invalidam o binding path→fonte e geram retry limitado/partial, nunca fonte externa atribuída ao path anterior. Reconciliar configuração, inventário e hashes antes de publicar a geração.

**Modelo explícito:** handles preservam acesso ao objeto aberto, inclusive se renomeado. Não garantem que esse objeto continue sob o nome/raiz corrente. Hard links e mounts também não equivalem a symlinks. Para o workspace vivo, prometer bytes capturados identificados por hash e cobertura de validação, não snapshot atômico de todo o filesystem ou sandbox contra um escritor hostil do mesmo usuário. Fonte pode mudar durante leitura sem que metadata prove um instante coerente. Se a tarefa exigir uma árvore imutável, usar captura fornecida em ambiente isolado/sem escritor ou snapshot de filesystem previamente validado. Nunca chamar metadata estável de prova suficiente.

Testar troca de ancestral por symlink externo antes/durante abertura, renome para fora após handle aberto, substituição da raiz, unlink/recreate, mudança em place do mesmo tamanho/mtime, hard link, mount (quando houver ambiente), arquivo especial, crescimento acima do teto e saída parcial. Oráculo: sem abertura de destino externo via symlink; bytes/hash e identidade sempre coerentes; binding inválido não publicado como atual; instabilidade/limitação explícita. Caso de diretório já aberto e movido exige diagnóstico/reconciliação, sem alegar confinamento absoluto. Testes nativos nos dois alvos e comparação incremental/rebuild em árvore estabilizada.

A direção Linux é sustentada pela [documentação de resolução de paths do kernel](https://www.kernel.org/doc/html/v6.2/filesystems/path-lookup.html). A equivalência da implementação macOS e as corridas listadas são obrigações de verificação do spike, não inferências de portabilidade.

## 4. Git e identidade

**L2-GIT01 resolvida:** adiar gix/libgit2, leitura de objetos/packs, histórico/diff e equivalência de gitignore até consumidor concreto. O spike existente atende seu recorte com std/BLAKE3 e `.gitfile` advisory. Não executar Git CLI em indexação do usuário. Ferramenta Git continua permitida na preparação das fixtures. P3 recebe base/head capturados do harness; não depende do histórico incorporado.

Regras atuais de exclusão são subárvores explícitas, não gitignore. M1-02 deve definir/testar precedência e sintaxe antes de anunciar padrões Git. Ao surgir necessidade real, comparar integração gix/libgit2 ou módulo delimitado sob ADR 024; não criar implementação completa de Git para identificar um checkout.

M1-02/03 devem separar: locator nativo da raiz, identidade física observada e ID persistido da encarnação do checkout. Hash root/device/inode do spike não é contrato público definitivo. Renome, aliases, recriação no mesmo path, reuso de inode e movimentação do cache precisam de regras/testes; dúvida de identidade cria encarnação nova ou pede reindexação, nunca compartilha banco gravável por suposição. Manter IDs de arquivo/símbolo do contrato e configuração versionada.

## 5. Consequências e pendências

Escolhas H01/F01/GIT01 deixam de aguardar o Arquiteto. Implementação: L3-02/03/04 da [revisão L2](../relatorios/REVISAO-L2.md). M0-08 conserva estado em andamento até recibo final do escopo original; a nova prova adversarial é M0-08.R1. Aprovação documental não encerra nenhuma prova.

Alternativas descartadas: confiar só em killpg (perde descendentes), repetir stat/canonicalize (corrida entre verificações), implementar Git completo já (sem consumidor) e exigir todos os recursos de campanha antes de continuar spikes locais (dependência desnecessária).
