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

Os testes usam clientes `mcp.Client` independentes em memória e a demo usa dois subprocessos reais via stdio, reiniciando o servidor entre A e B. Isso valida o protocolo e a persistência. Em uma sessão nativa do Codex no projeto `teste`, o agente chamou `memory_search` e `memory_read` e citou o registro e a versão usados. Resultados de lista usam o envelope `items` e escalares usam `result` no MCP.

Referência do SDK: https://py.sdk.modelcontextprotocol.io/run/ e https://py.sdk.modelcontextprotocol.io/client/.

Cada ferramenta publica agora o schema específico de `arguments`, com campos obrigatórios e tipos. Campos desconhecidos são rejeitados. Para ler memória, envie `project_id` e `record_id`, com `version` opcional. Reinicie a sessão do host para atualizar a lista de ferramentas. Erros estruturais de entrada são retornados pelo SDK com os campos inválidos; erros de domínio mantêm os códigos do serviço.

Projetos ativados por `memx init` fixam o `cwd` do servidor na raiz. Nesse modo, `project_id` pode ser omitido: o servidor o resolve pelo marcador local e rejeita identidades divergentes. A configuração nativa do Codex foi conferida com `codex mcp get memx --json`; um teste humano confirmou consulta espontânea e outro confirmou que o agente recusou consultar outro projeto. Uma chamada direta ao MCP com `project_id` divergente retornou `ACCESS_DENIED`. Esses testes não demonstram comportamento universal em outros hosts.
