# Fluxo visual do AI Ready

```mermaid
sequenceDiagram
    participant U as Advogado
    participant A as Angular
    participant B as FastAPI
    participant P as PyMuPDF
    participant T as gpt_bradesco.text_generator
    participant Q as gpt_bradesco.agente_informacional
    participant W as Workspace temporário

    U->>A: Seleciona PDFs do processo
    A->>B: POST /api/v3/ai-ready/analisar
    B->>P: Valida e extrai texto por página
    P-->>B: Texto + qualidade da camada textual
    loop Trechos dentro do limite configurado
        B->>T: Prompt de extração factual + páginas
        T-->>B: JSON parcial
    end
    B->>T: Consolidação das análises parciais
    T-->>B: Resumo + fatos + linha do tempo
    B->>W: Mantém contexto somente em memória com TTL
    B-->>A: Workspace estruturado
    A-->>U: Resumo, partes, pontos de atenção e timeline

    U->>A: Digita uma pergunta no chatbot
    A->>B: POST /api/v3/ai-ready/chat {pergunta}
    B->>Q: {workflow_code, question, async_mode:false}
    Q-->>B: {answer: "..."}
    B-->>A: {resposta: answer}
    A-->>U: Exibe a resposta na janela do chat
```

## Decisões importantes

- O PDF é lido localmente com PyMuPDF; o projeto não envia automaticamente o binário para o chatbot.
- A análise documental usa `text_generator`; o chatbot usa `agente_informacional`.
- A pergunta do chatbot é enviada sem reescrita no campo `question`.
- O chat não depende do workspace local dos PDFs.
- O conteúdo textual dos PDFs fica apenas no workspace em memória e expira pelo TTL configurado.
- A interface trata a saída como apoio à revisão; informações críticas devem ser conferidas nas fontes oficiais.
