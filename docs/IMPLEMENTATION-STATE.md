# Estado da implementação

## Branch e base

- Atual: `feat/m0-foundation`, derivada de `main` (`e599ab3`).
- Branches seguintes serão derivadas da entrega anterior até integração explícita na main.
- Os dois anexos originais estavam fora do controle de versão e foram preservados no local.

## Progresso

- M0 concluído: ambiente Python 3.12 isolado, dependências fixadas, migração inicial e cadastro/leitura explícitos de projeto.
- M1–M4 pendentes.

## Decisões

- SQLite local, dados em `~/.local/share/memx` por padrão; testes usam arquivos temporários.
- Migrações Alembic versionadas; nenhuma criação implícita de tabelas na inicialização.
- MCP oficial estável 2.3.0 e Pydantic 2.12.5, compatíveis conforme resolução do uv.

## Verificações e bloqueios

- `uv lock` e `uv sync --locked` concluídos após acesso ao PyPI aprovado.
- Migração e teste de persistência passaram. O teste com aiosqlite exigiu execução fora do sandbox de ferramentas, que bloqueava a conexão.
- Nenhum bloqueio funcional conhecido.

## Próximo passo

Validar e registrar M0. Em M1, implementar tarefa, sessão, evento, evidência e checkpoint transacional.
