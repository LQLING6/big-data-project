from datetime import timedelta

from app.db import SessionLocal, utcnow
from app.models import OutboxEvent
from app.services.reminders import claim_events, deliver_event, materialize_due


def run_inline_cycle(session_factory=SessionLocal) -> dict:
    """Single-process SQLite mode. No broker required; durable events still used."""
    with session_factory.begin() as db:
        due_count = materialize_due(db)
    with session_factory.begin() as db:
        ids = claim_events(db)
    completed = 0
    for event_id in ids:
        with session_factory.begin() as db:
            completed += int(deliver_event(db, event_id) == "recorded")
    return {"due_jobs": due_count, "claimed_events": len(ids), "recorded_notifications": completed}


def publish_cycle() -> dict:
    """PostgreSQL + Redis mode: expired queued leases are retried as well."""
    from app.celery_app import celery_app
    with SessionLocal.begin() as db:
        due_count = materialize_due(db)
    with SessionLocal.begin() as db:
        ids = claim_events(db)
    published = 0
    for event_id in ids:
        try:
            celery_app.send_task("campuscomp.deliver", args=[event_id], queue="notify")
            published += 1
        except Exception as error:
            # Durable row remains available if the broker rejects / loses publication.
            with SessionLocal.begin() as db:
                event = db.get(OutboxEvent, event_id)
                if event.state != "done":
                    event.state = "pending"
                    event.last_error = type(error).__name__  # Avoid leaking credentials from URLs.
                    event.next_attempt_at = utcnow() + timedelta(seconds=30)
    return {"due_jobs": due_count, "published_events": published}
