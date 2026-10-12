# Dependências de desenvolvimento L4

12/10/2026. Serialização dos experimentos em `xrai-eval`: `serde=1.0.229` com derive e `serde_json=1.0.154`, versões já presentes transitivamente no lockfile anterior. A alteração ativa derive e declara as dependências diretas; não atualiza os outros pacotes. O pin inicial JSON1.0.145 era incompatível com o requisito `^1.0.150` do Tree-sitter0.27.1 e foi corrigido antes da compilação.

MSRV declarada no pacote local do registry: serde/core1.56, derive/json1.71, compatíveis com o toolchain fixado1.98.1. Licenças MIT OR Apache-2.0; textos completos em `crates/xrai-eval/licenses/serialization/`, caminhos e hashes no [recibo](logs/L4/serialization-notices.json). Esses dados vêm dos pacotes fixados usados no build, não de versões inferidas pelo nome.

Tokenização offline tem requirements e assets próprios em `crates/xrai-eval/harness/`; o perfil declara implementação, vocabulário/merges, configuração, serializer e política de special tokens. Proveniência, avisos e verificações constam do [relatório de readiness](../../eval/reports/m0-agent-readiness.md). Dependências Python são do avaliador, sem configuração global ou credenciais.

As dependências novas permanecem experimentais. As crates de produção e a CLI instalada não dependem de `xrai-eval`; promoção segue os gates do projeto. Nenhum provedor pago foi chamado por esta entrega.
