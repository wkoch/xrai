# M0-05 — Gramáticas incorporadas e autonomia

12/10/2026. Spike de desenvolvimento em `xrai-eval`; o CLI de produto `xrai` permanece no estágio M0-02. **Implementação local verificada; cartão ainda depende das provas nativas da CI e do piso macOS 15.0.** Não inferir execução do piso pela versão do target ou por smoke macOS 27.

O binário `parsing-spike` incorpora Tree-sitter e as sete variantes Rust, JavaScript, JSX, TypeScript, TSX, Python e Go. Cada consulta de declarações é compilada e executada; fixtures válidas exigem matches. Fontes entram via stdin. A saída traz árvore, contagem de nós/matches e estado `complete`. Fontes incompletas preservam árvore e diagnósticos com byte inicial/final, linha iniciada em 1 e coluna em bytes iniciada em 0; retornam exit 2. Operação inválida retorna exit 1.

| Critério de aceite | Evidência e estado |
| --- | --- |
| Copiar um executável e processar todas as famílias sem runtimes, gramáticas externas ou download | `docs/relatorios/logs/L2/packaging-local.json`: diretório contém apenas binário, PATH vazio, 14 fixtures válidas/incompletas. Seatbelt `deny default` permite somente execução do binário e leitura dele/bibliotecas do SO. Probes negativos tentam conectar a listener real no host, executar `/bin/sh` e ler arquivo privado do avaliador; todos bloqueados. Linux usa namespace de rede/FS bubblewrap com somente binário e bibliotecas do SO. Prova Linux depende da CI. |
| Executar nativamente em Linux x86_64 e macOS arm64, com diagnósticos de sintaxe | Quatro testes de integração passam localmente; todas as sete gramáticas geram árvores e diagnósticos úteis. Smoke nativo arm64 macOS 27.0.1 passa; Linux e macOS da matriz CI ainda precisam de logs. |
| Fingerprints, bibliotecas e licenças; baseline de SO/ABI | `parsing-provenance.json` registra versões, checksum SHA-256 dos arquivos oficiais do registry e fingerprints C/H/node-types; a íntegra é incorporada no binário. `inventory` acrescenta BLAKE3 de node-types e consultas. Avisos upstream MIT e componentes Unicode/ICU copiados em `crates/xrai-eval/licenses/parsing/`. `otool -L` local encontra somente `/usr/lib/libSystem.B.dylib`; `LC_BUILD_VERSION` confirma minos 15.0 e SDK 27.0. A revisão independente R01 detectou aviso Unicode aninhado omitido; a coleta passou a ser recursiva, com origem/hash/texto completos e teste de presença no inventário do executável. Isso confirma fabricação para o piso, não execução nele. Ubuntu 24.04/glibc 2.39 e execução no macOS 15.0 permanecem a comprovar. |
| Observar tamanho, build, startup e RSS, sem retirar linguagem/plataforma | Binário release local de 8.161.120 bytes. Startup com Seatbelt: 232.87 ms na observação registrada. Pico RSS dos filhos do avaliador, incluindo inspeção ABI/sandbox: 16.334.848 bytes; não atribuir esse pico exclusivamente ao parser. Build em target vazio capturado em `packaging-build-local.json` com duração de 15.65 segundos e hashes das fontes/lockfile. Valores são observações, não gate de performance. |

## Inventário e reprodução

Pins exatos: Tree-sitter 0.27.1; Rust 0.24.2; JavaScript/JSX 0.25.0; TypeScript/TSX 0.23.2; Python 0.25.0; Go 0.25.0; tree-sitter-language 0.1.9 via lockfile. Os pacotes de gramáticas/runtime declaram MIT, e o runtime incorpora suporte Unicode/ICU com aviso próprio em `src/unicode/LICENSE`. O inventário preserva a íntegra dos avisos legais, inclusive o componente Unicode nativo; `src/wasm-stdlib/libc/LICENSE` também é preservado e marcado como componente opcional não compilado nos targets nativos. As licenças e fingerprints dos pacotes efetivos constam no JSON incorporado. O pacote TypeScript omitira LICENSE no tarball do registry; aviso oficial recuperado do [tag v0.23.2](https://raw.githubusercontent.com/tree-sitter/tree-sitter-typescript/v0.23.2/LICENSE), com hash e origem registrados. API de parsing/erro e compatibilidade de linguagens seguem a [documentação oficial Tree-sitter](https://docs.rs/tree-sitter/latest/tree_sitter/struct.Parser.html).

```sh
cargo fetch --locked
python3 crates/xrai-eval/scripts/record_parser_provenance.py
MACOSX_DEPLOYMENT_TARGET=15.0 cargo build --locked --release -p xrai-eval --bin parsing-spike
cargo test --locked -p xrai-eval --test parsing
python3 crates/xrai-eval/scripts/verify_packaging.py --binary target/release/parsing-spike --output /tmp/packaging-proof.json
```

O avaliador usa Python e ferramentas de inspeção do host fora do sandbox. Elas não são runtime do executável copiado. Linux requer bubblewrap instalado para **a prova**, não para usar o parser. Não há fallback sem sandbox; restrição de user namespaces ou sandbox-exec indisponível falha explicitamente. No macOS, caminhos temporários usam representação física `/private/...`, e leitura do diretório raiz é necessária para o loader dyld; essa regra não abre os arquivos filhos. Queries e proveniência são `include_str!`, disponíveis mesmo com repositório e cache Cargo inacessíveis.

A CI deve guardar o JSON completo por host, incluindo versão real do SO, ABI e `baseline_exactly_executed`. Runner macOS 15.x posterior ao 15.0 comprova apenas a versão registrada; ainda falta máquina 15.0 para fechar esse trecho literal do aceite. Essa pendência de infraestrutura não autoriza alterar o piso ou concluir o cartão.
