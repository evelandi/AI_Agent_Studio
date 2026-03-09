"""
Gestión de contenido generado — Fase 6: implementación completa.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, require_admin
from app.models.content_piece import ContentPiece
from app.schemas.content import ContentPieceResponse

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/", response_model=list[ContentPieceResponse])
async def list_content(
    status: str | None = "draft",
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    query = select(ContentPiece)
    if status:
        query = query.where(ContentPiece.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.put("/{content_id}/approve")
async def approve_content(
    content_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    result = await db.execute(select(ContentPiece).where(ContentPiece.id == content_id))
    piece = result.scalar_one_or_none()
    if not piece:
        raise HTTPException(status_code=404, detail="Contenido no encontrado")
    piece.status = "approved"
    await db.commit()
    return {"id": content_id, "status": "approved"}
