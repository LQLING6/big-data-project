from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utc, utcnow
from app.models import Competition, Notification, OutboxEvent, ReminderJob, Subscription, User, EmailDelivery, EmailStatus

def replan_subscription(db: Session, subscription: Subscription, now: datetime | None = None) -> ReminderJob | None:
    now = now or utcnow()
    competition = db.get(Competition, subscription.competition_id)
    key = f"sub:{subscription.id}:s{subscription.version}:c{competition.version}:h{subscription.lead_hours}"
    jobs = db.scalars(select(ReminderJob).where(ReminderJob.subscription_id == subscription.id)).all()
    for job in jobs:
        if job.dedup_key != key and job.state in {"pending", "queued"}:
            job.state = "cancelled"
    if (not subscription.active or competition.status != "open" or competition.review_status != "approved"
            or competition.deadline_precision != "datetime" or competition.deadline_at is None):
        for job in jobs:
            if job.state in {"pending", "queued"}:
                job.state = "cancelled"
        return None
    due_at = utc(competition.deadline_at) - timedelta(hours=subscription.lead_hours)
    if due_at <= now:
        return None  # No retroactive reminders on subscription / deadline edits.
    existing = next((job for job in jobs if job.dedup_key == key), None)
    if existing:
        return existing
    job = ReminderJob(
        subscription_id=subscription.id,
        competition_version=competition.version,
        subscription_version=subscription.version,
        dedup_key=key,
        due_at=due_at,
    )
    db.add(job)
    db.flush()
    return job


def replan_competition(db: Session, competition: Competition, now: datetime | None = None):
    for subscription in db.scalars(select(Subscription).where(Subscription.competition_id == competition.id)).all():
        replan_subscription(db, subscription, now)
        if subscription.active:
            key = f"change:{subscription.id}:v{competition.version}"
            if db.scalar(select(Notification.id).where(Notification.dedup_key == key)) is None:
                db.add(Notification(
                    user_id=subscription.user_id, competition_id=competition.id,
                    dedup_key=key, kind="change", title="你订阅的赛事信息有更新",
                    body=f"《{competition.title}》已更新到版本{competition.version}，请重新查看截止时间和来源证据。",
                ))


def materialize_due(db: Session, now: datetime | None = None) -> int:
    """Create durable events in the same transaction as moving due jobs to queued."""
    now = now or utcnow()
    jobs = db.scalars(select(ReminderJob).where(
        ReminderJob.state == "pending", ReminderJob.due_at <= now,
    ).with_for_update(skip_locked=True)).all()
    for job in jobs:
        if db.scalar(select(OutboxEvent.id).where(OutboxEvent.reminder_id == job.id)) is None:
            db.add(OutboxEvent(reminder_id=job.id, next_attempt_at=now))
        job.state = "queued"
    db.flush()
    return len(jobs)


def claim_events(db: Session, now: datetime | None = None, limit: int = 100) -> list[int]:
    now = now or utcnow()
    events = db.scalars(select(OutboxEvent).where(
        OutboxEvent.state.in_(["pending", "queued"]), OutboxEvent.next_attempt_at <= now,
    ).order_by(OutboxEvent.id).limit(limit).with_for_update(skip_locked=True)).all()
    ids = []
    for event in events:
        if event.attempts >= 5:
            event.state = "failed"
            event.last_error = "超过5次投递/补偿尝试，需要人工检查"
            continue
        event.state = "queued"
        event.attempts += 1
        event.next_attempt_at = now + timedelta(minutes=5)
        ids.append(event.id)
    return ids


def deliver_event(db: Session, event_id: int, now: datetime | None = None) -> str:
    """Exactly one local record per key; external email is deliberately not called here."""
    now = now or utcnow()
    event = db.scalar(select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update())
    if event is None:
        return "missing"
    if event.state == "done":
        return "already_done"
    if event.state == "failed":
        return "failed"
    job = db.get(ReminderJob, event.reminder_id)
    subscription = db.scalar(select(Subscription).where(Subscription.id == job.subscription_id).with_for_update())
    competition = db.scalar(select(Competition).where(Competition.id == subscription.competition_id).with_for_update())
    if (job.state == "cancelled" or not subscription.active or competition.status != "open"
            or competition.review_status != "approved" or competition.deadline_precision != "datetime"
            or competition.deadline_at is None or job.competition_version != competition.version
            or job.subscription_version != subscription.version):
        job.state = "cancelled"
        event.state = "done"
        return "cancelled"
    if utc(job.due_at) > now:
        event.state = "pending"
        event.next_attempt_at = utc(job.due_at)
        return "not_due"
    expired = utc(competition.deadline_at) <= now
    key = f"reminder:{job.id}:in_app"
    if db.scalar(select(Notification.id).where(Notification.dedup_key == key)) is None:
        db.add(Notification(
            user_id=subscription.user_id, competition_id=competition.id, dedup_key=key,
            kind="expired" if expired else "deadline",
            title="赛事已截止，请核对报名状态" if expired else "你订阅的赛事即将截止",
            body=f"《{competition.title}》截止时间：{utc(competition.deadline_at).isoformat()}。请查看详情与来源证据。",
        ))
        user = db.get(User, subscription.user_id)
        if user and user.email and user.email_verified and user.email_opt_in:
            # 构造稳定业务幂等键 (这里用 job.id 和 version 来做唯一标识)
            idempotency_key = f"email_{user.id}_{job.id}_{competition.version}"

            # 查重防止重复插入
            existing = db.scalar(select(EmailDelivery).where(EmailDelivery.idempotency_key == idempotency_key))
            if not existing:
                email_record = EmailDelivery(
                    user_id=user.id,
                    idempotency_key=idempotency_key,
                    status=EmailStatus.pending
                )
                db.add(email_record)
    job.state = "sent"
    event.state = "done"
    event.last_error = None
    return "recorded"
