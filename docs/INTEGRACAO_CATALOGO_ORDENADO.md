# Integração do catálogo ordenado do book

- Fonte: `config/catalogo_clausulas_bjn.xlsx`, quatro colunas, na ordem original.
- `GET /bjn/catalogo` expõe os 152 registros para consulta, sem presumir aplicabilidade.
- `POST /bjn/previa-clausulas` usa somente os IDs expressos em `config/bjn_book_image_mappings.json`, condicionados às respostas previstas no script.
- No momento, LGPD / `personal_data=sim` seleciona os IDs `BOOK-P02-T004`, `BOOK-P02-T005` e `BOOK-P02-T006` como prévia preliminar.
- O OCR da planilha contém ruídos e instruções não contratuais; NÃO está homologado. Demais regras e páginas do Anexo V precisam de validação e identificação exata.
- A rota de PDF continua bloqueada. A presença de um texto no Excel não é autorização para sua emissão.
- Ao substituir a planilha, preservar os nomes das quatro colunas e manter os IDs estáveis; revisar `bjn_book_image_mappings.json` se os IDs forem alterados.
