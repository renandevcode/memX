# MemX

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

O MVP é desenvolvido em marcos M0–M4. Consulte [o estado da implementação](docs/IMPLEMENTATION-STATE.md) para o progresso real.
