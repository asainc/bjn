# Registro de decisões técnicas

## 2026-10-01 — Remoção do domínio financeiro

**Decisão:** remover rotas, serviços, contratos, telas, testes, dados e dependências ligados à antiga auditoria de pagamentos e ao motor financeiro.

**Motivo:** o novo objetivo do produto é inteligência documental para processos cíveis. Manter o domínio anterior aumentaria acoplamento, superfície de manutenção e risco de executar funcionalidades fora do novo escopo.

## 2026-10-01 — Separação entre análise documental e Q&A

**Decisão:** resumo e consolidação dos PDFs continuam em `gpt_bradesco.text_generator`. O chatbot usa exclusivamente `gpt_bradesco.agente_informacional(payload)` e exibe o campo `answer` devolvido pela API corporativa.

**Motivo:** os dois serviços possuem contratos distintos. A pergunta do usuário deve chegar ao workflow Q&A sem ser transformada em um prompt local, preservando o contrato demonstrado da API.

**Rastreabilidade:** `BRADESCO_QA_WORKFLOW_CODE` é parametrizado; o valor padrão corresponde ao workflow fornecido no exemplo. O endpoint Q&A informado foi confirmado apenas em DEV, portanto outros ambientes exigem `BRADESCO_QA_URL` validado.

## 2026-10-01 — Contexto documental temporário

**Decisão:** manter texto extraído dos PDFs somente em memória, com TTL e limite de workspaces.

**Motivo:** reduzir persistência desnecessária de conteúdo potencialmente sensível. Para produção distribuída, a estratégia deve ser revisada com Segurança, Arquitetura, Jurídico/Compliance e DPO antes de adotar um armazenamento compartilhado.

## 2026-10-01 — Timeline com fonte

**Decisão:** cada evento de timeline deve manter documento e página sempre que o modelo conseguir identificá-los.

**Motivo:** permitir conferência humana rápida e reduzir dependência de uma síntese sem rastreabilidade.
