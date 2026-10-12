# P3 experimental Rust — primeira fatia L5-01

Entradas em `*-input.json` contêm apenas capturas imutáveis, configuração, pedido,
âncoras, hunks byte a byte e limites. `development-labels.json` é lido somente pelo
avaliador externo **depois** da seleção. Capturas e instantes dos descritores são
sintéticos de desenvolvimento; o timestamp fixo não é recibo de captura real.

`context-spike INPUT PYTHON` faz seleção, expansão, publicação de outra geração,
replay da expansão original, orçamento menor e expiração. Emite quatro controles
P2 desligado/ligado × head/par e curvas de 2k/4k/8k/16k/32k tokens, incluindo custo
integral das expansões. `verify_context.py INPUT OUTPUT` confronta o wire completo,
perfil L4, tokens, fontes/spans/BLAKE3, IR de origem e perfil documental v3.

O controle P2 desligado suprime lookup semântico e recuperação de consumidores,
mas ainda constrói a IR retida. É uma ablação do componente, não um baseline
lexical otimizado. Head/par mantém a mesma captura head e o mesmo conjunto
capturado inicial externo; o controle head desativa deliberadamente a captura base
na interface do seletor e remove âncoras/hunks base. Os recibos registram essa
mudança; não atribuir todo efeito do par à seleção ou a P2. IDs diferentes mudam
alguns tokens mesmo quando o conteúdo selecionado é igual. Sem afirmação de
superioridade, sucesso de agente ou call graph completo.

Regras `p3-rust-obligations-v1`: ordem determinística por revisão/path/span/ID,
obrigações obrigatórias primeiro; janela completa da linha da âncora/hunk,
contêiner AST para definição relacionada/understand; expansão tenta arquivo inteiro
e contêiner, nunca declara leitura mais completa ao repetir apenas o mínimo.
Intervalos sobrepostos da mesma revisão/blob são deduplicados; identidades dos
objetos e suas obrigações ficam no manifesto. Resoluções `candidate`/`unknown`
conservam o estado, motivo, IDs e evidência em `manifest.resolutions`; nenhuma é
emitida como afirmação causal. Relações disponíveis têm origem na IR Rust R1/R2.

Limites do spike: 2 contextos, 8 MiB de **contabilidade lógica serializada** de
capturas/IR, manifesto e pedido; TTL de 60.000 ms e 4 expansões por contexto.
As 4 expansões contam tentativas admitidas, inclusive falha de medição, contadores,
deadline ou orçamento do envelope. Validação barata de IDs/perfil/capturas pode
recusar o pedido antes de consumir tentativa. Esse limite não é RSS nem teto de
alocações transitórias. Evicção, TTL ou liberação
de qualquer lado invalida o contexto inteiro. O relógio de retenção é um argumento
monotônico fornecido pelo driver. `Store::new` obtém 32 bytes de entropia do SO nos
alvos experimentais Linux/macOS e falha explicitamente se isso não estiver
disponível. IDs ligam fingerprint da seleção, epoch do Store, contador de
encarnação sem wraparound, criação/expiração e política de retenção. Contexto vivo
equivalente pode ser reutilizado sem renovar TTL nem quota. Depois de TTL, pressão
ou liberação, recriar o mesmo pedido produz outra identidade: handle antigo não
ressuscita, inclusive em outro Store. Empates de idade usam a encarnação mais
antiga. Os IDs fixam fontes, configuração/produtor, pedido, regras e fingerprint
do código do seletor; não migram para `published` mais recente.

Rebuilds em Store independentes comparam seleção/objetos/fontes e normalizam
`context_id` explicitamente. Epochs e handles não devem ser igualados para obter
replay artificial: cada wire/contagem original é verificado separadamente. Tokens
podem variar por bytes dos IDs apesar de seleção igual, e isso permanece no custo.

Trabalho é limitado antes da IR pelas capturas completas admitidas (arquivos e
bytes de ambos os lados). Expansão contabiliza conservadoramente blobs completos
dos objetos solicitados, mesmo se devolver trecho menor. Excesso retorna erro de
trabalho explícito nesta interface experimental; ainda não há resposta de produto
para descoberta interrompida ou adapter de admissão. Deadline é cooperativo entre
etapas e medições; parsing/serialização internos não são preemptivos. O helper
Python persistente possui deadline de 5 s no setup, escrita e resposta, reply de
8 KiB e wire de 512 KiB; falha mata e reaproveita nenhum processo. O bridge é uma
dependência de desenvolvimento, não tokenizer embutido no produto.

Cada tentativa mede o JSON compacto completo, incluindo contadores, comparação,
motivos, omissões e next. Contadores têm 16 iterações e detecção de ciclos; falha
não publica envelope normal falso. Envelope mínimo que não cabe é recusado sem
truncamento nem aumento automático de orçamento. Tempo/chamadas do medidor e
setup constam nos recibos; tokens locais não são usage ou custo faturado.

Pendências: ranking marginal/diversidade e alternativas ponteiro/assinatura,
pipeline lexical sem âncora, trabalho interrompido com resposta parcial de produto,
deadline preemptivo, GC/pins de produção, curvas/casos reais de quatro famílias,
cobertura e perdas para tarefas completas. Interface typed-hunk usa offsets UTF-8
e valida reconstrução integral do path; o perfil documental conserva exemplos de
diff unificado verificados separadamente. `normalized_request` retido registra as
âncoras/hunks tipadas; a projeção documental do pedido não é adapter público.
M0-09 permanece aberto.
