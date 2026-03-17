"""
Herramientas del Agente de Perfilamiento A3.

Funciones async para CRUD de pacientes, historial clinico y segmentacion.
"""
import structlog
from datetime import date, datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.patient import Patient
from app.models.clinical_record import ClinicalRecord
from app.models.appointment import Appointment
from app.models.consent import Consent
from app.models.agent_config import AgentConfig
from app.agents.profiling.segmentation import compute_segment

log = structlog.get_logger()

# Segmentos → reglas por defecto
DEFAULT_SEGMENT_RULES = {
    "high_value": ["implante", "implante_valoracion", "carillas", "corona", "rehabilitacion", "cirugia_periodontal"],
    "inactive": {"no_visit_days": 180},
    "cronic": {"recurrence_days": 45},
}


async def get_profiling_config(db: AsyncSession) -> dict:
    """Carga la configuracion del agente de perfilamiento desde agent_configs."""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.agent_name == "profiling")
    )
    config = result.scalar_one_or_none()
    if config:
        return config.parameters
    return {
        "segment_rules": DEFAULT_SEGMENT_RULES,
        "inactive_threshold_days": 180,
        "proactive_days_before": 30,
    }


async def get_patient_profile(patient_id: int, db: AsyncSession) -> dict | None:
    """
    Retorna el perfil completo del paciente: datos + historial clinico + citas + segmento.
    """
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        return None

    # Historial clinico (no borrado logicamente)
    records_result = await db.execute(
        select(ClinicalRecord)
        .where(
            ClinicalRecord.patient_id == patient_id,
            ClinicalRecord.deleted_at.is_(None),
        )
        .order_by(ClinicalRecord.created_at.desc())
        .limit(10)
    )
    records = records_result.scalars().all()

    # Ultima cita completada
    appt_result = await db.execute(
        select(Appointment)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.status == "completed",
        )
        .order_by(Appointment.scheduled_at.desc())
        .limit(1)
    )
    last_appt = appt_result.scalar_one_or_none()

    # Proxima cita programada
    next_appt_result = await db.execute(
        select(Appointment)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.status == "scheduled",
        )
        .order_by(Appointment.scheduled_at.asc())
        .limit(1)
    )
    next_appt = next_appt_result.scalar_one_or_none()

    procedures = [r.procedure_type for r in records if r.procedure_type]
    last_visit = last_appt.scheduled_at.date() if last_appt and last_appt.scheduled_at else None

    return {
        "id": patient.id,
        "full_name": patient.full_name,
        "phone": patient.phone,
        "email": patient.email,
        "birth_date": patient.birth_date.isoformat() if patient.birth_date else None,
        "segment": patient.segment,
        "channel_pref": patient.channel_pref,
        "clinical_records": [
            {
                "id": r.id,
                "procedure_type": r.procedure_type,
                "notes": r.notes,
                "next_visit_due": r.next_visit_due.isoformat() if r.next_visit_due else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
        "last_visit": last_visit.isoformat() if last_visit else None,
        "next_appointment": next_appt.scheduled_at.isoformat() if next_appt and next_appt.scheduled_at else None,
    }


async def update_patient_data(
    patient_id: int,
    updates: dict,
    db: AsyncSession,
) -> Patient:
    """
    Actualiza datos demograficos del paciente (nombre, email, fecha de nacimiento, canal).
    Campos permitidos: full_name, email, birth_date, channel_pref.
    """
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError(f"Paciente {patient_id} no encontrado")

    allowed = {"full_name", "email", "birth_date", "channel_pref"}
    for key, value in updates.items():
        if key in allowed:
            setattr(patient, key, value)

    await db.flush()
    log.info("patient.updated", patient_id=patient_id, fields=list(updates.keys()))
    return patient


async def add_clinical_record(
    patient_id: int,
    procedure_type: str,
    notes: str,
    next_visit_due: date | None,
    created_by: str,
    db: AsyncSession,
) -> ClinicalRecord:
    """
    Agrega un registro clinico al historial del paciente.
    Requiere que exista consentimiento previo.
    """
    record = ClinicalRecord(
        patient_id=patient_id,
        procedure_type=procedure_type,
        notes=notes,
        next_visit_due=next_visit_due,
        created_by=created_by,
    )
    db.add(record)
    await db.flush()
    log.info("clinical_record.added", patient_id=patient_id, procedure=procedure_type)
    return record


async def refresh_patient_segment(
    patient_id: int,
    db: AsyncSession,
    config: dict | None = None,
) -> str:
    """
    Recalcula y actualiza el segmento del paciente basado en su historial.
    Retorna el nuevo segmento.
    """
    if config is None:
        config = await get_profiling_config(db)

    segment_rules = config.get("segment_rules", DEFAULT_SEGMENT_RULES)

    # Obtener ultima cita completada
    appt_result = await db.execute(
        select(Appointment)
        .where(Appointment.patient_id == patient_id, Appointment.status == "completed")
        .order_by(Appointment.scheduled_at.desc())
        .limit(1)
    )
    last_appt = appt_result.scalar_one_or_none()
    last_visit = last_appt.scheduled_at.date() if last_appt and last_appt.scheduled_at else None

    # Obtener procedimientos del historial clinico
    records_result = await db.execute(
        select(ClinicalRecord.procedure_type)
        .where(
            ClinicalRecord.patient_id == patient_id,
            ClinicalRecord.deleted_at.is_(None),
        )
    )
    procedures = [row[0] for row in records_result.fetchall() if row[0]]

    new_segment = compute_segment(last_visit, procedures, segment_rules)

    # Actualizar en DB
    patient_result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = patient_result.scalar_one_or_none()
    if patient:
        patient.segment = new_segment
        await db.flush()

    log.info("patient.segment_updated", patient_id=patient_id, segment=new_segment)
    return new_segment


async def has_consent(patient_id: int, db: AsyncSession) -> bool:
    """Verifica si el paciente tiene consentimiento de tratamiento de datos."""
    result = await db.execute(
        select(Consent).where(
            Consent.patient_id == patient_id,
            Consent.consent_type == "data_treatment",
        )
    )
    return result.scalar_one_or_none() is not None


def format_profile_summary(profile: dict) -> str:
    """Formatea el perfil del paciente como texto para incluir en el prompt."""
    if not profile:
        return "Perfil no disponible."

    lines = [
        f"Nombre: {profile.get('full_name') or 'No registrado'}",
        f"Segmento: {profile.get('segment') or 'nuevo'}",
        f"Ultima visita: {profile.get('last_visit') or 'Sin registros'}",
        f"Proxima cita: {profile.get('next_appointment') or 'No programada'}",
    ]

    records = profile.get("clinical_records", [])
    if records:
        lines.append(f"\nHistorial reciente ({len(records)} registros):")
        for r in records[:3]:
            lines.append(f"  - {r['procedure_type']} ({r.get('created_at', '')[:10]})")
            if r.get("next_visit_due"):
                lines.append(f"    Proxima revision: {r['next_visit_due']}")

    return "\n".join(lines)
