"""
Checkpointer LangGraph sobre PostgreSQL.
Usa un AsyncConnectionPool (psycopg) que se mantiene abierto durante
toda la vida de la aplicación.
"""
import structlog
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings

log = structlog.get_logger()

# Pool y checkpointer se inicializan una sola vez en setup_checkpointer()
_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


def _get_psycopg_url() -> str:
    """Convierte DATABASE_URL de asyncpg a formato psycopg3."""
    url = settings.database_url
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("asyncpg://", "postgresql://")
    )


async def setup_checkpointer() -> AsyncPostgresSaver:
    """
    Inicializa el pool de conexiones y el checkpointer.
    Las tablas de LangGraph se crean automáticamente con setup().
    Llamar una sola vez en el lifespan de FastAPI.
    """
    global _pool, _checkpointer

    conn_string = _get_psycopg_url()
    _pool = AsyncConnectionPool(
        conninfo=conn_string,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,          # abrir manualmente abajo
    )
    await _pool.open()

    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()

    log.info("checkpointer.initialized")
    return _checkpointer


async def close_checkpointer() -> None:
    """Cierra el pool al apagar la aplicación."""
    global _pool
    if _pool:
        await _pool.close()
        log.info("checkpointer.closed")


def get_checkpointer() -> AsyncPostgresSaver:
    """Retorna el checkpointer ya inicializado."""
    if _checkpointer is None:
        raise RuntimeError("Checkpointer no inicializado. Llamar setup_checkpointer() primero.")
    return _checkpointer
