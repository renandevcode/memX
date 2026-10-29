# Estado e próximo passo

Atualizado em 29/10/2026. O MVP M0–M4 e o README revisado estão integrados à
`main`. A [revisão de arquitetura](ARCHITECTURE-REVIEW.md) registra os limites
observados; [operação local](OPERATIONS.md) cobre backup, migrações e diagnóstico.

## MVP entregue

- M0: ambiente Python 3.12, SQLite local, migrações e cadastro de projeto.
- M1: tarefas, sessões, eventos, evidências, checkpoints e CLI.
- M2: memórias versionadas, fontes, busca FTS5 e contexto com orçamento.
- M3: handoff, API HTTP local com token e MCP stdio.
- M4: demo entre processos, contratos de entrada e saída, ativação por projeto,
  logs estruturados e procedimentos de operação.

## Validação de isolamento

O teste `tests/test_project_isolation.py` ativa duas pastas no mesmo banco e
inicia um processo MCP em cada uma. Cada processo grava e encontra apenas a
própria memória; leitura cruzada e ID explícito de outro projeto são rejeitados.
Em 29/10/2026, a suíte passou com 23 testes, e Ruff e mypy passaram. Esse teste
mede o comportamento do serviço e do vínculo MCP, não a decisão espontânea do
agente de consultar a ferramenta.

## Próximo objetivo: piloto em segundo projeto

Validar a experiência completa com Codex em um segundo projeto real, sem
modificar o projeto de teste anterior. O piloto estará concluído quando:

1. Cada projeto tiver uma decisão própria registrada no MemX.
2. Uma conversa Codex iniciada em cada pasta recuperar e citar a decisão local
   com ID e versão corretos.
3. Uma pergunta sobre a decisão do outro projeto não produzir uma resposta
   baseada naquela memória como se fosse local.
4. As chamadas MCP e as respostas forem registradas, junto com quaisquer
   limites observados. Uma falha reproduzível deve gerar teste de regressão.

O host decide quando usar MCP. A ativação configura o servidor e as instruções
de projeto, mas não garante que toda resposta consulte a memória. O teste
automatizado acima cobre o isolamento do serviço; o piloto cobre o uso real
do agente.
