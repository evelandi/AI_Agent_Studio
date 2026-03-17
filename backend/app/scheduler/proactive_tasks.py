"""
Logica de seguimiento proactivo de pacientes.
La tarea corre diariamente via APScheduler.
"""
import structlog
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.integrations.whatsapp.client import whatsapp_client
from app.models.appointment import Appointment
from app.models.patient import Patient

log = structlog.get_logger()

COLOMBIA_TZ = timezone(timedelta(hours=-5))


async def send_appointment_reminders() -> None:
    """
    Busca citas programadas para las proximas 24-48 horas
    y envia un recordatorio por WhatsApp a cada paciente.
    """
    now = datetime.now(COLOMBIA_TZ)
    window_start = now + timedelta(hours=24)
    window_end = now + timedelta(hours=48)

    log.info(
        "scheduler.reminders_start",
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
    )

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Appointment, Patient)
            .join(Patient, Patient.id == Appointment.patient_id)
            .where(
                Appointment.status == "scheduled",
                Appointment.scheduled_at >= window_start,
                Appointment.scheduled_at <= window_end,
            )
        )
        rows = result.fetchall()

    sent = 0
    for appt, patient in rows:
        if not patient.phone:
            continue

        date_str = appt.scheduled_at.strftime("%d/%m/%Y")
        time_str = appt.scheduled_at.strftime("%I:%M %p")
        procedure_label = (appt.procedure_type or "cita").replace("_", " ").title()
        patient_name = patient.full_name or "Paciente"

        text = (
            f"Hola {patient_name}! Te recordamos tu cita de {procedure_label} "
            f"programada para manana {date_str} a las {time_str}.\n\n"
            "Si necesitas cancelar o reprogramar, respondenos este mensaje.\n"
            "Recuerda llegar 10 minutos antes con tu documento de identidad."
        )

        try:
            await whatsapp_client.send_text(to=patient.phone, text=text)
            sent += 1
            log.info(
                "scheduler.reminder_sent",
                patient_id=patient.id,
                appointment_id=appt.id,
            )
        except Exception as exc:
            log.error(
                "scheduler.reminder_error",
                patient_id=patient.id,
                appointment_id=appt.id,
                error=str(exc),
            )

    log.info("scheduler.reminders_done", sent=sent, total=len(rows))
