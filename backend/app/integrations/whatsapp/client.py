"""
Meta Cloud API Client para WhatsApp.
Soporta: send_text, send_template, send_document, mark_as_read
"""
import structlog
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

log = structlog.get_logger()

WHATSAPP_API_URL = "https://graph.facebook.com/v19.0"


class WhatsAppClient:
    """
    Cliente para la Meta Cloud API de WhatsApp.
    Usa httpx async con reintentos automáticos (tenacity).
    """

    def __init__(self):
        self.messages_url = (
            f"{WHATSAPP_API_URL}/{settings.meta_phone_number_id}/messages"
        )
        self.headers = {
            "Authorization": f"Bearer {settings.meta_access_token}",
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _post(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.messages_url, json=payload, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def send_text(self, to: str, text: str) -> dict:
        """Envía un mensaje de texto libre al número indicado."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        log.info("whatsapp.send_text", to=to, length=len(text))
        return await self._post(payload)

    async def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "es",
        components: list | None = None,
    ) -> dict:
        """
        Envía un mensaje con plantilla aprobada por Meta.
        Las plantillas deben estar pre-aprobadas en el panel de Meta.
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components or [],
            },
        }
        log.info("whatsapp.send_template", to=to, template=template_name)
        return await self._post(payload)

    async def send_document(
        self, to: str, document_url: str, filename: str, caption: str = ""
    ) -> dict:
        """Envía un documento PDF al número indicado."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": {
                "link": document_url,
                "filename": filename,
                "caption": caption,
            },
        }
        log.info("whatsapp.send_document", to=to, filename=filename)
        return await self._post(payload)

    async def mark_as_read(self, message_id: str) -> dict:
        """Marca un mensaje como leído (ticks azules)."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        return await self._post(payload)


whatsapp_client = WhatsAppClient()
