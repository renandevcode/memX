# MemX

Ativação inicial em outro projeto (implementação ainda em validação):

```bash
cd /caminho/do/jogo
/home/renan/Documentos/memoryX/.venv/bin/memx init
codex
```

O comando associa a pasta ao banco externo, acrescenta instruções em `AGENTS.md` e configura o MCP local em `.codex/config.toml`. Preserve esses arquivos; o caminho do Python gerado é específico desta instalação. O Codex pode exigir confiança no projeto para carregar sua configuração. O fluxo nativo ainda não foi validado. Para apenas migrar o banco, use `memx db-init`.

Se uma gravação da ativação falhar, execute `memx init` novamente com o mesmo diretório de dados. Arquivos são substituídos atomicamente e configurações equivalentes são reutilizadas. Configurações conflitantes são preservadas e geram erro para reconciliação explícita. Execute apenas uma ativação por projeto de cada vez.

Para executar a demo OCR com dois clientes MCP stdio em processos separados:

```bash
uv sync --locked
uv run --locked python examples/demo_ocr.py
```

A fixture é sintética e usa dados temporários. O teste verifica persistência e continuidade; não executa um algoritmo OCR real. O MVP ainda tem lacunas registradas em `docs/IMPLEMENTATION-STATE.md`.

Memória persistente local para agentes de programação. Implementação inicial em Python 3.12.

## Ambiente

```bash
uv sync --locked
uv run --locked pytest
```

Os dados operacionais ficam em `~/.local/share/memx` por padrão. Defina `MEMX_DATA_DIR` para outro local. Nenhuma chave de modelo é necessária.

## CLI local

```bash
uv run --locked memx init
uv run --locked memx call project_register '{"root":"/caminho/para/projeto","name":"Exemplo"}'
uv run --locked memx call task_create '{"project_id":"ID","title":"OCR","objective":"Corrigir rotação","acceptance_criteria":["fixture passa"],"scope":"ocr"}'
```

O comando `call` recebe um objeto JSON com os argumentos nomeados do serviço. IDs retornados devem ser passados explicitamente nas operações seguintes. `memx --help` lista comandos.

## Fontes e contexto

`source_index` importa apenas arquivos UTF-8 explicitamente indicados sob a raiz do projeto (até 64 KiB por arquivo). `kind` aceita `policies`, `decisions` e `project_map`. Arquivos de política importados são somente leitura pelo serviço e precisam ser editados no repositório de origem. O contexto é construído por `context_build` com `project_id`, `task_id`, `query` e `budget_chars`. O orçamento mede caracteres do JSON serializado, não tokens de um modelo. Fonte alterada gera aviso e o texto antigo da política não é fornecido como atual.

`memory_delete` elimina versões e índice FTS do registro de banco, mas não apaga backups, histórico Git ou artefatos externos. `memory_reindex` reconstrói o índice apenas a partir de registros vivos. Dados sensíveis já presentes em backups exigem tratamento separado pelo operador.

## HTTP e MCP

Para HTTP local, defina `MEMX_HTTP_TOKEN` e execute `uv run --locked memx serve-http`. O servidor escuta apenas em loopback, por padrão `127.0.0.1:8765`. Exemplo:

```bash
curl -H "Authorization: Bearer $MEMX_HTTP_TOKEN" -H 'Content-Type: application/json' \
  -d '{"schema_version":1,"arguments":{"project_id":"ID","task_id":"ID"}}' \
  http://127.0.0.1:8765/v1/task_read
```

OpenAPI fica em `/docs`. Para MCP stdio, use `uv run --locked memx-mcp`; consulte [conexão manual](docs/integrations/MCP.md) e [instruções sugeridas ao agente](docs/integrations/AGENT-INSTRUCTIONS.example.md).

O MVP é desenvolvido em marcos M0–M4. Consulte [o estado da implementação](docs/IMPLEMENTATION-STATE.md) para o progresso real.
