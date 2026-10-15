"""Persistência de demandas BJN, histórico auditável e documentos privados.

O armazenamento local em SQLite é destinado a desenvolvimento ou instalação de instância única.
Produção exige volume persistente criptografado, backup e política de retenção homologada.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO, Iterable
from uuid import uuid4

from pydantic import Field

from backend.contracts.base import Contract
from backend.errors import ServiceError
from backend.services.bjn_journey import validate_journey_fields, NATURES

STATUS = ("RECEBIDA", "EM_TRIAGEM", "EM_ANALISE", "AGUARDANDO_INFORMACOES", "CONCLUIDA", "CANCELADA", "RESOLVIDA_IA", "TRIAGEM_ADMINISTRATIVA", "ENCAMINHADA_AREA", "PARECER_EM_REVISAO")

# Identidades sintéticas de desenvolvimento, nunca cadastradas como pessoas reais.
DEMO_LAWYERS = {
    "advogada.teste01@example.invalid": "Advogada de Testes 01 · Contratos",
    "advogado.teste02@example.invalid": "Advogado de Testes 02 · Consultivo",
    "advogada.teste03@example.invalid": "Advogada de Testes 03 · Proteção de Dados",
    "advogado.teste04@example.invalid": "Advogado de Testes 04 · Contencioso",
}

DOCUMENT_TYPES = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}
MAX_DOCUMENT_BYTES = 15 * 1024 * 1024
MAX_DOCUMENTS_PER_DEMAND = 20


class Involved(Contract):
    """Pessoa relacionada à consulta; somente dados necessários ao atendimento."""

    type: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=150)
    document: str = Field(default="", max_length=32)
    period: str = Field(default="", max_length=100)


class DemandCreate(Contract):
    """Dados de abertura fornecidos pelo demandante, sem permissão para escolher advogado/status."""

    legal_department: str = Field(min_length=2, max_length=120)
    consult_area: str = Field(min_length=2, max_length=120)
    service_nature: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=5, max_length=180)
    description: str = Field(min_length=15, max_length=8000)
    involved: list[Involved] = Field(default_factory=list, max_length=20)
    # Nova jornada: campos opcionais no contrato para permitir leitura de dados históricos.
    triage_type: str = ""
    triage_proof: str = Field(default="", max_length=100)
    branch: str = Field(default="", max_length=40)
    requester_email: str = Field(default="", max_length=250)
    client_name: str = Field(default="", max_length=180)
    client_document: str = Field(default="", max_length=14)


class Assignment(Contract):
    """Atribuição manual exclusivamente a advogado da lista autorizada."""

    lawyer_email: str = Field(min_length=5, max_length=250)


class StatusUpdate(Contract):
    """Atualização explícita de status com observação opcional para auditoria."""

    status: str
    note: str = Field(default="", max_length=300)


@dataclass(frozen=True)
class Actor:
    """Identidade previamente autenticada pelo gateway corporativo."""

    user_id: str
    display_name: str
    role: str


@dataclass
class SavedDocument:
    """Arquivo validado, temporariamente armazenado até a transação SQL terminar."""

    original_name: str
    media_type: str
    file_size: int
    sha256: str
    temp_path: Path
    category: str


def utc_now() -> str:
    """Representação única UTC para ordenação cronológica consistente."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_original_name(value: str) -> str:
    """Descarta diretórios e caracteres de controle vindos do upload."""
    name = re.split(r"[/\\]", value or "")[-1].strip()
    name = "".join(char for char in name if char.isprintable() and char not in '\\/:*?"<>|')
    if not name or len(name) > 180:
        raise ServiceError("Nome de arquivo inválido.", 422, code="INVALID_FILENAME")
    return name


def sniff_media(header: bytes) -> str | None:
    """Permite pré-visualização apenas de formatos conhecidos e não executáveis."""
    if header.startswith(b"%PDF-"):
        return "application/pdf"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


