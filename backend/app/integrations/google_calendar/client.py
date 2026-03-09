"""
Google Calendar API Client.
Implementación completa: Fase 4
"""
from app.config import settings


class GoogleCalendarClient:
    """
    Cliente para Google Calendar API usando Service Account.
    Métodos principales:
    - get_free_slots: consulta disponibilidad FreeBusy
    - create_event: crea una cita en el calendario
    - update_event: modifica una cita existente
    - delete_event: elimina/cancela una cita
    """

    def __init__(self):
        self.calendar_id = settings.google_calendar_id
        self.service_account_json = settings.google_service_account_json
        self._service = None

    def _get_service(self):
        """Inicializa el servicio de Google Calendar con Service Account."""
        # TODO: Fase 4 — implementar con google-auth y googleapiclient
        raise NotImplementedError("GoogleCalendarClient: implementar en Fase 4")

    async def get_free_slots(self, date_from: str, date_to: str) -> list[dict]:
        """Consulta períodos libres en el calendario."""
        # TODO: Fase 4
        raise NotImplementedError

    async def create_event(self, summary: str, start: str, end: str, description: str = "") -> dict:
        """Crea un evento en el calendario."""
        # TODO: Fase 4
        raise NotImplementedError

    async def update_event(self, event_id: str, updates: dict) -> dict:
        """Actualiza un evento existente."""
        # TODO: Fase 4
        raise NotImplementedError

    async def delete_event(self, event_id: str) -> bool:
        """Elimina un evento del calendario."""
        # TODO: Fase 4
        raise NotImplementedError


google_calendar_client = GoogleCalendarClient()
