import httpx
import structlog
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from sqlalchemy import text

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1 import admin, patients, appointments, content, rag
from app.integrations.whatsapp.webhook import router as whatsapp_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Iniciando AI Assistant Hub", environment=settings.environment)

    # Inicializar grafo LangGraph (carga checkpointer PostgreSQL)
    from app.graph.hub_graph import setup_graph
    await setup_graph()

    # Inicializar scheduler de tareas proactivas
    from app.scheduler import start_scheduler
    start_scheduler()

    yield

    log.info("Apagando AI Assistant Hub")
    from app.graph.checkpointer import close_checkpointer
    from app.scheduler import stop_scheduler
    stop_scheduler()
    await close_checkpointer()


app = FastAPI(
    title="AI Assistant Hub Odontológico",
    description="Sistema multi-agente para gestión de consultorio odontológico",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────
app.include_router(whatsapp_router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(appointments.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")


# ── Endpoints base ────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check detallado: PostgreSQL, Ollama, LangGraph.
    """
    checks: dict = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
        "services": {},
    }

    # PostgreSQL
    try:
        from app.core.database import async_engine
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["services"]["postgres"] = "ok"
    except Exception as exc:
        checks["services"]["postgres"] = f"error: {exc}"
        checks["status"] = "degraded"

    # Ollama
    if settings.llm_provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            checks["services"]["ollama"] = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
        except Exception as exc:
            checks["services"]["ollama"] = f"error: {exc}"
            checks["status"] = "degraded"

    # LangGraph
    from app.graph.hub_graph import _compiled_graph
    checks["services"]["langgraph"] = "ok" if _compiled_graph is not None else "not_initialized"

    return checks


@app.get("/", tags=["root"])
async def root():
    return {
        "name": "AI Assistant Hub Odontológico",
        "version": "0.2.0",
        "docs": "/docs",
        "health": "/health",
    }
