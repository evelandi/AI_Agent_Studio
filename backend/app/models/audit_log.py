from sqlalchemy import Column, BigInteger, Integer, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, index=True)
    agent_name = Column(String(50))
    action = Column(String(100))
    patient_id = Column(Integer)
    detail = Column(JSONB)
    triggered_by = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
