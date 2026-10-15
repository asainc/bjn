# BJN — Jornada de demandas com triagem, distribuição e parecer

**Data:** 14/10/2026  
**Base:** projeto AI Ready / BJN anterior e cinco imagens fornecidas como referência do novo fluxo.  
**Responsável pela homologação funcional:** a definir pela área jurídica.  
**Natureza desta entrega:** implementação inicial integrada, para testes e homologação; não significa aprovação para produção.

## Objetivo e experiência do usuário

A navegação preserva a identidade visual do BJN, o módulo de minutas e o chatbot próprio. A jornada foi dividida em cinco etapas, com explicação de cada decisão, mensagens de erro visíveis e navegação responsiva.

1. **Triagem inicial:** escolher uma das cinco opções apresentadas no fluxo. Quando o Banco for parte de processo judicial, informar **autor/réu** e existência de **GCPJ**. Quando a opção não comportar cadastro na equipe, apresentar orientação específica e **não** criar protocolo nem disparar e-mail.
2. **Cadastro:** fornecer departamento, área, natureza, agência, nome e e-mail do solicitante, cliente e CPF, descrição, título e documentos. Naturezas: Inventário, Alvará, Curatela, Procuração, Pareceres em geral. As quatro primeiras exigem pelo menos um anexo; pareceres gerais permitem anexo opcional. **Atenção:** a inclusão de título e departamento aproveita os campos existentes, sem modificar a referência principal.
3. **Distribuição:** ao cadastrar, gera um identificador exclusivo. Para naturezas pré-definidas, o status permanece Recebida até atribuição administrativa. Para Pareceres em geral, inicia em Triagem administrativa; um administrador registra se a demanda pertence à equipe. Caso não pertença, marca Encaminhada à área competente; não é feita transmissão externa. Caso pertença, fica disponível para atribuição a advogado autorizado.
4. **Parecer:** somente o advogado designado pode gerar proposta por `text_generator`. O system prompt está em `prompts/bjn/opinion_draft.system.md`. A IA recebe somente natureza e descrição e não recebe anexos ou os campos estruturados de CPF, cliente ou agência. O advogado edita integralmente o texto, confirma a revisão e publica. O rascunho não aparece ao solicitante. A publicação encerra a demanda e cria registro de notificação.
5. **Consulta:** o solicitante consulta protocolos e pareceres publicados, acompanha status, advogado responsável, histórico e documentos. Pode procurar por protocolo, título, data, agência, nome/e-mail e CPF. A busca por CPF ocorre por **POST**, nunca na URL.

## Módulos e responsabilidades

| Arquivo | Responsabilidade |
|---|---|
| `backend/services/bjn_journey.py` | Decisões de triagem, validade temporária da confirmação e validações por natureza |
| `backend/services/bjn_demand_store.py` | Repositório SQLite, acesso autorizado, histórico e metadados, parecer, HMAC do CPF e notificações pendentes |
| `backend/services/bjn_opinion.py` | Chamada `text_generator` com prompt versionado para rascunho |
| `backend/services/bjn_notifications.py` | Envio SMTP opcional pós-publicação, sem texto do parecer ou documentos |
| `backend/routers/bjn_demands.py` | Endpoints e autorização por identidade do gateway |
| `frontend/src/app/bjn/demands/demand-new.component.ts` | Triagem, cadastro e sugestão inicial da IA |
| `frontend/src/app/bjn/demands/demand-detail.component.ts` | Revisão de competência, parecer, histórico e central de documentos minimizável |
| `frontend/src/app/bjn/demands/demand-list.component.ts` | Pesquisa autorizada e filtros |

## Endpoints adicionais

- `POST /api/v3/bjn/demandas/triagem`: avalia a categoria e gera token de triagem com validade de 30 minutos quando a categoria exige cadastro.
- `POST /api/v3/bjn/demandas/fluxo`: cadastro multipart autenticado com token de triagem e validações no backend.
- `POST /api/v3/bjn/demandas/consulta`: pesquisa autenticada com filtros no corpo da requisição.
- `PATCH /api/v3/bjn/demandas/{id}/competencia`: revisão de competência pelo administrador.
- `POST /api/v3/bjn/demandas/{id}/parecer/rascunho`: chamada do modelo somente pelo advogado designado.
- `POST /api/v3/bjn/demandas/{id}/parecer/publicar`: publicação por advogado designado com confirmação de revisão, incluindo registro de tentativa de notificação.
- `POST /api/v3/bjn/demandas/{id}/notificacoes/reprocessar`: tentativa de reenvio de e-mail, restrita a administrador.

## Segurança e privacidade

