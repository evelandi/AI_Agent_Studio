"""
A4 - Generador de Contenido para Redes Sociales
Texto + imagen (opcional) para Instagram, Facebook, WhatsApp Status.

Flujo Chain-of-Thought (CoT):
  Paso 1 — Investigacion: el LLM analiza el topico y perfil de audiencia
  Paso 2 — Redaccion:     genera el texto adaptado al canal
  Paso 3 — Revision:      un LLM "critico" valida etica medica y ratio promo/educativo
  Paso 4 — Imagen:        genera imagen con Stable Diffusion (degradado si no hay GPU)
  Paso 5 — Guardado:      persiste como borrador en content_pieces para revision manual

Activacion:
  - Via WhatsApp: paciente/admin con intent CONTENT pide contenido
  - Via API admin: POST /api/v1/content/generate
"""
import json
import re
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.state import GlobalHubState, Message, MessageRole
from app.core.database import AsyncSessionLocal
from app.core.llm_factory import get_llm
from app.core.audit import write_audit_log
from app.agents.content.tools import (
    get_content_config,
    save_content_draft,
    list_content_drafts,
    truncate_for_channel,
    CHANNELS,
)
from app.agents.content.image_generator import ImageGenerator
from app.agents.content.prompts import CONTENT_SYSTEM_PROMPT, CRITIC_SYSTEM_PROMPT

log = structlog.get_logger()

# Keywords para detectar canal en el mensaje
CHANNEL_KEYWORDS = {
    "instagram": "instagram",
    "facebook": "facebook",
    "whatsapp": "whatsapp_status",
    "estado": "whatsapp_status",
    "status": "whatsapp_status",
}

# Keywords para listar borradores
LIST_KEYWORDS = {"borradores", "contenido pendiente", "que tengo", "listar", "ver contenido"}


def _detect_channel(text: str) -> str:
    """Detecta el canal objetivo en el mensaje. Default: instagram."""
    text_lower = text.lower()
    for kw, channel in CHANNEL_KEYWORDS.items():
        if kw in text_lower:
            return channel
    return "instagram"


def _detect_topic(text: str) -> str:
    """Extrae el topico del mensaje (todo excepto palabras de canal/accion)."""
    stop_words = {
        "crea", "genera", "haz", "quiero", "necesito", "un", "una",
        "post", "para", "de", "en", "el", "la", "contenido",
        "instagram", "facebook", "whatsapp", "estado", "status",
    }
    words = [w for w in text.lower().split() if w not in stop_words]
    topic = " ".join(words).strip()
    return topic if topic else "salud dental general"


async def _research_topic(topic: str, channel: str, config: dict, llm) -> str:
    """
    Paso 1 CoT — Investigacion del topico.
    El LLM produce puntos clave sobre el tema para guiar la redaccion.
    """
    prompt = (
        f"Eres un experto en marketing odontologico. "
        f"Para el canal {channel}, investiga el topico: '{topic}'.\n"
        "Lista 3-5 puntos clave educativos o informativos relevantes para pacientes dentales. "
        "Se conciso, en espanol. Solo los puntos, sin introduccion."
    )
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return response.content.strip()


async def _draft_content(
    topic: str,
    channel: str,
    research: str,
    config: dict,
    llm,
) -> str:
    """
    Paso 2 CoT — Redaccion del contenido adaptado al canal.
    """
    edu_ratio = config.get("educational_ratio", 0.7)
    promo_ratio = config.get("promotional_ratio", 0.3)
    specialties = ", ".join(config.get("specialties_focus", ["ortodoncia", "implantes", "estetica"]))
    brand_colors = ", ".join(config.get("brand_colors", ["azul marino", "blanco"]))

    system = CONTENT_SYSTEM_PROMPT.format(
        educational_ratio=edu_ratio,
        promotional_ratio=promo_ratio,
        specialties_focus=specialties,
        brand_colors=brand_colors,
    )
    user_prompt = (
        f"Topico: {topic}\n"
        f"Canal: {channel}\n"
        f"Puntos clave investigados:\n{research}\n\n"
        "Redacta el contenido completo listo para publicar. "
        "Incluye emojis apropiados y hashtags si el canal lo requiere."
    )
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=user_prompt),
    ])
    return response.content.strip()


async def _critic_review(content: str, config: dict, llm) -> tuple[bool, str]:
    """
    Paso 3 CoT — Revision critica del contenido.
    Retorna (aprobado, razon).
    """
    promo_limit = config.get("promotional_limit", 0.4)
    system = CRITIC_SYSTEM_PROMPT.format(promotional_limit=promo_limit)
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=f"Contenido a revisar:\n\n{content}"),
    ])
    try:
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        result = json.loads(json_match.group()) if json_match else {}
        approved = bool(result.get("approved", False))
        reason = result.get("reason", "")
        return approved, reason
    except Exception:
        return True, "revision no disponible"


