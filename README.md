# AI Ready — Assistente Processual Cível

Aplicação Angular + FastAPI para leitura assistida de PDFs de processos cíveis. O produto organiza os autos em uma visão executiva, monta uma linha do tempo com referências de documento/página e oferece um chatbot integrado à API corporativa de perguntas e respostas.

## O que foi removido

A versão atual não contém a antiga aplicação de auditoria de pagamentos, histórico de cálculos, motor financeiro, parcelas, índices financeiros, taxas, atualização monetária ou integração com fontes externas de índices. Esses módulos foram removidos da árvore do backend, frontend, testes, dados e configuração.

## Funcionalidades atuais

- Upload múltiplo de PDFs.
- Validação de tipo, tamanho, assinatura PDF e quantidade de páginas.
- Extração local da camada textual com PyMuPDF.
- Análise hierárquica de documentos extensos.
- Resumo factual do processo.
- Identificação de classe, tribunal, unidade, fase, assunto, valor da causa e partes quando presentes.
- Pedidos, fatos controvertidos, pontos de atenção e próximas verificações.
- Linha do tempo com categoria, documento, página e indicador de confiança.
- Visualização local dos PDFs no navegador.
- Chat flutuante no canto inferior direito.
- Análise documental utilizando `gpt_bradesco.text_generator`.
- Chatbot utilizando `gpt_bradesco.agente_informacional(payload)` e apresentando o campo `answer` retornado pela API Q&A.
- Descarte explícito do workspace e expiração automática do texto mantido em memória.

## Arquitetura resumida

```text
Angular 21
  └─ AI Ready workspace
      ├─ upload/preview local de PDFs
      ├─ resumo e timeline
      └─ chat flutuante
            │
            ▼
FastAPI /api/v3
  ├─ validação de upload
  ├─ PyMuPDF
  ├─ ProcessIntelligenceService
  ├─ WorkspaceStore (memória + TTL)
  ├─ BradescoBridgeClient
  │     ├─ gpt_bradesco.text_generator        ← análise dos PDFs
  │     └─ gpt_bradesco.agente_informacional ← chatbot Q&A
  └─ ChatService
```

Detalhes: `docs/ARQUITETURA.md` e `docs/FLUXO_EXTRACAO_VISUAL.md`.

## Estrutura principal

```text
backend/
  contracts/                 contratos HTTP
  routers/processes.py       endpoints do AI Ready
  services/
    bradesco_bridge.py       fachada para text_generator e agente_informacional
    chat_service.py           encaminhamento das perguntas do chatbot
    pdf_text_extractor.py    leitura local do PDF
    process_intelligence.py  análise e consolidação dos PDFs
    prompt_loader.py         leitura dos prompts versionados
    workspace_store.py       contexto temporário em memória
  config.py                  configuração central
  principal.py               aplicação FastAPI

frontend/src/app/
  ai-ready/                  tela principal
  core/                      contratos, configuração e API
  templates/                 página BJN preservada

prompts/
  analise_trecho.md
  consolidacao_processo.md
```

## Pré-requisitos

- Python 3.12 ou 3.13.
- Node.js conforme `frontend/.node-version` e política do ambiente corporativo.
- Acesso ao deployment corporativo configurado para `gpt_bradesco.py`.

## Compatibilidade do ambiente Python

A aplicação **não exige mais que o runtime tenha exatamente as mesmas versões do `requirements.lock`**. Existem dois usos diferentes:

- `requirements.lock`: referência para criar uma `.venv` nova e reproduzível.
- `scripts/check-python-environment.py`: valida se um ambiente já existente está dentro das faixas realmente suportadas pelo código.

Por exemplo, o conjunto abaixo é aceito pelo projeto:

```text
FastAPI 0.121.2
Starlette 0.49.3
Pydantic 2.13.4
Requests 2.32.5
Uvicorn 0.38.0
```

O projeto também deixou de fixar `Starlette` de forma independente. A versão de Starlette deve respeitar o intervalo declarado pela versão de FastAPI instalada, evitando conflitos artificiais entre os dois pacotes.

### Sobre `chardet`

O AI Ready não depende de `chardet`. `Requests 2.x` usa `charset-normalizer` no ambiente recomendado. Se uma estação corporativa compartilhada possuir `chardet >= 6`, o validador apenas apresenta um **aviso** e não bloqueia a API.

