"""
Grafo LangGraph principal del AI Assistant Hub.

Fase 4: routing condicional por intent
  supervisor → [communications_agent | agenda_agent | echo (placeholder fases 5-6)] → response

Flujo:
  [WhatsApp Webhook]
        ↓
  [supervisor]            ← identifica paciente, clasifica intención
        ↓ (conditional)
  ┌─────┴────────────────┬────────────────────┐
  │ COMMUNICATION/UNKNOWN│ SCHEDULING          │ PROFILING/CONTENT
  ▼                      ▼                    ▼
  [communications_agent] [agenda_agent]       [echo]
        └──────────────┬──────────────────────┘
                       ▼
                   [response]     ← envía por WhatsApp + audit log
"""
import uuid
import structlog
from datetime import datetime, timezone

from langgraph.graph import StateGraph, END

from app.core.state import GlobalHubState, Message, MessageRole, IntentType
from app.core.database import AsyncSessionLocal
from app.graph.checkpointer import setup_checkpointer
from app.graph.nodes import echo_node, response_node
from app.agents.supervisor import supervisor_node
from app.agents.communications.agent import communications_agent_node
from app.agents.agenda.agent import agenda_agent_node
from app.integrations.whatsapp.schemas import IncomingMessage

log = structlog.get_logger()

_compiled_graph = None


# ── Wrappers (adaptan coroutines async al formato dict de LangGraph) ──

async def _supervisor_wrapper(state: GlobalHubState) -> dict:
    async with AsyncSessionLocal() as db:
        new_state = await supervisor_node(state, db)
        await db.commit()
    return new_state.model_dump()


async def _communications_wrapper(state: GlobalHubState) -> dict:
    # El agente gestiona su propia sesión de DB internamente
    new_state = await communications_agent_node(state)
    return new_state.model_dump()


async def _agenda_wrapper(state: GlobalHubState) -> dict:
    # El agente gestiona su propia sesión de DB internamente
    new_state = await agenda_agent_node(state)
    return new_state.model_dump()


async def _echo_wrapper(state: GlobalHubState) -> dict:
    async with AsyncSessionLocal() as db:
        new_state = await echo_node(state, db)
        await db.commit()
    return new_state.model_dump()


async def _response_wrapper(state: GlobalHubState) -> dict:
    async with AsyncSessionLocal() as db:
        new_state = await response_node(state, db)
        await db.commit()
    return new_state.model_dump()


# ── Routing condicional ────────────────────────────────────────────

def _route_after_supervisor(state: GlobalHubState) -> str:
    """
    Decide a qué agente va el flujo después del supervisor.
    Los agentes aún no implementados usan echo como placeholder.
    """
    if state.requires_human_escalation:
        return "response"  # escalar: saltar agente, enviar directamente

    intent = state.current_intent
    if intent in (IntentType.COMMUNICATION, IntentType.UNKNOWN):
        return "communications_agent"

    if intent == IntentType.SCHEDULING:
        return "agenda_agent"

    # Fases 5-6: estos agentes aún no están implementados
    return "echo"


# ── Construcción del grafo ─────────────────────────────────────────

def _build_graph():
    graph = StateGraph(GlobalHubState)

    graph.add_node("supervisor", _supervisor_wrapper)
    graph.add_node("communications_agent", _communications_wrapper)
    graph.add_node("agenda_agent", _agenda_wrapper)
    graph.add_node("echo", _echo_wrapper)
    graph.add_node("response", _response_wrapper)

    graph.set_entry_point("supervisor")

    # Routing condicional después del supervisor
    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "communications_agent": "communications_agent",
            "agenda_agent": "agenda_agent",
            "echo": "echo",
            "response": "response",
        },
    )

    graph.add_edge("communications_agent", "response")
    graph.add_edge("agenda_agent", "response")
    graph.add_edge("echo", "response")
    graph.add_edge("response", END)

    return graph


async def setup_graph() -> None:
    """Inicializa el grafo con checkpointer PostgreSQL. Llamar en lifespan."""
    global _compiled_graph
    checkpointer = await setup_checkpointer()
    _compiled_graph = _build_graph().compile(checkpointer=checkpointer)
    log.info("hub_graph.ready")


# ── Punto de entrada desde el webhook ────────────────────────────

async def process_incoming_message(msg: IncomingMessage) -> None:
    """
    Procesa un mensaje de WhatsApp entrante.
    Thread ID = número de teléfono → estado persistente por paciente.
    """
    if _compiled_graph is None:
        log.error("hub_graph.not_initialized")
        return

    now = datetime.now(timezone.utc).isoformat()
    thread_id = msg.phone
    config = {"configurable": {"thread_id": thread_id}}

    # Recuperar historial previo del checkpointer
    existing = await _compiled_graph.aget_state(config)
    if existing and existing.values:
        prev_state = GlobalHubState(**existing.values)
    else:
        prev_state = GlobalHubState(
            conversation_id=str(uuid.uuid4()),
            patient_phone=msg.phone,
            session_start=now,
        )

    new_message = Message(role=MessageRole.USER, content=msg.text, timestamp=now)
    initial_state = prev_state.model_copy(
        update={"messages": prev_state.messages + [new_message], "last_activity": now}
    )

    log.info(
        "hub_graph.processing",
        phone=msg.phone,
        message_preview=msg.text[:60],
        history_length=len(initial_state.messages),
    )

    try:
        await _compiled_graph.ainvoke(initial_state.model_dump(), config=config)
    except Exception as exc:
        log.error("hub_graph.error", phone=msg.phone, error=str(exc), exc_info=True)
