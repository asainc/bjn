import json
from io import BytesIO

import pymupdf
import pytest
from fastapi import UploadFile

from backend.config import Settings
from backend.services.process_intelligence import ProcessIntelligenceService
from backend.services.workspace_store import WorkspaceStore


class FakeBridge:
    configured = True

    def __init__(self):
        self.calls = []

    def generate_text(self, payload: str, *, max_tokens: int) -> str:
        self.calls.append((payload, max_tokens))
        if "# Pergunta atual" in payload:
            return 'A decisão está na página 1.\nFONTES_JSON: [{"documento":"sentenca.pdf","pagina":1}]'
        return json.dumps({
            "processo": {
                "numero_processo": "0000000-00.2026.8.26.0000",
                "classe_processual": "Procedimento comum",
                "tribunal": "Tribunal sintético",
                "unidade_judicial": "Vara sintética",
                "fase_processual": "Conhecimento",
                "assunto_principal": "Teste",
                "valor_causa": None,
                "ultima_data_relevante": "2026-09-30",
                "partes": [{"nome": "Parte A", "papel": "Autor"}],
                "resumo": "Resumo sintético.",
                "pedidos": ["Pedido sintético"],
                "fatos_controvertidos": [],
                "pontos_atencao": ["Conferir decisão"],
                "proximas_acoes_sugeridas": ["Revisar a página indicada"]
            },
            "linha_tempo": [{
                "data": "2026-09-30",
                "titulo": "Decisão",
                "descricao": "Decisão sintética para teste.",
                "categoria": "decisao",
                "documento": "sentenca.pdf",
                "pagina": 1,
                "confianca": "alta"
            }]
        }, ensure_ascii=False)


def make_pdf() -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Processo sintetico. Em 30/09/2026 foi proferida decisao para fins de teste automatizado.")
    data = pdf.tobytes()
    pdf.close()
    return data


@pytest.mark.asyncio
async def test_analysis_uses_text_generation_bridge() -> None:
    settings = Settings(bradesco_text_model="deployment-teste", bradesco_prompt_max_chars=12000)
    bridge = FakeBridge()
    service = ProcessIntelligenceService(settings, bridge, WorkspaceStore(settings))
    upload = UploadFile(filename="sentenca.pdf", file=BytesIO(make_pdf()), headers={"content-type": "application/pdf"})

    result = await service.analyze_uploads([upload])

    assert result.processo.numero_processo == "0000000-00.2026.8.26.0000"
    assert result.linha_tempo[0].documento == "sentenca.pdf"
    assert len(bridge.calls) >= 2
