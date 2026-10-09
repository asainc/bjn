# Fidelidade ao script BJN

Fonte exclusiva do questionário: `docs/bjn_evidencias/script_bjn.zip` (8 fotografias). Configuração: `config/bjn_script_workflow.json`. Cada campo possui `source_page`, tipo, alternativas e, quando indicada, condição de visibilidade.

O frontend **não** cria perguntas, alternativas, opções “Não sei”, ou bloqueios próprios; consome `GET /bjn/questionario` do backend. O backend rejeita opções não documentadas e campos extras. Uma resposta a campo oculto é inválida. A origem das decisões fica registrada no catálogo.

Regras de exceção visíveis no script: escolha "Outros, especificar" no instrumento direciona para atendimento humano (CopecJuri); responsabilidade civil "com limitação" interrompe triagem para análise humana; multa fora do padrão requer aprovação prévia e, se negada, impede avanço. Outras notas sobre encaminhamento/níveis de alçada não são interpretadas como autorização para gerar contratos.

**Lacunas de homologação:** O script apresenta conteúdos MVP 1 / MVP 2 e anotações de inclusão de cláusulas. Para não inventar vínculos, nenhuma opção foi relacionada a um ID de cláusula do book. O mapeamento das cláusulas e eventuais páginas sobrepostas/incompletas precisam ser validados com o Jurídico. O endpoint PDF continua bloqueado até a conclusão dessa homologação. Não foi implementada abertura automática de chamada externa.

As perguntas das fotografias foram transcritas manualmente para operação inicial. Conferir **item a item** com a imagem original, especialmente redação, apresentação e alternativas, antes da produção. O questionário de tecnologia é exibido quando a modalidade selecionada é "Contrato de Tecnologia". A regra de elegibilidade por MVP, os caminhos de múltiplos instrumentos e regras de tela não explícitas permanecem pendentes de validação, sem inferência automática.
