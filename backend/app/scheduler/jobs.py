"""
Definición de tareas programadas con APScheduler.
Implementación completa: Fase 4
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


def setup_scheduler() -> AsyncIOScheduler:
    """
    Registra todas las tareas programadas y retorna el scheduler.
    Llamar en el lifespan de FastAPI.
    """
    # TODO: Fase 4 — registrar tarea proactiva diaria de recordatorios
    # scheduler.add_job(
    #     proactive_appointment_reminders,
    #     "cron",
    #     hour=9,
    #     minute=0,
    #     id="proactive_reminders",
    #     replace_existing=True,
    # )
    return scheduler
