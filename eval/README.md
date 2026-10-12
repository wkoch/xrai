# Corpus de desenvolvimento M0-03

20 tarefas D0 e 32 propostas D1-seed, em quatro famílias e oito upstreams reais. Os 20 snapshots são cópias de árvores Git fixadas por SHA completo, com arquivos/tamanhos/hashes e licenças no manifest. Não há histórico `.git` nos inputs. A [decisão L1-C01 / ADR 021](../docs/decisoes/CORPUS-QUALIFICADO.md) aceita este material para desenvolver o harness; o piloto exige 32 casos qualificados em M0-03.R1. IDs/bytes `D1` históricos são preservados e `corpus.toml` os classifica como seed. `challenge-qualified.jsonl` e `supplementary.jsonl` têm carregamento explícito e começam vazios. O gate recusa esse estado antes de qualquer campanha; não há promoção automática a G0. Os comandos abaixo operam o corpus inicial existente.

```sh
python3 eval/scripts/verify_corpus.py
python3 eval/scripts/materialize_task.py D1-PY-02 /tmp/xrai-task-py02
python3 -m unittest discover -s eval/scripts/tests -v
python3 eval/scripts/verify_qualified.py # exit 1 enquanto as 32 qualificadas não forem admitidas
```

Entregar ao agente somente `/tmp/xrai-task-py02/workspace` e `request.json`; `proposed.diff` existe apenas nas revisões. Não dar ao agente acesso ao checkout deste projeto. `relevant_sources`, critérios de aceite, oracles, patches de referência e probes são metadados do avaliador. O verificador materializa todas as 52 tarefas e confere ausência de arquivos do oracle; sandbox do processo de avaliação é trabalho de M0-04.

Para evento incremental, o avaliador chama `materialize(id, destino, phase='A')`, inicia/aquece seu braço e chama `apply_event(id, destino/'workspace')` mantendo processo/cache/índice. A função retorna hashes/tamanho/mtime antes/depois. O request público não contém operações do evento. O default `cold` continua aplicando mudanças antes da primeira consulta e é classificado `cold_changed_checkout`. [Triagem, admissão e pendências R1](reports/m0-corpus-qualification.md) incluem os oito projetos medidos e os 32 recibos seed ainda sem revisão semântica individual comprovada.

Todos os rótulos foram selecionados lendo fonte upstream/patch/testes públicos. Nenhum extrator xrai, parser ou grafo gerou a verdade esperada. Campos `recovery_criteria` cobrem fonte/revisão/configuração; `agent_success_criteria` apontam oracle distinto com fatos, vetores e julgamento do resultado. Doze probes executáveis demonstram a regressão de oito correções e quatro revisões. Os oito requisitos de contrato precisam ser implementados pelo agente antes de executar novos testes: probes de correção não provam sucesso do agente.

Para repetir os probes locais (ferramentas de desenvolvimento, não dependências do binário): Rust, Node, TypeScript, Go e Python. A CLI slugify requer `text-unidecode==1.3` em diretório isolado. Não executar atalhos `setup.py publish` presentes em versões históricas upstream.

```sh
python3 -m pip install --target /tmp/xrai-corpus-pydeps text-unidecode==1.3
python3 eval/scripts/verify_oracles.py --python-dependencies /tmp/xrai-corpus-pydeps
```

O comando mede baseline antes/depois de aplicar patch em checkout descartável. Correções: baseline falha e referência passa. Revisões: baseline passa e diff proposto falha. Referência não é usada para comparar igualdade textual com resposta do agente; há asserts comportamentais e tipos. Não foram rodadas sessões de agente ou campanha de modelos.

Para reconstrução independente, clone os oito URLs em `sources/manifest.json` para um diretório temporário, usando os nomes `strsim`, `shellwords`, `mitt`, `ms`, `cachetools`, `slugify`, `uuid`, `humanize`. O gerador acessa apenas clones locais e commits completos; não consulta HEAD nem executa o código upstream. Licenças/README/arquivos de pacotes são preservados. O baseline histórico mitt sem LICENSE tem declaração MIT em README/package.json e notice oficial suplementar identificado separadamente; materializador adiciona `UPSTREAM-LICENSE-SUPPLEMENTARY`, sem representá-lo como arquivo original desse commit.

```sh
python3 eval/scripts/build_corpus.py /tmp/upstreams
python3 eval/scripts/build_oracle_probes.py
python3 eval/scripts/generate_fixtures.py eval/fixtures
python3 eval/scripts/verify_corpus.py
```

As fixtures também podem ser ampliadas deterministamente: `--modules 10000 --statements 100000`, para medir bases/funções grandes depois; isto não aumenta contagem de tarefas reais. Timestamps de arquivos versionados não sobrevivem ao Git; o gerador aplica timestamps controlados e o verificador compara reproduções em diretórios novos. Os cenários de tarefas com mtime preservado aplicam duas escritas iguais em tamanho com mtime idêntico.

[Relatório e limitações](reports/m0-corpus.md) · [Política de H1/H2](HOLDOUT-POLICY.md)
