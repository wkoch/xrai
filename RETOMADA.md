# Retomada em outro computador

16/10/2026. Ponto de passagem do Arquiteto para o Implementador. Pedido atual: salvar pendências para remover este checkout e continuar a partir do GitHub. O Implementador prepara a publicação e verifica um clone independente; o resultado final deve ser conferido pelo SHA entregue ao usuário. Este pedido não retoma a implementação pausada nem dispara experimentos.

## 1. Ler primeiro e preservar as prioridades

1. [AGENTS.md](AGENTS.md): papéis, Git e instruções vigentes.
2. [Prioridades de 16/10](docs/relatorios/PRIORIDADES-LINGUAGENS-2026-10-16.md): Rust/Go/JavaScript/TypeScript com maior profundidade na linguagem e biblioteca padrão; Python existente preservado, novos investimentos no básico, IA e DOCX/XLSX/documentos semelhantes. **Perguntar ao usuário antes de escolher ou aprofundar frameworks em qualquer linguagem.**
3. [Checkpoint C07](docs/relatorios/L5-C07.md): trabalho mais recente, inclusive preparação ainda sem prova nativa.
4. [Estado](docs/STATUS-IMPLEMENTACAO.md), [handoff](IMPLEMENTADOR.md) e [roteiro v1](docs/ROTEIRO-V1.md).
5. Contratos anteriores: [fechamento C06](docs/relatorios/REVISAO-L5-C06-FECHAMENTO.md) e [vertical Rust](docs/INTEGRACAO-VERTICAL-RUST.md), subordinados às novas prioridades e ao checkpoint C07. Texto antigo dizendo “implementar” não apaga preparação já salva; texto dizendo “próxima execução Django” não autoriza ampliar framework após 16/10.

Arquiteto mantém decisões/planos; Implementador escreve código e comprova aceite. Não é necessário recuperar esta conversa ou os agentes anteriores: as pendências substantivas estão nos arquivos indicados. Ferramentas, skills, índices e credenciais do aplicativo são configurações da máquina, não parte do clone.

## 2. Corte encontrado e estado real

HEAD observado: `e61c31631bfbc0891d8c907f0c3f98261ea8c341`, branch `main`; tracking local `origin/main` no mesmo commit. Esse é o corte inicial da passagem. O Implementador confirmou esse mesmo SHA diretamente pela API do GitHub e por `ls-remote` antes de publicar os arquivos de retomada. Histórico relevante:

| Commit | Conteúdo salvo |
|---|---|
| `e61c316` | Prioridades de linguagens e consulta obrigatória sobre frameworks |
| `9faea6e` | WIP Store, coletor/verificador/workflow/fixtures e checkpoint da pausa |
| `f700036` | Transporte público fake, protocolo de processo e preparação do oracle Django |
| `cee7b4d` | Arquitetura da ponte Store–consumer e primeira tarefa Rust inteira |

A última revisão arquitetural de implementação aceita C06 no seu recorte. **C07 foi lido nesta passagem pelo relatório; não recebeu nova auditoria de código ou aceite do Arquiteto.** Não converter resultados relatados em verificações recém-executadas.

- Transporte público fake: Implementador relata 38 testes e oito registros; não é provider/modelo/cobrança. [Relatório](docs/relatorios/L5-PUBLIC-TRANSPORT.md).
- Protocolo de processo: 14 testes com processos Python próprios; não prova conexão ao Store real. [Checkpoint](docs/relatorios/L5-C07.md).
- Store: código, sessão, sete fixtures, coletor, verificador e workflow salvos; 42 testes data-only com 40 passes e dois skips factuais, Rustfmt aprovado no checkpoint. **Prova nativa/rebuild/retensão continua pendente.** [Relatório](docs/relatorios/L5-STORE-BRIDGE.md).
- Django v2: preparado, 38 contraprovas relatadas. Run `38629057823`, head `f7000369b6d47c613ba4657deac2e466932efd24`, havia sido disparado antes da pausa; resultado/API/ZIP não autenticados no checkpoint. Estado atual desse run não foi consultado aqui. [Relatório](docs/relatorios/L5-DJANGO-PHYSICAL.md).
- M0 permanece experimental: 9 cartões concluídos, 7 em andamento, 25 não iniciados; oito dossiês elegíveis, D1 global 0/32, quatro eventos, projeção multimódulo 19/20; G0/G1/G2 não avaliados. Não há estimativa de data/percentual confiável de v1.

## 3. Pendências do Arquiteto

