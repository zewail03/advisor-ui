from celery import Celery
from celery.schedules import crontab

from core.config import settings

celery_app = Celery(
    "academic_advisor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "tasks.waitlist_monitor",
        "tasks.alerts",
        "tasks.registration_reminders",
        "tasks.attendance_monitor",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "check-waitlist-every-5min": {
        "task": "tasks.waitlist_monitor.check_waitlist",
        "schedule": 300.0,
    },
    "run-daily-alerts": {
        "task": "tasks.alerts.run_daily_alerts",
        "schedule": crontab(hour=6, minute=0),
    },
    "registration-reminders": {
        "task": "tasks.registration_reminders.send_registration_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
    "weekly-attendance-audit": {
        "task": "tasks.attendance_monitor.audit_attendance",
        "schedule": crontab(hour=7, minute=0, day_of_week=1),
    },
}
