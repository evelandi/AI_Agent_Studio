"""
Herramientas del Agente de Contenido A4.
"""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.content_piece import ContentPiece
from app.models.agent_config import AgentConfig

log = structlog.get_logger()

CHANNELS = ("instagram", "facebook", "whatsapp_status")
CHAR_LIMITS = {"instagram": 2200, "facebook": 5000, "whatsapp_status": 700}


async def get_content_config(db: AsyncSession) -> dict:
    """Carga la configuracion del agente de contenido desde agent_configs."""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.agent_name == "content")
    )
    config = result.scalar_one_or_none()
    if config:
        return config.parameters
    return {
        "educational_ratio": 0.7,
        "promotional_ratio": 0.3,
        "promotional_limit": 0.4,
        "specialties_focus": ["ortodoncia", "implantes", "estetica"],
        "brand_colors": ["azul marino", "blanco", "dorado"],
        "channels": ["instagram", "facebook", "whatsapp_status"],
    }


async def save_content_draft(
    channel: str,
    content_text: str,
    topic: str,
    target_segment: str,
    image_path: str | None,
    db: AsyncSession,
) -> ContentPiece:
    """Guarda un borrador de contenido en DB con status='draft'."""
    piece = ContentPiece(
        channel=channel,
        content_text=content_text,
        image_path=image_path,
        topic=topic,
        target_segment=target_segment,
        status="draft",
    )
    db.add(piece)
    await db.flush()
    log.info("content.draft_saved", channel=channel, topic=topic, id=piece.id)
    return piece


async def list_content_drafts(db: AsyncSession, status: str = "draft") -> list[dict]:
    """Lista los borradores de contenido pendientes de revision."""
    result = await db.execute(
        select(ContentPiece)
        .where(ContentPiece.status == status)
        .order_by(ContentPiece.created_at.desc())
        .limit(20)
    )
    pieces = result.scalars().all()
    return [
        {
            "id": p.id,
            "channel": p.channel,
            "topic": p.topic,
            "target_segment": p.target_segment,
            "content_text": p.content_text[:200] + "..." if len(p.content_text) > 200 else p.content_text,
            "image_path": p.image_path,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in pieces
    ]


async def approve_content(content_id: int, db: AsyncSession) -> bool:
    """Marca un borrador como aprobado."""
    result = await db.execute(
        select(ContentPiece).where(ContentPiece.id == content_id)
    )
    piece = result.scalar_one_or_none()
    if not piece:
        return False
    piece.status = "approved"
    await db.flush()
    log.info("content.approved", content_id=content_id)
    return True


def truncate_for_channel(text: str, channel: str) -> str:
    """Trunca el texto al limite del canal si es necesario."""
    limit = CHAR_LIMITS.get(channel, 2200)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text
