"""
Pipeline de ingesta RAG.
Carga PDF/TXT desde knowledge_base/, genera embeddings con Ollama y almacena en pgvector.
"""
import structlog
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.core.llm_factory import get_embed_model
from app.models.knowledge_chunk import KnowledgeChunk

log = structlog.get_logger()

KNOWLEDGE_BASE_DIR = Path(__file__).parent / "knowledge_base"
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def _load_document(file_path: Path) -> list[Document]:
    """Carga un archivo y retorna Documents de LangChain."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        from langchain_community.document_loaders import PyPDFLoader
        return PyPDFLoader(str(file_path)).load()
    elif suffix in (".txt", ".md"):
        from langchain_community.document_loaders import TextLoader
        return TextLoader(str(file_path), encoding="utf-8").load()
    raise ValueError(f"Extensión no soportada: {suffix}")


def _split_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(docs)


async def ingest_document(file_path: Path, db: AsyncSession) -> int:
    """
    Ingesta un documento: carga → split → embed → guardar en pgvector.
    Reemplaza chunks previos del mismo archivo si ya existían.
    Retorna el número de chunks insertados.
    """
    source = file_path.name
    log.info("rag.ingest_start", source=source)

    # Eliminar chunks previos del mismo archivo
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source == source))

    # Cargar y dividir en chunks
    raw_docs = _load_document(file_path)
    chunks = _split_documents(raw_docs)

    if not chunks:
        log.warning("rag.no_chunks", source=source)
        return 0

    # Generar embeddings en batch
    embedder = get_embed_model()
    texts = [c.page_content for c in chunks]
    embeddings = await embedder.aembed_documents(texts)

    # Persistir en PostgreSQL + pgvector
    for text, embedding in zip(texts, embeddings):
        db.add(KnowledgeChunk(content=text, source=source, embedding=embedding))

    await db.flush()
    log.info("rag.ingest_done", source=source, chunks=len(chunks))
    return len(chunks)


async def ingest_all(db: AsyncSession) -> int:
    """Ingesta todos los documentos de knowledge_base/."""
    total = 0
    for file_path in sorted(KNOWLEDGE_BASE_DIR.iterdir()):
        if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            total += await ingest_document(file_path, db)
    return total
