# L5-03 — recursos dos workers em fontes reais capturadas

Estado: desenho e implementação experimental preparados; compilação, equivalência nativa e medição Linux/macOS **pendentes de CI descartável**. Nenhum benchmark, Cargo, parser nativo ou código upstream foi executado localmente. O aceite de M0-06 e a decisão de workers em produção permanecem pendentes.

## Desenho congelado antes do driver

Critérios: `REVISAO-L5.md §6`, `REVISAO-L4.md §5` e `WORKERS-E-MEDICAO.md §3`. `eval/resources/real-v1/freeze-before-driver.json` registra a captura anterior ao novo algoritmo e ao runner, em 2026-10-13T01:08:32.306400Z. SHA-256 do protocolo: `1a5aff585dc9546c19cc36ba3f3519a7dd417c99ad5d88a88b908becb3deb17d`. Os bytes congelados não foram corrigidos ou reclassificados após implementação.

O denominador capturado contém 80 unidades/9.332.768 bytes: 52 arquivos reais completos, 14 prefixos controlados de arquivos reais e 14 controles sintéticos históricos de comentários grandes, mantidos byte a byte. Rust, JavaScript, JSX, TypeScript, TSX, Python e Go participam; TSX **dense e large têm zero unidades elegíveis**. O texto `known_gaps` congelado menciona somente large; a disponibilidade estruturada já registra dense e large. Esta discrepância fica explícita no resultado derivado, preservando a preregistração.

As fontes vêm exclusivamente dos arquivos já capturados e pinados do projeto. `source-manifest.json` preserva archive/member, SHA-256 do arquivo upstream integral, classificação, densidade lexical e denominadores: Rust1117, JavaScript959, JSX789, TypeScript18925, TSX327, Python810 e Go2483 candidatos UTF-8/64..262144 bytes. Dois arquivos são selecionados por célula disponível. Pequeno:64..2047 bytes; médio:2048..32767; denso:16384..131071 com proxy de pontuação≥10%; grande:65536..262144. Arquivos de testes e desenvolvimento podem estar incluídos; classificação por bytes não prova tarefas naturais ou admissão D1. A seleção JSX é lexical e pode selecionar strings/fixtures; cobertura sintática será observada sem alterar rótulos. Prefixos incompletos são intervenções controladas, não defeitos originais. Os arquivos originais e suas licenças permanecem nos arquivos capturados anteriores; esta frente não instala, importa, compila ou executa projetos upstream.

O protocolo exige quatro métodos (`direct`, `direct_cached`, XRW1 e XRW2), concorrências1 e2, três sessões independentes/método/concorrência, rotação fixa de ordem e 30 consultas por dialeto/classe/padrão. São40 células disponíveis ×2 padrões ×30=2400 consultas medidas/sessão, mais2 warmups/lane. O padrão distinto alterna duas unidades, não30 arquivos independentes. Configurações A/B alternam para expor retenção indevida de configuração; equivalência prévia cobre todas80 fontes ×2 configurações ×4 métodos. O teto é150MiB de evidências e1200s por sessão; excesso aborta com evidências incompletas preservadas.

## Implementação e vínculo com os controles

Novo binário `crates/xrai-eval/src/bin/worker-benchmark-real.rs`. Nenhuma API de workers, parsing, matriz histórica ou prova sintética foi alterada. `direct_cached` copia a política privada de `worker_persistent::cached_response`: cache parser/query exclusivamente por dialeto, valida identidade/fonte/configuração, reset antes/depois, árvore anterior `None`, sem cache de resposta/AST/fonte, ranges ou edits. Cada lane possui seu cache. Todos métodos recebem as mesmas capturas de bytes, feitas uma vez por sessão antes das consultas, e validação completa de resposta. Um `source_id` repetido com path/dialeto/hash conflitante é rejeitado.

A referência mantém a **Response codificada inteira**: identidade, estado, contadores, todos spans/diagnósticos/posições, tree e payload. Somente `identity.request` é normalizado para0 depois de validar correlação; tentativa permanece0. Os quatro modos retêm160 respostas completas comprimidas cada, comparadas literalmente antes da primeira sessão medida. A recomposição rejeita flags de equivalência autodeclaradas sem bytes. Respostas medidas devem coincidir em hash e tamanho com a referência completa; método/config/fonte, cardinalidade, ordem e2400 consultas são reconstruídos a partir do protocolo congelado.

