from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date, datetime


class PatientBase(BaseModel):
    phone: str
    full_name: Optional[str] = None
    birth_date: Optional[date] = None
    email: Optional[str] = None
    segment: Optional[str] = None
    channel_pref: Optional[str] = "whatsapp"


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    full_name: Optional[str] = None
    birth_date: Optional[date] = None
    email: Optional[str] = None
    segment: Optional[str] = None
    channel_pref: Optional[str] = None


class PatientResponse(PatientBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
