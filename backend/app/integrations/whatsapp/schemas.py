"""
Schemas Pydantic para el payload del webhook de Meta Cloud API.
Referencia: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples
"""
from pydantic import BaseModel
from typing import Optional


class WhatsAppTextMessage(BaseModel):
    body: str


class WhatsAppMessage(BaseModel):
    id: str
    from_: str
    timestamp: str
    type: str
    text: Optional[WhatsAppTextMessage] = None

    model_config = {"populate_by_name": True}

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        # 'from' es palabra reservada en Python; renombrarla
        if isinstance(obj, dict) and "from" in obj:
            obj = {**obj, "from_": obj.pop("from")}
        return super().model_validate(obj, *args, **kwargs)


class WhatsAppContact(BaseModel):
    wa_id: str
    profile: Optional[dict] = None


class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: dict
    contacts: Optional[list[WhatsAppContact]] = None
    messages: Optional[list[WhatsAppMessage]] = None
    statuses: Optional[list[dict]] = None


class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str


class WhatsAppEntry(BaseModel):
    id: str
    changes: list[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    object: str
    entry: list[WhatsAppEntry]


class IncomingMessage(BaseModel):
    """Mensaje normalizado extraído del payload de Meta."""
    message_id: str
    phone: str          # número del remitente (e.g. '573001234567')
    text: str
    timestamp: str
    contact_name: Optional[str] = None


def extract_messages(payload: WhatsAppWebhookPayload) -> list[IncomingMessage]:
    """
    Extrae todos los mensajes de texto del payload webhook de Meta.
    Ignora statusses y otros tipos de eventos.
    """
    result: list[IncomingMessage] = []
    for entry in payload.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue
            value = change.value
            if not value.messages:
                continue
            contacts_map = {
                c.wa_id: (c.profile or {}).get("name") for c in (value.contacts or [])
            }
            for msg in value.messages:
                if msg.type != "text" or not msg.text:
                    continue
                result.append(
                    IncomingMessage(
                        message_id=msg.id,
                        phone=msg.from_,
                        text=msg.text.body,
                        timestamp=msg.timestamp,
                        contact_name=contacts_map.get(msg.from_),
                    )
                )
    return result
