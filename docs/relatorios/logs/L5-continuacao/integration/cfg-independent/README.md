# Revisão independente da correção cfg de R3

Escopo: implementação `r3::evaluate`, consumidor `extract_items`, verificador Python `parse_cfg`/`evaluate_cfg`, matriz adicional de oito casos e recibos congelados em `r3/cfg-review`. Esta revisão não altera código, provas anteriores ou o denominador principal de **34 casos / 16 resolvíveis**.

O defeito anterior confundia predicado não suportado com configuração válida desconhecida. A correção usa `Result<Option<bool>, ()>` e propaga erro de cada filho antes de combinar `all`, `any` ou `not`; o Python valida a árvore inteira antes da avaliação. O consumidor converte esse erro em `not_evaluated` e em lacuna `configuration_not_evaluated`, impedindo promoção de símbolos nesse módulo. Configuração válida desconhecida conserva a lógica ternária, inclusive `any(true, unknown)` e `all(false, unknown)`.

Os 24 rótulos suplementares foram gravados antes da execução (`labels-first.json`): **24/24 corretos, 4/4 resolvíveis e zero promoções falsas**. Cobrem operadores conhecidos antes/depois de formas não suportadas, aninhamento, aridade inválida de `not`, valores raw/numeric, escape, chave inválida, operador desconhecido, vírgula extra, vírgula final válida, operadores vazios e família fechada. Cada estado de condição e a presença/ausência da lacuna foram verificados explicitamente, além do verificador existente.

Cinco contrachecks de formas externas conservadoras também passaram: atributos com espaço, atributo interno, `cfg_attr` e string com parênteses mantêm resultado `unknown` e lacuna. A string válida com parênteses continua fora do parser restrito; isso é limitação de cobertura, não promoção falsa. Não se afirma equivalência com toda a gramática de cfg do compilador.

Todos os hashes de fontes e artefatos do manifesto `r3/cfg-review` foram conferidos, inclusive igualdade entre o executável local e os bytes descomprimidos do executável retido. `graph-coverage.json` registra cobertura best-effort de cinco fontes, sem problema registrado na geração citada; foram lidos os trechos materiais da implementação e do consumidor.

**Nenhum bloqueador concreto encontrado neste escopo.** As provas nativas completas da entrega atual permanecem responsabilidade da integração/CI. A falha inicial do leitor do resumo suplementar, por campo opcional `conditions` ausente, está registrada em `summary-first-error.txt`; corrigir o leitor não alterou implementação, rótulos ou resultados.

`review.py` executa somente o binário próprio `semantics-spike` com fixtures próprias. Os recibos são imutáveis; para repetir, use diretório de saída novo ou execute os arquivos de matriz com o binário correspondente e o verificador Python. Nenhum código upstream, Cargo amplo ou hook de projeto capturado foi executado.
