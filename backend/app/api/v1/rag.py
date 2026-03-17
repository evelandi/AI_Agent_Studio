"""
Endpoints para gestión de la knowledge base del RAG.
Permite al admin cargar, listar y eliminar documentos indexados.
"""
import aiofiles
import structlog
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from app.api.deps import get_db, require_admin
from app.models.knowledge_chunk import KnowledgeChunk
from app.rag.ingestion import (
    KNOWLEDGE_BASE_DIR,
    SUPPORTED_EXTENSIONS,
    ingest_document,
    ingest_all,
)

log = structlog.get_logger()

router = APIRouter(prefix="/rag", tags=["knowledge-base"])


@router.get("/knowledge-base")
async def list_knowledge_base(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Lista todos los documentos indexados con su cantidad de chunks."""
    result = await db.execute(
        select(KnowledgeChunk.source, func.count(KnowledgeChunk.id).label("chunks"))
        .group_by(KnowledgeChunk.source)
        .order_by(KnowledgeChunk.source)
    )
    rows = result.fetchall()
    return [{"source": row.source, "chunks": row.chunks} for row in rows]


@router.post("/knowledge-base")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """
    Carga un documento PDF/TXT y lo ingesta en pgvector.
    Si el documento ya existía, se reindexan sus chunks.
    """
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo no soportado. Usar: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    # Guardar archivo en knowledge_base/
    dest_path = KNOWLEDGE_BASE_DIR / file.filename
    async with aiofiles.open(dest_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Ingestar
    try:
        chunks = await ingest_document(dest_path, db)
        await db.commit()
        log.info("rag.upload_success", file=file.filename, chunks=chunks)
        return {"file": file.filename, "chunks_indexed": chunks}
    except Exception as exc:
        dest_path.unlink(missing_ok=True)  # limpiar si falla
        raise HTTPException(status_code=500, detail=f"Error al ingestar: {exc}")


@router.post("/knowledge-base/ingest-all")
async def ingest_all_documents(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Re-ingesta todos los documentos de la carpeta knowledge_base/."""
    total = await ingest_all(db)
    await db.commit()
    return {"total_chunks_indexed": total}


@router.delete("/knowledge-base/{source}")
async def delete_document(
    source: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Elimina los chunks de un documento de la base vectorial."""
    result = await db.execute(
        delete(KnowledgeChunk).where(KnowledgeChunk.source == source)
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Documento '{source}' no encontrado")

    # Eliminar archivo físico si existe
    file_path = KNOWLEDGE_BASE_DIR / source
    file_path.unlink(missing_ok=True)

    return {"deleted": source, "chunks_removed": result.rowcount}
