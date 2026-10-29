# Exemplo mínimo

`python app.py` imprime uma saudação em português.

Para testar o MemX sem modificar este repositório, copie esta pasta para um
diretório temporário. Com as dependências do MemX instaladas, execute na cópia
(ajuste o caminho da instalação):

```bash
MEMX_BIN=/caminho/do/memoryX/.venv/bin/memx
"$MEMX_BIN" init
"$MEMX_BIN" call memory_create '{"category":"decisions","title":"Idioma","body":"A saudação deste exemplo é em português.","status":"active"}'
"$MEMX_BIN" call memory_search '{"query":"saudação"}'
```

Depois, inicie o Codex na pasta ativada e peça: “Qual idioma a saudação usa?
Consulte a memória deste projeto e cite o ID e a versão.” Verifique se o Codex
carregou o servidor MCP local antes de usar a resposta como validação do host.
