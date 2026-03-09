from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import mapped_column
from pgvector.sqlalchemy import Vector
from app.models.base import Base


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    source = Column(String(200))
    embedding = mapped_column(Vector(768))  # nomic-embed-text dimension
    created_at = Column(DateTime(timezone=True), server_default=func.now())
