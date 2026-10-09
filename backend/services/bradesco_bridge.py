"""Integração do AI Ready com as funções corporativas de ``gpt_bradesco.py``.

A análise dos PDFs usa ``text_generator``. O chatbot usa
``agente_informacional`` e apresenta o campo ``answer`` retornado pela API Q&A.
Credenciais, autenticação e transporte continuam centralizados no módulo corporativo.
"""
from __future__ import annotations

import importlib
import inspect
import logging
import re
from dataclasses import dataclass

import requests
from typing import Any, Sequence

from backend.config import Settings
from backend.errors import ServiceError

logger = logging.getLogger("judicial")


@dataclass(frozen=True)
class TextGenerationResult:
    """Texto e contadores reais quando o gateway os expõe explicitamente."""
    text: str
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None


class BradescoBridgeError(ServiceError):
    """Erro sanitizado da integração corporativa, sem conteúdo documental."""

    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(message, status_code)
        self.code = code


class BradescoBridgeClient:
    """Facade para geração documental e perguntas e respostas corporativas.

    Responsabilidade:
        Carregar ``gpt_bradesco.py`` sob demanda e isolar as chamadas a
        ``text_generator`` e ``agente_informacional``.

    Entradas:
        ``Settings`` com deployment, timeout e parâmetros de geração.

    Saída:
        Texto retornado pelo serviço corporativo.

    Observação:
        O módulo fornecido pelo banco continua responsável por autenticação,
        endpoints e transporte. A aplicação não duplica OCR, File Manager ou autenticação nesta camada.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._module: Any | None = None

    @property
    def configured(self) -> bool:
        """Indica se a análise documental possui deployment de geração configurado."""
        return bool(self.settings.bradesco_text_model.strip())

    @property
    def qa_configured(self) -> bool:
        """Indica se existe um workflow de perguntas e respostas configurado."""
        return bool(self.settings.bradesco_qa_workflow_code.strip())

    def _load(self) -> Any:
        """Importa o módulo corporativo somente na primeira chamada de prompt."""
        if self._module is not None:
            return self._module
        try:
            module = importlib.import_module("gpt_bradesco")
        except Exception as exc:  # pragma: no cover - depende do host corporativo
            raise BradescoBridgeError(
                "bradesco_modulo_indisponivel",
                "Não foi possível carregar gpt_bradesco.py. Confirme que o arquivo corporativo está na raiz do projeto e que suas dependências aprovadas estão instaladas.",
                500,
            ) from exc

        if not callable(getattr(module, "text_generator", None)):
            raise BradescoBridgeError(
                "bradesco_modulo_incompativel",
                "gpt_bradesco.py precisa expor a função text_generator(payload, parameters).",
                500,
            )

        # Algumas versões do módulo disponibilizam configuração explícita. Ela é
        # utilizada quando existe, inclusive para ambiente e CA sem credenciais; versões
        # que autenticam internamente continuam funcionando sem adaptação.
        configure = getattr(module, "configure_iagen", None)
        if callable(configure):
            credentials = {
                "ambiente": self.settings.bradesco_environment,
                "identificador": self.settings.bradesco_identificador.get_secret_value(),
                "senha": self.settings.bradesco_senha.get_secret_value(),
                "token": self.settings.bradesco_authorization_token.get_secret_value(),
                "ca_bundle": str(self.settings.bradesco_ca_bundle) if self.settings.bradesco_ca_bundle else "",
            }
            # As opções adicionais pertencem ao cliente distribuído neste projeto.
            # Quando o módulo não aceita metadados adicionais, enviamos somente os argumentos essenciais.
            if getattr(module, "CONNECTION_CONFIG_VERSION", 0) == 1:
                credentials.update({
                    "timeout": self.settings.bradesco_timeout_seconds,
                    "text_url": self.settings.bradesco_text_url,
                    "identity_url": self.settings.bradesco_identity_url,
                    "qa_url": self.settings.bradesco_qa_url,
                })
            self._invoke_callable("configuração corporativa", configure, [(credentials,)])

        self._module = module
        return module

    @staticmethod
    def _safe_request_id(value: Any) -> str | None:
        """Aceita somente identificadores técnicos curtos em mensagens de erro."""
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", value):
            return value
        return None

    @staticmethod
    def _safe_status_code(exc: Exception) -> int | None:
        """Recupera apenas o código HTTP sem propagar corpo de resposta ou documento.

        Algumas implementações de ``gpt_bradesco.py`` levantam ``Exception`` comum
        com texto no formato ``Erro na execução: 400 - ...`` em vez de anexar
        ``status_code`` ao objeto. A aplicação extrai somente os três dígitos para
        produzir diagnóstico acionável, descartando todo o restante da mensagem.
        """
        direct = getattr(exc, "status_code", None)
        if isinstance(direct, int) and 100 <= direct <= 599:
            return direct
        match = re.search(
            r"(?:erro\s+na\s+execu[cç][aã]o|http|status(?:\s+code)?)\s*[:=]?\s*(\d{3})\b",
            str(exc),
            re.IGNORECASE,
        )
        if match:
            value = int(match.group(1))
            return value if 100 <= value <= 599 else None
        return None

    def _classify_error(self, exc: Exception, operation: str) -> BradescoBridgeError:
        """Traduz falhas externas sem ecoar prompt, documento ou credencial."""
        # O cliente HTTP encapsula erros: percorremos as causas sem divulgar seu texto.
        current: BaseException | None = exc
        causes: list[BaseException] = []
        while current is not None and all(current is not item for item in causes):
            causes.append(current)
            current = current.__cause__ or current.__context__
        for error_type, code, message in (
            (requests.exceptions.SSLError, "bradesco_certificado_invalido",
             "Falha de certificado TLS. Sem BRADESCO_CA_BUNDLE, a aplicação usa o repositório de certificados confiáveis do sistema operacional. Confirme que a CA corporativa está instalada no Windows ou configure BRADESCO_CA_BUNDLE com um bundle PEM autorizado."),
            (requests.exceptions.Timeout, "bradesco_tempo_esgotado",
             "O serviço corporativo excedeu o timeout. Verifique a rede e BRADESCO_TIMEOUT_SECONDS."),
            (requests.exceptions.ConnectionError, "bradesco_falha_rede",
             "Falha de rede corporativa. Verifique VPN, DNS, proxy, ambiente e URLs de identidade e geração de texto."),
        ):
            if any(isinstance(item, error_type) for item in causes):
                return BradescoBridgeError(code, message)
        status_code = self._safe_status_code(exc)
        request_id = self._safe_request_id(getattr(exc, "request_id", None))
        suffix = f" Referência técnica: {request_id}." if request_id else ""

        # O módulo corporativo novo fornece um código técnico sanitizado. Versões
        # O atributo de métricas é opcional; quando ausente, usamos os dados disponíveis na resposta.
        external_code = next(
            (getattr(item, "code", None) for item in causes if getattr(item, "code", None)),
            None,
        )
        if external_code in {"tls_error", "tls_configuration_error"}:
            return BradescoBridgeError(
                "bradesco_certificado_invalido",
                "A cadeia de confiança TLS não pôde ser validada. Sem BRADESCO_CA_BUNDLE, a aplicação usa o repositório confiável do sistema operacional; com a variável preenchida, valide se o arquivo é um bundle PEM de CA válido e completo.",
            )
        if external_code == "auth_missing" or str(exc).startswith("Faltam credenciais:"):
            return BradescoBridgeError(
                "bradesco_credencial_ausente",
                "A geração de texto não possui credencial disponível. Configure BRADESCO_AUTHORIZATION_TOKEN "
                "ou BRADESCO_IDENTIFICADOR e BRADESCO_SENHA no ambiente/.env do backend e reinicie a API.",
                500,
            )
        if external_code == "auth_refresh_unavailable":
            return BradescoBridgeError(
                "bradesco_token_nao_renovavel",
                "O token configurado não pode ser renovado sem identificador e senha. Forneça um token válido "
                "ou configure as credenciais de serviço no backend.",
                500,
            )
        if external_code == "auth_response_invalid":
            return BradescoBridgeError(
                "bradesco_resposta_autenticacao_invalida",
                "O serviço de identidade respondeu sem o token esperado. Valide a URL de identidade e o contrato "
                "de autenticação do ambiente configurado.",
            )
        if external_code in {"invalid_json_response", "invalid_text_response"}:
            return BradescoBridgeError(
                "bradesco_resposta_incompativel",
                "O serviço de geração de texto respondeu em formato incompatível com o contrato esperado. "
                "Valide a versão da API corporativa e o envelope response.output_text.",
            )
        if status_code == 400:
            return BradescoBridgeError(
                "bradesco_requisicao_rejeitada",
                "O serviço corporativo rejeitou os parâmetros da geração de texto (HTTP 400). "
                "O AI Ready usa o contrato mínimo compatível com gpt_bradesco.py; valide o deployment e o contrato de parâmetros aceito pelo gateway." + suffix,
            )
        if status_code == 401:
            return BradescoBridgeError(
                "bradesco_credencial_invalida",
                "A autenticação corporativa foi recusada. Revise as credenciais administradas pelo gpt_bradesco.py." + suffix,
            )
        if status_code == 403:
            return BradescoBridgeError(
                "bradesco_acesso_negado",
                "O serviço corporativo recusou a geração de texto. Valide as permissões do deployment configurado." + suffix,
            )
        if status_code == 404:
            return BradescoBridgeError(
                "bradesco_recurso_indisponivel",
                "Recurso corporativo não encontrado. Verifique a URL do serviço, o ambiente e o deployment." + suffix,
            )
        if status_code == 429:
            return BradescoBridgeError(
                "bradesco_limite_requisicoes",
                "O serviço corporativo limitou temporariamente as requisições. Aguarde e repita a extração." + suffix,
            )
        if isinstance(exc, (ValueError, TypeError)):
            return BradescoBridgeError(
                "bradesco_configuracao_invalida",
                f"Configuração inválida na etapa {operation}. Revise os parâmetros de geração de texto.",
                500,
            )
        if "timeout" in type(exc).__name__.lower() or "tempo máximo" in str(exc).lower():
            return BradescoBridgeError(
                "bradesco_tempo_esgotado",
                f"O serviço corporativo excedeu o tempo máximo na etapa {operation}." + suffix,
            )
        return BradescoBridgeError(
            "bradesco_indisponivel",
            f"A etapa corporativa {operation} não foi concluída. Os PDFs locais foram preservados." + suffix,
        )

    @staticmethod
    def _binds(function: Any, args: Sequence[Any]) -> bool:
        """Confere a assinatura antes da chamada para evitar tentativa por exceção."""
        try:
            inspect.signature(function).bind(*args)
            return True
        except (TypeError, ValueError):
            return False

    def _invoke_callable(self, operation: str, function: Any, variants: Sequence[Sequence[Any]]) -> Any:
        """Executa a primeira assinatura conhecida compatível com a função."""
        selected: Sequence[Any] | None = None
        for args in variants:
            if self._binds(function, args):
                selected = args
                break
        if selected is None:
            raise BradescoBridgeError(
                "bradesco_assinatura_incompativel",
                f"A função corporativa usada na etapa {operation} possui assinatura não reconhecida pelo AI Ready.",
                500,
            )
        try:
            return function(*selected)
        except BradescoBridgeError:
            raise
        except Exception as exc:
            logger.warning(
                "bradesco_bridge_failure",
                extra={"operation": operation, "error_type": type(exc).__name__},
            )
            raise self._classify_error(exc, operation) from None

    def generate_text_with_metadata(self, payload: str, *, max_tokens: int) -> TextGenerationResult:
        """Executa geração e preserva contadores reais apenas quando expostos pelo gateway."""
        module = self._load()
        function = getattr(module, "text_generator")
        parameters = {
            "deployment_name": self.settings.bradesco_text_model,
            "temperature": self.settings.bradesco_text_temperature,
            "max_tokens": min(max_tokens, self.settings.bradesco_text_max_tokens),
            "async_mode": False,
            "stream": False,
            "message_format": {"type": "text"},
        }
        response = self._invoke_callable("geração de texto", function, [(payload, parameters)])
        if not isinstance(response, str) or not response.strip():
            raise BradescoBridgeError(
                "bradesco_saida_vazia",
                "O gerador corporativo não retornou texto para a etapa de extração.",
            )
        usage: dict[str, Any] = {}
        usage_reader = getattr(module, "get_last_text_usage", None)
        if callable(usage_reader):
            try:
                candidate = usage_reader()
                if isinstance(candidate, dict):
                    usage = candidate
            except Exception:
                # Telemetria opcional nunca invalida uma resposta funcional.
                usage = {}
        return TextGenerationResult(
            text=response.strip(),
            input_tokens=usage.get("input_tokens") if isinstance(usage.get("input_tokens"), int) else None,
            cached_input_tokens=usage.get("cached_input_tokens") if isinstance(usage.get("cached_input_tokens"), int) else None,
            output_tokens=usage.get("output_tokens") if isinstance(usage.get("output_tokens"), int) else None,
        )

    def generate_text(self, payload: str, *, max_tokens: int) -> str:
        """Retorna somente o texto para consumidores que não precisam das métricas."""
        return self.generate_text_with_metadata(payload, max_tokens=max_tokens).text

    def answer_question(self, question: str) -> str:
        """Envia a pergunta ao ``agente_informacional`` e retorna o campo ``answer``.

        O texto digitado pelo usuário é enviado sem enriquecimento ou reescrita no
        campo ``question`` do payload corporativo.
        """
        module = self._load()
        function = getattr(module, "agente_informacional", None)
        if not callable(function):
            raise BradescoBridgeError(
                "bradesco_qa_indisponivel",
                "gpt_bradesco.py precisa expor a função agente_informacional(payload).",
                500,
            )
        payload = {
            "workflow_code": self.settings.bradesco_qa_workflow_code,
            "question": question,
            "async_mode": False,
        }
        response = self._invoke_callable("perguntas e respostas", function, [(payload,)])
        if not isinstance(response, dict):
            raise BradescoBridgeError(
                "bradesco_qa_resposta_incompativel",
                "A API de perguntas e respostas retornou um formato incompatível.",
            )
        answer = response.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise BradescoBridgeError(
                "bradesco_qa_resposta_vazia",
                "A API de perguntas e respostas não retornou o campo answer preenchido.",
            )
        return answer.strip()
