from sqlalchemy import Column, Integer, String, Date, DateTime, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    full_name = Column(String(200))
    birth_date = Column(Date)
    email = Column(String(200))
    segment = Column(String(50))          # cronic, inactive, new, high_value
    channel_pref = Column(String(20))     # whatsapp, email
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    appointments = relationship("Appointment", back_populates="patient")
    clinical_records = relationship("ClinicalRecord", back_populates="patient")
    consents = relationship("Consent", back_populates="patient")
