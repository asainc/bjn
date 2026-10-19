# BJN — Diagnóstico de configuração do text_generator

Data: 2026-10-19. Responsável técnico: a designar.

## Causa identificada

A aplicação habilitava a análise por `BRADESCO_TEXT_MODEL` e não esclarecia ao usuário que **identificador/senha são credenciais da Bridge**, enquanto `BRADESCO_QA_WORKFLOW_CODE` identifica o agente de perguntas e respostas, **não** o deployment de `text_generator`. Além disso, o componente podia interpretar a configuração ainda não carregada como uma indisponibilidade definitiva.

## Correções

1. `backend/services/bradesco_bridge.py`: status explícito de configuração, diferenciando `TEXT_MODEL_MISSING`, `BRIDGE_CREDENTIALS_MISSING` e `CONFIGURED_NOT_TESTED`. O status representa somente a configuração estática; não comprova acesso à rede, implantação ou permissão.
2. `backend/routers/bjn_demands.py`: `GET /api/v3/bjn/demandas/configuracao` acrescenta `ai_configuration` com `code`/`message`. **Nenhum valor secreto** é retornado.
3. `frontend/src/app/bjn/demands/demand-new.component.ts`: sem mensagem falsa antes da resposta da API, reprocessa arquivos selecionados durante o carregamento, e mostra a causa específica. Continua permitindo cadastro sem IA.
4. `frontend/src/app/bjn/demands/demand-detail.component.ts`: erros de configuração com a mesma classificação do backend.
5. `scripts/test_text_generator_connection.py`: modo `--check-only` (não realiza chamadas externas), modo padrão realiza teste sintético contra o serviço corporativo; retorna apenas presença booleana de credenciais.

## Configuração e execução

No arquivo `.env` da **raiz do projeto** `ai_ready_processual_civel_v3.1.0/.env`, configure as variáveis:

```dotenv
BRADESCO_IDENTIFICADOR=
BRADESCO_SENHA=
BRADESCO_TEXT_MODEL=
BRADESCO_QA_WORKFLOW_CODE=
```

O valor de `BRADESCO_TEXT_MODEL` deve ser o **nome do deployment de geração de texto homologado no ambiente corporativo**. Não reutilize o código do workflow Q&A. Não copie credenciais para a interface, mensagens, logs ou testes.

Reinicie a API após alterar o `.env`, pois as configurações são carregadas na inicialização. Para verificação local, a partir da raiz:

```powershell
python scripts/test_text_generator_connection.py --check-only
```

Um resultado `CONFIGURED_NOT_TESTED` informa apenas que os parâmetros obrigatórios foram carregados. Para testar o acesso real, com permissão da equipe de infraestrutura e rede corporativa, execute `python scripts/test_text_generator_connection.py`, que envia **apenas um texto sintético**, sem dados de clientes.

Se a IA continuar indisponível, verifique se `APP_ENV_FILE` ou variáveis de ambiente do serviço não apontam para outro arquivo/valor. Variáveis de ambiente do processo têm precedência sobre `.env` e sobre `config/app.settings.json`. A configuração precisa estar no backend, não no Angular.

## Testes e limitações

Testes automatizados cobrem configurações ausentes, resposta pública sem segredos, precedência de `.env` e atualização da interface. A disponibilidade real do deployment, autenticação na Bridge, certificados e autorização devem ser validadas no ambiente corporativo. A revisão dos prompts e documentos cabe ao time Jurídico/Compliance/DPO.
