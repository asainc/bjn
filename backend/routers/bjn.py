"""API BJN isolada do chatbot processual."""
from fastapi import APIRouter, Request, HTTPException, Response
from backend.services.bjn_rules import Answers, Assessment, assess, workflow
from backend.contracts import ChatRequest, ChatResponse
router = APIRouter(prefix="/bjn", tags=["BJN"])
@router.get("/questionario")
def questionnaire() -> dict:
    """Publica o script transcrito, sem perguntas adicionadas pelo frontend."""
    return workflow()
@router.post("/avaliar", response_model=Assessment)
def evaluate(body: Answers) -> Assessment:
    try:
        return assess(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    return request.app.state.bjn_chat_service.ask(body.pergunta)
@router.post("/gerar-pdf")
def generate_contract_pdf(body: Answers) -> Response:
    try:
        decision = assess(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    raise HTTPException(409, {"message": "PDF bloqueado enquanto não houver homologação da matriz literal script_bjn / book", "reasons": decision.reasons})


@router.post("/previa-clausulas")
def preview_book_clauses(body: Answers) -> dict:
    """Aplica os vínculos documentados sem exigir o questionário completo."""
    from backend.services.bjn_book_preview import selected_book_clauses
    schema = workflow()
    by_id = {q["id"]:q for q in schema["questions"]}
    for key,value in body.answers.items():
        if key not in by_id:
            raise HTTPException(422, f"Pergunta não prevista: {key}")
        options = {option["value"] for option in by_id[key].get("options", [])}
        if options and (value not in options if not isinstance(value,list) else any(v not in options for v in value)):
            raise HTTPException(422, f"Opção não prevista: {key}")
    return {"clauses":selected_book_clauses(body.answers),
            "note":"Catálogo ordenado em Excel; cláusulas OCR ainda pendentes de conferência literal. PDF bloqueado."}

@router.get("/book-evidencia/{filename}")
def get_book_evidence(filename: str) -> Response:
    from backend.services.bjn_book_preview import book_image
    return Response(book_image(filename),media_type="image/jpeg",headers={"Cache-Control":"private, max-age=300"})

@router.get("/catalogo")
def clause_catalog() -> dict:
    """Permite consultar todos os registros do Excel sem acionar regras não homologadas."""
    from backend.services.bjn_book_preview import catalog_records
    records = catalog_records()
    return {"total":len(records),"columns":["ID","Tema","Número / título","Texto literal (OCR a conferir)"],
            "status":"OCR_PENDENTE_CONFERENCIA","items":records}
