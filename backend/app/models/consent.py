from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class Consent(Base):
    __tablename__ = "consents"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    consent_type = Column(String(50))     # data_treatment, clinical_procedure
    document_hash = Column(String(64))   # SHA-256
    signed_at = Column(DateTime(timezone=True))
    ip_or_channel = Column(String(100))  # e.g. 'whatsapp:+57...'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="consents")
