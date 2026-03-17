"""
Herramientas del Agente de Comunicaciones A1.
Implementadas como funciones async — el agente las llama directamente.
"""
import structlog
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import hash_consent_document
from app.models.consent import Consent
from app.models.agent_config import AgentConfig
from app.rag.retriever import retrieve, format_context
from app.integrations.whatsapp.client import whatsapp_client
from app.integrations.whatsapp.templates import CONSENT_REQUEST

log = structlog.get_logger()

# ── Texto canónico de consentimiento (debe coincidir con lo enviado por WhatsApp) ──
CONSENT_TEXT = (
    "Autorizo al consultorio odontológico el tratamiento de mis datos personales "
    "conforme a la Ley 1581 de 2012 y el Decreto 1377 de 2013 de Colombia."
)


async def query_knowledge_base(query: str, db: AsyncSession, top_k: int = 5) -> str:
    """
    Busca información en la base de conocimiento del consultorio.
    Retorna el contexto formateado listo para incluir en el prompt del LLM.
    """
    chunks = await retrieve(query=query, db=db, top_k=top_k)
    return format_context(chunks)


async def check_consent(patient_id: int, db: AsyncSession) -> bool:
    """
    Verifica si el paciente tiene consentimiento de tratamiento de datos vigente.
    """
    result = await db.execute(
        select(Consent).where(
            Consent.patient_id == patient_id,
            Consent.consent_type == "data_treatment",
        )
    )
    return result.scalar_one_or_none() is not None


async def register_consent(patient_id: int, phone: str, db: AsyncSession) -> Consent:
    """
    Registra el consentimiento del paciente con hash SHA-256.
    Llamar cuando el paciente responde 'ACEPTO'.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()
    document_hash = hash_consent_document(phone, timestamp, CONSENT_TEXT)

    consent = Consent(
        patient_id=patient_id,
        consent_type="data_treatment",
        document_hash=document_hash,
        signed_at=now,
        ip_or_channel=f"whatsapp:{phone}",
    )
    db.add(consent)
    await db.flush()
    log.info("consent.registered", patient_id=patient_id, phone=phone)
    return consent


async def send_consent_request(phone: str, patient_name: str | None = None) -> None:
    """Envía el mensaje de solicitud de consentimiento por WhatsApp."""
    name = patient_name or "paciente"
    text = CONSENT_REQUEST.format(patient_name=name)
    await whatsapp_client.send_text(to=phone, text=text)
    log.info("consent.request_sent", phone=phone)


async def get_agent_config(db: AsyncSession) -> dict:
    """Carga la configuración del agente de comunicaciones desde agent_configs."""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.agent_name == "communications")
    )
    config = result.scalar_one_or_none()
    if config:
        return config.parameters
    # Valores por defecto si no hay config en DB
    return {
        "tone": "cercano",
        "business_hours": {"start": "08:00", "end": "18:00"},
        "emergency_keywords": ["dolor", "urgencia", "accidente", "sangrado"],
        "auto_response_outside_hours": True,
        "human_escalation_threshold": 3,
    }


def is_within_business_hours(config: dict) -> bool:
    """
    Verifica si la hora actual está dentro del horario de atención.
    Usa hora de Colombia (UTC-5).
    """
    colombia_tz = timezone(timedelta(hours=-5))
    now = datetime.now(colombia_tz).time()
    start_str = config.get("business_hours", {}).get("start", "08:00")
    end_str = config.get("business_hours", {}).get("end", "18:00")
    start = datetime.strptime(start_str, "%H:%M").time()
    end = datetime.strptime(end_str, "%H:%M").time()
    return start <= now <= end


def contains_emergency_keywords(text: str, config: dict) -> bool:
    """Detecta palabras clave de emergencia en el mensaje."""
    keywords = config.get("emergency_keywords", [])
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)