1. Rever prospectivamente frontends, corpus e aceites conforme as prioridades de 16/10. Definir “suporte mais completo” por capacidades verificáveis de Rust/Go/JS/TS; distinguir linguagem, biblioteca padrão, runtime e framework, especialmente em JS/TS.
2. Delimitar básico de Python e necessidades de IA/documentos, mantendo o que já funciona. Infraestrutura Python do harness não é suporte semântico Python e não precisa ser reescrita por essa prioridade.
3. Reavaliar Django v2 e demais aprofundamentos em frameworks. Preservar trabalho e resultados históricos. A aquisição de um artefato já gerado é preservação de evidência; nova execução/ampliação de framework não deve ser escolhida automaticamente. Consultar o usuário quando for decidir foco.
4. Revisar corpus/quotas/gates explicitamente se o novo foco exigir mudança; nunca alterar denominadores/resultados retroativamente. As 20 tarefas D0 não substituem as 32 D1 do piloto.
5. Revisar as entregas C07 por código, testes e artefatos reais quando a implementação for retomada. Preparação, testes próprios e prova nativa são estados diferentes.
6. Preservar na ponte a identidade entre capturas/envelopes/handles, BASE inicial sem solução privada, HEAD apenas de edição pública, deadline incluindo escrita/leitura e orçamento acumulado entre bindings. [Contrato da vertical](docs/INTEGRACAO-VERTICAL-RUST.md).

Não há escolha nova de framework nem autorização de campanha paga neste documento.

## 4. Pendências do Implementador após retomada autorizada

- Conferir CI regular dos commits salvos. Resultados de um commit anterior não aprovam o WIP Store por herança.
- Preservar/adquirir API, logs e ZIP originais do run Django já iniciado, se ainda disponíveis, vinculando run/head/digest. Se expiraram, registrar perda/indisponibilidade; não inventar prova nem relançar framework automaticamente para preencher a lacuna.
- Depois da retomada e da revisão de prioridades, executar a prova própria `.github/workflows/l5-store-bridge.yml` sobre o código salvo. Autenticar artefatos e recompor respostas completas, preservando falhas e skips factuais. Não usar o receipt C06 byte-only como prova C07 Store.
- Integrar o handler/consumer ao mesmo processo Store, com envelope/binding prospectivos, fonte ampla/busca→âncora e teto comum entre revisões. O protocolo de processo novo e o Store preparado não comprovam essa ligação.
- A tarefa Tokio/FIFO é o candidato já planejado para diagnóstico inteiro; reavaliar sua prioridade conforme a instrução de 16/10 antes de aprofundar suporte à biblioteca/ecossistema. Não promovê-la a ganho P2 ou novo crédito de corpus. Nunca alimentar busca/seleção com patch/oracle privado.
- Demais pendências conservadas em [C05](docs/relatorios/REVISAO-L5-C05.md): conjunto lexical24 e expansão medida; recortes semânticos por perda útil; instrumentação/calibradores de recursos v2; ABA/blobs; comparadores fortes e manifesto de quatro smokes; inspeção S02 limitada. A nova prioridade de linguagens controla a escolha dos próximos recortes. Não retomar setup/build de Gitea nem ampliar permissões por causa da migração.

## 5. Antes de apagar este computador — responsável: Implementador

- Incluir `RETOMADA.md`, os links de entrada, atualização de estado e [inventário da passagem](docs/relatorios/logs/retomada-2026-10-16/inventario.json) nos últimos commits. Preservar outras alterações que surgirem; não usar `git add -f` em caches nem enviar credenciais.
- Conferir `git status`, arquivos não rastreados, stashes, branches e worktrees novamente no fechamento. Nesta inspeção inicial havia uma branch/worktree, nenhum stash ou commit de branch fora dos remotes locais e nenhum arquivo não rastreado. Isso pode mudar até o push final.
- Fazer commit/push de tudo necessário e confirmar o SHA final em `git ls-remote origin refs/heads/main`. Registrar esse SHA na mensagem de entrega. Tracking local sozinho não comprova publicação.
- Preferir um clone novo de verificação em outro diretório/máquina e confirmar HEAD, arquivos desta passagem e assets necessários antes de remover o original. A remoção só deve ocorrer depois dessa confirmação do Implementador; esta passagem, ainda sem commit, não é sinal verde para apagar.

## 6. O que acompanha o clone e o que precisa ser recriado

