# BJN — Análise documental por natureza e configuração da Bridge

Data: 2026-10-16. Responsável técnico: equipe responsável pela implantação do BJN (a designar).

## Objetivo e escopo

Ao selecionar a natureza e anexar PDF **pesquisável**, o BJN lê o texto presente no documento, combina-o com o prompt correspondente e chama `text_generator`. O texto aparece em **Sugestão da IA**. Antes do cadastro a análise é efêmera; quando o protocolo é criado ou são anexados novos PDFs, a análise é repetida a partir dos arquivos armazenados e registrada no histórico autorizado. O usuário poderá reanalisar após mudar a descrição. A sugestão **não** é publicada como parecer jurídico.

A geração final continua reservada à revisão, edição, confirmação e publicação pelo advogado designado. O serviço não decide aceitação de documentos ou realização de operações bancárias. A aprovação das regras e do conteúdo dos prompts depende do Jurídico, Compliance e DPO antes de receber dados reais.

## Arquivos e execução

| Componente | Entrada | Saída |
|---|---|---|
| `frontend/src/app/bjn/demands/demand-new.component.ts` | Natureza e arquivo selecionado | Prévia textual na Sugestão da IA |
| `backend/routers/bjn_demands.py` | `POST /api/v3/bjn/demandas/assistente/analisar-documentos`, multipart `nature`, `description`, `files` | Sugestão efêmera, sem protocolo |
| `backend/services/bjn_document_opinion.py` | Nome, MIME, bytes do PDF, natureza, descrição | Texto da IA, alertas, hashes SHA-256 |
| `prompts/bjn/naturezas/inventario.system.md` | Natureza Inventário | Prompt especializado |
| `prompts/bjn/naturezas/alvara.system.md` | Natureza Alvará | Prompt especializado |
| `prompts/bjn/naturezas/curatela.system.md` | Natureza Curatela | Prompt especializado |
| `prompts/bjn/naturezas/procuracao.system.md` | Natureza Procuração | Prompt especializado |
| `backend/services/bjn_demand_store.py` | Sugestão validada e IDs de origem | Tabela `bjn_document_suggestions`, evento de auditoria |
| `frontend/src/app/bjn/demands/demand-detail.component.ts` | Consulta do protocolo | Sugestão, histórico, visualizador de anexos e editor exclusivo do advogado |

**Pareceres em geral:** mantém a análise orientativa baseada na descrição e a triagem administrativa. Não possui prompt documental especializado nesta mudança.

### Comportamento e limitações

- Limite atual de análise: até quatro PDFs, as primeiras 40 páginas por PDF e 36.000 caracteres somados. São *limites configurados de engenharia*, não métricas de performance.
- Somente texto extraível de PDFs pesquisáveis é analisado automaticamente. PDFs digitalizados sem camada textual, imagens PNG/JPEG, documentos protegidos e arquivos ilegíveis continuam disponíveis ao advogado, mas não têm parecer gerado por essa rotina. **Não é correto alegar que o conteúdo dessas imagens foi analisado.** OCR corporativo exige integração e homologação específicas.
- Arquivos de upload aceitos pelo BJN permanecem PDF, PNG e JPEG. Falhas do serviço de IA **não bloqueiam a criação do protocolo ou o armazenamento do documento**; um erro específico é retornado no upload. Falhas durante o cadastro também podem ser verificadas pela opção de reanálise no acompanhamento.
- Upload no cadastro pode desencadear análise prévia e análise posterior à criação do protocolo. As duas chamadas não compartilham cache: custos e latência dependem do serviço corporativo, sem promessa de tempo de resposta.
- Conteúdo dos anexos é enviado à Bridge corporativa após extração e escolha do usuário. Verificar base legal, necessidade, minimização, retenção e autorização de uso desse serviço com Jurídico/Compliance/DPO.
- Não há extração, armazenamento ou exposição de credenciais em logs. Os eventos guardam apenas versões do prompt, hashes, número de documentos e alterações de estado; a sugestão fica na base restrita de demandas.

## Único ponto de configuração — Bridge e agente

