from celery import Celery
from app.core.config import settings
celery = Celery("ooi", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    task_track_started=True,
    timezone="UTC",
    beat_schedule={
        "foundation-heartbeat":{"task":"app.tasks.jobs.foundation_heartbeat","schedule":60.0},
        "database-config-dispatcher":{"task":"app.tasks.jobs.dispatch_due_collectors","schedule":60.0},
        "metric-event-consumer":{"task":"app.tasks.jobs.process_metric_events","schedule":5.0},
    },
)
celery.autodiscover_tasks(["app.tasks"])
