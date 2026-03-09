from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AppointmentBase(BaseModel):
    patient_id: int
    procedure_type: str
    duration_minutes: int
    scheduled_at: datetime
    status: str = "scheduled"


class AppointmentCreate(AppointmentBase):
    google_event_id: Optional[str] = None
    created_by_agent: bool = False


class AppointmentUpdate(BaseModel):
    status: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    google_event_id: Optional[str] = None


class AppointmentResponse(AppointmentBase):
    id: int
    google_event_id: Optional[str]
    created_by_agent: bool
    created_at: datetime

    model_config = {"from_attributes": True}
