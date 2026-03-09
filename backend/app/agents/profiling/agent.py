"""
A3 — Perfilamiento de Pacientes
EHR + CRM, segmentación, consentimientos.

Implementación completa: Fase 5
"""
from app.core.state import GlobalHubState


async def profiling_agent_node(state: GlobalHubState) -> GlobalHubState:
    """
    - CRUD de pacientes y registros clínicos
    - Segmentación automática después de cada actualización
    - Verificación de consentimiento antes de escribir datos PHI
    - Exposición de datos agregados anonimizados para A4
    """
    # TODO: Fase 5
    raise NotImplementedError("ProfilingAgent: implementar en Fase 5")
