"""Despacho opcional de notificações simples, após publicação humana do parecer."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from backend.services.bjn_demand_store import DemandStore


def dispatch_notifications(store: DemandStore, settings: object, demand_id: str) -> dict:
    """Não inclui conteúdo jurídico ou dados pessoais no corpo do e-mail.

    Sem SMTP validado, mantém o registro PENDENTE para reprocessamento operacional.
    """
    notifications = store.pending_notifications(demand_id)
    if not (settings.bjn_notification_smtp_host and settings.bjn_notification_sender):
        return {"status": "PENDENTE_CONFIGURACAO", "count": len(notifications)}
    count = 0
    for entry in notifications:
        message = EmailMessage()
        message["Subject"] = "BJN | Retorno disponível para consulta"
        message["From"] = settings.bjn_notification_sender
        message["To"] = entry["destination"]
        message.set_content(
            "Seu retorno jurídico está disponível no portal BJN. "
            "Acesse o ambiente autenticado e consulte o protocolo na lista de demandas. "
            "Por segurança, este e-mail não contém documentos nem informações do caso."
        )
        try:
            with smtplib.SMTP(settings.bjn_notification_smtp_host, settings.bjn_notification_smtp_port, timeout=8) as client:
                client.starttls(context=ssl.create_default_context())
                if settings.bjn_notification_username:
                    client.login(settings.bjn_notification_username, settings.bjn_notification_password.get_secret_value())
                client.send_message(message)
            store.notification_result(entry["id"], True)
            count += 1
        except (smtplib.SMTPException, OSError, ValueError):
            store.notification_result(entry["id"], False, "SMTP_UNAVAILABLE")
    return {"status": "ENVIADO" if count == len(notifications) else "PENDENTE_REENVIO", "count": count}
