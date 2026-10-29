# Estado da implementação

## Branch e base

- Atual: `feat/project-activation`, derivada de `feat/m4-demo-validation` (`5c092bd`), ainda não integrada na main.
- Branches seguintes serão derivadas da entrega anterior até integração explícita na main.
- Os dois anexos originais estavam fora do controle de versão e foram preservados no local.

## Progresso

- M0 concluído: ambiente Python 3.12 isolado, dependências fixadas, migração inicial e cadastro/leitura explícitos de projeto.
- M1 concluído: tarefa, sessão, evento idempotente, evidência declarativa, checkpoint atômico e CLI local.
- M2 concluído: registros versionados, documentos oficiais indexados, FTS5 e contexto com limite de caracteres.
- M3 concluído: handoff persistente, API HTTP local com token e MCP stdio via SDK oficial.
- M4 parcialmente concluído: demo com dois subprocessos MCP stdio passa; suíte com 8 testes passa, Ruff e mypy passam.
- M4 ainda exige revisão de conformidade arquitetural, contratos por operação, observabilidade, operação e validação de atualização de migração.

## Decisões

- SQLite local, dados em `~/.local/share/memx` por padrão; testes usam arquivos temporários.
- Migrações Alembic versionadas; nenhuma criação implícita de tabelas na inicialização.
- MCP oficial estável 2.3.0 e Pydantic 2.12.5, compatíveis conforme resolução do uv.

## Verificações e bloqueios

- `uv lock` e `uv sync --locked` concluídos após acesso ao PyPI aprovado.
- Migração e teste de persistência passaram. O teste com aiosqlite exigiu execução fora do sandbox de ferramentas, que bloqueava a conexão.
- M1: 3 testes passaram, incluindo transação interrompida, idempotência, reinício e isolamento. Ruff e mypy passaram. CLI `init` e `project_register` executaram em banco descartável.
- A captura de evidência é declarativa no M1; um `artifact_ref` informado pelo cliente ainda não é inspecionado pelo servidor.
- M2: 5 testes passaram. Busca por projeto/escopo, histórico, exclusão e reconstrução do índice, política obrigatória, fonte alterada, symlink fora da raiz e orçamento foram verificados. Ruff e mypy passaram.
- M3: 7 testes passaram, incluindo dois clientes MCP em memória e corrida por duas conexões SQLite. Ruff e mypy passaram. A integração nativa com hosts externos ainda não foi testada; stdio em subprocesso será testado na demo M4.

## Próximo passo

Completar M4 antes de considerar o MVP integralmente entregue. Lacunas conhecidas: serviços ainda dependem de SQLAlchemy; não há DTO específico por operação; expansão de relações no contexto, configuração de exclusões, logs estruturados e transições completas de tarefa ainda precisam ser implementados. Validar migração de atualização, além da criação de banco vazio já exercitada nos testes. Nenhum host nativo externo foi validado.

## Incremento de demo validado

- Robustez da ativação: escrita atômica por arquivo e retomada por reexecução após falha entre arquivos. Configuração TOML existente é comparada semanticamente; blocos equivalentes são reutilizados, conflitos são preservados e rejeitados. Symlinks são verificados antes de ler o marcador. Três testes de ativação passaram, incluindo falha injetada; Ruff e mypy passaram. Ainda não há exclusão mútua para duas ativações simultâneas.

- Ativação inicial por projeto: `memx init --root CAMINHO` cadastra/reutiliza a raiz, grava `.memx.json`, acrescenta configuração MCP em `.codex/config.toml` e instruções em `AGENTS.md`. `memx db-init` mantém a preparação exclusiva do banco. 10 testes passaram; Ruff e mypy passaram. Validação nativa Codex, recuperação de falhas parciais e reconciliação de configuração existente ainda pendentes. A presença das instruções não garante captura automática pelo host.

- Correção de contrato MCP: descrições agora enumeram parâmetros reais; argumentos incorretos retornam `INVALID_INPUT` com indicação do campo obrigatório. `memory_read` exige `record_id`. Teste dedicado passou; Ruff e mypy passaram. Schemas específicos por operação continuam pendentes.

- Executar: `uv run --locked python examples/demo_ocr.py`.
- `uv run --locked pytest -q`: 8 testes passaram, incluindo a demo em subprocessos reais.
- Ruff e mypy passaram após as correções dos retornos MCP de listas e escalares.
- Evidência exige arquivo sob a raiz, hash correspondente e limite de tamanho; permanece `unverified`, pois o teste OCR é uma fixture sintética.
- Eventos rejeitam campos sensíveis também em estruturas aninhadas. Isso não constitui detecção completa de segredos.
