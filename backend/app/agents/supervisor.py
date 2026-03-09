"""
Supervisor Agent — orquestador central del hub.
Clasifica la intención del mensaje y decide el routing al agente correspondiente.

Implementación completa: Fase 2
"""
from app.core.state import GlobalHubState, IntentType


async def supervisor_node(state: GlobalHubState) -> GlobalHubState:
    """
    Nodo supervisor del grafo LangGraph.
    - Identifica al paciente por número de teléfono
    - Clasifica la intención del mensaje
    - Establece next_agent para el routing
    """
    # TODO: Fase 2 — implementar clasificación con LLM
    # TODO: Fase 2 — cargar/crear paciente en DB por phone
    # TODO: Fase 2 — escribir audit log de entrada
    raise NotImplementedError("Supervisor: implementar en Fase 2")
