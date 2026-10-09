# BJN — Triagem de minutas contratuais

## Escopo entregue

A rota `/bjn` reutiliza o shell, a paleta, a tipografia e a navegação originais. O questionário captura modalidade, parte contratante, prazo, dados pessoais, confidencialidade, trabalhadores, tecnologia, nuvem, transferência internacional, segurança, criticidade, continuidade e equipamentos. O motor Python expõe `POST /api/.../bjn/avaliar` (prefixo definido em `backend/version.py`) e calcula, de forma reproduzível, temas sugeridos e motivos de revisão. O chatbot possui uma rota BJN e um componente de interface próprios, mas reutiliza a integração corporativa `BradescoBridgeClient` com instância de serviço isolada.

## Limitação jurídica obrigatória

O material `book_clausulas.zip` contém apenas 69 fotografias e `script_bjn.zip`, 8 fotografias. As perguntas foram **adaptadas a partir de imagens**, e não constituem transcrição homologada da lógica completa. O catálogo das cláusulas não foi reconstruído palavra por palavra. **A emissão da minuta está intencionalmente bloqueada** até revisão por Jurídico e Compliance. A aplicação oferece uma triagem funcional e encaminhamento humano, sem fingir que produziu uma minuta pronta.

## Próximos passos para habilitar a geração

1. Obter o book em DOCX pesquisável e a árvore de decisão original (ou formalizar uma transcrição dupla com revisão jurídica).
2. Registrar cláusula com ID estável, versão, texto integral, modalidade, condição de aplicabilidade, obrigações de exclusão mútua, referências de origem e homologador.
3. Validar todas as combinações da árvore e condições de atendimento humano com o time jurídico; criar testes de regressão por cenário.
4. Só então implementar composição DOCX, variáveis contratuais, revisão humana, trilha de auditoria, hash das versões e histórico de aprovação.
5. Confirmar destino do atendimento humano, autorização de acesso e retenção de dados com Jurídico, Compliance e DPO.

## Testes

`python -m pytest tests/test_bjn_rules.py -q` (com dependências do projeto instaladas). Os testes demonstram bloqueio e rotas de encaminhamento, não homologação das regras jurídicas.

## Saída obrigatória PDF e origem exclusiva das cláusulas

- A única saída contratual permitida é **PDF** (`application/pdf`). Nenhum DOCX é produzido.
- `POST /bjn/gerar-pdf` responde HTTP 409 até a transcrição integral e a aprovação jurídica da árvore de seleção.
- `backend/services/bjn_pdf.py` gera PDF a partir de texto literal cadastrado em `config/bjn_clauses_approved.json` (ou `BJN_CLAUSE_CATALOG`).
- Cada cláusula exige `id`, `source_image`, `text` e `text_sha256`; o catálogo exige `approval_status=approved`, `approved_by` e `source_book_sha256`. Não inserir dados inventados ou textos de exemplo nesse catálogo.
- A aplicação deve validar também a correspondência de cada transcrição com a fotografia original e vincular sua condição de inclusão a uma regra homologada. O PDF **não é liberado** enquanto essa seleção não estiver implementada; o endpoint permanece bloqueado de propósito.
- O chatbot não compõe ou edita cláusulas. Os testes usam texto sintético apenas em memória temporária, jamais na minuta real.

### Pré-visualização lateral (08/10/2026)
- A tela BJN exibe, à direita, uma prévia estrutural que reage às respostas por meio de estado Angular derivado.
- O cabeçalho solicitado `2.2 Contratada` foi incluído na prévia, sem presumir o texto jurídico dessa seção.
- A prévia distingue claramente dados fornecidos no script e cláusulas contratuais homologadas. Sem correspondência aprovada com o book, nenhuma cláusula é apresentada como texto contratual.
- O PDF permanece bloqueado até a homologação das correspondências. Esse bloqueio é intencional para impedir documentos com conteúdo não proveniente do book.
