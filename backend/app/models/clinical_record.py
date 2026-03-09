from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class ClinicalRecord(Base):
    __tablename__ = "clinical_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    procedure_type = Column(String(100))
    notes = Column(Text)                  # PHI — cifrado AES-256 en Fase 7
    next_visit_due = Column(Date)
    created_by = Column(String(100))
    deleted_at = Column(DateTime(timezone=True))  # borrado lógico
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="clinical_records")
