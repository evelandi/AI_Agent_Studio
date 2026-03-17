"""
Scheduler de tareas proactivas — APScheduler.
"""
import structlog
from app.scheduler.jobs import scheduler, setup_scheduler

log = structlog.get_logger()


def start_scheduler() -> None:
    """Configura y arranca el scheduler. Llamar desde el lifespan de FastAPI."""
    setup_scheduler()
    scheduler.start()
    log.info("scheduler.started", jobs=len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Detiene el scheduler. Llamar en el shutdown del lifespan."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("scheduler.stopped")
