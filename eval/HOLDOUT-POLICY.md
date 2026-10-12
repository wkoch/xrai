# Separação de H1/H2

D0, D1-seed, D1 qualificado e seus oracles são dados de desenvolvimento conhecidos. Não servem como confirmação estatística. Nenhum task, solução, patch ou rótulo H1/H2 foi preparado neste checkout.

Antes de H1, um avaliador separado da implementação escolhe tarefas em armazenamento inacessível aos implementadores e ao processo de indexação. Sua designação é registrada no manifest de campanha; soluções não são preparadas nesta conversa nem neste checkout. Mantém estratos de linguagem/tarefa, ao menos três repositórios por família, dois ausentes de todo D0/seed/D1 qualificado; exclui linhagens e patches semelhantes usando commit de origem, fingerprint e revisão independente. Pelo menos metade dos casos e metade de cada família cumpre o recorte complexo do [ADR 021](../docs/decisoes/CORPUS-QUALIFICADO.md). Fixtures sintéticas não contam como tarefas independentes.

Tamanho H1 depende de variância/discordância e agrupamento observados em D1 qualificado. Proposta inicial 120; teto H1+H2 240; registrar antes dos resultados, junto de commits, configurações, modelos, prompts, budgets, retries, pesos, critérios, potência e custos. Implementador registra hardware disponível e estima campanha; mantenedor autoriza despesas antes de uso pago. Esta entrega não inicia campanha paga nem exige uma nova decisão arquitetural para trabalho local.

O harness recebe somente checkout baseline isolado e entrada natural da tarefa; diff proposto é permitido quando parte do pedido de revisão. Referência, testes ocultos, resultados e rótulos ficam no avaliador. O processo da ferramenta/agente recebe acesso somente ao diretório materializado, sem mount do repositório xrai, eval/oracles, arquivos reservados ou histórico Git com a correção. O materializador de D0/D1 aplica allowlist; isolamento de permissões/processos pertence a M0-04.

O ranking indexa somente o workspace materializado. Não incluir request.json, relatório, reference.patch ou oracles como fonte. Congelar finalistas/variante antes de abrir H1; não retunar no holdout. H2 permite apenas extensão/replicação pré-registrada, com tarefas novas, sem reabrir seleção pelo resultado.
