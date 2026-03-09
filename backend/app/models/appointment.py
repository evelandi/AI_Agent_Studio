from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    google_event_id = Column(String(200))
    procedure_type = Column(String(100))
    duration_minutes = Column(Integer)
    scheduled_at = Column(DateTime(timezone=True))
    status = Column(String(30), default="scheduled")  # scheduled, confirmed, cancelled, completed
    created_by_agent = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="appointments")
