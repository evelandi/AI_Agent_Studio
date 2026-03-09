"""
Pipeline de ingesta RAG: carga PDF/TXT, genera embeddings y almacena en pgvector.
Implementación completa: Fase 3
"""
from pathlib import Path

KNOWLEDGE_BASE_DIR = Path(__file__).parent / "knowledge_base"

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


async def ingest_document(file_path: Path, db) -> int:
    """
    Carga un documento, lo divide en chunks, genera embeddings
    con Ollama y los almacena en la tabla knowledge_chunks.

    Retorna el número de chunks ingresados.
    """
    # TODO: Fase 3 — implementar con LangChain loaders + text_splitter
    raise NotImplementedError("RAG ingestion: implementar en Fase 3")


async def ingest_all_knowledge_base(db) -> int:
    """
    Ingesta todos los documentos en la carpeta knowledge_base/.
    """
    total = 0
    for file_path in KNOWLEDGE_BASE_DIR.iterdir():
        if file_path.suffix in SUPPORTED_EXTENSIONS:
            total += await ingest_document(file_path, db)
    return total
