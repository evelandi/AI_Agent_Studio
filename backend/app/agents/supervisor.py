"""
Supervisor Agent — orquestador central del hub.
Clasifica la intención del mensaje y decide el routing al agente correspondiente.
"""
import structlog
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.state import GlobalHubState, IntentType, Message, MessageRole
from app.core.llm_factory import get_llm
from app.core.audit import write_audit_log
from app.models.patient import Patient

log = structlog.get_logger()

INTENT_SYSTEM_PROMPT = """Eres el supervisor de un sistema de gestión de consultorio odontológico.
Clasifica la intención del mensaje del paciente en una de estas categorías:

- scheduling: el paciente quiere agendar, cancelar, confirmar o consultar una cita
- communication: preguntas sobre servicios, precios, horarios, ubicación, información general
- profiling: el paciente actualiza sus datos personales, hace preguntas sobre su historial
- content: solicitudes de información para redes sociales o marketing (uso interno)
- unknown: no es posible clasificar con certeza

Responde ÚNICAMENTE con una de las palabras anteriores, sin explicación adicional.
"""


async def get_or_create_patient(phone: str, db: AsyncSession) -> Patient:
    """Carga el paciente por teléfono o lo crea si no existe."""
    result = await db.execute(select(Patient).where(Patient.phone == phone))
    patient = result.scalar_one_or_none()
    if not patient:
        patient = Patient(phone=phone, channel_pref="whatsapp")
        db.add(patient)
        await db.flush()  # obtener el ID sin commitear
        log.info("supervisor.patient_created", phone=phone, patient_id=patient.id)
    return patient


async def classify_intent(text: str) -> IntentType:
    """Clasifica la intención del mensaje usando el LLM."""
    try:
        llm = get_llm("supervisor")
        messages = [
            SystemMessage(content=INTENT_SYSTEM_PROMPT),
            HumanMessage(content=text),
        ]
        response = await llm.ainvoke(messages)
        raw = response.content.strip().lower()
        return IntentType(raw) if raw in IntentType._value2member_map_ else IntentType.UNKNOWN
    except Exception as exc:
        log.warning("supervisor.classify_intent_failed", error=str(exc))
        return IntentType.UNKNOWN


async def supervisor_node(state: GlobalHubState, db: AsyncSession) -> GlobalHubState:
    """
    Nodo supervisor del grafo LangGraph:
    1. Carga o crea el paciente por número de teléfono
    2. Clasifica la intención del mensaje con el LLM
    3. Establece next_agent para el routing
    4. Registra en audit_log
    """
    now = datetime.now(timezone.utc).isoformat()

    # Cargar o crear paciente
    patient = await get_or_create_patient(state.patient_phone, db)

    # Obtener el último mensaje del usuario
    user_messages = [m for m in state.messages if m.role == MessageRole.USER]
    last_text = user_messages[-1].content if user_messages else ""

    # Clasificar intención
    intent = await classify_intent(last_text)

    # Routing: en Fase 2 todo va al echo (communications por defecto)
    # En Fase 3+ los agentes especializados manejarán cada intent
    next_agent = {
        IntentType.SCHEDULING: "agenda_agent",
        IntentType.COMMUNICATION: "communications_agent",
        IntentType.PROFILING: "profiling_agent",
        IntentType.CONTENT: "content_agent",
        IntentType.UNKNOWN: "communications_agent",
    }.get(intent, "communications_agent")

    log.info(
        "supervisor.routed",
        phone=state.patient_phone,
        intent=intent,
        next_agent=next_agent,
    )

    await write_audit_log(
        db=db,
        agent_name="supervisor",
        action="classify_intent",
        triggered_by=f"whatsapp_message:{state.conversation_id}",
        patient_id=patient.id,
        detail={"intent": intent, "next_agent": next_agent, "message_preview": last_text[:100]},
    )

    return state.model_copy(
        update={
            "patient_id": patient.id,
            "current_intent": intent,
            "next_agent": next_agent,
            "last_activity": now,
            "session_start": state.session_start or now,
        }
    )
