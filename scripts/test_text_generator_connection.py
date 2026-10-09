"""Diagnóstico seguro da conexão com o gerador corporativo.

Executa somente uma mensagem sintética; não lê PDFs, prompts do processo nem dados pessoais.
Nunca imprime token, identificador ou senha.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import load_settings
from backend.services.bradesco_bridge import BradescoBridgeClient, BradescoBridgeError


def main() -> int:
    """Valida configuração local e realiza uma chamada mínima ao text_generator."""
    try:
        settings = load_settings()
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "etapa": "configuracao_local",
            "tipo_erro": type(exc).__name__,
            "mensagem": str(exc),
        }, ensure_ascii=False, indent=2))
        return 2

    token_present = bool(settings.bradesco_authorization_token.get_secret_value().strip())
    credentials_present = bool(
        settings.bradesco_identificador.get_secret_value().strip()
        and settings.bradesco_senha.get_secret_value().strip()
    )
    diagnostic = {
        "ambiente": settings.bradesco_environment,
        "modelo": settings.bradesco_text_model,
        "autenticacao_configurada": token_present or credentials_present,
        "modo_autenticacao": "token" if token_present else "identificador_senha" if credentials_present else "ausente",
        "ca_corporativa_configurada": bool(settings.bradesco_ca_bundle),
        "tls_origem_confianca": "bundle_corporativo" if settings.bradesco_ca_bundle else "sistema_operacional",
        "tls_repositorio": "Windows Certificate Store" if os.name == "nt" and not settings.bradesco_ca_bundle else "bundle PEM configurado" if settings.bradesco_ca_bundle else "repositório padrão do sistema/OpenSSL",
        "url_texto_sobrescrita": bool(settings.bradesco_text_url),
        "url_identidade_sobrescrita": bool(settings.bradesco_identity_url),
        "timeout_segundos": settings.bradesco_timeout_seconds,
    }

    if not settings.bradesco_text_model.strip():
        diagnostic.update({
            "ok": False,
            "etapa": "configuracao_local",
            "codigo": "bradesco_modelo_ausente",
            "mensagem": "Defina BRADESCO_TEXT_MODEL antes de testar a conexão.",
        })
        print(json.dumps(diagnostic, ensure_ascii=False, indent=2))
        return 2

    client = BradescoBridgeClient(settings)
    try:
        response = client.generate_text(
            "Responda apenas com a palavra OK. Esta é uma mensagem sintética de diagnóstico sem dados pessoais.",
            max_tokens=1024,
        )
    except BradescoBridgeError as exc:
        diagnostic.update({
            "ok": False,
            "etapa": "geracao_texto",
            "codigo": exc.code,
            "mensagem": exc.message,
        })
        print(json.dumps(diagnostic, ensure_ascii=False, indent=2))
        return 1

    diagnostic.update({
        "ok": True,
        "etapa": "geracao_texto",
        "resposta_recebida": bool(response.strip()),
        "mensagem": "Conexão com text_generator concluída com resposta textual.",
    })
    print(json.dumps(diagnostic, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
