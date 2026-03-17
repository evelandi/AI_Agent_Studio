"""
Algoritmo de optimización de slots para el Gestor de Agendas.

Lógica:
1. Genera ventanas de tiempo dentro del horario de atención (lun-sáb).
2. Excluye períodos ocupados (de Google Calendar FreeBusy).
3. Aplica duración del procedimiento + buffer entre citas.
4. Reserva slots de emergencia al inicio de cada día.
5. Retorna hasta `max_slots` opciones ordenadas cronológicamente.
"""
from datetime import datetime, timedelta, timezone, time


# Horario de atención por día de la semana (0=lun … 5=sáb, 6=dom)
BUSINESS_HOURS: dict[int, tuple[time, time]] = {
    0: (time(8, 0), time(18, 0)),  # lunes
    1: (time(8, 0), time(18, 0)),  # martes
    2: (time(8, 0), time(18, 0)),  # miércoles
    3: (time(8, 0), time(18, 0)),  # jueves
    4: (time(8, 0), time(18, 0)),  # viernes
    5: (time(8, 0), time(14, 0)),  # sábado
    # domingo (6) no trabaja
}

COLOMBIA_UTC_OFFSET = timedelta(hours=-5)
COLOMBIA_TZ = timezone(COLOMBIA_UTC_OFFSET)


def _colombia_now() -> datetime:
    return datetime.now(COLOMBIA_TZ)


def _to_colombia(dt: datetime) -> datetime:
    """Convierte un datetime (cualquier tz o naive) a Colombia UTC-5."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=COLOMBIA_TZ)
    return dt.astimezone(COLOMBIA_TZ)


def _parse_iso(iso_str: str) -> datetime:
    """Parsea un string ISO 8601 a datetime con timezone."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return _to_colombia(dt)


def get_optimal_slots(
    procedure_duration_minutes: int,
    busy_periods: list[dict],
    days_ahead: int = 7,
    buffer_minutes: int = 15,
    emergency_slots_per_day: int = 1,
    max_slots: int = 3,
) -> list[dict]:
    """
    Calcula los mejores horarios disponibles.

    Args:
        procedure_duration_minutes: Duración del procedimiento en minutos.
        busy_periods: Lista de {"start": ISO, "end": ISO} de Google Calendar FreeBusy.
        days_ahead: Cuántos días hacia adelante buscar.
        buffer_minutes: Minutos de buffer entre citas.
        emergency_slots_per_day: Slots reservados al inicio de cada día para emergencias.
        max_slots: Número máximo de opciones a retornar.

    Returns:
        Lista de dicts {"start": ISO str, "end": ISO str, "label": str humano}.
    """
    total_duration = procedure_duration_minutes + buffer_minutes
    slot_delta = timedelta(minutes=total_duration)

    # Convertir períodos ocupados a datetime Colombia
    busy: list[tuple[datetime, datetime]] = []
    for period in busy_periods:
        busy.append((_parse_iso(period["start"]), _parse_iso(period["end"])))

    now = _colombia_now()
    # No proponer slots en la hora actual; empezar 1h en el futuro
    search_start = now + timedelta(hours=1)

    available: list[dict] = []

    for day_offset in range(days_ahead):
        day = (search_start + timedelta(days=day_offset)).date()
        weekday = day.weekday()

        if weekday not in BUSINESS_HOURS:
            continue  # domingo

        bh_start, bh_end = BUSINESS_HOURS[weekday]
        day_start = datetime.combine(day, bh_start, tzinfo=COLOMBIA_TZ)
        day_end = datetime.combine(day, bh_end, tzinfo=COLOMBIA_TZ)

        # Reservar 'emergency_slots_per_day' slots al principio del día
        protected_end = day_start + timedelta(minutes=total_duration * emergency_slots_per_day)
        candidate = max(day_start, search_start)
        if candidate < protected_end:
            candidate = protected_end

        while candidate + slot_delta <= day_end:
            slot_end = candidate + timedelta(minutes=procedure_duration_minutes)

            # Verificar que no se superpone con períodos ocupados
            overlaps = any(
                not (slot_end <= b_start or candidate >= b_end)
                for b_start, b_end in busy
            )

            if not overlaps:
                label = candidate.strftime("%A %d/%m a las %I:%M %p")
                available.append({
                    "start": candidate.isoformat(),
                    "end": slot_end.isoformat(),
                    "label": label,
                })
                if len(available) >= max_slots:
                    return available

            candidate += slot_delta

    return available


def format_slots_for_patient(slots: list[dict]) -> str:
    """
    Formatea la lista de slots como mensaje para el paciente.

    Ejemplo:
        Te ofrecemos estas opciones:
        1️⃣ Lunes 10/03 a las 09:00 AM
        2️⃣ Lunes 10/03 a las 10:00 AM
        3️⃣ Martes 11/03 a las 08:00 AM

        Responde con el número de tu preferencia (1, 2 o 3).
    """
    if not slots:
        return (
            "Lo sentimos, no encontramos disponibilidad en los próximos días. "
            "Por favor llámanos al +57 601 234 5678 para buscar una alternativa."
        )

    lines = ["Te ofrecemos estas opciones:\n"]
    emojis = ["1️⃣", "2️⃣", "3️⃣"]
    for i, slot in enumerate(slots):
        emoji = emojis[i] if i < len(emojis) else f"{i + 1}."
        lines.append(f"{emoji} {slot['label']}")

    lines.append("\nResponde con el número de tu preferencia (1, 2 o 3).")
    return "\n".join(lines)
