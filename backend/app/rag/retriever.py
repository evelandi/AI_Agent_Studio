"""
Retriever RAG con búsqueda por similitud coseno en pgvector.
Implementación completa: Fase 3
"""


async def retrieve(query: str, top_k: int = 5, db=None) -> list[dict]:
    """
    Genera embedding del query y busca los top-k chunks más similares
    usando similitud coseno en pgvector.

    Retorna lista de {"content": str, "source": str, "score": float}
    """
    # TODO: Fase 3
    raise NotImplementedError("RAG retriever: implementar en Fase 3")
