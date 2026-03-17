"""
A2 - Gestor de Agendas
Google Calendar, agendamiento reactivo y proactivo.

Flujo reactivo:
1. Paciente solicita cita (SCHEDULING intent)
2. Detectar procedimiento o preguntar
3. Consultar slots disponibles en Google Calendar
4. Proponer 3 opciones al paciente
5. Paciente elige slot (1, 2, o 3)
6. Crear evento en Calendar + guardar en DB
7. Enviar confirmacion por WhatsApp

Flujo cancelacion/reprogramacion:
- Detectar "cancelar" o "reprogramar" en el mensaje
- Buscar la cita mas reciente del paciente
- Confirmar accion con el paciente
"""
import structlog
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.core.state import GlobalHubState, Message, MessageRole
from app.core.database import AsyncSessionLocal
from app.core.audit import write_audit_log
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.agents.agenda.tools import (
    get_agenda_config,
    detect_procedure_type,
    get_available_slots,
    book_slot,
    cancel_appointment,
    send_appointment_confirmation,
    format_slots_for_patient,
)

log = structlog.get_logger()

# Palabras clave para cancelacion y reprogramacion
CANCEL_KEYWORDS = {"cancelar", "cancel", "anular", "no puedo ir", "no voy a poder"}
RESCHEDULE_KEYWORDS = {"reprogramar", "cambiar", "mover", "otro dia", "otro horario"}
CONFIRM_KEYWORDS = {"confirmar cancelacion", "confirmar cancelación", "si, cancelar", "si cancelar"}

# Paso del flujo almacenado en pending_appointment["step"]
STEP_AWAITING_SLOT_SELECTION = "awaiting_slot_selection"
STEP_AWAITING_PROCEDURE = "awaiting_procedure"
STEP_AWAITING_CANCEL_CONFIRM = "awaiting_cancel_confirm"


def _format_history(messages: list[Message], max_turns: int = 6) -> str:
    recent = messages[-(max_turns * 2):]
    lines = []
    for msg in recent:
        role = "Paciente" if msg.role == MessageRole.USER else "Asistente"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines) if lines else "(inicio)"


def _is_slot_selection(text: str) -> int | None:
    """Retorna el indice 0-based del slot elegido (0, 1 o 2), o None."""
    stripped = text.strip()
    if stripped in ("1", "1.", "opcion 1", "opcion1", "primera"):
        return 0
    if stripped in ("2", "2.", "opcion 2", "opcion2", "segunda"):
        return 1
    if stripped in ("3", "3.", "opcion 3", "opcion3", "tercera"):
        return 2
    return None


