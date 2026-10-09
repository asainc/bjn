# Ficha técnica — AI Ready Processual

## Uso pretendido

Apoiar profissionais jurídicos na leitura e organização de documentos de processos cíveis. A aplicação resume conteúdo, estrutura informações, monta cronologia factual e responde perguntas usando o contexto fornecido pelo usuário.

## Modelo

O deployment é definido por `BRADESCO_TEXT_MODEL` e executado pela função `gpt_bradesco.text_generator`. O repositório não fixa o nome de um modelo corporativo específico porque essa informação depende do ambiente autorizado.

## Dados de entrada

PDFs enviados pelo usuário durante a sessão. O texto é extraído localmente com PyMuPDF. PDFs sem camada textual suficiente são rejeitados para evitar inferência a partir de conteúdo ausente.

## Limitações

- A IA pode omitir, interpretar incorretamente ou associar uma informação à página errada.
- A aplicação não substitui leitura dos autos nem validação jurídica.
- Imagens digitalizadas sem texto pesquisável não são automaticamente submetidas a OCR neste fluxo.
- O chatbot recebe apenas uma parcela dos trechos quando o conjunto excede o limite de contexto configurado; o resumo estruturado do workspace também é incluído para preservar informação consolidada.
- Métricas de acurácia não são declaradas neste documento porque precisam ser medidas em uma base de validação representativa e aprovada.

## Validação recomendada

Criar conjunto anonimizado/adequadamente autorizado de processos cíveis, definir campos esperados e medir precisão/recall por tipo de informação, além de taxa de citações corretas de documento/página. Qualquer uso com efeito decisório deve passar por validação adicional de Jurídico, Compliance e DPO quando aplicável.