A inspeção inicial encontrou 6.430 arquivos rastreados, incluindo quatro archives de fontes (46.300.818 bytes no total), fixtures, logs/receipts e fontes WIP. Nenhum symlink rastreado ou submódulo foi encontrado. O inventário registra paths/hashes dos archives e Git; não é auditoria de toda a máquina.

Os itens ignorados encontrados no checkout eram `target/`, `graft/`, `.codebase-memory/`, `.trace-mcp/` e diretórios `__pycache__/`: builds/índices/caches regeneráveis. O conteúdo desses caches não foi auditado arquivo a arquivo; a classificação como regeneráveis vem da política do repositório. Arquivos externos ao checkout, ambientes `/tmp`, toolchains, caches de pacotes, autenticação GitHub e configuração pessoal não acompanham o clone. Não copiar segredos para resolver isso. Caso o Implementador conheça input insubstituível externo ou ignorado, preservá-lo de forma apropriada antes da remoção e atualizar o inventário.

Pareceres e contraprovas anteriores usados pela arquitetura foram incorporados nos JSONs de `docs/relatorios/logs/`; paths `/tmp` dentro desses relatos são contexto histórico. Não executar receitas antigas literalmente em paths de outro computador. Reconstruir venvs em local novo usando os pins/requisitos e os workflows pertinentes; não depender de `/Users/wkoch`.

Retomada básica, sem disparar testes ou código upstream:

```sh
git clone https://github.com/wkoch/xrai.git
cd xrai
git status --short --branch
git log -5 --oneline
```

Conferir o SHA entregue pelo Implementador e ler este arquivo antes de executar. Rust está fixado em `rust-toolchain.toml` (1.98.1, edição2024 no workspace); Python difere por perfil (CI documental3.15.0, ferramentas de medição/provas3.13.13). Consultar workflows, requirements e locks específicos. As ferramentas codebase-memory/graft e suas skills podem ser reinstaladas e os índices reconstruídos; índices antigos não são autoridade sobre o novo checkout. Preservar execução upstream isolada, oracle privado e separação de ambientes mesmo na máquina nova.

## 7. Auditoria de preservação pelo Implementador — 16/10/2026

Conferidos os arquivos não commitados, todos os paths ignorados, refs locais/remotas, stashes, worktrees e objetos sem referência. O único trabalho pendente encontrado eram os quatro arquivos desta passagem. Nenhum stash, branch local extra, submódulo ou symlink rastreado. As três branches Dependabot também estão publicadas no GitHub.

Os 37.368 arquivos ignorados foram agrupados por path e tamanho: builds Cargo, índices graft/codebase-memory, bytecode Python e duas preferências trace-mcp. Não houve grupo sem classificação ou arquivo adicional identificado como input necessário. Não foi feita auditoria semântica de cada cache. As preferências trace-mcp foram copiadas para o backup privado; os caches podem ser reconstruídos.

Foram encontrados **84 blobs e 96 árvores Git sem referência**, sem commits órfãos. Para preservar versões intermediárias sem expor conteúdo que não passou por revisão de segredos, foi criado fora do checkout o diretório privado **`/Users/wkoch/Projetos/xrai-backup-local-2026-10-16`**. Ele contém `historico-e-refs.bundle`, `objetos-sem-referencia.pack`, manifesto SHA-256, instruções de recuperação e as duas preferências trace-mcp. A restauração dos 180 objetos foi comprovada em clone isolado do bundle, com `index-pack --strict`, `cat-file` e `fsck --full`. Esse backup **não acompanha o clone do GitHub**; copiá-lo separadamente para guardar também as versões intermediárias ao trocar de computador. Não publicar seu conteúdo bruto.

A publicação é documental: código WIP, fixtures, arquivos de fontes e evidências anteriores são preservados byte a byte. Checks desta entrega: integridade Git, JSON, links locais, cartões/gates, hashes de arquivos/archives e revisão dos novos textos para padrões de credenciais. Não houve execução de código do produto, suíte de implementação, upstream, provider ou novo experimento. CI e provas nativas anteriores continuam com o estado histórico indicado acima.

A conferência do clone usa HTTPS sem referência ao repositório local, compara todos os arquivos versionados com os blobs do commit e recompõe os hashes dos assets. O inventário distingue o corte verificado de cada fase; o SHA final é confirmado novamente na API do GitHub e informado na entrega. Só apagar o checkout original depois dessa confirmação. Apagar apenas o diretório `xrai` preserva o clone de verificação e o backup irmão; apagar/formatar a máquina exige transferir o backup privado separadamente. Autenticação, toolchains e skills devem ser provisionados no computador novo.
