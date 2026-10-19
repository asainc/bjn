# BJN — Cadastro e acompanhamento de demandas

## 1. Objetivo

Adicionar atendimento jurídico por demanda, preservando as funcionalidades do questionário de minutas (`/bjn`) e o chatbot BJN. O módulo de demandas não altera as regras do `script_bjn`, nem o catálogo das cláusulas contratadas ou os bloqueios de emissão de PDF de minutas.

O layout mantém a identidade da aplicação existente: plano de fundo cinza-claro, superfícies brancas, bordas discretas e vermelho como cor de ação. Campos obrigatórios são identificados por rótulos, com orientação antes do envio. A visualização de documentos ocorre **na própria página de acompanhamento**.

## 2. Como acessar

- **BJN > Demandas**: `http://localhost:4200/bjn/demandas`, com busca, filtro e lista das demandas a que o usuário tem acesso.
- **BJN > Nova demanda**: `http://localhost:4200/bjn/demandas/nova`, com Departamento Solicitante, solicitante autenticado, área, natureza, título, descrição, envolvidos opcionais e anexos.
- **BJN > Acompanhamento**: `http://localhost:4200/bjn/demandas/{id}`, com resumo, status, advogado, envolvidos, documentos, prévia de PDF/imagem, novos uploads e histórico de eventos.

O identificador da demanda é gerado no servidor. Não é presumido que represente o número de processo utilizado em outra ferramenta do banco. **Não há integração com sistema externo de protocolo ou distribuição neste pacote.**

## 3. Arquivos relevantes

| Arquivo | Responsabilidade |
| --- | --- |
| `frontend/src/app/bjn/demands/demand-new.component.ts` | Formulário e carregamento inicial de anexos |
| `frontend/src/app/bjn/demands/demand-list.component.ts` | Consulta das demandas disponíveis |
| `frontend/src/app/bjn/demands/demand-detail.component.ts` | Acompanhamento, histórico e visualizador incorporado |
| `frontend/src/app/bjn/demands/demands.scss` | Estilos responsivos |
| `frontend/src/app/core/bjn-demand-api.service.ts` | Contratos HTTP, uploads e leitura de documentos |
| `backend/routers/bjn_demands.py` | Rotas de entrada, autenticação da identidade e respostas |
| `backend/services/bjn_demand_store.py` | Esquema SQLite, controles de acesso, anexos e trilha de eventos |
| `backend/config.py` | Configurações de armazenamento e advogados habilitados |
| `tests/test_bjn_demands.py` | Testes de ponta a ponta da API em ambiente isolado |

## 4. Ambiente e execução

Pré-requisitos: Python compatível com as dependências `requirements.lock`; Node/npm e pacotes Angular na versão prevista pelo projeto, instalados pelo registro corporativo.

1. Descompactar o projeto e abrir terminal na pasta `ai_ready_processual_civel_v3.1.0`.
2. Preparar ambiente Python conforme as instruções originais do README e instalar `requirements.lock`.
3. Configurar `.env` a partir de `.env.example` sem versionar credenciais ou arquivos enviados.
4. Inicializar o backend com `python scripts/run_backend.py` ou os scripts corporativos existentes.
5. Em `frontend`, instalar as dependências aprovadas e iniciar `npm start`.
6. Acessar `/bjn/demandas/nova`, preencher um cadastro sintético e anexar um PDF sintético ou imagem criada para teste.
7. Ao enviar, a aplicação abre o acompanhamento da demanda. Selecionar um arquivo na **Central de documentos** para vê-lo sem sair da tela.
8. Para executar os testes: `pytest -q tests/test_bjn_demands.py` e `cd frontend && npm test`.

Parâmetros novos:

```env
BJN_DATABASE_PATH=.runtime/bjn/demandas.sqlite3
BJN_UPLOAD_DIRECTORY=.runtime/bjn/uploads
BJN_ALLOWED_LAWYERS=
```

`BJN_ALLOWED_LAWYERS` recebe uma lista de e-mails corporativos autorizados, separada por vírgula. **Deixar vazio bloqueia distribuição manual.** Em produção, o caminho SQLite e o diretório de documentos exigem volume persistente, criptografia, backup, acesso restrito ao processo backend e política de retenção aprovada.

## 5. Exemplo do fluxo técnico

