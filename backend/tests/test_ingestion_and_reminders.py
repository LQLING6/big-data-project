from datetime import timedelta

from sqlalchemy import func, select

from app.crawlers.fixture import FixtureAdapter
from app.db import utc, utcnow
from app.models import Competition, Notification, OutboxEvent, ReminderJob, Source, Subscription
from app.services.ingestion import ingest_notice
from app.services.reminders import claim_events, deliver_event, materialize_due


def subscribe_first(client, headers):
    competition = next(item for item in client.get("/api/v1/competitions").json() if item["deadline_precision"] == "datetime")
    result = client.post("/api/v1/me/subscriptions", headers=headers, json={"competition_id": competition["id"]})
    assert result.status_code == 200
    return competition, result.json()


def due_event(factory):
    with factory.begin() as db:
        job = db.scalar(select(ReminderJob))
        job.due_at = utcnow() - timedelta(seconds=1)
        materialize_due(db)
        db.flush()
        return db.scalar(select(OutboxEvent.id))


def test_fixture_import_is_idempotent(session_factory):
    with session_factory.begin() as db:
        source = db.scalar(select(Source))
        payload = FixtureAdapter(source.created_at).collect()[0]
        competition, changed = ingest_notice(db, source, payload, approve_demo=True)
        assert not changed
        assert competition.version == 1
        payload["source_url"] += "#signup"
        _, changed = ingest_notice(db, source, payload, approve_demo=True)
        assert not changed
        assert db.scalar(select(func.count()).select_from(Competition)) == 6


def test_repeat_subscribe_does_not_create_duplicates(client, student_headers, session_factory):
    competition, _ = subscribe_first(client, student_headers)
    client.post("/api/v1/me/subscriptions", headers=student_headers, json={"competition_id": competition["id"]})
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Subscription)) == 1
        assert db.scalar(select(func.count()).select_from(ReminderJob)) == 1


def test_date_only_never_creates_precise_job(client, student_headers, session_factory):
    item = next(item for item in client.get("/api/v1/competitions").json() if item["deadline_precision"] == "date")
    result = client.post("/api/v1/me/subscriptions", headers=student_headers, json={"competition_id": item["id"]})
    assert not result.json()["reminder_scheduled"]
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ReminderJob)) == 0


def test_duplicate_delivery_records_one_notification(client, student_headers, session_factory):
    subscribe_first(client, student_headers)
    event_id = due_event(session_factory)
    with session_factory.begin() as db:
        assert deliver_event(db, event_id) == "recorded"
    with session_factory.begin() as db:
        assert deliver_event(db, event_id) == "already_done"
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.kind == "deadline")) == 1


def test_unsubscribe_cancels_already_queued_event(client, student_headers, session_factory):
    _, result = subscribe_first(client, student_headers)
    event_id = due_event(session_factory)
    client.delete(f"/api/v1/me/subscriptions/{result['id']}", headers=student_headers)
    with session_factory.begin() as db:
        assert deliver_event(db, event_id) == "cancelled"
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.kind == "deadline")) == 0


def test_deadline_change_cancels_old_job_and_rebuilds(client, student_headers, admin_headers, session_factory):
    competition, _ = subscribe_first(client, student_headers)
    old_event = due_event(session_factory)
    result = client.patch(f"/api/v1/admin/competitions/{competition['id']}/deadline", headers=admin_headers, json={
        "precision": "datetime", "deadline_at": (utcnow() + timedelta(days=20)).isoformat(), "reason": "合成演练：主办方延期通知已核对",
    })
    assert result.status_code == 200
    with session_factory.begin() as db:
        assert deliver_event(db, old_event) == "cancelled"
        jobs = db.scalars(select(ReminderJob).order_by(ReminderJob.id)).all()
        assert len(jobs) == 2
        assert jobs[0].state == "cancelled"
        assert jobs[1].state == "pending"
        assert jobs[1].competition_version == 2


def test_naive_deadline_is_rejected(client, admin_headers):
    result = client.patch("/api/v1/admin/competitions/1/deadline", headers=admin_headers, json={
        "precision": "datetime", "deadline_at": "2027-01-01T18:00:00", "reason": "这个时间缺少时区信息",
    })
    assert result.status_code == 422


def test_other_user_cannot_delete_subscription_or_read_notice(client, student_headers, admin_headers):
    _, result = subscribe_first(client, student_headers)
    assert client.delete(f"/api/v1/me/subscriptions/{result['id']}", headers=admin_headers).status_code == 404
    note = client.get("/api/v1/me/notifications", headers=student_headers).json()[0]
    assert client.post(f"/api/v1/me/notifications/{note['id']}/read", headers=admin_headers).status_code == 404


def test_outbox_recovers_lost_queued_message(client, student_headers, session_factory):
    subscribe_first(client, student_headers)
    event_id = due_event(session_factory)
    now = utcnow()
    with session_factory.begin() as db:
        assert claim_events(db, now) == [event_id]
    with session_factory.begin() as db:
        assert claim_events(db, now + timedelta(minutes=1)) == []
        assert claim_events(db, now + timedelta(minutes=6)) == [event_id]


def test_late_recovery_says_expired_not_upcoming(client, student_headers, session_factory):
    subscribe_first(client, student_headers)
    event_id = due_event(session_factory)
    with session_factory.begin() as db:
        competition = db.scalar(select(Competition).where(Competition.external_key == "data-lab"))
        late_time = utc(competition.deadline_at) + timedelta(minutes=1)
        deliver_event(db, event_id, late_time)
        db.flush()
        note = db.scalar(select(Notification).where(Notification.kind == "expired"))
        assert "已截止" in note.title


def test_rolled_back_transaction_leaves_no_outbox(client, student_headers, session_factory):
    subscribe_first(client, student_headers)
    with session_factory() as db:
        job = db.scalar(select(ReminderJob))
        job.due_at = utcnow() - timedelta(seconds=1)
        materialize_due(db)
        db.rollback()
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(OutboxEvent)) == 0
        assert db.scalar(select(ReminderJob)).state == "pending"
