"""
A1 — Gestor de Comunicaciones
Interfaz WhatsApp, RAG sobre conocimiento del consultorio, consentimientos,
horario de atención y escalamiento a humano.
"""
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.state import GlobalHubState, Message, MessageRole
from app.core.llm_factory import get_llm
from app.core.database import AsyncSessionLocal
from app.core.audit import write_audit_log
from app.agents.communications.tools import (
    query_knowledge_base,
    check_consent,
    register_consent,
    send_consent_request,
    get_agent_config,
    is_within_business_hours,
    contains_emergency_keywords,
)
from app.agents.communications.prompts import (
    COMMUNICATIONS_SYSTEM_PROMPT,
    OUTSIDE_HOURS_MESSAGE,
    ESCALATION_MESSAGE,
    CONSENT_ACCEPTED_MESSAGE,
    NO_INFO_MESSAGE,
)

log = structlog.get_logger()

# Palabras que indican aceptación del consentimiento
CONSENT_ACCEPTANCE_WORDS = {"acepto", "si", "sí", "ok", "de acuerdo", "acepto términos"}


def _format_chat_history(messages: list[Message], max_turns: int = 6) -> str:
    """Formatea las últimas N interacciones como historial para el prompt."""
    recent = messages[-max_turns * 2:]
    lines = []
    for msg in recent:
        role = "Paciente" if msg.role == MessageRole.USER else "Asistente"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines) if lines else "(inicio de conversación)"


async def communications_agent_node(state: GlobalHubState) -> GlobalHubState:
    """
    Nodo del Agente de Comunicaciones A1.

    Flujo:
    1. Cargar configuración del agente desde agent_configs
    2. Verificar horario de atención → respuesta automática si fuera de horario
    3. Detectar keywords de emergencia → escalamiento inmediato
    4. Verificar consentimiento del paciente → solicitar si no existe
    5. Detectar respuesta "ACEPTO" → registrar consentimiento
    6. Consultar RAG y generar respuesta con LLM
    7. Registrar en audit_log
    """
    async with AsyncSessionLocal() as db:
        config = await get_agent_config(db)

        user_messages = [m for m in state.messages if m.role == MessageRole.USER]
        last_text = user_messages[-1].content if user_messages else ""
        reply_text: str | None = None
        new_requires_escalation = state.requires_human_escalation

        # ── 1. Horario de atención ────────────────────────────────
        if not is_within_business_hours(config) and config.get("auto_response_outside_hours"):
            bh = config.get("business_hours", {})
            reply_text = OUTSIDE_HOURS_MESSAGE.format(
                start=bh.get("start", "08:00"),
                end=bh.get("end", "18:00"),
            )
            await write_audit_log(
                db=db,
                agent_name="communications",
                action="outside_hours_response",
                triggered_by="config:auto_response_outside_hours",
                patient_id=state.patient_id,
            )

        # ── 2. Keywords de emergencia ─────────────────────────────
        elif contains_emergency_keywords(last_text, config):
            reply_text = ESCALATION_MESSAGE
            new_requires_escalation = True
            await write_audit_log(
                db=db,
                agent_name="communications",
                action="emergency_escalation",
                triggered_by="config:emergency_keywords",
                patient_id=state.patient_id,
                detail={"message": last_text[:100]},
            )

        # ── 3. Verificar consentimiento ───────────────────────────
        elif state.patient_id and not await check_consent(state.patient_id, db):
            # Detectar si el paciente está respondiendo "ACEPTO"
            if last_text.strip().lower() in CONSENT_ACCEPTANCE_WORDS:
                await register_consent(state.patient_id, state.patient_phone, db)
                reply_text = CONSENT_ACCEPTED_MESSAGE
                await write_audit_log(
                    db=db,
                    agent_name="communications",
                    action="consent_registered",
                    triggered_by="patient_response:ACEPTO",
                    patient_id=state.patient_id,
                )
            else:
                # Solicitar consentimiento
                await send_consent_request(state.patient_phone)
                reply_text = None  # ya se envió directamente por WhatsApp
                await write_audit_log(
                    db=db,
                    agent_name="communications",
                    action="consent_requested",
                    triggered_by="first_contact",
                    patient_id=state.patient_id,
                )

        # ── 4. Flujo normal: RAG + LLM ────────────────────────────
        else:
            context = await query_knowledge_base(query=last_text, db=db)
            bh = config.get("business_hours", {})
            chat_history = _format_chat_history(state.messages[:-1])  # excluir el último

            system_prompt = COMMUNICATIONS_SYSTEM_PROMPT.format(
                tone=config.get("tone", "cercano"),
                business_hours_start=bh.get("start", "08:00"),
                business_hours_end=bh.get("end", "18:00"),
                context=context,
                chat_history=chat_history,
            )

            llm = get_llm("communications", db=None)
            lc_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=last_text),
            ]

            try:
                response = await llm.ainvoke(lc_messages)
                reply_text = response.content.strip() or NO_INFO_MESSAGE
            except Exception as exc:
                log.error("communications.llm_error", error=str(exc))
                reply_text = NO_INFO_MESSAGE

            await write_audit_log(
                db=db,
                agent_name="communications",
                action="rag_response",
                triggered_by="patient_message",
                patient_id=state.patient_id,
                detail={"query": last_text[:100], "context_chunks": context[:200]},
            )

        await db.commit()

    # Construir nuevo estado
    new_messages = list(state.messages)
    if reply_text:
        new_messages.append(Message(role=MessageRole.ASSISTANT, content=reply_text))

    return state.model_copy(
        update={
            "messages": new_messages,
            "requires_human_escalation": new_requires_escalation,
            "next_agent": "response",
        }
    )