1. `BjnDemandNewComponent` coleta e valida os campos. O solicitante vem de `GET /bjn/demandas/configuracao`, nunca de um campo editável.
2. `BjnDemandApiService.create` cria um `FormData` com o JSON do cadastro e arquivos, e chama `POST /bjn/demandas`.
3. `DemandCreate` valida tamanho e tipos de cada campo. `save_upload` valida extensão, MIME e assinatura binária de PDFs/PNG/JPEG, impõe 15 MB por arquivo e grava temporariamente em disco.
4. `DemandStore.create` cria identificador real, persiste demandante, envolvidos, documentos (nome físico por UUID e SHA-256) e registra o evento de abertura na mesma transação.
5. Angular redireciona para `/bjn/demandas/{id}`. `GET /bjn/demandas/{id}` retorna demanda, envolvidos, arquivos autorizados e histórico, filtrados por identidade.
6. Ao selecionar um documento, Angular busca um `Blob` na rota autenticada `GET /bjn/demandas/{id}/documentos/{documento_id}/arquivo`, cria URL local e apresenta PDF em `iframe` ou imagem em `img`, **sem redirecionar a outra página**. A URL é revogada quando a prévia é substituída ou o componente termina.
7. `POST /bjn/demandas/{id}/documentos` insere outros arquivos com evento de atualização.
8. `PATCH /bjn/demandas/{id}/atribuicao` permite distribuição **manual** por administrador a advogado explicitamente cadastrado. `PATCH /bjn/demandas/{id}/status` registra uma mudança autorizada no histórico.

### Rotas de API

Todas têm prefixo `/api/v3` e reutilizam o controle de acesso já aplicado no projeto original.

| Método | Caminho | Finalidade |
| --- | --- | --- |
| GET | `/bjn/demandas/configuracao` | Identidade e lista de advogados permitidos ao administrador |
| GET | `/bjn/demandas` | Busca filtrada por autorização do usuário |
| POST | `/bjn/demandas` | Cadastro multipart com anexos |
| GET | `/bjn/demandas/{id}` | Resumo, responsáveis, histórico, documentos |
| POST | `/bjn/demandas/{id}/documentos` | Upload posterior |
| GET | `/bjn/demandas/{id}/documentos/{doc_id}/arquivo` | Visualização/download autorizado |
| PATCH | `/bjn/demandas/{id}/atribuicao` | Distribuição manual (admin) |
| PATCH | `/bjn/demandas/{id}/status` | Andamento (admin ou advogado responsável) |

## 6. Segurança e limites de implantação

- Fora do ambiente `local`, chamadas HTTP devem passar pelo **gateway corporativo** e informar identidade autenticada por `X-Authenticated-User`, `X-Authenticated-Name`, `X-Authenticated-Role`. É obrigatório que o gateway remova esses headers de requisições externas e os reescreva com dados confiáveis. O gateway deve incluir também a autenticação do projeto (`X-Gateway-Token`) na comunicação interna com o backend.
- O modo `local` permite um usuário de desenvolvimento fictício para execução em `127.0.0.1`; nunca expor esse modo na rede.
- Consultas e anexos são filtrados por demandante, advogado responsável ou administrador. Atribuição não é automática nem baseada em suposição.
- PDF, PNG e JPEG são os formatos permitidos para a prévia. Tamanho máximo: 15 MB por documento; quantidade máxima: 20 documentos por demanda. Aplicam-se também validações de cabeçalho binário. Arquivos são armazenados sob UUID, fora da pasta pública do frontend.
- Os documentos **não são enviados ao modelo de IA** para gerar resumos neste módulo. O resumo é o texto informado no cadastro; o chatbot BJN permanece separado.
- Antes do uso produtivo, homologar com Segurança/Infra o armazenamento corporativo, antivírus ou varredura antimalware, backup, política de retenção, implantação em múltiplas instâncias, trilha de auditoria, autorização do gateway e recuperação de desastres. Validar com Jurídico/Compliance/DPO os requisitos de dados pessoais, retenção e acesso. SQLite não é um banco recomendado para operação distribuída multi-instância.

## 7. Decisões técnicas

| Decisão | Justificativa |
| --- | --- |
| Rotas separadas de minutas | Não altera os critérios de cláusulas do `script_bjn` e do book |
| Upload em multipart na abertura | Evita demanda criada sem os anexos da mesma solicitação |
| Identidade vinda do gateway | Impede que o solicitante se faça passar por outro no próprio formulário |
| Atribuição manual com allowlist | Sem diretório corporativo integrado, é inseguro simular distribuição automática |
| PDF/imagens pré-visualizados no Angular | Usuário confere evidências sem sair do acompanhamento |
| SQLite parametrizado | Simplicidade e testes locais reproduzíveis; substituir por repositório corporativo em escala |
| Eventos separados das requisições HTTP | Histórico funcional sem copiar conteúdo sensível para logs técnicos |

### Testes

Os testes usam usuários, nomes e documentos inteiramente sintéticos. Cobrem cadastro, anexos, isolamento entre solicitantes, acesso do advogado, distribuição manual, restrições de status, validação de formato e persistência do histórico.
