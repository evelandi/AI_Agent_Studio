"""
Registro de tareas programadas con APScheduler.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scheduler.proactive_tasks import send_appointment_reminders

scheduler = AsyncIOScheduler(timezone="America/Bogota")


def setup_scheduler() -> AsyncIOScheduler:
    """
    Registra todas las tareas programadas y retorna el scheduler.
    Llamar en el lifespan de FastAPI antes de scheduler.start().
    """
    # Recordatorios diarios: 9:00 AM hora Colombia
    scheduler.add_job(
        send_appointment_reminders,
        trigger=CronTrigger(hour=9, minute=0, timezone="America/Bogota"),
        id="daily_appointment_reminders",
        replace_existing=True,
        misfire_grace_time=600,  # 10 min de gracia si el servidor estaba apagado
    )
    return scheduler
