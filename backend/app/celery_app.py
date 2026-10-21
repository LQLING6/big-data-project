from celery import Celery
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.db import SessionLocal
from app.services.reminders import deliver_event

celery_app = Celery("campuscomp", broker=settings.redis_url)
celery_app.conf.update(
    task_serializer="json", accept_content=["json"], task_ignore_result=True,
    task_acks_late=True, task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, timezone="Asia/Shanghai", enable_utc=True,
    task_soft_time_limit=45, task_time_limit=60,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 120},
    task_routes={"campuscomp.tick": {"queue": "control"}, "campuscomp.deliver": {"queue": "notify"}},
    beat_schedule={"scan-every-minute": {"task": "campuscomp.tick", "schedule": 60.0}},
)


@celery_app.task(name="campuscomp.tick", autoretry_for=(OperationalError,), retry_backoff=True, max_retries=3)
def tick():
    from app.worker import publish_cycle
    return publish_cycle()


@celery_app.task(name="campuscomp.deliver", autoretry_for=(OperationalError,), retry_backoff=True, max_retries=3)
def deliver(event_id: int):
    with SessionLocal.begin() as db:
        return deliver_event(db, event_id)
