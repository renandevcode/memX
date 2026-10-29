# Conexão MCP local

O servidor usa o SDK oficial Python MCP 2.3.0 em stdio. Configure o host MCP para iniciar, na raiz deste checkout:

```json
{
  "command": "uv",
  "args": ["run", "--locked", "memx-mcp"],
  "env": {"MEMX_DATA_DIR": "/caminho/para/dados"}
}
```

Use caminho absoluto para `uv` e `cwd` do checkout caso o host não herde esses valores. O host escolhe quando chamar as ferramentas; o servidor não controla o loop do agente. Cada ferramenta recebe `arguments`, um objeto JSON com os argumentos nomeados do serviço. Os identificadores `project_id`, `task_id` e `session_id` são explícitos. Erros de domínio retornam resultado MCP com `is_error=true` e código estável no texto. Nenhuma configuração pessoal é instalada automaticamente.

O teste automatizado usa dois clientes `mcp.Client` independentes contra objetos de servidor separados e o mesmo arquivo SQLite. Isso valida o protocolo MCP em memória, não a integração nativa de hosts como Codex ou Claude. A demo M4 exercitará também stdio em subprocessos.

Referência do SDK: https://py.sdk.modelcontextprotocol.io/run/ e https://py.sdk.modelcontextprotocol.io/client/.
