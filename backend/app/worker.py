from datetime import timedelta

from app.db import SessionLocal, utcnow
from sqlalchemy import select
from app.models import OutboxEvent, EmailDelivery, EmailStatus, User
# 1. 从 reminders 只导入它里面有的函数
from app.services.reminders import claim_events, deliver_event, materialize_due

# 2. 另外单独写一行导入 EmailProvider
from app.services.email_provider import EmailProvider

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
    sent_emails_count = 0
    with session_factory.begin() as db:
        # 取 10 条待发送的邮件
        pending_emails = db.scalars(
            select(EmailDelivery).where(EmailDelivery.status == EmailStatus.pending).limit(10)).all()

        if pending_emails:
            provider = EmailProvider()
            for record in pending_emails:
                record.status = EmailStatus.accepted  # 标记为正在发送

                user = db.get(User, record.user_id)
                if user and user.email:
                    try:
                        success = provider.send(
                            to_email=user.email,
                            subject="赛事提醒",
                            content="您的赛事即将截止，请查看。"
                        )
                        if success:
                            record.status = EmailStatus.delivered
                            sent_emails_count += 1
                        else:
                            record.status = EmailStatus.failed
                            record.retry_count += 1
                    except Exception as e:
                        record.status = EmailStatus.failed
                        record.error_message = str(e)
                        record.retry_count += 1
                else:
                    record.status = EmailStatus.failed
                    record.error_message = "User email not found"
    return {
        "due_jobs": due_count,
        "claimed_events": len(ids),
        "recorded_notifications": completed,
        "sent_emails": sent_emails_count
    }


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
