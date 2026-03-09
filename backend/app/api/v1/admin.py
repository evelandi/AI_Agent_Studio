"""
Endpoints de administración de configuración de agentes.
Fase 7: implementación completa con JWT y RBAC.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, require_admin
from app.models.agent_config import AgentConfig

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/agents/{agent_name}/config")
async def get_agent_config(
    agent_name: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.agent_name == agent_name)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail=f"Config no encontrada para: {agent_name}")
    return {"agent_name": config.agent_name, "parameters": config.parameters}


@router.put("/agents/{agent_name}/config")
async def update_agent_config(
    agent_name: str,
    parameters: dict,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.agent_name == agent_name)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail=f"Config no encontrada para: {agent_name}")
    config.parameters = parameters
    await db.commit()
    return {"agent_name": agent_name, "parameters": config.parameters}


@router.get("/audit-logs")
async def get_audit_logs(
    agent: str | None = None,
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # TODO: implementar filtros por agente y rango de fechas (Fase 7)
    return {"message": "Audit logs - implementación completa en Fase 7"}
