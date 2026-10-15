# BJN — Correção da publicação do parecer

**Data:** 14/10/2026  
**Objetivo:** permitir que a pessoa efetivamente designada publique o parecer, inclusive em desenvolvimento com advogados fictícios, sem liberar publicação por administrador ou por IA.

## Diagnóstico confirmado no código anterior

1. **Impossibilidade de testar o papel de advogado:** a API identificava o usuário local como `admin` por padrão. Depois de distribuir a demanda para um advogado fictício, a tela não oferecia troca de perfil. A API corretamente exigia `role=advogado` e identidade idêntica ao `lawyer_email` da demanda. O editor permanecia invisível para o administrador.
2. **Incompatibilidade de cadastros antigos:** `publish_opinion` rejeitava protocolos que não possuíam o registro de e-mail de notificação, mesmo quando o parecer estava revisado e a notificação era secundária.
3. **Validação sem orientação suficiente:** o botão exigia texto de pelo menos 40 caracteres e confirmação de revisão, mas não mostrava essas pendências explicitamente.

## Mudanças

- A API informa `demo_session_available` somente em `APP_ENV=local` **e** `BJN_DEMO_LAWYERS=true`.
- O Angular mostra **Testar como advogado designado** somente para uma demanda distribuída a um perfil fictício habilitado. A troca é temporária, mantida apenas na memória do navegador, sem credencial no código. **Voltar ao administrador** restaura a sessão local anterior.
- Cabeçalhos de teste estão permitidos no CORS **somente em `local`**. Em ambientes publicados, o gateway corporativo continua sendo responsável pela identidade e autorização.
- O backend continua exigindo advogado atribuído, etapa permitida, pelo menos 40 caracteres e confirmação expressa de revisão. Administrador, solicitante e IA não podem publicar.
- Demandas criadas antes da inclusão do e-mail de cadastro podem receber parecer. O sistema registra a publicação e não cria notificação sem destinatário. A interface informa que o retorno está disponível no portal.
- As restrições de dados e documentos, e a trilha de auditoria da publicação, permanecem ativas.

## Reproduzir a publicação no ambiente local

1. Configure `APP_ENV=local` e `BJN_DEMO_LAWYERS=true` no `.env` do backend. Reinicie o backend e o frontend após substituir os arquivos. Não habilite esse recurso em ambientes publicados.
2. No BJN, cadastre a demanda normalmente. Se for **Pareceres em geral**, conclua antes a análise de competência na tela de acompanhamento.
3. Em **Gestão da demanda**, atribua a um advogado marcado **(teste)**.
4. Selecione **Testar como advogado designado** no topo da tela de acompanhamento. O editor do parecer será exibido na sessão de teste.
5. Gere rascunho por IA **ou escreva o parecer manualmente**. O serviço `text_generator` não é pré-requisito para publicação manual.
6. Digite um parecer com pelo menos 40 caracteres, marque a confirmação **Li e revisei integralmente o parecer**, e clique **Publicar parecer e disponibilizar retorno**.
7. Confira status **Concluída**, texto publicado, data e responsável. Clique **Voltar ao administrador**. O demandante poderá consultar o parecer na mesma demanda.

## Restrições de produção

A troca de perfil é **exclusiva do ambiente local** para advogados fictícios. Em produção, o advogado designado deve entrar com sua identidade corporativa, e os cabeçalhos devem ser validados e injetados pelo gateway. Não permita simulações com identidade de usuários reais.

Protocolos legados sem e-mail não recebem e-mail, apenas publicação no portal. A ausência de SMTP configurado não impede a publicação, e a notificação fica pendente. Essa política requer aprovação operacional antes de produção.

## Evidências técnicas e limitações

- `python -m pytest -q tests`: 46 testes aprovados, incluindo atribuição a advogado fictício, publicação por perfil atribuído, bloqueio de admin e cenário legado sem e-mail.
- `node --test frontend/tests/*.test.cjs`: 23 verificações estruturais aprovadas, incluindo troca temporária de perfil e orientação de publicação.
- Compilação Angular completa e execução visual com as dependências corporativas **não realizadas neste ambiente**. Validar em navegador após instalação.

## Arquivos principais

- `backend/routers/bjn_demands.py`: informa simulação local e retorna status de notificação.
- `backend/services/bjn_demand_store.py`: aceita publicar protocolos legados sem destinatário.
- `backend/principal.py`: cabeçalhos de simulação apenas em CORS local.
- `frontend/src/app/core/bjn-demand-api.service.ts`: perfil de teste transitório, cabeçalhos locais.
- `frontend/src/app/bjn/demands/demand-detail.component.ts`: alternância de perfil, mensagens e publicação.
- `frontend/src/app/bjn/demands/demands.scss`: apresentação responsiva do painel de testes.
- `tests/test_bjn_publish_correction.py` e `frontend/tests/bjn-journey.test.cjs`: testes de regressão.
