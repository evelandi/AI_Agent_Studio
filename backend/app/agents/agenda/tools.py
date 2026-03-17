"""
Herramientas del Agente de Agendas A2.

Funciones async llamadas directamente por el agente.
"""
import structlog
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.appointment import Appointment
from app.models.agent_config import AgentConfig
from app.integrations.google_calendar.client import google_calendar_client
from app.integrations.whatsapp.client import whatsapp_client
from app.agents.agenda.optimizer import get_optimal_slots, format_slots_for_patient

log = structlog.get_logger()

COLOMBIA_TZ = timezone(timedelta(hours=-5))

# Duraciones por tipo de procedimiento (minutos)
DEFAULT_PROCEDURE_DURATIONS: dict[str, int] = {
    "control": 30,
    "limpieza": 45,
    "profilaxis": 45,
    "sellantes": 30,
    "fluorizacion": 30,
    "extraccion_simple": 60,
    "extraccion_cordal": 90,
    "resina": 60,
    "endodoncia": 90,
    "ortodoncia_valoracion": 60,
    "ortodoncia_control": 45,
    "implante_valoracion": 60,
    "blanqueamiento": 60,
    "carillas": 90,
    "corona": 90,
    "cirugia_periodontal": 120,
    "default": 60,
}


async def get_agenda_config(db: AsyncSession) -> dict:
    """Carga la configuración del agente de agenda desde agent_configs."""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.agent_name == "agenda")
    )
    config = result.scalar_one_or_none()
    if config:
        return config.parameters
    return {
        "buffer_minutes": 15,
        "days_ahead": 7,
        "emergency_slots_per_day": 1,
        "procedure_durations": DEFAULT_PROCEDURE_DURATIONS,
    }


def detect_procedure_type(text: str, procedure_durations: dict) -> str:
    """
    Intenta detectar el tipo de procedimiento a partir del mensaje del paciente.
    Retorna el tipo o 'default'.
    """
    text_lower = text.lower()
    mapping = {
        "limpieza": "limpieza",
        "profilaxis": "profilaxis",
        "blanqueamiento": "blanqueamiento",
        "ortodoncia": "ortodoncia_valoracion",
        "implante": "implante_valoracion",
        "extraccion": "extraccion_simple",
        "muela del juicio": "extraccion_cordal",
        "cordal": "extraccion_cordal",
        "endodoncia": "endodoncia",
        "conducto": "endodoncia",
        "resina": "resina",
        "sellante": "sellantes",
        "control": "control",
        "revision": "control",
        "revision": "control",
        "corona": "corona",
        "carilla": "carillas",
        "cirugia": "cirugia_periodontal",
    }
    for keyword, procedure in mapping.items():
        if keyword in text_lower:
            return procedure
    return "default"


async def get_available_slots(
    procedure_type: str,
    db: AsyncSession,
    days_ahead: int | None = None,
) -> list[dict]:
    """
    Consulta disponibilidad en Google Calendar y calcula los slots optimos.

    Returns:
        Lista de hasta 3 slots disponibles con su label para el paciente.
    """
    config = await get_agenda_config(db)
    buffer = config.get("buffer_minutes", 15)
    ahead = days_ahead or config.get("days_ahead", 7)
    emergency = config.get("emergency_slots_per_day", 1)
    durations = config.get("procedure_durations", DEFAULT_PROCEDURE_DURATIONS)

    duration_min = durations.get(procedure_type, durations.get("default", 60))

    now = datetime.now(COLOMBIA_TZ)
    date_to = now + timedelta(days=ahead)

    try:
        busy_periods = await google_calendar_client.get_busy_periods(now, date_to)
    except Exception as exc:
        log.warning("agenda.calendar_unavailable", error=str(exc))
        busy_periods = []

    slots = get_optimal_slots(
        procedure_duration_minutes=duration_min,
        busy_periods=busy_periods,
        days_ahead=ahead,
        buffer_minutes=buffer,
        emergency_slots_per_day=emergency,
        max_slots=3,
    )
    return slots


async def create_appointment_in_db(
    patient_id: int,
    procedure_type: str,
    start: datetime,
    end: datetime,
    google_event_id: str,
    db: AsyncSession,
) -> Appointment:
    """Persiste la cita en la tabla appointments."""
    duration = int((end - start).total_seconds() / 60)
    appt = Appointment(
        patient_id=patient_id,
        google_event_id=google_event_id,
        procedure_type=procedure_type,
        duration_minutes=duration,
        scheduled_at=start,
        status="scheduled",
        created_by_agent=True,
    )
    db.add(appt)
    await db.flush()
    log.info(
        "appointment.created",
        patient_id=patient_id,
        procedure=procedure_type,
        start=start.isoformat(),
    )
    return appt


async def book_slot(
    patient_id: int,
    patient_name: str,
    patient_email: str | None,
    procedure_type: str,
    slot: dict,
    db: AsyncSession,
) -> dict:
    """
    Crea el evento en Google Calendar y persiste la cita en DB.

    Args:
        slot: dict con "start" y "end" en ISO format.
    Returns:
        Dict con appointment_id y google_event_id.
    """
    start = datetime.fromisoformat(slot["start"])
    end = datetime.fromisoformat(slot["end"])

    summary = f"Cita {procedure_type.replace('_', ' ').title()} - {patient_name}"
    description = (
        f"Paciente: {patient_name}\n"
        f"Procedimiento: {procedure_type}\n"
        "Agendado por asistente IA."
    )

    try:
        event = await google_calendar_client.create_event(
            summary=summary,
            start=start,
            end=end,
            description=description,
            attendee_email=patient_email,
        )
        google_event_id = event.get("id", "")
    except Exception as exc:
        log.error("agenda.create_event_failed", error=str(exc))
        google_event_id = ""

    appt = await create_appointment_in_db(
        patient_id=patient_id,
        procedure_type=procedure_type,
        start=start,
        end=end,
        google_event_id=google_event_id,
        db=db,
    )
    return {"appointment_id": appt.id, "google_event_id": google_event_id}


async def cancel_appointment(appointment_id: int, db: AsyncSession) -> bool:
    """Cancela una cita: borra de Calendar y actualiza status en DB."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appt = result.scalar_one_or_none()
    if not appt:
        return False

    if appt.google_event_id:
        try:
            await google_calendar_client.delete_event(appt.google_event_id)
        except Exception as exc:
            log.warning("agenda.cancel_calendar_error", error=str(exc))

    appt.status = "cancelled"
    await db.flush()
    log.info("appointment.cancelled", appointment_id=appointment_id)
    return True


async def send_appointment_confirmation(
    phone: str,
    patient_name: str,
    procedure_type: str,
    slot: dict,
) -> None:
    """Envia confirmacion de cita por WhatsApp como texto libre."""
    start = datetime.fromisoformat(slot["start"])
    date_str = start.strftime("%A %d de %B de %Y")
    time_str = start.strftime("%I:%M %p")
    procedure_label = procedure_type.replace("_", " ").title()

    text = (
        f"Cita confirmada, {patient_name}!\n\n"
        f"Procedimiento: {procedure_label}\n"
        f"Fecha: {date_str}\n"
        f"Hora: {time_str}\n\n"
        "Recuerda llegar 10 minutos antes con tu documento de identidad.\n"
        "Si necesitas cancelar o reprogramar, escribenos con al menos 24 horas de anticipacion."
    )
    await whatsapp_client.send_text(to=phone, text=text)
    log.info("agenda.confirmation_sent", phone=phone)
