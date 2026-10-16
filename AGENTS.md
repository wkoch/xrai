# Instruções do projeto

<!-- codebase-memory-mcp:start -->
For structural codebase exploration, use the installed `codebase-memory` skill.
<!-- codebase-memory-mcp:end -->

## Prioridades de suporte — instrução do usuário em 16/10/2026

- Rust, Go e JavaScript/TypeScript: priorizar suporte mais completo, com foco na linguagem e na biblioteca padrão.
- Python: preservar o que já funciona; concentrar novas necessidades no básico e em áreas relacionadas a IA e geração/manipulação de DOCX/XLSX e documentos semelhantes. Evitar aprofundamento geral de Python sem ligação com essas prioridades.
- Antes de escolher ou aprofundar suporte a frameworks, perguntar ao usuário em quais focar. Não selecionar frameworks automaticamente em nenhuma linguagem.
- Registrar decisões arquiteturais necessárias como pendências para o Arquiteto. A revisão dos planos/corpus/aceites deve ser prospectiva e preservar os resultados históricos.

Detalhamento e pendências: [prioridades registradas](docs/relatorios/PRIORIDADES-LINGUAGENS-2026-10-16.md).

## Entregas e Git

Por instrução do usuário, após concluir uma entrega e passar nas verificações aplicáveis, faça commit e push para `origin` (`https://github.com/wkoch/xrai.git`). Registre as evidências e atualize o estado da implementação antes do commit. Preserve trabalho existente e histórico remoto; não use force push para substituir alterações.

Se commit ou push falhar, registre o impedimento e não declare a entrega publicada. O Arquiteto mantém plano/decisões; o Implementador escreve código e verifica o aceite. Questões arquiteturais ficam como pendências nos relatórios locais.
