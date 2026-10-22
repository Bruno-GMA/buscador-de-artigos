from apscheduler.schedulers.background import BackgroundScheduler

from app.agent.agent import start_pipeline
from app.config import settings


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=settings.timezone)
    scheduler.add_job(
        start_pipeline,
        "cron",
        hour=settings.schedule_hour,
        minute=settings.schedule_minute,
        id="daily_report",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler

