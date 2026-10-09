# Configuração

As configurações não sensíveis ficam em `config/app.settings.json`. Credenciais devem ser fornecidas por `.env` local não versionado ou variáveis de ambiente.

Variáveis principais:

- `BRADESCO_TEXT_MODEL`: deployment corporativo usado pelo `text_generator`.
- `BRADESCO_AMBIENTE`: `dev`, `homol` ou `prod`.
- `BRADESCO_IDENTIFICADOR` e `BRADESCO_SENHA`, ou `BRADESCO_AUTHORIZATION_TOKEN`: autenticação conforme o ambiente.
- `BRADESCO_CA_BUNDLE`: caminho opcional para bundle corporativo de CA.
- `MAX_UPLOAD_BYTES`: limite por PDF.
- `MAX_UPLOAD_FILES`: quantidade de PDFs por análise.
- `MAX_TOTAL_UPLOAD_BYTES`: limite total do conjunto enviado em uma análise.
- `WORKSPACE_TTL_MINUTES`: tempo máximo do contexto em memória.
- `BRADESCO_PROMPT_MAX_CHARS`: orçamento máximo aproximado de caracteres para cada trecho analisado.
- `MAX_ANALYSIS_CHUNKS`: quantidade máxima de trechos por análise; ao exceder, a API pede divisão do conjunto em vez de truncar silenciosamente.

Não versionar segredos, tokens ou PDFs reais de produção.
