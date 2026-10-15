# BJN — Correção do cadastro de demandas (2026-10-14)

## Problema observado

O botão **Cadastrar demanda** permanecia desabilitado quando uma condição interna não era satisfeita. Além dos campos destacados com asterisco, a interface exigia uma sessão já carregada, título com pelo menos cinco caracteres, descrição com pelo menos quinze e nome para toda linha de envolvido adicionada — apesar de a seção Envolvidos ser opcional. Não havia indicação do motivo do bloqueio.

Essa é a causa identificada no código, não uma confirmação de qual condição específica estava ausente na sessão do usuário.

## Arquivos alterados

- `frontend/src/app/bjn/demands/demand-new.component.ts`: identifica pendências, permite clicar para focar o campo, exclui envolvidos vazios, verifica sessão no envio e mantém informações em caso de falha.
- `frontend/src/app/bjn/demands/demands.scss`: apresenta pendências legíveis com o mesmo padrão visual do BJN.
- `frontend/src/app/bjn/demands/demand-ui.ts`: devolve mensagens diferenciadas para falhas da API; nenhuma credencial ou documento é incluído em erros.
- `backend/routers/bjn_demands.py`: estrutura o nome de campos inválidos sem revelar seus valores.
- `frontend/tests/bjn-demands.test.cjs` e `tests/test_bjn_demands.py`: testes de regressão e cadastro com envolvidos opcionais.

## Critérios de aceitação

1. Preencha departamento, área de consulta e natureza do serviço com dois ou mais caracteres; título com pelo menos cinco e descrição com pelo menos quinze.
2. Adicione um envolvido e deixe todos os seus campos em branco; ele não deve bloquear o cadastro nem ser enviado à API.
3. Preencha documento ou período do envolvido sem nome; o painel deve mostrar pendência específica, com atalho até o campo.
4. Envie uma demanda sem envolvidos e sem anexos, com informações sintéticas; o backend deve retornar 201 e identificador da demanda.
5. Anexe PDF sintético válido e verifique que a demanda e o arquivo são consultáveis somente por usuários autorizados.
6. Com API desligada, o cadastro deve exibir mensagem de indisponibilidade sem perder o preenchimento.
7. Em caso de ausência de autorização pelo gateway, o envio deve informar o problema de autenticação.

## Validação e limitações

Foram executados testes Python de API e verificações estruturais do frontend. A compilação Angular e a reprodução da falha em navegador corporativo ainda dependem da instalação das dependências aprovadas e do ambiente utilizado pelo usuário. O endpoint `/api/v3/bjn/demandas/configuracao` exige autenticação válida e segue protegido pelo gateway; nenhuma identidade foi simulada no código de produção.

## Segurança

Dados submetidos ficam retidos na tela quando um erro ocorre; não são gravados no log do navegador por esta correção. A instalação em produção requer gateway autenticado, armazenamento seguro, retenção, rastreabilidade e validação pelas áreas responsáveis.
