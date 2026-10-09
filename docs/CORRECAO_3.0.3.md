# Correção 3.0.3 — visibilidade do chatbot flutuante

## Problema observado

O balão do chatbot podia não ficar visível no uso normal da tela do AI Ready por três motivos de interface:

1. o posicionamento `left` considerava a janela inteira e podia colocar o botão sobre a barra lateral da plataforma;
2. o visualizador de PDF utilizava uma camada visual superior ao chatbot;
3. o botão ficava desabilitado enquanto ainda não existia um workspace analisado, tornando a descoberta da funcionalidade pouco clara.

## Correção aplicada

- A largura atual da barra lateral é exposta pela variável CSS `--app-sidebar-width`.
- O botão e a janela do chat usam essa variável para se posicionarem dentro da área útil da aplicação.
- Os níveis de empilhamento do chat foram elevados para permanecerem acima do visualizador de PDF.
- O balão permanece sempre visível e pode ser aberto mesmo sem análise concluída.
- Antes de existir um workspace, o chat mostra uma orientação para upload/análise e mantém o campo de pergunta desabilitado.
- O envio de mensagens continua condicionado à existência de um `workspace_id`, evitando chamadas ao backend sem contexto documental.

## Comportamento esperado

Ao entrar em `/ai-ready`, o balão circular `AI` deve aparecer no canto inferior esquerdo da área de conteúdo. Ao abrir um PDF, o balão deve continuar visível. Ao recolher ou expandir a barra lateral, o botão acompanha a largura da navegação. Em telas pequenas, o botão permanece a 14 px da borda esquerda.
