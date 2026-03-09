"""
Meta Cloud API Client para WhatsApp.
Implementación completa: Fase 2
"""
import httpx
from app.config import settings

WHATSAPP_API_URL = "https://graph.facebook.com/v19.0"


class WhatsAppClient:
    """
    Cliente para la Meta Cloud API de WhatsApp.
    Métodos principales:
    - send_text: envía mensaje de texto libre
    - send_template: envía mensaje con plantilla aprobada por Meta
    - send_document: envía documento PDF
    """

    def __init__(self):
        self.base_url = f"{WHATSAPP_API_URL}/{settings.meta_phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {settings.meta_access_token}",
            "Content-Type": "application/json",
        }

    async def send_text(self, to: str, text: str) -> dict:
        """Envía un mensaje de texto al número indicado."""
        # TODO: Fase 2
        raise NotImplementedError("WhatsAppClient.send_text: implementar en Fase 2")

    async def send_template(self, to: str, template_name: str, components: list) -> dict:
        """Envía un mensaje con plantilla aprobada por Meta."""
        # TODO: Fase 2
        raise NotImplementedError("WhatsAppClient.send_template: implementar en Fase 2")

    async def send_document(self, to: str, document_url: str, filename: str) -> dict:
        """Envía un documento PDF al número indicado."""
        # TODO: Fase 2
        raise NotImplementedError("WhatsAppClient.send_document: implementar en Fase 2")


# Singleton
whatsapp_client = WhatsAppClient()
