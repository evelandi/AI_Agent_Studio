"""
A2 — Gestor de Agendas
Google Calendar, agendamiento reactivo y proactivo.

Implementación completa: Fase 4
"""
from app.core.state import GlobalHubState


async def agenda_agent_node(state: GlobalHubState) -> GlobalHubState:
    """
    - Consulta disponibilidad en Google Calendar
    - Propone 3 slots óptimos al paciente
    - Confirma y crea evento en Calendar
    - Envía confirmación por WhatsApp
    """
    # TODO: Fase 4
    raise NotImplementedError("AgendaAgent: implementar en Fase 4")
