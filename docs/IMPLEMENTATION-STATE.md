# Estado da implementação

## Branch e base

- Atual: `feat/m1-continuity`, derivada de `feat/m0-foundation` (`79607bb`), ainda não integrada na main.
- Branches seguintes serão derivadas da entrega anterior até integração explícita na main.
- Os dois anexos originais estavam fora do controle de versão e foram preservados no local.

## Progresso

- M0 concluído: ambiente Python 3.12 isolado, dependências fixadas, migração inicial e cadastro/leitura explícitos de projeto.
- M1 concluído: tarefa, sessão, evento idempotente, evidência declarativa, checkpoint atômico e CLI local.
- M2–M4 pendentes.

## Decisões

- SQLite local, dados em `~/.local/share/memx` por padrão; testes usam arquivos temporários.
- Migrações Alembic versionadas; nenhuma criação implícita de tabelas na inicialização.
- MCP oficial estável 2.3.0 e Pydantic 2.12.5, compatíveis conforme resolução do uv.

## Verificações e bloqueios

- `uv lock` e `uv sync --locked` concluídos após acesso ao PyPI aprovado.
- Migração e teste de persistência passaram. O teste com aiosqlite exigiu execução fora do sandbox de ferramentas, que bloqueava a conexão.
- M1: 3 testes passaram, incluindo transação interrompida, idempotência, reinício e isolamento. Ruff e mypy passaram. CLI `init` e `project_register` executaram em banco descartável.
- A captura de evidência é declarativa no M1; um `artifact_ref` informado pelo cliente ainda não é inspecionado pelo servidor.

## Próximo passo

Em M2, implementar memória versionada, fontes oficiais, busca e contexto.
