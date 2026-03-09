from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.models.base import Base


class ContentPiece(Base):
    __tablename__ = "content_pieces"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String(30))          # instagram, facebook, whatsapp_status
    content_text = Column(Text)
    image_path = Column(String(500))
    topic = Column(String(200))
    target_segment = Column(String(50))
    status = Column(String(20), default="draft")  # draft, approved, published
    created_at = Column(DateTime(timezone=True), server_default=func.now())