async def agenda_agent_node(state: GlobalHubState) -> GlobalHubState:
    """
    Nodo del Agente de Agendas A2.
    """
    async with AsyncSessionLocal() as db:
        config = await get_agenda_config(db)

        user_messages = [m for m in state.messages if m.role == MessageRole.USER]
        last_text = user_messages[-1].content.strip() if user_messages else ""
        last_text_lower = last_text.lower()

        pending = dict(state.pending_appointment or {})
        step = pending.get("step")
        reply_text: str | None = None

        # ── Flujo cancelacion ──────────────────────────────────────────
        if step == STEP_AWAITING_CANCEL_CONFIRM:
            if any(kw in last_text_lower for kw in CONFIRM_KEYWORDS):
                appointment_id = pending.get("appointment_id")
                success = await cancel_appointment(appointment_id, db)
                if success:
                    reply_text = (
                        "Tu cita ha sido cancelada exitosamente. "
                        "Cuando quieras reagendar, solo escribenos."
                    )
                else:
                    reply_text = (
                        "No pudimos cancelar la cita. "
                        "Por favor llama al +57 601 234 5678 para cancelar directamente."
                    )
                pending = {}
                await write_audit_log(
                    db=db,
                    agent_name="agenda",
                    action="appointment_cancelled" if success else "cancel_failed",
                    triggered_by="patient_message",
                    patient_id=state.patient_id,
                    detail={"appointment_id": appointment_id},
                )
            elif any(kw in last_text_lower for kw in RESCHEDULE_KEYWORDS):
                # Reprogramar: ir al flujo de seleccion de slot
                procedure_type = pending.get("procedure_type", "default")
                slots = await get_available_slots(procedure_type, db)
                slots_text = format_slots_for_patient(slots)
                reply_text = f"Perfecto, busquemos una nueva fecha para tu cita:\n\n{slots_text}"
                pending = {
                    "step": STEP_AWAITING_SLOT_SELECTION,
                    "procedure_type": procedure_type,
                    "slots": slots,
                    "cancel_previous_id": pending.get("appointment_id"),
                }
            else:
                reply_text = (
                    "Para confirmar la cancelacion responde: CONFIRMAR CANCELACION\n"
                    "Si prefieres reprogramar, escribe: REPROGRAMAR"
                )

        # ── Flujo seleccion de slot ────────────────────────────────────
        elif step == STEP_AWAITING_SLOT_SELECTION:
            slot_idx = _is_slot_selection(last_text_lower)
            slots = pending.get("slots", [])

            if slot_idx is not None and slot_idx < len(slots):
                chosen_slot = slots[slot_idx]

                # Obtener datos del paciente
                patient_name = "Paciente"
                patient_email = None
                if state.patient_id:
                    result = await db.execute(
                        select(Patient).where(Patient.id == state.patient_id)
                    )
                    patient = result.scalar_one_or_none()
                    if patient:
                        patient_name = patient.full_name or patient_name
                        patient_email = patient.email

                # Cancelar cita anterior si es reprogramacion
                cancel_prev = pending.get("cancel_previous_id")
                if cancel_prev:
                    await cancel_appointment(cancel_prev, db)

                # Crear cita
                procedure_type = pending.get("procedure_type", "default")
                result = await book_slot(
                    patient_id=state.patient_id or 0,
                    patient_name=patient_name,
                    patient_email=patient_email,
                    procedure_type=procedure_type,
                    slot=chosen_slot,
                    db=db,
                )
                await db.commit()

                # Enviar confirmacion WhatsApp
                await send_appointment_confirmation(
                    phone=state.patient_phone or "",
                    patient_name=patient_name,
                    procedure_type=procedure_type,
                    slot=chosen_slot,
                )

                reply_text = None  # ya se envio por whatsapp; evitar duplicado en response_node
                pending = {}

                await write_audit_log(
                    db=db,
                    agent_name="agenda",
                    action="appointment_booked",
                    triggered_by="patient_slot_selection",
                    patient_id=state.patient_id,
                    detail={
                        "appointment_id": result["appointment_id"],
                        "procedure_type": procedure_type,
                        "slot": chosen_slot["label"],
                    },
                )

            elif "otro" in last_text_lower:
                reply_text = (
                    "Entendido. Por favor indicanos que dia o rango de dias prefieres "
                    "(por ejemplo: 'la semana proxima' o 'en 15 dias')."
                )
                pending = {"step": STEP_AWAITING_PROCEDURE, "procedure_type": pending.get("procedure_type", "default")}
            else:
                slots_text = format_slots_for_patient(slots)
                reply_text = (
                    f"Por favor elige una opcion respondiendo con 1, 2 o 3:\n\n{slots_text}"
                )

        # ── Flujo seleccion de procedimiento ──────────────────────────
        elif step == STEP_AWAITING_PROCEDURE:
            durations = config.get("procedure_durations", {})
            procedure_type = detect_procedure_type(last_text, durations)
            slots = await get_available_slots(procedure_type, db)
            slots_text = format_slots_for_patient(slots)
            reply_text = (
                f"Para tu cita de {procedure_type.replace('_', ' ').title()}, "
                f"tenemos estas opciones disponibles:\n\n{slots_text}"
            )
            pending = {
                "step": STEP_AWAITING_SLOT_SELECTION,
                "procedure_type": procedure_type,
                "slots": slots,
            }

        # ── Detectar cancelacion sin flujo previo ──────────────────────
        elif any(kw in last_text_lower for kw in CANCEL_KEYWORDS):
            if state.patient_id:
                result = await db.execute(
                    select(Appointment)
                    .where(
                        Appointment.patient_id == state.patient_id,
                        Appointment.status == "scheduled",
                    )
                    .order_by(Appointment.scheduled_at.desc())
                    .limit(1)
                )
                appt = result.scalar_one_or_none()
                if appt:
                    date_str = appt.scheduled_at.strftime("%d/%m/%Y a las %I:%M %p") if appt.scheduled_at else "fecha desconocida"
                    reply_text = (
                        f"Encontramos tu cita de {appt.procedure_type} programada para el {date_str}.\n\n"
                        "Para confirmar la cancelacion responde: CONFIRMAR CANCELACION\n"
                        "Si prefieres reprogramar, escribe: REPROGRAMAR"
                    )
                    pending = {
                        "step": STEP_AWAITING_CANCEL_CONFIRM,
                        "appointment_id": appt.id,
                        "procedure_type": appt.procedure_type,
                    }
                else:
                    reply_text = "No encontramos citas programadas para tu numero. Si crees que es un error, llama al +57 601 234 5678."
            else:
                reply_text = "No encontramos citas asociadas a tu numero de telefono."

        # ── Primer contacto: detectar procedimiento y proponer slots ──
        else:
            durations = config.get("procedure_durations", {})
            procedure_type = detect_procedure_type(last_text, durations)

            if procedure_type == "default":
                # No se detecto procedimiento; preguntar
                reply_text = (
                    "Con gusto te ayudo a agendar tu cita.\n"
                    "Que tipo de procedimiento necesitas? Por ejemplo:\n"
                    "- Limpieza dental\n- Control\n- Ortodoncia\n- Blanqueamiento\n"
                    "- Extraccion\n- Implante\n- Otro"
                )
                pending = {"step": STEP_AWAITING_PROCEDURE}
            else:
                slots = await get_available_slots(procedure_type, db)
                slots_text = format_slots_for_patient(slots)
                reply_text = (
                    f"Perfecto! Para tu cita de {procedure_type.replace('_', ' ').title()}, "
                    f"tenemos estas opciones:\n\n{slots_text}"
                )
                pending = {
                    "step": STEP_AWAITING_SLOT_SELECTION,
                    "procedure_type": procedure_type,
                    "slots": slots,
                }

            await write_audit_log(
                db=db,
                agent_name="agenda",
                action="slot_options_offered",
                triggered_by="patient_message",
                patient_id=state.patient_id,
                detail={"procedure_type": procedure_type, "slots_count": len(pending.get("slots", []))},
            )

        await db.commit()

    # Construir nuevo estado
    new_messages = list(state.messages)
    if reply_text:
        new_messages.append(Message(role=MessageRole.ASSISTANT, content=reply_text))

    return state.model_copy(
        update={
            "messages": new_messages,
            "pending_appointment": pending if pending else None,
            "awaiting_confirmation": bool(pending.get("step") == STEP_AWAITING_SLOT_SELECTION),
            "next_agent": "response",
        }
    )
