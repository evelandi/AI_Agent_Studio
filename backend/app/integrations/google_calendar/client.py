"""
Google Calendar API Client — async via httpx + google-auth Service Account.

Autenticación: Service Account JSON key file.
Todas las llamadas HTTP son async para no bloquear el event loop de FastAPI.
"""
import structlog
from datetime import datetime
from pathlib import Path

import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest

from app.config import settings

log = structlog.get_logger()

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarClient:
    """
    Cliente async para Google Calendar API usando Service Account.

    Métodos:
    - get_busy_periods(date_from, date_to) → lista de períodos ocupados
    - create_event(summary, start, end, description) → dict con el evento creado
    - update_event(event_id, updates) → dict con el evento actualizado
    - delete_event(event_id) → bool
    """

    def __init__(self):
        self.calendar_id: str = settings.google_calendar_id
        self._sa_file: str = settings.google_service_account_json
        self._creds: service_account.Credentials | None = None

    def _load_credentials(self) -> service_account.Credentials:
        """Carga (o reusa) las credenciales de Service Account."""
        if self._creds and self._creds.valid:
            return self._creds

        sa_path = Path(self._sa_file)
        if not sa_path.exists():
            raise FileNotFoundError(
                f"Service Account JSON no encontrado: {self._sa_file}. "
                "Coloca el archivo en credentials/google_service_account.json"
            )

        creds = service_account.Credentials.from_service_account_file(
            str(sa_path), scopes=SCOPES
        )
        if not creds.valid:
            creds.refresh(GoogleAuthRequest())

        self._creds = creds
        return creds

    def _auth_headers(self) -> dict[str, str]:
        """Devuelve los headers de Authorization con el token actual."""
        creds = self._load_credentials()
        if not creds.valid:
            creds.refresh(GoogleAuthRequest())
        return {
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json",
        }

    # ── FreeBusy ─────────────────────────────────────────────────────────

    async def get_busy_periods(
        self, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        """
        Consulta la API FreeBusy de Google Calendar.

        Returns:
            Lista de dicts {"start": ISO str, "end": ISO str} con períodos ocupados.
        """
        body = {
            "timeMin": date_from.isoformat(),
            "timeMax": date_to.isoformat(),
            "timeZone": "America/Bogota",
            "items": [{"id": self.calendar_id}],
        }
        url = f"{CALENDAR_BASE}/freeBusy"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=body, headers=self._auth_headers())
            resp.raise_for_status()
            data = resp.json()
            calendars = data.get("calendars", {})
            busy = calendars.get(self.calendar_id, {}).get("busy", [])
            log.debug("calendar.freebusy", busy_periods=len(busy))
            return busy
        except httpx.HTTPStatusError as exc:
            log.error(
                "calendar.freebusy_error",
                status=exc.response.status_code,
                body=exc.response.text,
            )
            raise

    # ── Events ───────────────────────────────────────────────────────────

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str = "",
        attendee_email: str | None = None,
    ) -> dict:
        """
        Crea un evento en Google Calendar.

        Returns:
            Dict con los datos del evento creado (incluye 'id' del evento).
        """
        body: dict = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start.isoformat(),
                "timeZone": "America/Bogota",
            },
            "end": {
                "dateTime": end.isoformat(),
                "timeZone": "America/Bogota",
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                    {"method": "email", "minutes": 60},
                ],
            },
        }
        if attendee_email:
            body["attendees"] = [{"email": attendee_email}]

        url = f"{CALENDAR_BASE}/calendars/{self.calendar_id}/events"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=body, headers=self._auth_headers())
        resp.raise_for_status()
        event = resp.json()
        log.info("calendar.event_created", event_id=event.get("id"), summary=summary)
        return event

    async def update_event(self, event_id: str, updates: dict) -> dict:
        """
        Actualiza un evento existente (PATCH).

        Args:
            event_id: ID del evento en Google Calendar.
            updates: campos a modificar (p. ej. {"summary": "...", "start": {...}}).
        Returns:
            Dict con el evento actualizado.
        """
        url = f"{CALENDAR_BASE}/calendars/{self.calendar_id}/events/{event_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(url, json=updates, headers=self._auth_headers())
        resp.raise_for_status()
        event = resp.json()
        log.info("calendar.event_updated", event_id=event_id)
        return event

    async def delete_event(self, event_id: str) -> bool:
        """
        Elimina/cancela un evento del calendario.

        Returns:
            True si se eliminó correctamente.
        """
        url = f"{CALENDAR_BASE}/calendars/{self.calendar_id}/events/{event_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(url, headers=self._auth_headers())
        if resp.status_code == 404:
            log.warning("calendar.event_not_found", event_id=event_id)
            return False
        resp.raise_for_status()
        log.info("calendar.event_deleted", event_id=event_id)
        return True


# Singleton — credenciales cacheadas en la instancia
google_calendar_client = GoogleCalendarClient()
