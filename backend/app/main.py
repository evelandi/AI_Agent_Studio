import os
import httpx
import structlog
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.v1 import admin, patients, appointments, content

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Iniciando AI Assistant Hub", environment=settings.environment)
    yield
    log.info("Apagando AI Assistant Hub")


app = FastAPI(
    title="AI Assistant Hub Odontológico",
    description="Sistema multi-agente para gestión de consultorio odontológico",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers de la API v1
app.include_router(admin.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(appointments.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check detallado del sistema.
    Verifica conectividad con PostgreSQL, Ollama y APIs externas.
    """
    checks: dict = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
        "services": {},
    }

    # Check PostgreSQL
    try:
        from app.core.database import async_engine
        async with async_engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy", fromlist=["text"]).text("SELECT 1")
            )
        checks["services"]["postgres"] = "ok"
    except Exception as e:
        checks["services"]["postgres"] = f"error: {e}"
        checks["status"] = "degraded"

    # Check Ollama
    if settings.llm_provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            checks["services"]["ollama"] = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
        except Exception as e:
            checks["services"]["ollama"] = f"error: {e}"
            checks["status"] = "degraded"

    return checks


@app.get("/", tags=["root"])
async def root():
    return {
        "name": "AI Assistant Hub Odontológico",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