**Configure somente o arquivo `.env` da raiz do projeto, ou variáveis de ambiente equivalentes injetadas pelo gestor de segredos da organização**. O código carregará todos os valores por `backend/config.py` e repassará à única instância de `BradescoBridgeClient` usada pelo AI Ready e pelo BJN. O arquivo `.env` é ignorado pelo Git; não contém valores no pacote. O `.env.example` é apenas um modelo sem segredos.

```env
BRADESCO_AMBIENTE=dev
BRADESCO_IDENTIFICADOR=
BRADESCO_SENHA=
BRADESCO_AUTHORIZATION_TOKEN=
BRADESCO_TEXT_MODEL=
BRADESCO_QA_WORKFLOW_CODE=CD_WRFL_QA_778_LEITURA_SENTENCA_PIAUI_AAJR_SYNC
BRADESCO_CA_BUNDLE=
```

- Identificador e senha **não** devem ser copiados para os prompts, componentes Angular, `gpt_bradesco.py` ou logs. Use um cofre corporativo para ambientes publicados.
- O código do agente não possui mais valor padrão replicado em `Settings`; sem `BRADESCO_QA_WORKFLOW_CODE`, o chatbot Q&A permanece indisponível até ser configurado.
- `BRADESCO_TEXT_MODEL` é **separado** do código do agente Q&A: o primeiro configura `text_generator` e o segundo configura `agente_informacional`. Não são intercambiáveis.
- Reinicie o backend ao atualizar configurações. URLs e certificados opcionais também são definidos nesse mesmo local.

## Como validar com dados sintéticos

1. Copie `.env.example` para `.env` e configure credenciais aprovadas em ambiente de testes; não compartilhe esse arquivo.
2. Inicie FastAPI e Angular conforme `README.md`. Acesse **BJN → Nova demanda**, complete a triagem e selecione **Procuração**.
3. Selecione um PDF sintético com texto. A área **Sugestão da IA** deverá exibir um rascunho identificado como preliminar. Troque a natureza para **Alvará** e confira a reanálise com o prompt correspondente.
4. Preencha as validações restantes e cadastre. No acompanhamento, confirme a sugestão persistida, o arquivo visível na Central de Documentos e o histórico. Sem Bridge configurada, o cadastro ainda deve prosseguir e a mensagem de indisponibilidade aparecer.
5. Distribua manualmente a um advogado fictício no modo `APP_ENV=local` e, com sessão do advogado, elabore/revise o parecer. A publicação exige confirmação humana explícita.
6. Execute `python -m pytest -q` e `cd frontend && npm test`. Os testes do gerador usam um simulador: não validam a disponibilidade real da Bridge.

## Registro de decisões

| Data | Decisão | Motivo / trade-off | Validação pendente |
|---|---|---|---|
| 2026-10-16 | Quatro prompts Markdown por natureza | Evita usar instruções genéricas e permite versionamento | Aprovação do Jurídico |
| 2026-10-16 | Extração limitada a PDF com camada textual | Evita fingir que OCR/visão funcionou; exclui PDFs sem camada de texto | Integração OCR corporativa |
| 2026-10-16 | Documento recebido é fonte não confiável | Mitiga instruções indevidas embutidas em anexos | Testes de segurança corporativos |
| 2026-10-16 | Parecer preliminar separado do parecer publicado | Impede efeito jurídico sem revisão humana | Homologação dos fluxos de autorização |
| 2026-10-16 | `requesting_department` novo e migração aditiva | Mantém demandas antigas sem perder dados | Revisão da migração no ambiente de homologação |
| 2026-10-16 | Segredos e agente centralizados em `.env` | Evita credenciais e códigos repetidos | Gestão corporativa de segredos |

## Monitoramento

Monitorar falhas de autenticação, falhas de extração, quantidade de documentos com texto insuficiente, tempo de atendimento das chamadas e quantidade de sugestões revisadas ou rejeitadas. Nenhuma métrica foi medida em ambiente real nesta entrega. Registrar versão do prompt e do modelo em auditoria corporativa antes do uso em produção.
