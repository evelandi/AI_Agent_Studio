"""
FastAPI router para el webhook de WhatsApp (Meta Cloud API).
Implementación completa: Fase 2
"""
from fastapi import APIRouter, Request, Response, HTTPException
from app.config import settings
from app.core.security import verify_whatsapp_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    """Verificación del webhook por Meta (GET)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verificación fallida")


@router.post("/whatsapp")
async def receive_webhook(request: Request):
    """
    Recibe mensajes de WhatsApp.
    Responde HTTP 200 inmediatamente y procesa de forma asíncrona.
    Implementación completa: Fase 2
    """
    # Validar firma HMAC
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if settings.meta_app_secret and not verify_whatsapp_signature(body, signature):
        raise HTTPException(status_code=403, detail="Firma inválida")

    # TODO: Fase 2 — parsear payload y despachar al grafo LangGraph
    return {"status": "received"}
