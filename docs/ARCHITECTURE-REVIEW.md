# Revisão de arquitetura do MVP

Revisão em 29/10/2026, sobre a branch `feat/project-binding`. Esta revisão
registra o que a implementação demonstra e onde ainda diverge da
`ESPECIFICACAO-TECNICA (1).md`. Os testes de aceitação não provam ganho de
produtividade, segurança multiusuário ou compatibilidade com todos os hosts.

| Fronteira | Estado observado |
| --- | --- |
| Projeto | `.memx.json` vincula raiz, ID e banco; CLI/MCP rejeitam ID ou banco conflitante. |
| Persistência | SQLite local, migrações Alembic 0001/0002; atualização com dados preexistentes testada. |
| Contratos | Entrada e saída por operação com tipos estritos; HTTP publica OpenAPI específico por rota. |
| Memória | Versões, busca FTS, arquivamento, exclusão e reindexação; fontes do repositório são somente leitura via API. |
| Continuidade | Eventos idempotentes, checkpoints transacionais, handoff com compare-and-swap e transições de tarefa versionadas. |
| Contexto | Políticas obrigatórias, orçamento medido no JSON serializado, verificação de fonte e expansão de uma relação explícita com limite de dez itens. |
| Observabilidade | Linha JSON por operação com ID, projeto, duração, contrato e código; sem argumentos e corpos. |
| Operação | Procedimentos de backup, restauração, migração, reindexação e exclusão em `docs/OPERATIONS.md`. |

## Fronteira de armazenamento e dívida restante

`application.storage` define uma porta pequena de sessão/transação; o adaptador
`infrastructure.db` implementa essa porta com SQLAlchemy. A aplicação não
importa mais SQLAlchemy diretamente. A suíte de aceitação passou após essa
mudança.

As consultas SQL e o conhecimento do schema ainda estão em
`application/{service,memory,handoff}.py`. Portanto, a aplicação continua
acoplada ao modelo relacional e não há uma troca de banco pronta. A próxima
refatoração arquitetural, se outro backend for necessário, é mover consultas
para um repositório com operações de domínio e deixar validações, permissão,
estado e seleção de contexto na aplicação. A função `text()` da porta só
transporta a string; ela não resolve esse acoplamento. Não há migração para
PostgreSQL implícita ou prometida neste MVP local.

## Limites operacionais

- O host decide quando chamar MCP; as instruções de projeto não garantem captura automática.
- Evidência criada pelo cliente permanece `unverified`. Uma tarefa só passa a
  `done` com evidência `verified` ou exceção humana explícita registrada.
- Logs não incluem conteúdo, mas IDs de projeto e operação podem ser dados
  operacionais; proteja o destino de stderr.
- O backup pode reter conteúdo excluído; exclusão forense e de histórico Git
  ficam fora do escopo do MVP.
- A expansão de relações usa somente arestas explícitas de saída, uma camada,
  no projeto e escopo da tarefa; não é uma busca geral em grafo.
