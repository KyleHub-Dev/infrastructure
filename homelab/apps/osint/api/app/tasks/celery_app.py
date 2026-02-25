"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "osint",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    # Task routing — each observable type goes to its dedicated queue
    task_routes={
        "workers.maigret.analyzer.analyze_username": {"queue": "queue_username"},
        "workers.holehe.analyzer.analyze_email": {"queue": "queue_email"},
        "workers.theharvester.analyzer.analyze_domain": {"queue": "queue_domain"},
        "workers.social-analyzer.analyzer.analyze_username": {"queue": "queue_username"},
    },
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Limits
    task_soft_time_limit=300,  # 5 min soft limit
    task_time_limit=600,  # 10 min hard limit (Maigret can be slow)
    # Scheduled tasks
    beat_schedule={
        "gdpr-ttl-purge": {
            "task": "app.tasks.analyzers.purge_expired_data",
            "schedule": crontab(hour=3, minute=0),  # Daily at 03:00 UTC
        },
    },
)
