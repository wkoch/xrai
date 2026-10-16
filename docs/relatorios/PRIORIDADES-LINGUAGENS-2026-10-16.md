# Prioridades de linguagens — orientação do usuário

16/10/2026, registro do Implementador. Fonte: instrução direta do usuário nesta conversa, posterior ao checkpoint `9faea6e`. Este registro conserva a decisão de produto e encaminha seus impactos arquiteturais; não declara implementação ou aprovação de novos critérios.

## Diretriz vigente

| Área | Prioridade definida |
|---|---|
| Rust | Suporte mais completo à linguagem e biblioteca padrão. |
| Go | Suporte mais completo à linguagem e biblioteca padrão. |
| JavaScript/TypeScript | Suporte mais completo à linguagem e biblioteca padrão. |
| Python | Manter o que funciona; foco novo no básico, áreas relacionadas a IA e geração/manipulação de DOCX/XLSX e documentos semelhantes. |
| Frameworks, em qualquer linguagem | Perguntar ao usuário quais priorizar antes de escolher ou aprofundar o suporte. Nenhum framework novo foi escolhido nesta orientação. |

O código, os testes e as evidências existentes são preservados. Não há pedido de reescrita da infraestrutura funcional em Python. A distinção entre cobertura das linguagens analisadas e infraestrutura de avaliação deve permanecer explícita ao propor próximos investimentos.

## Pendências para o Arquiteto

1. Ajustar prospectivamente a ordem e a profundidade dos frontends, capacidades P2/P3, corpus e comparadores para priorizar Rust/Go/JS/TS. Definir critérios verificáveis para “suporte mais completo”, sem prometer cobertura universal.
2. Delimitar o básico de Python e os casos úteis de IA e documentos Office; identificar integrações necessárias e levar escolhas de frameworks ao usuário antes de focá-las.
3. Reavaliar a prioridade do oracle Django v2 já preparado e dos demais casos de frameworks. Preservar código/receipts/CI já iniciada; não ampliar esse foco automaticamente com base no plano anterior.
4. Definir os perfis de biblioteca padrão/ambiente aplicáveis, especialmente os ambientes JavaScript/TypeScript, sem confundir biblioteca da linguagem, runtime e framework.
5. Se a redistribuição alterar corpus, quotas ou condições de saída, propor a revisão explícita antes de novas avaliações. Não excluir resultados, mudar denominadores ou promover gates retroativamente.

As escolhas de frameworks continuam dependendo do usuário, mesmo após a análise do Arquiteto. Nenhuma mensagem foi enviada a outra conversa; este relatório é o encaminhamento local.

## Registro da entrega

Diretriz incluída em `AGENTS.md` e no início de `IMPLEMENTADOR.md`; estado atualizado com referência a este relatório. Verificação aplicável: revisão do diff, links locais e `git diff --check`. Somente documentação/instruções alteradas; nenhuma suíte, execução nativa, framework, provider ou campanha disparada manualmente. O pedido anterior de pausa da implementação permanece respeitado. Commit/push serão confirmados após publicação.
