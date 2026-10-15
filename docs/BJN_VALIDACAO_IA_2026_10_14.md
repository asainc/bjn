# Evidências de validação — 2026-10-14

## Validações executadas

| Conjunto | Resultado neste ambiente | Observação |
|---|---|---|
| `python -m pytest -q` | 36 testes passaram | Backend, permissões, fluxo de IA simulado, persistência, demanda e componentes preexistentes |
| `node --test frontend/tests/bjn-demands.test.cjs frontend/tests/structure.test.cjs` | 16 testes passaram | Estrutura e integrações do frontend, inclusive minimizar documentos e ações de IA |
| `python -m compileall -q backend` | Sem erros | Sintaxe Python do backend |

## Limitações

- **Não** foi feita chamada a serviço corporativo real `gpt_bradesco.text_generator`: testes usam resposta sintética sem informações pessoais.
- **Não** foi executada a compilação completa do Angular nem teste de UI em navegador: dependências locais de `frontend/node_modules` não estão presentes no ambiente.
- Testes estruturais não substituem teste de integração UI/API com autenticação corporativa.
- Nenhuma taxa de acerto, segurança jurídica ou redução de acionamentos foi medida; a homologação depende da área jurídica, de compliance e do DPO.

## Critérios de homologação manual

1. Validar `BRADESCO_TEXT_MODEL`, autenticação e contrato de retorno da versão corporativa de `text_generator`.
2. Analisar consultas sintéticas de baixo risco e risco jurídico para comprovar que o modelo recomenda humano nos casos de exceção.
3. Confirmar que nenhum texto de anexo é transmitido ao gerador nesta etapa.
4. Testar no navegador o minimizador, responsividade, texto grande, falhas e tempos limites da API.
5. Confirmar permissões de administrador, advogado, solicitante e ausência da equipe fictícia em ambientes publicados.
