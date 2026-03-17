"""
Nodos del grafo LangGraph.
Cada nodo recibe y retorna el estado global del hub.
"""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.state import GlobalHubState, MessageRole, Message
from app.core.audit import write_audit_log
from app.integrations.whatsapp.client import whatsapp_client

log = structlog.get_logger()


async def echo_node(state: GlobalHubState, db: AsyncSession) -> GlobalHubState:
    """
    Nodo de echo para Fase 2.
    Repite el último mensaje del usuario con un prefijo.
    Será reemplazado por los agentes especializados en Fases 3-6.
    """
    user_messages = [m for m in state.messages if m.role == MessageRole.USER]
    last_text = user_messages[-1].content if user_messages else "(sin mensaje)"

    response_text = f"[Echo] Recibí tu mensaje: {last_text}"

    reply = Message(role=MessageRole.ASSISTANT, content=response_text)

    await write_audit_log(
        db=db,
        agent_name="echo",
        action="echo_response",
        triggered_by=f"intent:{state.current_intent}",
        patient_id=state.patient_id,
        detail={"response_preview": response_text[:100]},
    )

    return state.model_copy(
        update={"messages": state.messages + [reply], "next_agent": "response"}
    )


async def response_node(state: GlobalHubState, db: AsyncSession) -> GlobalHubState:
    """
    Nodo final del grafo.
    Toma el último mensaje del asistente y lo envía por WhatsApp.
    Registra la acción en audit_log.
    """
    assistant_messages = [m for m in state.messages if m.role == MessageRole.ASSISTANT]
    if not assistant_messages:
        log.warning("response_node.no_assistant_message", phone=state.patient_phone)
        return state

    final_text = assistant_messages[-1].content

    try:
        await whatsapp_client.send_text(to=state.patient_phone, text=final_text)
        log.info("response_node.sent", phone=state.patient_phone, length=len(final_text))
    except Exception as exc:
        log.error("response_node.send_failed", phone=state.patient_phone, error=str(exc))

    await write_audit_log(
        db=db,
        agent_name="response",
        action="send_whatsapp_message",
        triggered_by=f"graph_completion:{state.conversation_id}",
        patient_id=state.patient_id,
        detail={"message_preview": final_text[:100]},
    )

    return state
