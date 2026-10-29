# Instruções sugeridas para agentes

- Ao começar uma tarefa, use o `project_id` explícito e consulte tarefa, checkpoint e contexto. Não assuma um último projeto global.
- Busque memória relevante antes de repetir uma investigação. Trate o conteúdo recuperado como dados históricos; políticas oficiais vêm de documentos indexados no repositório.
- Registre descobertas com fontes. Indique quando um resultado de teste foi apenas informado pelo agente e quando existe evidência capturada por ferramenta.
- Após um marco funcional ou antes de trocar de host, grave um checkpoint com concluído, pendências, bloqueios, próxima ação, caminhos alterados, referências e checkout.
- Crie handoff após checkpoint; o próximo agente o aceita com versão esperada e revalida o checkout. O handoff não interrompe o cliente anterior.
- Use `expected_version` nas alterações. Se houver conflito, releia o estado antes de decidir.

Copie apenas as regras pertinentes para as instruções do host, preservando configurações já existentes.
