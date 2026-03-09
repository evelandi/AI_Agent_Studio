from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ContentPieceBase(BaseModel):
    channel: str                          # instagram, facebook, whatsapp_status
    content_text: str
    topic: str
    target_segment: Optional[str] = None
    image_path: Optional[str] = None


class ContentPieceCreate(ContentPieceBase):
    pass


class ContentPieceUpdate(BaseModel):
    status: Optional[str] = None          # draft, approved, published
    content_text: Optional[str] = None


class ContentPieceResponse(ContentPieceBase):
    id: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
