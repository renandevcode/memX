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

O MVP é desenvolvido em marcos M0–M4. Consulte [o estado da implementação](docs/IMPLEMENTATION-STATE.md) para o progresso real.
