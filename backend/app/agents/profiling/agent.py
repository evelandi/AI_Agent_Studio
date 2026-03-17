"""
A3 - Agente de Perfilamiento de Pacientes
EHR + CRM, segmentacion automatica, consentimientos.

Flujo:
1. Cargar perfil del paciente desde DB
2. Determinar intencion: ver historial / actualizar datos / ver segmento
3. Verificar consentimiento antes de escribir datos PHI
4. Ejecutar accion y actualizar segmento si aplica
5. Responder al paciente con resumen
"""
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.state import GlobalHubState, Message, MessageRole
from app.core.database import AsyncSessionLocal
from app.core.llm_factory import get_llm
from app.core.audit import write_audit_log
from app.agents.profiling.tools import (
    get_profiling_config,
    get_patient_profile,
    update_patient_data,
    add_clinical_record,
    refresh_patient_segment,
    has_consent,
    format_profile_summary,
)
from app.agents.profiling.prompts import PROFILING_SYSTEM_PROMPT

log = structlog.get_logger()

# Palabras clave para detectar intencion dentro de PROFILING
HISTORY_KEYWORDS = {"historial", "registros", "mis citas", "mis procedimientos", "que tengo registrado"}
UPDATE_KEYWORDS = {"actualizar", "cambiar", "modificar", "nuevo correo", "nuevo email", "mi nombre"}
SEGMENT_KEYWORDS = {"segmento", "perfil", "como estoy", "mi estado", "soy paciente"}


def _detect_profiling_intent(text: str) -> str:
    """Detecta sub-intencion dentro de PROFILING: history | update | segment | general."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in HISTORY_KEYWORDS):
        return "history"
    if any(kw in text_lower for kw in UPDATE_KEYWORDS):
        return "update"
    if any(kw in text_lower for kw in SEGMENT_KEYWORDS):
        return "segment"
    return "general"


def _format_history(messages: list[Message], max_turns: int = 4) -> str:
    recent = messages[-(max_turns * 2):]
    lines = []
    for msg in recent:
        role = "Paciente" if msg.role == MessageRole.USER else "Asistente"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines) if lines else "(inicio)"


async def profiling_agent_node(state: GlobalHubState) -> GlobalHubState:
    """
    Nodo del Agente de Perfilamiento A3.
    """
    async with AsyncSessionLocal() as db:
        config = await get_profiling_config(db)
        inactive_days = config.get("inactive_threshold_days", 180)

        user_messages = [m for m in state.messages if m.role == MessageRole.USER]
        last_text = user_messages[-1].content.strip() if user_messages else ""

        reply_text: str | None = None

        # Sin patient_id no podemos hacer nada util
        if not state.patient_id:
            reply_text = (
                "No pude identificar tu perfil. "
                "Por favor escribe tu nombre completo o numero de documento para buscarte."
            )
        else:
            sub_intent = _detect_profiling_intent(last_text)
            consent = await has_consent(state.patient_id, db)
            profile = await get_patient_profile(state.patient_id, db)

            if sub_intent == "history":
                if not consent:
                    reply_text = (
                        "Para mostrarte tu historial clinico necesito que primero aceptes "
                        "el tratamiento de datos. Responde ACEPTO para continuar."
                    )
                elif profile:
                    summary = format_profile_summary(profile)
                    reply_text = f"Aqui esta tu informacion:\n\n{summary}"
                else:
                    reply_text = "No encontramos historial clinico registrado para tu numero."

            elif sub_intent == "update":
                if not consent:
                    reply_text = (
                        "Para actualizar tus datos necesito que primero aceptes "
                        "el tratamiento de datos. Responde ACEPTO para continuar."
                    )
                else:
                    # Extraer campos a actualizar del mensaje con LLM
                    llm = get_llm("profiling", db=None)
                    extract_prompt = (
                        "El paciente quiere actualizar sus datos. Extrae del siguiente mensaje "
                        "los campos a actualizar en formato JSON con claves: "
                        "full_name, email, birth_date (YYYY-MM-DD), channel_pref (whatsapp/email). "
                        "Solo incluye los campos mencionados. Si no hay campos claros, responde {}.\n\n"
                        f"Mensaje: {last_text}"
                    )
                    try:
                        response = await llm.ainvoke([HumanMessage(content=extract_prompt)])
                        import json, re
                        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                        updates = json.loads(json_match.group()) if json_match else {}
                    except Exception:
                        updates = {}

                    if updates:
                        await update_patient_data(state.patient_id, updates, db)
                        await refresh_patient_segment(state.patient_id, db, config)
                        fields = ", ".join(updates.keys())
                        reply_text = f"Perfecto, actualice tu informacion ({fields}) exitosamente."
                    else:
                        reply_text = (
                            "Que dato deseas actualizar? Puedo modificar:\n"
                            "- Nombre completo\n- Email\n- Fecha de nacimiento\n- Canal preferido (WhatsApp/email)"
                        )

                    await write_audit_log(
                        db=db,
                        agent_name="profiling",
                        action="patient_data_updated",
                        triggered_by="patient_message",
                        patient_id=state.patient_id,
                        detail={"fields": list(updates.keys())},
                    )

            elif sub_intent == "segment":
                new_segment = await refresh_patient_segment(state.patient_id, db, config)
                segment_labels = {
                    "high_value": "Paciente de alto valor (tratamientos especializados)",
                    "cronic": "Paciente recurrente (visitas regulares)",
                    "inactive": f"Paciente inactivo (sin visita en mas de {inactive_days} dias)",
                    "new": "Paciente nuevo (sin historial previo)",
                }
                label = segment_labels.get(new_segment, new_segment)
                reply_text = f"Tu perfil actual: {label}."

            else:
                # Flujo general: LLM con contexto del perfil
                profile_summary = format_profile_summary(profile) if profile else "Sin perfil registrado."
                chat_history = _format_history(state.messages[:-1])

                system_prompt = PROFILING_SYSTEM_PROMPT.format(
                    inactive_threshold_days=inactive_days,
                ) + f"\n\nPerfil del paciente:\n{profile_summary}\n\nHistorial conversacion:\n{chat_history}"

                llm = get_llm("profiling", db=None)
                try:
                    response = await llm.ainvoke([
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=last_text),
                    ])
                    reply_text = response.content.strip()
                except Exception as exc:
                    log.error("profiling.llm_error", error=str(exc))
                    reply_text = "Hubo un error al procesar tu solicitud. Intenta de nuevo."

            await write_audit_log(
                db=db,
                agent_name="profiling",
                action=f"profiling_{sub_intent}",
                triggered_by="patient_message",
                patient_id=state.patient_id,
            )

        await db.commit()

    new_messages = list(state.messages)
    if reply_text:
        new_messages.append(Message(role=MessageRole.ASSISTANT, content=reply_text))

    return state.model_copy(
        update={
            "messages": new_messages,
            "next_agent": "response",
        }
    )