async def _generate_image_prompt(topic: str, channel: str, llm) -> str:
    """Genera un prompt en ingles para Stable Diffusion."""
    response = await llm.ainvoke([
        HumanMessage(content=(
            f"Generate a concise English image prompt (max 80 words) for Stable Diffusion. "
            f"Topic: dental clinic social media post about '{topic}' for {channel}. "
            "Style: professional, clean, bright dental office or smile. "
            "No text in image. Photorealistic. High quality."
        ))
    ])
    return response.content.strip()


async def content_agent_node(state: GlobalHubState) -> GlobalHubState:
    """
    Nodo del Agente de Contenido A4.
    """
    async with AsyncSessionLocal() as db:
        config = await get_content_config(db)
        llm = get_llm("content", db=None)

        user_messages = [m for m in state.messages if m.role == MessageRole.USER]
        last_text = user_messages[-1].content.strip() if user_messages else ""
        last_text_lower = last_text.lower()

        reply_text: str | None = None

        # ── Listar borradores ──────────────────────────────────────────
        if any(kw in last_text_lower for kw in LIST_KEYWORDS):
            drafts = await list_content_drafts(db)
            if drafts:
                lines = [f"Tienes {len(drafts)} borrador(es) pendiente(s):\n"]
                for d in drafts[:5]:
                    lines.append(f"#{d['id']} [{d['channel']}] {d['topic']} — {d['content_text'][:80]}...")
                reply_text = "\n".join(lines)
            else:
                reply_text = "No hay borradores pendientes de revision."

        # ── Generar contenido (flujo CoT) ──────────────────────────────
        else:
            channel = _detect_channel(last_text)
            topic = _detect_topic(last_text)

            reply_text = f"Generando contenido para {channel} sobre '{topic}'..."
            log.info("content.generating", channel=channel, topic=topic)

            try:
                # Paso 1: Investigacion
                research = await _research_topic(topic, channel, config, llm)
                log.debug("content.research_done", chars=len(research))

                # Paso 2: Redaccion
                draft_text = await _draft_content(topic, channel, research, config, llm)
                draft_text = truncate_for_channel(draft_text, channel)
                log.debug("content.draft_done", chars=len(draft_text))

                # Paso 3: Revision critica
                approved, reason = await _critic_review(draft_text, config, llm)
                if not approved:
                    # Reintentar con instruccion de correccion
                    correction_prompt = (
                        f"El siguiente contenido fue rechazado: {reason}\n\n"
                        f"Corrige el contenido manteniendo el topico '{topic}':\n\n{draft_text}"
                    )
                    retry = await llm.ainvoke([HumanMessage(content=correction_prompt)])
                    draft_text = truncate_for_channel(retry.content.strip(), channel)
                    log.info("content.draft_corrected", reason=reason)

                # Paso 4: Imagen (degradado si no hay GPU)
                image_path: str | None = None
                if ImageGenerator.is_available():
                    img_prompt = await _generate_image_prompt(topic, channel, llm)
                    image_path = ImageGenerator.generate(
                        prompt=img_prompt,
                        filename=f"{channel}_{topic[:20].replace(' ', '_')}",
                    )

                # Paso 5: Guardar borrador
                piece = await save_content_draft(
                    channel=channel,
                    content_text=draft_text,
                    topic=topic,
                    target_segment=state.retrieved_context or "general",
                    image_path=image_path,
                    db=db,
                )

                img_note = f" (con imagen)" if image_path else " (sin imagen, no hay GPU)"
                reply_text = (
                    f"Contenido generado y guardado como borrador #{piece.id}{img_note}.\n\n"
                    f"Vista previa:\n{draft_text[:300]}{'...' if len(draft_text) > 300 else ''}\n\n"
                    "Para aprobarlo ve al panel admin o pide: APROBAR #" + str(piece.id)
                )

                await write_audit_log(
                    db=db,
                    agent_name="content",
                    action="content_draft_created",
                    triggered_by="patient_message",
                    patient_id=state.patient_id,
                    detail={"channel": channel, "topic": topic, "content_id": piece.id, "approved_by_critic": approved},
                )

            except Exception as exc:
                log.error("content.generation_error", error=str(exc), exc_info=True)
                reply_text = (
                    "Hubo un error al generar el contenido. "
                    "Verifica que el LLM este activo e intenta de nuevo."
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
