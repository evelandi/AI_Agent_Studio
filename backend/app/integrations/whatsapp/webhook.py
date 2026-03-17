"""
FastAPI router para el webhook de WhatsApp (Meta Cloud API).
Responde HTTP 200 inmediatamente; procesa mensajes de forma asíncrona.
"""
import asyncio
import structlog
from fastapi import APIRouter, Request, Response, HTTPException

from app.config import settings
from app.core.security import verify_whatsapp_signature
from app.integrations.whatsapp.schemas import (
    WhatsAppWebhookPayload,
    extract_messages,
    IncomingMessage,
)
from app.integrations.whatsapp.client import whatsapp_client

log = structlog.get_logger()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    """
    Verificación del webhook por Meta (GET).
    Meta envía este request al registrar el webhook en el panel.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        log.info("whatsapp.webhook_verified")
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verificación fallida")


@router.post("/whatsapp")
async def receive_webhook(request: Request):
    """
    Recibe eventos de WhatsApp de Meta Cloud API.
    Valida la firma HMAC, responde 200 inmediatamente
    y despacha el procesamiento de forma asíncrona.
    """
    body = await request.body()

    # Validar firma HMAC-SHA256 (solo si META_APP_SECRET está configurado)
    signature = request.headers.get("X-Hub-Signature-256", "")
    if settings.meta_app_secret and not verify_whatsapp_signature(body, signature):
        log.warning("whatsapp.invalid_signature")
        raise HTTPException(status_code=403, detail="Firma inválida")

    # Parsear payload
    try:
        payload = WhatsAppWebhookPayload.model_validate_json(body)
    except Exception as exc:
        log.warning("whatsapp.parse_error", error=str(exc))
        return {"status": "ignored"}

    # Ignorar eventos que no son de WhatsApp
    if payload.object != "whatsapp_business_account":
        return {"status": "ignored"}

    # Extraer mensajes de texto entrantes
    messages = extract_messages(payload)
    for msg in messages:
        # Marcar como leído inmediatamente
        asyncio.create_task(_mark_read(msg.message_id))
        # Procesar en background (no bloquear la respuesta a Meta)
        asyncio.create_task(_dispatch_to_graph(msg))

    return {"status": "received"}


async def _mark_read(message_id: str) -> None:
    try:
        await whatsapp_client.mark_as_read(message_id)
    except Exception as exc:
        log.warning("whatsapp.mark_read_failed", message_id=message_id, error=str(exc))


async def _dispatch_to_graph(msg: IncomingMessage) -> None:
    """
    Despacha el mensaje al grafo LangGraph para su procesamiento.
    Importación diferida para evitar dependencia circular.
    """
    try:
        from app.graph.hub_graph import process_incoming_message
        await process_incoming_message(msg)
    except Exception as exc:
        log.error(
            "whatsapp.dispatch_error",
            phone=msg.phone,
            error=str(exc),
            exc_info=True,
        )