O probe próprio `--producers` emite dados da gramática efetivamente vinculada. Python recomputa o produtor BLAKE3 do worker a partir de runtime0.27.1/crate/versão/NODE_TYPES/query/provenance/ABI. NODE_TYPES é verificado contra os SHA da provenance e queries contra arquivos pinados. ABI Rust/JS/JSX/Python/Go15 e TS/TSX14 foi inspecionada como dado em `parser.c` dos pacotes fixos, sem compilar/executar. O envelope vincula integralmente driver/política copiada/worker/parsing/queries/Cargo/protocolo/método/workflow e os três executáveis realmente consumidos, retidos por host.

Interface CI:

```text
python eval/scripts/run_real_resources.py --binary target/release/worker-benchmark-real --single-worker target/release/worker-spike --persistent-worker target/release/worker-persistent --output resource-evidence/event
python eval/scripts/verify_real_resources.py --output resource-evidence/event
XRAI_REAL_RESOURCES_OUTPUT=resource-evidence/event python -m unittest discover -s eval/scripts -p test_real_resources.py -v
```

O runner rejeita execução fora de `GITHUB_ACTIONS=true` em Linux/Darwin. Só os três executáveis do projeto e o programa controlado de calibração são executados em CI. Fontes upstream são exclusivamente entrada inerte do próprio parser.

## Observação, limites e evidências

Observador Python separado usa `wait4` para a única coleta terminal do processo nativo; CPU inclusiva de pai+descendentes aguardados é calibrada uma vez/host com o programa controlado histórico e recomputada a partir dos recibos reais. CPU self/ps do observador fica em domínio próprio, sem duplicar CPU terminal dos workers. CPU do alvo inclui capture/setup, esperas idle, warmup, consultas, validação, serialização e shutdown; não há atribuição por consulta.

RSS utiliza snapshots comuns de `ps` a25ms, soma de processos vivos e séries brutas; `sampled_peak_sum_rss` não é pico físico contínuo. Baselines idle/warm_idle exigem três amostras válidas distintas do pai antes de liberar gates ready/start. Gates e timestamps, PID do alvo, comando do binário retido, origem CPU, calibração, tipos/intervalos e domínio temporal são validados. Lstart tem granularidade do `ps`; perdas por conjunto de PID não demonstram observação de cada incarnation nativa. Picos entre amostras, processos curtos e páginas compartilhadas permanecem limitações declaradas.

Warmup cobre somente Rust small; primeiras chamadas de outros dialetos ficam incluídas. O pool XRW2 é lazy: spawn/handshake/compilação caem em dispatch externo, e não viram zero inferido. `compile_ns` é observável somente no controle direto cacheado. Queue/codec/roundtrip internos e bytes de IPC/stderr XRW2 são `null` com motivo. `source_read_ns` pertence à captura única e se repete por consulta, portanto não é somado. Latência sequencial e throughput com concorrência2 são reportados separadamente por sessão/classe/padrão; percentis de componentes não são somados.

Verificação local permitida: rustfmt do arquivo novo PASS; desenho data-only PASS;21 testes data-only PASS e9 testes que exigem a prova real ficam skipped localmente. Os testes rejeitam produtores zero, JSON duplicado, bool como contador, tipos/coords/kind de diagnóstico adulterados, truncamento, bytes extras, infinidade de CPU, RSS float, baselines repetidos/negativos/fora de intervalo, PID diferente, calibração substituída e perda ocultada. Em CI, os9 testes adicionais consomem evidências reais e exigem24 sessões distintas,3 bins, produtor pinado, matriz congelada e equivalência antes da medição. Logs: `docs/relatorios/logs/L5-C04/resources/{design-before-ci.json,python-before-ci.stdout,python-before-ci.stderr,before-ci.json}`.

Pendências do Arquiteto: ampliar classes reais TSX dense/large com novo protocolo; tarefas com30 arquivos distintos; casos originalmente incompletos; separação de cold/fully-warm para todas gramáticas; instrumentação privada XRW2; calibradores restantes de M0-06 (tickets/deadline/slow-consumer/real workloads), além de decisão de produção. Nenhum resultado de CPU/RSS/ganho foi inventado nesta entrega.
