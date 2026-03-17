"""
Retriever RAG con búsqueda por similitud coseno en pgvector.
"""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.llm_factory import get_embed_model

log = structlog.get_logger()


async def retrieve(query: str, db: AsyncSession, top_k: int = 5) -> list[dict]:
    """
    Genera embedding del query y busca los top-k chunks más similares
    usando similitud coseno en pgvector (operador <=>).

    Retorna lista de {"content": str, "source": str, "score": float}
    """
    embedder = get_embed_model()
    query_embedding = await embedder.aembed_query(query)

    # pgvector cosine distance: (1 - cosine_similarity) → menor = más similar
    sql = text("""
        SELECT content, source, 1 - (embedding <=> CAST(:embedding AS vector)) AS score
        FROM knowledge_chunks
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
    """)

    result = await db.execute(
        sql,
        {"embedding": str(query_embedding), "top_k": top_k},
    )
    rows = result.fetchall()

    log.debug("rag.retrieved", query=query[:50], results=len(rows))
    return [
        {"content": row.content, "source": row.source, "score": float(row.score)}
        for row in rows
    ]


def format_context(chunks: list[dict]) -> str:
    """Formatea los chunks recuperados como contexto para el LLM."""
    if not chunks:
        return "No se encontró información relevante en la base de conocimiento."
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(f"[{i}] {chunk['content']}")
    return "\n\n".join(parts)
