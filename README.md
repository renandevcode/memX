# MemX

Memória persistente local para agentes de programação. Implementação inicial em Python 3.12.

## Ambiente

```bash
uv sync --locked
uv run --locked pytest
```

Os dados operacionais ficam em `~/.local/share/memx` por padrão. Defina `MEMX_DATA_DIR` para outro local. Nenhuma chave de modelo é necessária.

O MVP é desenvolvido em marcos M0–M4. Consulte [o estado da implementação](docs/IMPLEMENTATION-STATE.md) para o progresso real.
