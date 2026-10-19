"""Testes isolados do fluxo das cinco telas usando dados exclusivamente sintéticos."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from backend.config import Settings
from backend.principal import create_app
from backend.services.bjn_journey import routing_decision, TriageInput

BASE = "/api/v3/bjn/demandas"


def identity(role: str = "solicitante") -> dict[str, str]:
    """Identidades reservadas a testes; jamais usam dados reais."""
    address = {"solicitante": "solicitante@example.invalid", "advogado": "advogado@example.invalid", "admin": "admin@example.invalid"}[role]
    return {"X-Authenticated-User": address, "X-Authenticated-Role": role,
            "X-Authenticated-Name": "Pessoa sintetica"}


def synthetic_cpf() -> str:
    """Gera apenas valor numérico de teste com dígitos verificadores consistentes."""
    digits = [int(char) for char in "120000003"]
    for size in (9, 10):
        value = (sum(char * (size + 1 - pos) for pos, char in enumerate(digits[:size])) * 10) % 11
        digits.append(0 if value == 10 else value)
    return "".join(map(str, digits))


def demand_data(nature: str = "Inventário") -> dict:
    """Campos alinhados ao script das imagens; cliente e usuário fictícios."""
    return {"triage_type": "OUTRAS", "legal_department": "Jurídico de testes", "consult_area": "Negócios regionais",
            "service_nature": nature, "title": "Dúvida sintética sobre atendimento",
            "description": "Descrição de teste sobre uma situação jurídica simulada, sem dados reais.",
            "branch": "Agência fictícia 000", "requester_email": "solicitante@example.invalid",
            "client_name": "Cliente sintético", "client_document": synthetic_cpf(), "involved": []}


def client_in(directory: str):
    """Garante que cada teste usa banco e documentos temporários."""
    root = Path(directory)
    app = create_app(Settings(environment="local", bjn_database_path=root/"data.db",
        bjn_upload_directory=root/"uploads", bjn_allowed_lawyers=["advogado@example.invalid"]))
    return TestClient(app), app


def send(client: TestClient, nature: str = "Inventário", with_file: bool = True):
    """Inclui arquivo PDF sintético quando a natureza exige evidência."""
    files = [("files", ("exemplo.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n", "application/pdf"))] if with_file else []
    triage=client.post(f"{BASE}/triagem",headers=identity(),json={"category":"OUTRAS"})
    assert triage.status_code == 200
    data=demand_data(nature)
    data["triage_proof"]=triage.json()["proof"]
    return client.post(f"{BASE}/fluxo", headers=identity(), data={"payload": json.dumps(data)}, files=files)


def test_triage_distinguishes_external_routes_from_registration():
    """Nenhuma categoria externa deve criar demanda no banco."""
    with TemporaryDirectory() as tmp:
        client,_ = client_in(tmp)
        for value in ("OFICIO_DELEGACIA", "INTIMACAO_DELEGACIA", "OFICIO_SEM_BANCO"):
            result=client.post(f"{BASE}/triagem",json={"category":value})
            assert result.status_code==200
            assert result.json()["requires_registration"] is False
            assert result.json()["external_action_performed"] is False
        assert client.post(f"{BASE}/triagem",json={"category":"PROCESSO_COM_BANCO"}).status_code==422
        assert client.post(f"{BASE}/triagem",json={"category":"PROCESSO_COM_BANCO","bank_role":"REU","has_gcpj":False}).json()["requires_registration"] is False
        assert client.post(f"{BASE}/triagem",json={"category":"OUTRAS"}).json()["requires_registration"] is True
        assert client.get(BASE).json()["items"]==[]


def test_mandatory_attachment_and_protected_client_lookup():
    """Valida regra da natureza e busca por hash sem gravar CPF em claro."""
    with TemporaryDirectory() as tmp:
        client,_=client_in(tmp)
        assert send(client,with_file=False).status_code==422
        created=send(client)
        assert created.status_code==201,created.text
        record=created.json()
        assert record["status"]=="RECEBIDA"
        assert record["registration"]["branch"]=="Agência fictícia 000"
        assert synthetic_cpf() not in str(record)
        with sqlite3.connect(Path(tmp)/"data.db") as db:
            raw=str(db.execute("SELECT * FROM bjn_demand_context").fetchall())
            assert synthetic_cpf() not in raw
        search=client.get(BASE,headers=identity(),params={"client_cpf":synthetic_cpf()})
        assert search.status_code==200
        assert len(search.json()["items"])==1
        assert client.get(BASE,headers={"X-Authenticated-User":"outra@example.invalid","X-Authenticated-Role":"solicitante"},params={"client_cpf":synthetic_cpf()}).json()["items"]==[]


def test_general_opinion_requires_admin_competence_review():
    """Distingue triagem administrativa e encaminhamento humano."""
    with TemporaryDirectory() as tmp:
        client,_=client_in(tmp)
        created=send(client,"Pareceres em geral",False)
        assert created.status_code==201,created.text
        uid=created.json()["id"]
        assert created.json()["status"]=="TRIAGEM_ADMINISTRATIVA"
        assert client.patch(f"{BASE}/{uid}/atribuicao", headers=identity("admin"),json={"lawyer_email":"advogado@example.invalid"}).status_code==409
        assert client.patch(f"{BASE}/{uid}/competencia", headers=identity(), json={"is_team_competence":True}).status_code==403
        approved=client.patch(f"{BASE}/{uid}/competencia",headers=identity("admin"),json={"is_team_competence":True})
        assert approved.status_code==200
        assert approved.json()["status"]=="RECEBIDA"
        assert client.patch(f"{BASE}/{uid}/atribuicao",headers=identity("admin"),json={"lawyer_email":"advogado@example.invalid"}).status_code==200


def test_opinion_approved_by_assigned_lawyer_and_notified_only_when_configured():
    """Impede que IA e solicitante publiquem parecer sem validação humana."""
    with TemporaryDirectory() as tmp:
        client,app=client_in(tmp)
        created=send(client)
        assert created.status_code==201
        uid=created.json()["id"]
        assigned=client.patch(f"{BASE}/{uid}/atribuicao",headers=identity("admin"),json={"lawyer_email":"advogado@example.invalid"})
        assert assigned.status_code==200
        assert client.post(f"{BASE}/{uid}/parecer/rascunho",headers=identity()).status_code==403
        # O retorno sintético permite testar a integração sem conectar à API corporativa.
        from backend.services.bjn_document_opinion import OpinionSuggestion
        app.state.bjn_document_opinion.analyze=lambda nature,description,documents: OpinionSuggestion(
            nature, "Minuta sintética provisória a ser integralmente revisada pelo advogado responsável.",
            "hash-teste", "documento-teste", len(documents), ())
        draft=client.post(f"{BASE}/{uid}/parecer/rascunho",headers=identity("advogado"))
        assert draft.status_code==200,draft.text
        assert draft.json()["status"]=="PARECER_EM_REVISAO"
        assert draft.json()["opinion"]["draft_text"]
        requester=client.get(f"{BASE}/{uid}",headers=identity())
        assert requester.json()["opinion"]["draft_text"]==""
        final_text="Parecer sintético revisado, validado e concluído exclusivamente por profissional jurídico no ambiente de testes."
        assert client.post(f"{BASE}/{uid}/parecer/publicar",headers=identity("advogado"),json={"final_text":final_text,"human_review_confirmed":False}).status_code==422
        assert client.post(f"{BASE}/{uid}/parecer/publicar",headers=identity(),json={"final_text":final_text,"human_review_confirmed":True}).status_code==403
        published=client.post(f"{BASE}/{uid}/parecer/publicar",headers=identity("advogado"),json={"final_text":final_text,"human_review_confirmed":True})
        assert published.status_code==200,published.text
        assert published.json()["status"]=="CONCLUIDA"
        assert published.json()["notification_dispatch"]["status"]=="PENDENTE_CONFIGURACAO"
        assert client.get(f"{BASE}/{uid}",headers=identity()).json()["opinion"]["final_text"]==final_text
        with sqlite3.connect(Path(tmp)/"data.db") as db:
            assert db.execute("SELECT status FROM bjn_notifications").fetchone()[0]=="PENDENTE"
        assert client.post(f"{BASE}/{uid}/parecer/publicar",headers=identity("advogado"),json={"final_text":final_text,"human_review_confirmed":True}).status_code==409


def test_general_redirect_to_area_ends_internal_flow():
    """Triagem sem competência não atribui advogado automaticamente."""
    with TemporaryDirectory() as tmp:
        client,_=client_in(tmp)
        uid=send(client,"Pareceres em geral",False).json()["id"]
        relocated=client.patch(f"{BASE}/{uid}/competencia",headers=identity("admin"),json={"is_team_competence":False,"destination_area":"Equipe jurídica externa de teste"})
        assert relocated.status_code==200,relocated.text
        assert relocated.json()["status"]=="ENCAMINHADA_AREA"
        assert relocated.json()["lawyer_email"] is None
        assert client.patch(f"{BASE}/{uid}/atribuicao",headers=identity("admin"),json={"lawyer_email":"advogado@example.invalid"}).status_code==409


def test_prevent_skipping_triage_or_reusing_another_users_proof():
    """O comprovante emitido para um solicitante não autoriza cadastro de outro."""
    with TemporaryDirectory() as tmp:
        client,_=client_in(tmp)
        data=demand_data()
        no_proof=client.post(f"{BASE}/fluxo", headers=identity(), data={"payload":json.dumps(data)})
        assert no_proof.status_code==409
        triage=client.post(f"{BASE}/triagem", headers=identity(), json={"category":"OUTRAS"}).json()
        data["triage_proof"]=triage["proof"]
        wrong=client.post(f"{BASE}/fluxo",headers=identity("admin"),data={"payload":json.dumps(data)})
        assert wrong.status_code==409
        assert client.get(BASE,headers=identity()).json()["items"]==[]


def test_search_filters_are_sent_in_request_body():
    """Mantém CPF fora da URL e preserva a visibilidade por usuário."""
    with TemporaryDirectory() as tmp:
        client,_=client_in(tmp)
        uid=send(client).json()["id"]
        result=client.post(f"{BASE}/consulta",headers=identity(),json={"client_cpf":synthetic_cpf(),"branch":"Agência fictícia 000"})
        assert result.status_code==200
        assert [item["id"] for item in result.json()["items"]]==[uid]
        assert client.post(f"{BASE}/consulta",headers={"X-Authenticated-User":"outra@example.invalid","X-Authenticated-Role":"solicitante"},json={"client_cpf":synthetic_cpf()}).json()["items"]==[]