Em uma `.venv exclusiva` do projeto, se `chardet` tiver sido instalado por outro processo, ele pode ser removido para evitar o aviso emitido pelo próprio Requests:

```bash
python -m pip uninstall chardet
python -m pip install "charset-normalizer>=2,<4"
```

Não remova `chardet` automaticamente de um Python compartilhado sem verificar se outro sistema depende dele.

### Instalação recomendada no Windows

Para criar uma nova `.venv` a partir da referência validada:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.lock
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe scripts\check-python-environment.py
```

Se o ambiente corporativo já possui as dependências, primeiro execute apenas:

```powershell
python scripts\check-python-environment.py
```

Se a saída for `Dependências Python compatíveis`, não é necessário substituir patches apenas para coincidir com o lock.

## Configuração do backend

1. Copie `.env.example` para `.env` somente no ambiente local.
2. Preencha o deployment e a autenticação corporativa sem versionar segredos.
3. Revise `config/app.settings.json` para limites não sensíveis.

Exemplo de configuração mínima:

```env
APP_ENV=local
BRADESCO_AMBIENTE=dev
BRADESCO_TEXT_MODEL=<deployment_autorizado>
BRADESCO_IDENTIFICADOR=<segredo_no_ambiente>
BRADESCO_SENHA=<segredo_no_ambiente>
BRADESCO_QA_WORKFLOW_CODE=CD_WRFL_QA_778_LEITURA_SENTENCA_PIAUI_AAJR_SYNC
```

O projeto também aceita token conforme o contrato já implementado em `gpt_bradesco.py`.

## Execução

Backend:

```bash
python scripts/run_backend.py --reload
```

Frontend:

```bash
cd frontend
npm install
npm start
```

Abra `http://127.0.0.1:4200`. O arquivo `frontend/public/app-config.json` aponta para `/api/v3`, e o proxy local encaminha para a API em `127.0.0.1:8000`.

## Fluxo completo

1. O advogado seleciona um ou mais PDFs.
2. O Angular valida extensão/tamanho básico e mantém `ObjectURL` apenas para visualização local.
3. `POST /api/v3/ai-ready/analisar` envia os PDFs.
4. O backend valida novamente os arquivos e extrai texto por página.
5. Páginas utilizáveis são agrupadas em trechos limitados por configuração.
6. Cada trecho é enviado ao `text_generator` com `prompts/analise_trecho.md`.
7. As respostas parciais são consolidadas por uma nova chamada ao `text_generator` usando `prompts/consolidacao_processo.md`.
8. O backend valida o JSON final com Pydantic e guarda o texto dos documentos somente em memória com TTL.
9. O frontend renderiza resumo, indicadores, partes, timeline, pedidos e pontos de atenção.
10. A pergunta digitada no chat é enviada a `POST /api/v3/ai-ready/chat`.
11. O backend monta o payload com `workflow_code`, a pergunta original em `question` e `async_mode: false`.
12. `BradescoBridgeClient` chama `gpt_bradesco.agente_informacional(payload)`.
13. O backend lê o campo `answer` e o frontend o apresenta na janela do chatbot preservando quebras de linha.
14. O chat não depende do workspace local de PDFs. O workspace continua sendo descartado separadamente quando necessário e também expira por TTL.

## Endpoints

```text
GET    /api/v3/saude
GET    /api/v3/ai-ready/configuracao
POST   /api/v3/ai-ready/analisar
POST   /api/v3/ai-ready/chat
DELETE /api/v3/ai-ready/{workspace_id}
```

## Segurança e privacidade

- Segredos nunca são enviados ao navegador.
- Logs HTTP registram identificador técnico, status e duração, sem conteúdo documental.
- O backend não grava o texto dos autos em banco ou arquivo neste desenho.
- PDFs de produção não devem ser adicionados ao repositório, testes ou documentação.
- Em ambiente publicado, o backend exige `GATEWAY_TOKEN`; o navegador não conhece esse segredo.
- Antes de adotar armazenamento compartilhado, OCR externo, embeddings ou persistência de conversas, validar arquitetura, retenção e base legal com Segurança, Jurídico/Compliance e DPO.

## Qualidade da IA

