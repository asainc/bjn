# Correção 3.0.2 — Angular e inicialização do backend

## Problemas corrigidos

### TS2551 no AI Ready
O contrato `TimelineEvent` e as fontes do chat usam o campo `documento`. O template continha três referências residuais ao nome inglês `document`, que não existe no contrato TypeScript.

Foram corrigidos:
- `event.document` → `event.documento` no `track` da linha do tempo;
- `source.document` → `source.documento` no `track` das fontes;
- `source.document` → `source.documento` na exibição da fonte.

### `ModuleNotFoundError: No module named backend`
O iniciador usava o import string `backend.principal:aplicacao`, porém dependia do diretório atual ou de scripts externos para colocar a raiz do projeto no caminho de importação do Python.

O `scripts/run_backend.py` agora:
1. descobre a raiz pelo próprio arquivo;
2. adiciona essa raiz ao `sys.path`;
3. adiciona a raiz ao `PYTHONPATH` herdado pelo processo de reload;
4. altera o diretório de trabalho para a raiz antes de iniciar o Uvicorn.

Com isso, a execução não depende mais do diretório em que o terminal foi aberto.

### Health check do modo integrado
O `scripts/start-dev.mjs` ainda consultava `/api/v2/saude`. O contrato atual usa `/api/v3`; a rota foi alinhada.

## Execução recomendada no Windows
Na raiz do projeto:

```powershell
.\scripts\start-dev.ps1
```

Para iniciar somente o backend:

```powershell
.\scripts\start-backend-dev.ps1
```

Ou diretamente:

```powershell
python scripts\run_backend.py --reload
```

## Validações executadas
- testes Python;
- testes estruturais do frontend;
- validação da arquitetura;
- compilação sintática dos módulos Python;
- smoke test real do backend iniciado a partir de outro diretório, com `GET /api/v3/saude` retornando HTTP 200.

A compilação Angular completa requer as dependências npm instaladas no ambiente do projeto.
