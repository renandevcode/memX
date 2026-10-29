# Operação local do MemX

O MemX usa SQLite em `~/.local/share/memx/memx.sqlite3` por padrão. Defina
`MEMX_DATA_DIR` para outro diretório antes de iniciar CLI, HTTP ou MCP. Cada
projeto ativado guarda o diretório escolhido em `.memx.json`; usar outro banco
nesse projeto é rejeitado. Não inclua o banco nem backups no repositório.

## Preparação e atualização

Execute `memx db-init` antes do primeiro uso e após atualizar o código. Esse
comando aplica as migrações Alembic até a revisão atual. Faça um backup antes de
atualizar uma instalação com dados. O teste automatizado cobre a passagem de
`0001` para `0002` com um projeto preexistente e a reexecução da migração.

## Backup consistente

Use a API de backup do SQLite, inclusive quando o banco estiver em modo WAL.
Defina um destino fora do diretório de dados e execute:

```bash
MEMX_BACKUP_PATH=/caminho/seguro/memx-backup.sqlite3 \
  python3 - <<'PY'
import os
import sqlite3
from pathlib import Path

data_dir = Path(os.environ.get("MEMX_DATA_DIR", Path.home() / ".local/share/memx"))
destination = Path(os.environ["MEMX_BACKUP_PATH"])
destination.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(data_dir / "memx.sqlite3") as source:
    with sqlite3.connect(destination) as backup:
        source.backup(backup)
        assert backup.execute("PRAGMA quick_check").fetchone() == ("ok",)
print(destination)
PY
```

Proteja o backup com as mesmas permissões do banco. Ele pode conter versões e
conteúdo que já foram excluídos do banco ativo.

## Restauração

Pare todos os clientes MCP, a API HTTP e a CLI antes de substituir o banco.
Conserve uma cópia do banco atual. Verifique `PRAGMA quick_check` no backup e
copie o arquivo para `MEMX_DATA_DIR/memx.sqlite3` somente com os clientes
parados. Execute `memx db-init` depois da restauração para aplicar migrações
pendentes. Confirme a identidade do projeto com `memx call project_read` antes
de retomar o uso. Um backup anterior a uma exclusão recoloca os dados excluídos.

## Busca e reindexação

Se o índice FTS estiver inconsistente, execute `memx call memory_reindex` com o
`project_id` explícito fora de um projeto ativado, ou sem ele dentro da pasta
ativada. A reindexação reconstrói somente versões atuais de registros vivos;
não ressuscita registros excluídos. Verifique uma busca conhecida depois.

`task_transition` altera o estado da tarefa com `expected_version` e motivo.
Os estados terminais são `done` e `cancelled`. `done` exige evidência verificada
ou `human_exception` explícita; o motivo e a exceção ficam na auditoria. Um
checkpoint só é aceito em `todo`, `in_progress` ou `blocked`.

## Exclusão e retenção

`memory_archive` retira o registro da busca comum e mantém versões.
`memory_delete` remove versões do registro de banco e entradas do índice, mas
não apaga backups, histórico Git, documentos oficiais do repositório ou
artefatos externos. Para um documento oficial, edite ou remova o arquivo no
repositório e reindexe a fonte. O operador deve tratar backups conforme sua
política de retenção. O MVP não executa limpeza automática.

## Diagnóstico

CLI, HTTP e MCP emitem uma linha JSON por operação em stderr com `request_id`,
`project_id`, `operation`, `duration_ms`, `schema_version` e `code`. Corpos,
argumentos, tokens e detalhes de erro não entram no log. A API HTTP exige
`MEMX_HTTP_TOKEN` e aceita apenas endereço de loopback. O MCP é local via stdio.

`MEMX_EXCLUDED_PATHS` aceita uma lista JSON de padrões de caminho, por exemplo
`[".env","secrets/**","*.pem","private/**"]`. Os padrões valem para indexação
de fontes, artefatos, caminhos alterados e campos de caminho em eventos. A
configuração substitui os padrões padrão; inclua os padrões de proteção que
quiser manter. Os limites de tamanho continuam aplicados independentemente.
