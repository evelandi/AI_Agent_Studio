"""
Lógica de segmentación automática de pacientes.
Implementación completa: Fase 5
"""
from datetime import date, timedelta


def compute_segment(
    last_visit_date: date | None,
    procedures: list[str],
    segment_rules: dict,
) -> str:
    """
    Asigna el segmento al paciente según las reglas configuradas en agent_configs.

    Segmentos:
    - high_value: paciente con procedimientos de alto valor (implantes, rehabilitación)
    - cronic: paciente con visitas recurrentes mensuales
    - inactive: sin visita en más de N días
    - new: primer registro, sin historial clínico
    """
    if not last_visit_date:
        return "new"

    high_value_procs = segment_rules.get("high_value", [])
    if any(p in high_value_procs for p in procedures):
        return "high_value"

    inactive_days = segment_rules.get("inactive", {}).get("no_visit_days", 180)
    if (date.today() - last_visit_date).days >= inactive_days:
        return "inactive"

    cronic_days = segment_rules.get("cronic", {}).get("recurrence_days", 30)
    if (date.today() - last_visit_date).days <= cronic_days:
        return "cronic"

    return "new"
