# Changelog

## 3.0.3 - 2026-10-01

- Corrigido o posicionamento do balão do chatbot para respeitar a largura da barra lateral e permanecer no canto inferior esquerdo da área útil do AI Ready.
- O chatbot agora fica acima do visualizador de PDF e continua acessível durante a conferência dos documentos.
- O balão passa a ser sempre visível e pode ser aberto antes da análise; nesse estado, a janela explica como habilitar as perguntas.
- O envio de mensagens permanece bloqueado até existir um workspace analisado, evitando chamadas sem contexto documental.
- Adicionados atributos de acessibilidade e teste de regressão específico para visibilidade/empilhamento do chatbot.

## 3.0.2 - 2026-10-01

### Correções
- Corrigidas referências Angular `document` para o contrato oficial `documento` na linha do tempo e nas fontes do chat.
- O iniciador do backend agora adiciona a raiz do projeto ao `sys.path` e ao `PYTHONPATH`, permitindo execução a partir de qualquer diretório e evitando `ModuleNotFoundError: backend`.
- Corrigido o health check do orquestrador local de `/api/v2/saude` para `/api/v3/saude`.
- Removidas referências de inicialização à pasta inexistente `src`; o `PYTHONPATH` local usa somente a raiz real do projeto.
- Adicionados testes de regressão para os três cenários.

## 3.0.1 — 2026-10-01

- Corrigida a validação do runtime Python para aceitar versões funcionalmente compatíveis em vez de exigir igualdade exata com o `requirements.lock`.
- Ajustadas as dependências do `pyproject.toml` para faixas compatíveis, evitando upgrades desnecessários em ambientes corporativos já válidos.
- Removido o pin independente de Starlette; a compatibilidade passa a seguir a restrição declarada pela versão de FastAPI instalada.
- `chardet >= 6` deixou de bloquear a inicialização. O projeto não depende de chardet e orienta o uso de `charset-normalizer` em ambiente isolado.
- `requirements.lock` passou a representar um ambiente de referência reproduzível baseado em FastAPI 0.121.2, Pydantic 2.13.4, Requests 2.32.5 e Uvicorn 0.38.0.

## 3.0.0 — 2026-10-01

- Removido o domínio anterior de auditoria financeira e seus módulos executáveis.
- Removido o pacote de motor financeiro e seus dados auxiliares.
- Criada a tela AI Ready para upload múltiplo de PDFs de processos cíveis.
- Adicionados resumo processual, partes, pedidos, fatos controvertidos, pontos de atenção e linha do tempo com referência documental.
- Adicionado visualizador local dos PDFs selecionados.
- Adicionado chatbot flutuante no canto inferior esquerdo.
- Mantida a geração de linguagem por `gpt_bradesco.text_generator` através de `BradescoBridgeClient`.
- Adicionado workspace temporário em memória com TTL, descarte explícito e limites de volume.
- Atualizados contratos HTTP, documentação, testes e identidade do pacote para AI Ready.


## 3.0.4
- Ícone flutuante do chatbot reposicionado para o canto inferior direito.
- Janela do chat reposicionada para abrir à direita.


## 3.1.0 — Chatbot integrado à API Q&A
- O chatbot deixou de usar `text_generator` e passou a chamar `gpt_bradesco.agente_informacional(payload)`.
- A pergunta digitada é enviada sem reescrita no campo `question`.
- O payload inclui o `workflow_code` fornecido e `async_mode: false`.
- A resposta exibida no chat é o conteúdo do campo `answer` retornado pela API.
- O chat foi desacoplado do workspace de PDFs e pode ser usado sem executar a análise documental.
- `BRADESCO_QA_WORKFLOW_CODE` e `BRADESCO_QA_URL` foram parametrizados.
- O endpoint fornecido foi tratado como confirmado apenas em DEV; homol/prod exigem URL explicitamente validada.