O CPF novo não é gravado em claro na tabela `bjn_demand_context`: há apenas máscara com os últimos dois dígitos e HMAC-SHA256 para consulta exata. A chave é fornecida por `BJN_DOCUMENT_HASH_KEY` no ambiente corporativo. No ambiente **local**, se não for configurada, o projeto cria uma chave aleatória em `.runtime/bjn/.bjn-cpf-local.key` com permissão restrita. **Não compartilhar o arquivo, não versioná-lo e fazer backup da chave conforme política do ambiente:** a perda inviabiliza buscas dos CPFs antigos. Essa abordagem ainda precisa de validação de LGPD e retenção pelo DPO e pela segurança da informação.

O acesso é restrito ao solicitante, advogado designado ou administrador, mantendo a mesma política do módulo anterior. O gateway corporativo precisa remover cabeçalhos de identidade fornecidos pelo cliente e injetar informações autenticadas. O perfil `local` permite perfis simulados e não é apropriado para implantação pública.

Para envio de e-mail: configurar `BJN_NOTIFICATION_SMTP_HOST`, `BJN_NOTIFICATION_SMTP_PORT` (padrão 587), `BJN_NOTIFICATION_SENDER`, `BJN_NOTIFICATION_USERNAME`, `BJN_NOTIFICATION_PASSWORD`. Sem SMTP, a publicação funciona e a mensagem permanece **PENDENTE** em `bjn_notifications`; nada é enviado nem tratado como entregue. O e-mail só informa que há retorno disponível no portal, sem documentos ou trechos do parecer. A fila local não substitui um serviço de mensageria confiável para produção. Validação de servidores, identidade do remetente e política de envio permanecem pendentes.

**Destinos externos de triagem:** as caixas postais e integrações a GCPJ, WCPS e ON aparecem nas imagens. A implementação registra a orientação de canal, mas **não contém endereços corporativos fixos nem faz transmissão para esses sistemas**; destinos, permissões e caixas oficiais requerem validação do time jurídico/operacional. Qualquer ativação de envio exige configuração e testes separados.

**IA:** qualquer texto gerado é provisório. Não cria automaticamente parecer final, não envia parecer e não aplica interpretação normativa como verdade verificada. Prompt, versão e responsáveis devem passar por homologação. Revisar a política de dados de entrada e retenção do serviço corporativo.

## Execução e testes

No ambiente com dependências instaladas, usar os scripts usuais do projeto e as orientações de `README.md` / `docs/BJN_DEMANDAS.md`. A API usa a mesma base Angular + FastAPI; não é necessário alterar serviços do AI Ready.

1. Configurar `.env` a partir de `.env.example` e definir a identidade do gateway corporativo. Em local, a chave HMAC é gerada automaticamente.
2. Rodar o backend conforme `scripts/start-backend-dev.sh` ou o comando equivalente para seu sistema operacional.
3. Rodar o Angular com as dependências aprovadas do repositório corporativo.
4. Abrir `BJN → Demandas → Nova demanda`, selecionar **Nenhuma das opções anteriores** e prosseguir.
5. Selecionar uma natureza e testar a presença/ausência de anexo, corrigindo as mensagens de validação.
6. Como administrador autorizado, validar a competência dos pareceres gerais e distribuir para um advogado habilitado.
7. Como advogado atribuído, criar ou editar um parecer, confirmar a revisão, publicar e consultar o retorno com o usuário solicitante.

Testes backend: `python -m pytest -q tests`. Testes estáticos frontend: `node --test frontend/tests/*.test.cjs`.

## Pendências antes de produção

- Homologar alternativas, destinatários institucionais e competências da triagem, inclusive caixa GCPJ/WCPS/ON.
- Validar se CPF, nome do cliente e os demais campos são estritamente necessários em todas as naturezas, inclusive à luz da LGPD.
- Homologar prompts e aprovações de parecer com equipe jurídica; confirmar trilha de auditoria e retenção.
- Substituir SQLite e diretório local de anexos pela infraestrutura corporativa com backup, criptografia e alta disponibilidade.
- Implantar autenticação corporativa, perfis de acesso e integração de distribuição com equipe real.
- Validar envio SMTP, fila confiável, política de retentativas e métricas de entrega.
- Executar a compilação Angular completa, testes end-to-end no navegador e testes de acessibilidade com infraestrutura e dependências corporativas.

## Decisões técnicas relevantes

- **Triagem antes do cadastro:** evita protocolos indevidos, mas não executa encaminhamentos externos sem integração autorizada.
- **Token temporal vinculado ao usuário:** impede que o frontend envie a opção OUTRAS sem passar pela API de triagem; validade de 30 minutos.
- **Anexos obrigatórios no backend:** uma regra somente visual seria facilmente contornada.
- **Rascunho privado e publicação humana:** mitiga risco de IA tomada por decisão jurídica definitiva.
- **Notificação desacoplada da publicação:** falha de SMTP não desfaz parecer revisado; status pendente fica auditável.
- **HMAC do CPF em vez de armazenamento reversível:** permite busca por igualdade sem salvar o número em claro, mas não elimina a necessidade de governança de dados.
