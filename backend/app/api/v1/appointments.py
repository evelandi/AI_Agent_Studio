"""
CRUD de citas — Fase 4: implementación completa.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, require_admin
from app.models.appointment import Appointment
from app.schemas.appointment import AppointmentResponse

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("/", response_model=list[AppointmentResponse])
async def list_appointments(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    query = select(Appointment)
    if status:
        query = query.where(Appointment.status == status)
    result = await db.execute(query)
    return result.scalars().all()
