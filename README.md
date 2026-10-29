# MemX

Memória persistente local para agentes de programação. O MemX guarda projetos, tarefas, decisões, fontes e checkpoints em SQLite para que um agente possa recuperar contexto e retomar trabalho entre sessões. O MVP usa Python 3.12 e não precisa de chave de modelo.

## Início rápido

Instale as dependências no repositório do MemX e ative a pasta do projeto que usará a memória:

```bash
cd /caminho/do/memoryX
uv sync --locked
MEMX_BIN="$PWD/.venv/bin/memx"

cd /caminho/do/projeto
"$MEMX_BIN" init
"$MEMX_BIN" call task_create '{"title":"OCR","objective":"Corrigir rotação","acceptance_criteria":["fixture passa"],"scope":"ocr"}'
```

`init` registra a pasta, grava sua identidade em `.memx.json`, acrescenta instruções a `AGENTS.md` e configura o servidor MCP em `.codex/config.toml`. Dentro da pasta ativada, CLI e MCP preenchem `project_id` automaticamente. Para usar o MemX no Codex, inicie `codex` nessa pasta depois da ativação; o Codex pode exigir confiança no projeto para carregar a configuração local.

Os dados ficam em `~/.local/share/memx` por padrão. Defina `MEMX_DATA_DIR` antes de `init` para usar outro diretório. Um valor diferente do registrado em `.memx.json` gera erro, evitando consultar outro banco por engano. A configuração gerada aponta para o Python desta instalação do MemX; preserve `.memx.json`, `AGENTS.md` e `.codex/config.toml` ao reutilizar o projeto.

## Uso local

`memx call` recebe o nome da operação e um objeto JSON com seus argumentos. Dentro de um projeto ativado, omita `project_id`; fora dele, informe o ID explicitamente. Use os IDs retornados para consultar ou atualizar tarefas, sessões e registros. Execute `"$MEMX_BIN" --help` para ver os comandos. Para aplicar apenas as migrações do banco, use `"$MEMX_BIN" db-init`.

Depois que houver memórias registradas, consulte-as com `"$MEMX_BIN" call memory_search '{"query":"OCR"}'` e leia o resultado com `memory_read`, passando o `id` encontrado como `record_id`. A busca comum mostra apenas registros ativos.

`source_index` importa arquivos UTF-8 indicados explicitamente sob a raiz do projeto, com limite de 64 KiB por arquivo. O argumento `kind` aceita `policies`, `decisions` e `project_map`. Políticas importadas são editadas no arquivo de origem, não pelo serviço. `context_build` reúne contexto para uma tarefa com orçamento medido em caracteres do JSON serializado, não em tokens. Fontes alteradas geram aviso, e o texto antigo de uma política não é apresentado como atual.

Consulte [operação local](docs/OPERATIONS.md) para backup, restauração, reindexação, exclusões e diagnóstico. A [revisão de arquitetura](docs/ARCHITECTURE-REVIEW.md) descreve o alcance e os limites do MVP, que cobre os marcos M0–M4. O [estado e próximo passo](docs/ROADMAP.md) registra a validação atual e o próximo objetivo.

## Integrações

O `init` configura o MCP stdio para o projeto ativado. Para conectar outro cliente manualmente, consulte [conexão MCP](docs/integrations/MCP.md) e [instruções sugeridas ao agente](docs/integrations/AGENT-INSTRUCTIONS.example.md). A consulta nativa com Codex foi validada em um projeto de teste; outros clientes podem se comportar de forma diferente.

Para a API HTTP local, defina `MEMX_HTTP_TOKEN` e execute `uv run --locked memx serve-http` no repositório do MemX. O servidor escuta apenas em loopback, por padrão `127.0.0.1:8765`; a documentação OpenAPI fica em `/docs`.

```bash
curl -H "Authorization: Bearer $MEMX_HTTP_TOKEN" -H 'Content-Type: application/json' \
  -d '{"schema_version":1,"arguments":{"project_id":"ID","task_id":"ID"}}' \
  http://127.0.0.1:8765/v1/task_read
```

## Desenvolvimento e demonstração

No repositório do MemX:

```bash
uv sync --locked
uv run --locked pytest
uv run --locked python examples/demo_ocr.py
```

A demonstração usa uma fixture sintética e dois clientes MCP stdio em processos separados. Ela verifica persistência e continuidade; não executa um algoritmo OCR real.

Se uma ativação for interrompida, execute `memx init` novamente com o mesmo diretório de dados. Gravações são atômicas e configurações equivalentes são reutilizadas. Configurações conflitantes são preservadas e exigem reconciliação explícita. Execute apenas uma ativação por projeto de cada vez.