class DemandStore:
    """Repositório coeso de cadastro, acesso, eventos e anexos."""

    def __init__(self, database: Path, uploads: Path, allowed_lawyers: Iterable[str] = (), document_key: str = ""): 
        self.document_key = document_key.encode("utf-8")
        self.database = database.expanduser().resolve()
        self.uploads = uploads.expanduser().resolve()
        self.allowed_lawyers = sorted({email.lower().strip() for email in allowed_lawyers if email.strip()})
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.uploads.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        """Conexão independente por solicitação; chaves estrangeiras obrigatórias."""
        connection = sqlite3.connect(str(self.database), timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        return connection

    def _initialize(self) -> None:
        """Migração inicial aditiva e idempotente, sem criar dados fictícios."""
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS bjn_demands (
                  id TEXT PRIMARY KEY, legal_department TEXT NOT NULL, consult_area TEXT NOT NULL,
                  service_nature TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
                  requester_id TEXT NOT NULL, requester_name TEXT NOT NULL,
                  lawyer_email TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_bjn_requester ON bjn_demands(requester_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_bjn_lawyer ON bjn_demands(lawyer_email, created_at);
                CREATE TABLE IF NOT EXISTS bjn_involved (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, demand_id TEXT NOT NULL REFERENCES bjn_demands(id) ON DELETE CASCADE,
                  type TEXT NOT NULL, name TEXT NOT NULL, document TEXT NOT NULL, period TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bjn_documents (
                  id TEXT PRIMARY KEY, demand_id TEXT NOT NULL REFERENCES bjn_demands(id) ON DELETE CASCADE,
                  original_name TEXT NOT NULL, media_type TEXT NOT NULL, file_size INTEGER NOT NULL,
                  sha256 TEXT NOT NULL, storage_name TEXT NOT NULL, category TEXT NOT NULL,
                  uploaded_by TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_bjn_doc_demand ON bjn_documents(demand_id);
                CREATE TABLE IF NOT EXISTS bjn_events (
                  id TEXT PRIMARY KEY, demand_id TEXT NOT NULL REFERENCES bjn_demands(id) ON DELETE CASCADE,
                  event_type TEXT NOT NULL, description TEXT NOT NULL, actor_id TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_bjn_events_demand ON bjn_events(demand_id, created_at);
                CREATE TABLE IF NOT EXISTS bjn_ai_guidance (
                  demand_id TEXT PRIMARY KEY REFERENCES bjn_demands(id) ON DELETE CASCADE,
                  resumo TEXT NOT NULL, orientacao TEXT NOT NULL, passos_json TEXT NOT NULL,
                  encaminhamento TEXT NOT NULL, prompt_hash TEXT NOT NULL, description_hash TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bjn_demand_context (
                  demand_id TEXT PRIMARY KEY REFERENCES bjn_demands(id) ON DELETE CASCADE,
                  triage_type TEXT NOT NULL, branch TEXT NOT NULL,
                  requester_email TEXT NOT NULL, client_name TEXT NOT NULL,
                  document_hmac TEXT NOT NULL, document_mask TEXT NOT NULL,
                  competence TEXT NOT NULL DEFAULT 'PENDENTE', destination_area TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_bjn_branch ON bjn_demand_context(branch);
                CREATE INDEX IF NOT EXISTS idx_bjn_client_document ON bjn_demand_context(document_hmac);
                CREATE TABLE IF NOT EXISTS bjn_opinions (
                  demand_id TEXT PRIMARY KEY REFERENCES bjn_demands(id) ON DELETE CASCADE,
                  draft_text TEXT NOT NULL DEFAULT '', final_text TEXT NOT NULL DEFAULT '',
                  prompt_hash TEXT NOT NULL DEFAULT '', draft_at TEXT,
                  published_at TEXT, reviewer_id TEXT, version INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS bjn_notifications (
                  id TEXT PRIMARY KEY, demand_id TEXT NOT NULL REFERENCES bjn_demands(id) ON DELETE CASCADE,
                  destination TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
                  delivered_at TEXT, error_code TEXT NOT NULL DEFAULT ''
                );
            """)

    @staticmethod
    def _can_view(demand: sqlite3.Row, actor: Actor) -> bool:
        """Princípio do menor privilégio: autor, advogado responsável ou administrador."""
        return actor.role == "admin" or demand["requester_id"] == actor.user_id or (
            actor.role == "advogado" and demand["lawyer_email"] == actor.user_id
        )

    def _require(self, db: sqlite3.Connection, demand_id: str, actor: Actor) -> sqlite3.Row:
        """Usa 404 também para demandas sem permissão, evitando enumeração."""
        row = db.execute("SELECT * FROM bjn_demands WHERE id = ?", (demand_id,)).fetchone()
        if row is None or not self._can_view(row, actor):
            raise ServiceError("Demanda não encontrada.", 404, code="DEMAND_NOT_FOUND")
        return row

    @staticmethod
    def _event(db: sqlite3.Connection, demand_id: str, event_type: str, description: str, actor: Actor, now: str) -> None:
        """Mantém histórico separado de logs técnicos, sem conteúdo documental."""
        db.execute("INSERT INTO bjn_events VALUES (?,?,?,?,?,?)", (uuid4().hex, demand_id, event_type, description, actor.user_id, now))

    def list_demands(self, actor: Actor, status: str = "", query: str = "", limit: int = 50,
                     branch: str = "", registered_email: str = "", from_date: str = "", client_cpf: str = "") -> list[dict]:
        """Lista solicitações acessíveis em ordem decrescente, sem expor pessoas de outras equipes."""
        if status and status not in STATUS:
            raise ServiceError("Status inválido.", 422, code="INVALID_STATUS")
        conditions: list[str] = []
        params: list[object] = []
        if actor.role != "admin":
            if actor.role == "advogado":
                conditions.append("(requester_id = ? OR lawyer_email = ?)")
                params.extend([actor.user_id, actor.user_id])
            else:
                conditions.append("requester_id = ?")
                params.append(actor.user_id)
        if branch.strip():
            conditions.append("id IN (SELECT demand_id FROM bjn_demand_context WHERE branch = ?)")
            params.append(branch.strip()[:40])
        if registered_email.strip():
            conditions.append("(requester_id LIKE ? OR requester_name LIKE ?)")
            filter_value = f"%{registered_email.strip()[:120]}%"
            params.extend([filter_value, filter_value])
        if from_date.strip():
            conditions.append("substr(created_at,1,10)=?")
            params.append(from_date.strip()[:10])
        if client_cpf.strip():
            if not self.document_key:
                raise ServiceError("Busca por CPF indisponível sem chave HMAC.", 503, code="DOCUMENT_KEY_MISSING")
            import re
            digits = re.sub(r"\D", "", client_cpf)
            if len(digits) != 11:
                raise ServiceError("Informe um CPF com 11 dígitos.", 422, code="INVALID_CPF_FILTER")
            digest = hmac.new(self.document_key, digits.encode("ascii"), hashlib.sha256).hexdigest()
            conditions.append("id IN (SELECT demand_id FROM bjn_demand_context WHERE document_hmac = ?)")
            params.append(digest)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if query.strip():
            conditions.append("(id LIKE ? OR title LIKE ? OR consult_area LIKE ?)")
            search = f"%{query.strip()[:120]}%"
            params.extend([search, search, search])
        sql = "SELECT id,title,consult_area,service_nature,status,lawyer_email,requester_name,created_at,updated_at FROM bjn_demands"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(min(50, max(1, limit)))
        with self._connect() as db:
            return [dict(row) for row in db.execute(sql, params).fetchall()]

    def get_demand(self, demand_id: str, actor: Actor) -> dict:
        """Compõe cabeçalho, envolvidos, documentos e linha do tempo na mesma resposta."""
        with self._connect() as db:
            base = dict(self._require(db, demand_id, actor))
            base["involved"] = [dict(r) for r in db.execute(
                "SELECT type,name,document,period FROM bjn_involved WHERE demand_id = ? ORDER BY id", (demand_id,)
            )]
            base["documents"] = [dict(r) for r in db.execute(
                "SELECT id,original_name,media_type,file_size,sha256,category,uploaded_by,created_at FROM bjn_documents WHERE demand_id = ? ORDER BY created_at,id", (demand_id,)
            )]
            base["events"] = [dict(r) for r in db.execute(
                "SELECT event_type,description,actor_id,created_at FROM bjn_events WHERE demand_id = ? ORDER BY created_at DESC,id DESC", (demand_id,)
            )]
            guidance = db.execute("SELECT resumo,orientacao,passos_json,encaminhamento,created_at FROM bjn_ai_guidance WHERE demand_id=?", (demand_id,)).fetchone()
            base["ai_guidance"] = ({"resumo": guidance["resumo"], "orientacao": guidance["orientacao"], "passos_sugeridos": json.loads(guidance["passos_json"]), "encaminhamento": guidance["encaminhamento"], "created_at": guidance["created_at"]} if guidance else None)
            context = db.execute("SELECT triage_type,branch,requester_email,client_name,document_mask,competence,destination_area FROM bjn_demand_context WHERE demand_id=?", (demand_id,)).fetchone()
            base["registration"] = dict(context) if context else None
            opinion = db.execute("SELECT draft_text,final_text,published_at,reviewer_id,draft_at,version FROM bjn_opinions WHERE demand_id=?", (demand_id,)).fetchone()
            base["opinion"] = dict(opinion) if opinion else None
            if base["opinion"] and not (actor.role == "admin" or (actor.role == "advogado" and base["lawyer_email"] == actor.user_id)):
                base["opinion"]["draft_text"] = ""

            base["can_review_opinion"] = actor.role == "advogado" and base["lawyer_email"] == actor.user_id and base["status"] in {"EM_ANALISE", "PARECER_EM_REVISAO"}
            base["can_review_competence"] = actor.role == "admin" and base["status"] == "TRIAGEM_ADMINISTRATIVA"
            base["can_resolve_ai"] = (base["requester_id"] == actor.user_id and base["status"] in {"RECEBIDA", "EM_TRIAGEM"} and not base["lawyer_email"] and bool(guidance) and guidance["encaminhamento"] == "POSSIVEL_AUTOATENDIMENTO")
            base["can_manage"] = actor.role == "admin" or (actor.role == "advogado" and base["lawyer_email"] == actor.user_id)
            base["can_assign"] = actor.role == "admin"
            return base

    def create(self, data: DemandCreate, actor: Actor, docs: list[SavedDocument]) -> dict:
        """Salva dados e documentos juntos; remove arquivos se a transação falhar."""
        demand_id = f"BJN-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:10].upper()}"
        now = utc_now()
        moved: list[Path] = []
        try:
            with self._connect() as db:
                if data.triage_type:
                    validate_journey_fields(data, len(docs))
                    if not self.document_key:
                        raise ServiceError("A chave de proteção do CPF não está configurada.", 503, code="DOCUMENT_KEY_MISSING")
                    if actor.role != "admin" and actor.user_id.find("@") > 0 and data.requester_email.strip().lower() != actor.user_id:
                        raise ServiceError("O e-mail do demandante deve coincidir com a sessão.", 403, code="REQUESTER_EMAIL_MISMATCH")
                initial_status = "TRIAGEM_ADMINISTRATIVA" if data.triage_type and data.service_nature == "Pareceres em geral" else "RECEBIDA"
                db.execute("INSERT INTO bjn_demands VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                    demand_id, data.legal_department, data.consult_area, data.service_nature,
                    data.title, data.description, actor.user_id, actor.display_name,
                    None, initial_status, now, now,
                ))
                if data.triage_type:
                    import re
                    digits = re.sub(r"\D", "", data.client_document)
                    hashed = hmac.new(self.document_key, digits.encode("ascii"), hashlib.sha256).hexdigest()
                    masked = "***.***.***-" + digits[-2:]
                    db.execute("INSERT INTO bjn_demand_context VALUES (?,?,?,?,?,?,?,?,?)", (
                        demand_id, data.triage_type, data.branch.strip(), data.requester_email.strip().lower(),
                        data.client_name.strip(), hashed, masked, "PENDENTE" if initial_status == "TRIAGEM_ADMINISTRATIVA" else "DIRETO", "",
                    ))
                for row in data.involved:
                    db.execute("INSERT INTO bjn_involved (demand_id,type,name,document,period) VALUES (?,?,?,?,?)", (
                        demand_id, row.type, row.name, row.document, row.period
                    ))
                for document in docs:
                    target = self._insert_document(db, demand_id, actor, document, now)
                    moved.append(target)
                self._event(db, demand_id, "CRIACAO", "Protocolo criado; triagem administrativa pendente." if initial_status == "TRIAGEM_ADMINISTRATIVA" else "Protocolo criado; fluxo direto para distribuição.", actor, now)
        except Exception:
            for path in moved:
                path.unlink(missing_ok=True)
            raise
        return self.get_demand(demand_id, actor)

    def _insert_document(self, db: sqlite3.Connection, demand_id: str, actor: Actor, item: SavedDocument, now: str) -> Path:
        """Arquivo armazenado por UUID sem usar o nome do upload como caminho."""
        doc_id = uuid4().hex
        stored_name = doc_id + DOCUMENT_TYPES[item.media_type]
        target = self.uploads / stored_name
        # Primeiro registra metadados sob a transação; somente depois move o arquivo.
        # Caso a movimentação falhe, o rollback elimina os metadados incompletos.
        db.execute("INSERT INTO bjn_documents VALUES (?,?,?,?,?,?,?,?,?,?)", (
            doc_id, demand_id, item.original_name, item.media_type, item.file_size, item.sha256,
            stored_name, item.category, actor.user_id, now
        ))
        os.replace(item.temp_path, target)
        return target

    def add_documents(self, demand_id: str, actor: Actor, docs: list[SavedDocument]) -> dict:
        """Anexa documentos posteriores sem modificar conteúdo previamente recebido."""
        moved: list[Path] = []
        try:
            with self._connect() as db:
                demand = self._require(db, demand_id, actor)
                if demand["status"] in {"CONCLUIDA", "CANCELADA", "RESOLVIDA_IA", "ENCAMINHADA_AREA"}:
                    raise ServiceError("Não é possível anexar documentos a uma demanda encerrada.", 409, code="CLOSED_DEMAND")
                count = db.execute("SELECT COUNT(*) FROM bjn_documents WHERE demand_id=?", (demand_id,)).fetchone()[0]
                if count + len(docs) > MAX_DOCUMENTS_PER_DEMAND:
                    raise ServiceError("Limite de documentos da demanda excedido.", 422, code="TOO_MANY_FILES")
                now = utc_now()
                for document in docs:
                    moved.append(self._insert_document(db, demand_id, actor, document, now))
                self._event(db, demand_id, "DOCUMENTO", f"{len(docs)} documento(s) incluído(s).", actor, now)
                db.execute("UPDATE bjn_demands SET updated_at=? WHERE id=?", (now, demand_id))
        except Exception:
            for path in moved:
                path.unlink(missing_ok=True)
            raise
        return self.get_demand(demand_id, actor)

    def document(self, demand_id: str, document_id: str, actor: Actor) -> tuple[Path, dict]:
        """Autoriza o acesso ANTES de buscar o caminho físico do documento."""
        with self._connect() as db:
            self._require(db, demand_id, actor)
            row = db.execute("SELECT * FROM bjn_documents WHERE id=? AND demand_id=?", (document_id, demand_id)).fetchone()
            if row is None:
                raise ServiceError("Documento não encontrado.", 404, code="DOCUMENT_NOT_FOUND")
            path = self.uploads / row["storage_name"]
            if not path.is_file():
                raise ServiceError("Arquivo indisponível. Contate o suporte.", 503, code="DOCUMENT_UNAVAILABLE")
            return path, dict(row)

    def assign(self, demand_id: str, actor: Actor, lawyer_email: str) -> dict:
        """Distribuição MANUAL, somente para advogado explicitamente autorizado."""
        if actor.role != "admin":
            raise ServiceError("Somente administração pode distribuir demandas.", 403, code="FORBIDDEN")
        normalized = lawyer_email.lower().strip()
        if normalized not in self.allowed_lawyers:
            raise ServiceError("Advogado não consta do cadastro autorizado.", 422, code="UNKNOWN_LAWYER")
        with self._connect() as db:
            demand = self._require(db, demand_id, actor)
            if demand["status"] in {"CONCLUIDA", "CANCELADA", "RESOLVIDA_IA", "ENCAMINHADA_AREA"}:
                raise ServiceError("Demanda encerrada não pode ser distribuída.", 409, code="CLOSED_DEMAND")
            if demand["status"] == "TRIAGEM_ADMINISTRATIVA":
                raise ServiceError("Conclua a triagem administrativa antes da distribuição.", 409, code="COMPETENCE_PENDING")
            now = utc_now()
            db.execute("UPDATE bjn_demands SET lawyer_email=?,status=?,updated_at=? WHERE id=?", (normalized, "EM_ANALISE", now, demand_id))
            self._event(db, demand_id, "DISTRIBUICAO", f"Demanda atribuída a {normalized}.", actor, now)
        return self.get_demand(demand_id, actor)

    def save_ai_guidance(self, demand_id: str, actor: Actor, guidance: object, prompt_hash: str, description_hash: str) -> dict:
        """Persiste a sugestão sem permitir alterar demanda por usuário não autorizado."""
        with self._connect() as db:
            demand = self._require(db, demand_id, actor)
            actual_hash = hashlib.sha256(demand["description"].strip().encode("utf-8")).hexdigest()
            if actual_hash != description_hash:
                raise ServiceError("A descrição da demanda mudou. Refaça a análise.", 409, code="AI_STALE_DESCRIPTION")
            now = utc_now()
            db.execute("""INSERT INTO bjn_ai_guidance(demand_id,resumo,orientacao,passos_json,encaminhamento,prompt_hash,description_hash,created_at)
                VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(demand_id) DO UPDATE SET resumo=excluded.resumo,
                orientacao=excluded.orientacao,passos_json=excluded.passos_json,encaminhamento=excluded.encaminhamento,
                prompt_hash=excluded.prompt_hash,description_hash=excluded.description_hash,created_at=excluded.created_at""", (
                demand_id, guidance.resumo, guidance.orientacao, json.dumps(guidance.passos_sugeridos,ensure_ascii=False),
                guidance.encaminhamento, prompt_hash, description_hash, now,
            ))
            self._event(db, demand_id, "SUGESTAO_IA", "Orientação informacional gerada com text_generator (sem decisão automática).", actor, now)
            db.execute("UPDATE bjn_demands SET updated_at=? WHERE id=?", (now, demand_id))
        return self.get_demand(demand_id, actor)

    def resolve_with_ai(self, demand_id: str, actor: Actor) -> dict:
        """Registra escolha explícita do solicitante, sem concluir análise jurídica."""
        with self._connect() as db:
            demand = self._require(db, demand_id, actor)
            if demand["requester_id"] != actor.user_id:
                raise ServiceError("Somente o solicitante pode encerrar por autoatendimento.", 403, code="FORBIDDEN")
            guidance = db.execute("SELECT encaminhamento FROM bjn_ai_guidance WHERE demand_id=?", (demand_id,)).fetchone()
            if demand["status"] not in {"RECEBIDA", "EM_TRIAGEM"} or demand["lawyer_email"] or not guidance or guidance["encaminhamento"] != "POSSIVEL_AUTOATENDIMENTO":
                raise ServiceError("Esta demanda exige encaminhamento ou não está disponível para autoatendimento.", 409, code="AI_RESOLUTION_NOT_ALLOWED")
            now = utc_now()
            db.execute("UPDATE bjn_demands SET status=?,updated_at=? WHERE id=?", ("RESOLVIDA_IA", now, demand_id))
            self._event(db, demand_id, "AUTOATENDIMENTO", "Solicitante informou que a orientação inicial resolveu sua dúvida; não houve parecer jurídico.", actor, now)
        return self.get_demand(demand_id, actor)

    def update_status(self, demand_id: str, actor: Actor, data: StatusUpdate) -> dict:
        """Somente responsável designado ou administração podem alterar andamento."""
        permitted = {
            "RECEBIDA": {"EM_TRIAGEM", "CANCELADA"},
            "TRIAGEM_ADMINISTRATIVA": {"CANCELADA"},
            "ENCAMINHADA_AREA": set(),
            "PARECER_EM_REVISAO": {"AGUARDANDO_INFORMACOES", "CANCELADA"},
            "EM_TRIAGEM": {"EM_ANALISE", "AGUARDANDO_INFORMACOES", "CANCELADA"},
            "EM_ANALISE": {"AGUARDANDO_INFORMACOES", "CONCLUIDA", "CANCELADA"},
            "AGUARDANDO_INFORMACOES": {"EM_ANALISE", "CANCELADA"},
            "CONCLUIDA": set(), "CANCELADA": set(), "RESOLVIDA_IA": set(),
        }
        with self._connect() as db:
            current = self._require(db, demand_id, actor)
            if actor.role != "admin" and not (actor.role == "advogado" and current["lawyer_email"] == actor.user_id):
                raise ServiceError("Usuário não autorizado a alterar o status.", 403, code="FORBIDDEN")
            if data.status not in permitted[current["status"]]:
                raise ServiceError("Transição de status não permitida.", 409, code="INVALID_TRANSITION")
            if data.status == "CONCLUIDA" and db.execute("SELECT 1 FROM bjn_demand_context WHERE demand_id=?", (demand_id,)).fetchone():
                if not db.execute("SELECT 1 FROM bjn_opinions WHERE demand_id=? AND published_at IS NOT NULL", (demand_id,)).fetchone():
                    raise ServiceError("Publique o parecer validado pelo advogado antes da conclusão.", 409, code="OPINION_REQUIRED")
            if data.status == "EM_ANALISE" and not current["lawyer_email"]:
                raise ServiceError("Distribua a demanda antes de iniciar a análise.", 409, code="NOT_ASSIGNED")
            now = utc_now()
            db.execute("UPDATE bjn_demands SET status=?,updated_at=? WHERE id=?", (data.status, now, demand_id))
            # A observação é visível somente para quem possui acesso à demanda.
            description = f"Status atualizado para {data.status.replace('_', ' ').lower()}."
            if data.note:
                description += f" Observação: {data.note}"
            self._event(db, demand_id, "STATUS", description, actor, now)
        return self.get_demand(demand_id, actor)


    def review_competence(self, demand_id: str, actor: Actor, in_scope: bool, destination: str) -> dict:
        """A triagem administrativa define competência antes de distribuição de parecer geral."""
        if actor.role != "admin":
            raise ServiceError("Acesso restrito à triagem administrativa.", 403, code="FORBIDDEN")
        with self._connect() as db:
            demand = self._require(db, demand_id, actor)
            if demand["status"] != "TRIAGEM_ADMINISTRATIVA":
                raise ServiceError("Demanda não está aguardando triagem administrativa.", 409, code="INVALID_COMPETENCE_STATE")
            if not in_scope and len(destination.strip()) < 3:
                raise ServiceError("Informe a área de destino.", 422, code="DESTINATION_REQUIRED")
            now = utc_now()
            status = "RECEBIDA" if in_scope else "ENCAMINHADA_AREA"
            db.execute("UPDATE bjn_demand_context SET competence=?,destination_area=? WHERE demand_id=?",
                       ("SIM" if in_scope else "NAO", "" if in_scope else destination.strip(), demand_id))
            db.execute("UPDATE bjn_demands SET status=?,updated_at=? WHERE id=?", (status, now, demand_id))
            message = "Competência da equipe confirmada; disponível para distribuição." if in_scope else "Encaminhamento indicado à área competente (sem transmissão externa automática)."
            self._event(db, demand_id, "TRIAGEM_COMPETENCIA", message, actor, now)
        return self.get_demand(demand_id, actor)

    def demand_for_opinion(self, demand_id: str, actor: Actor) -> dict:
        """Recupera somente natureza e descrição após confirmar advogado designado."""
        with self._connect() as db:
            demand = self._require(db, demand_id, actor)
            if actor.role != "advogado" or demand["lawyer_email"] != actor.user_id:
                raise ServiceError("Somente advogado designado pode redigir parecer.", 403, code="FORBIDDEN")
            if demand["status"] not in {"EM_ANALISE", "PARECER_EM_REVISAO"}:
                raise ServiceError("Demanda fora da etapa de elaboração.", 409, code="OPINION_STATE_INVALID")
            return {"service_nature": demand["service_nature"], "description": demand["description"]}

    def save_opinion_draft(self, demand_id: str, actor: Actor, text: str, prompt_hash: str) -> dict:
        """Persiste versão preliminar; nunca torna visível o rascunho ao demandante."""
        self.demand_for_opinion(demand_id, actor)
        with self._connect() as db:
            now = utc_now()
            db.execute("""INSERT INTO bjn_opinions(demand_id,draft_text,prompt_hash,draft_at,version)
                VALUES (?,?,?,?,1) ON CONFLICT(demand_id) DO UPDATE SET
                draft_text=excluded.draft_text,prompt_hash=excluded.prompt_hash,draft_at=excluded.draft_at,
                version=bjn_opinions.version+1""", (demand_id, text, prompt_hash, now))
            db.execute("UPDATE bjn_demands SET status=?,updated_at=? WHERE id=?", ("PARECER_EM_REVISAO", now, demand_id))
            self._event(db, demand_id, "PARECER_RASCUNHO", "Proposta de IA criada para revisão jurídica (não publicada).", actor, now)
        return self.get_demand(demand_id, actor)

    def publish_opinion(self, demand_id: str, actor: Actor, final_text: str) -> dict:
        """Registra aprovação humana e cria evento de e-mail pendente de despacho."""
        self.demand_for_opinion(demand_id, actor)
        with self._connect() as db:
            now = utc_now()
            email = db.execute("SELECT requester_email FROM bjn_demand_context WHERE demand_id=?", (demand_id,)).fetchone()
            # Demandas legadas não possuem cadastro de e-mail: o parecer pode ser
            # publicado com revisão humana, mas não se cria notificação sem destino.
            requester_email = email["requester_email"].strip() if email and email["requester_email"] else ""
            db.execute("""INSERT INTO bjn_opinions(demand_id,final_text,published_at,reviewer_id,version)
                VALUES (?,?,?,?,1) ON CONFLICT(demand_id) DO UPDATE SET
                final_text=excluded.final_text,published_at=excluded.published_at,reviewer_id=excluded.reviewer_id,
                version=bjn_opinions.version+1""", (demand_id, final_text.strip(), now, actor.user_id))
            db.execute("UPDATE bjn_demands SET status=?,updated_at=? WHERE id=?", ("CONCLUIDA", now, demand_id))
            if requester_email:
                db.execute("INSERT INTO bjn_notifications VALUES (?,?,?,?,?,?,?)", (
                    uuid4().hex, demand_id, requester_email, "PENDENTE", now, None, ""))
            self._event(db, demand_id, "PARECER_PUBLICADO", "Parecer revisado e publicado pelo advogado responsável.", actor, now)
        return self.get_demand(demand_id, actor)

    def pending_notifications(self, demand_id: str) -> list[dict]:
        """Lista apenas notificações ainda não entregues para envio transacional."""
        with self._connect() as db:
            return [dict(r) for r in db.execute("SELECT id,destination FROM bjn_notifications WHERE demand_id=? AND status='PENDENTE'", (demand_id,))]

    def notification_result(self, notification_id: str, delivered: bool, code: str = "") -> None:
        """Atualiza o outbox após tentativa efetiva; nunca registra conteúdo do parecer."""
        with self._connect() as db:
            db.execute("UPDATE bjn_notifications SET status=?,delivered_at=?,error_code=? WHERE id=? AND status='PENDENTE'",
                       ("ENVIADO" if delivered else "PENDENTE", utc_now() if delivered else None, code[:48], notification_id))


def save_upload(stream: BinaryIO, original_name: str, media_type: str, temp_directory: Path, category: str) -> SavedDocument:
    """Valida assinatura e limite durante leitura em blocos, sem carregar o arquivo na memória."""
    name = safe_original_name(original_name)
    if category not in {"ANEXO", "DOCUMENTO_ENVIADO"}:
        raise ServiceError("Categoria inválida.", 422, code="INVALID_CATEGORY")
    tmp_path: Path | None = None
    try:
        with NamedTemporaryFile(dir=temp_directory, delete=False, prefix=".upload-", suffix=".tmp") as buffer:
            tmp_path = Path(buffer.name)
            digester = hashlib.sha256()
            size = 0
            first = b""
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                if not first:
                    first = chunk[:16]
                size += len(chunk)
                if size > MAX_DOCUMENT_BYTES:
                    raise ServiceError("Documento excede o limite de 15 MB.", 413, code="FILE_TOO_LARGE")
                digester.update(chunk)
                buffer.write(chunk)
        found = sniff_media(first)
        extensions = {"application/pdf": {".pdf"}, "image/png": {".png"}, "image/jpeg": {".jpeg", ".jpg"}}
        if not found or found != media_type or Path(name).suffix.lower() not in extensions.get(found, set()):
            raise ServiceError("Formato inválido. Utilize PDF, PNG ou JPEG.", 415, code="UNSUPPORTED_MEDIA")
        return SavedDocument(name, found, size, digester.hexdigest(), tmp_path, category)
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise
