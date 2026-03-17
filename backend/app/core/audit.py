"""
Utilidad de audit log.
Registra automáticamente las acciones de agentes en la tabla audit_logs.
"""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from app.models.audit_log import AuditLog

log = structlog.get_logger()


async def write_audit_log(
    db: AsyncSession,
    agent_name: str,
    action: str,
    triggered_by: str,
    patient_id: int | None = None,
    detail: dict | None = None,
) -> None:
    """
    Inserta un registro en audit_logs.
    No lanza excepción si falla (el audit log no debe bloquear el flujo principal).
    """
    try:
        await db.execute(
            insert(AuditLog).values(
                agent_name=agent_name,
                action=action,
                patient_id=patient_id,
                detail=detail or {},
                triggered_by=triggered_by,
            )
        )
        await db.flush()
        log.debug("audit_log.written", agent=agent_name, action=action)
    except Exception as exc:
        log.error("audit_log.write_failed", error=str(exc), agent=agent_name, action=action)
