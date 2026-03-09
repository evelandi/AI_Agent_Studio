"""
Lógica de seguimiento proactivo de pacientes.
La tarea corre diariamente via APScheduler.

Implementación completa: Fase 4
"""


async def proactive_appointment_reminders() -> None:
    """
    Consulta pacientes con next_visit_due dentro de proactive_days_before.
    Inicia conversación WhatsApp automáticamente para recordar la cita.
    """
    # TODO: Fase 4 — implementar:
    # 1. Obtener configuración de agenda (proactive_days_before)
    # 2. Consultar clinical_records con next_visit_due próximos
    # 3. Para cada paciente, iniciar conversación WhatsApp si no hay cita programada
    # 4. Registrar en audit_log con triggered_by='scheduler:proactive_reminders'
    raise NotImplementedError("proactive_appointment_reminders: implementar en Fase 4")
