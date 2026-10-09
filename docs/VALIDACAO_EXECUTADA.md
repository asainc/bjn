# Validação executada em 2026-10-01

## Executado com sucesso

- `pytest -q`: 6 testes de backend aprovados.
- `python scripts/validate_architecture.py`: arquitetura executável aprovada.
- Smoke HTTP com `TestClient`: `GET /api/v3/saude` e `GET /api/v3/ai-ready/configuracao` responderam conforme o contrato 3.0.0.
- Comparação AST com o ZIP original: a função `gpt_bradesco.text_generator` foi preservada exatamente.
- `npm --prefix frontend test`: 3 testes estruturais do frontend aprovados.
- `npm --prefix frontend run prebuild`: baseline Angular 21.2.19 e dependências declaradas validados pelo script do projeto.

## Não executado neste ambiente

O `ng build` de produção não foi concluído porque o ZIP fornecido não contém `node_modules` nem `package-lock.json` corporativo. Uma tentativa de instalação externa das dependências não concluiu dentro do ambiente de validação e não foi usada como evidência de build.

Antes de publicar, instale as dependências pelo Nexus/lock corporativo aprovado, conforme `docs/INSTALACAO_FRONTEND_NEXUS_TARBALLS.md`, e execute:

```bash
cd frontend
npm run build
```

Essa limitação não afeta os testes do backend nem a confirmação de preservação do `text_generator`, mas o bundle Angular final deve ser compilado no ambiente corporativo antes do deploy.

## Correção 3.0.1 — compatibilidade Python

Após o relato de incompatibilidade por pins exatos, foram executadas validações adicionais:

- o validador foi executado no runtime disponível e concluiu como compatível;
- foi adicionado teste de regressão simulando `FastAPI 0.121.2`, `Starlette 0.49.3`, `Pydantic 2.13.4`, `Requests 2.32.5`, `Uvicorn 0.38.0` e `chardet 7.4.0.post2`;
- nesse cenário, o retorno esperado e obtido é sucesso, com `chardet` tratado somente como aviso;
- foi adicionado um segundo cenário que confirma que uma versão de Starlette fora da faixa declarada pelo FastAPI continua sendo rejeitada.

A mudança 3.0.1 não alterou o contrato HTTP da API; somente a versão da aplicação passou para `3.0.1`.

## Correção 3.0.2

- Teste estrutural confirma uso consistente de `documento` no template Angular.
- Teste do runner confirma importação de `backend.principal` mesmo após iniciar fora da raiz do projeto.
- O orquestrador local aguarda `/api/v3/saude`, alinhado a `API_PREFIX`.

## Correção 3.0.3 — chatbot flutuante

- `node --test frontend/tests/*.test.cjs`: 6 testes estruturais aprovados.
- `pytest -q`: 7 testes de backend aprovados.
- `python -m compileall -q backend scripts tests`: compilação sintática Python aprovada.
- Teste de regressão confirma que o launcher não depende de `workspace()` para ser exibido/aberto.
- Teste de regressão confirma deslocamento pela variável `--app-sidebar-width` e `z-index` superior ao visualizador de PDF.
- O `ng build` completo continua dependente da instalação das dependências Angular no ambiente corporativo; o pacote não inclui `node_modules`.


## Versão 3.1.0 — integração do chatbot com Q&A

- Testes Python: 10 aprovados.
- Testes estruturais do frontend: 6 aprovados.
- `scripts/validate_architecture.py`: aprovado.
- Smoke test de `POST /api/v3/ai-ready/chat`: HTTP 200 com serviço simulado.
- Teste de regressão confirma que a pergunta é encaminhada sem reescrita para `agente_informacional`.
- Teste de regressão confirma que o retorno `answer` é convertido em `resposta` para o frontend.
- O build Angular completo depende das dependências npm corporativas do ambiente de execução; os testes estruturais não substituem esse build.