A aplicação não declara uma taxa de acerto sem medição. A saída do modelo deve ser validada em uma base representativa e autorizada. O arquivo `docs/MODEL_CARD.md` registra limitações e uma proposta de validação.

## Testes e validações

Backend:

```bash
pytest
python scripts/validate_architecture.py
```

Frontend:

```bash
cd frontend
npm test
npm run build
```

Os testes do repositório usam dados sintéticos e mocks; não inclua dados reais de clientes ou processos.


## Ajuste 3.0.4

- Ícone flutuante do chatbot movido para o canto inferior direito.
- Janela do chat também aberta à direita, mantendo o mesmo comportamento visual.

## Integração Q&A do chatbot — v3.1.0

O campo do chatbot não usa `text_generator`. A pergunta é encaminhada sem reescrita para `gpt_bradesco.agente_informacional`. O payload usado é:

```python
{
    "workflow_code": "CD_WRFL_QA_778_LEITURA_SENTENCA_PIAUI_AAJR_SYNC",
    "question": pergunta_digitada,
    "async_mode": False,
}
```

A aplicação espera que a função retorne um dicionário contendo `answer`. O token permanece exclusivamente no backend via `BRADESCO_AUTHORIZATION_TOKEN` ou pelo mecanismo de autenticação já existente em `gpt_bradesco.py`. `BRADESCO_QA_URL` pode sobrescrever o endpoint; o endereço fornecido foi confirmado apenas para DEV, portanto homol/prod exigem URL explicitamente validada.


## BJN — Minutas contratuais

Acesse `/bjn` para a jornada BJN. A nova área usa o shell existente, um motor de triagem independente e um chatbot próprio. **A geração de minutas está bloqueada** até que as cláusulas fotografadas sejam transcritas, conferidas e aprovadas pelo Jurídico. Consulte [docs/BJN.md](docs/BJN.md) para a arquitetura, as regras, as limitações e os passos de homologação.

## Cadastro e acompanhamento de demandas BJN

Na aplicação BJN também estão disponíveis **Demandas**, **Nova demanda** e **Acompanhamento da demanda**. O cadastro recebe anexos; a página de acompanhamento mostra responsável, histórico, status e documentos em visualizador PDF/imagem embutido. A distribuição para advogado é manual, por administrador, usando lista autorizada.

Consulte [docs/BJN_DEMANDAS.md](docs/BJN_DEMANDAS.md) para arquitetura, rotas, permissões, limites e instalação. O questionário original de minutas e o chatbot não foram substituídos.

## BJN — Orientação inicial com IA e distribuição de teste

O BJN inclui análise opcional do campo **Descrição da consulta** com `gpt_bradesco.text_generator`, exibição de uma sugestão informacional antes do cadastro e no acompanhamento, resolução explícita por autoatendimento e uma Central de Documentos minimizável. Os quatro advogados fictícios do ambiente local podem ser usados para testar a distribuição, sem afetar produção. Consulte `docs/BJN_IA_ORIENTACAO_E_DISTRIBUICAO.md` para configuração, controles, API e testes. O serviço de IA depende de `BRADESCO_TEXT_MODEL` válido no ambiente corporativo.


### Gestão de demandas BJN — jornada integrada

Consulte `docs/BJN_JORNADA_DEMANDAS_2026_10_14.md` para o novo fluxo de triagem, cadastro, distribuição, geração assistida e revisão de parecer, consulta, privacidade e configuração de notificações.


## BJN — Sugestão documental de IA (2026-10-16)

O cadastro de demandas oferece uma **Sugestão da IA** automática ao anexar PDF pesquisável e selecionar Inventário, Alvará, Curatela ou Procuração. O backend utiliza um prompt `.md` próprio por natureza e registra uma sugestão preliminar no acompanhamento após o cadastro. A publicação jurídica permanece exclusiva do advogado designado.

Para a arquitetura, regras de arquivos, limites, exemplos de execução e o único local de configuração da Bridge/agente, consulte [`docs/BJN_ANALISE_DOCUMENTAL_AUTOMATICA.md`](docs/BJN_ANALISE_DOCUMENTAL_AUTOMATICA.md). Nenhuma credencial real acompanha o repositório. PDFs digitalizados e imagens sem camada textual ainda exigem análise humana.
