"""
Condiciones de routing del grafo LangGraph.
Implementación completa: Fase 2
"""
from app.core.state import GlobalHubState, IntentType

AGENT_MAP = {
    IntentType.COMMUNICATION: "communications_agent",
    IntentType.SCHEDULING: "agenda_agent",
    IntentType.PROFILING: "profiling_agent",
    IntentType.CONTENT: "content_agent",
    IntentType.UNKNOWN: "communications_agent",  # fallback
}


def route_to_agent(state: GlobalHubState) -> str:
    """
    Función de routing condicional del grafo.
    Retorna el nombre del nodo al que debe ir el flujo.
    """
    if state.requires_human_escalation:
        return "human_escalation"

    if state.next_agent:
        return state.next_agent

    return AGENT_MAP.get(state.current_intent, "communications_agent")
