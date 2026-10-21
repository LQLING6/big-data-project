from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, utcnow
from app.models import AuditLog, Competition, Notice, OutboxEvent, ReminderJob, Source, User
from app.schemas import CompetitionOutput, DeadlineUpdate
from app.security import admin_user
from app.services.reminders import replan_competition

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_user)])


@router.get("/sources")
def sources(db: Session = Depends(get_db)):
    return [{"id": source.id, "name": source.name, "base_url": source.base_url, "is_demo": source.is_demo,
             "network_enabled": source.network_enabled, "policy_status": source.policy_status,
             "interval_seconds": source.interval_seconds} for source in db.scalars(select(Source)).all()]


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return {"sources": db.scalar(select(func.count()).select_from(Source)),
            "notices": db.scalar(select(func.count()).select_from(Notice)),
            "pending_reminders": db.scalar(select(func.count()).select_from(ReminderJob).where(ReminderJob.state.in_(["pending", "queued"]))),
            "failed_events": db.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.state == "failed")),
            "outbound_crawling": "disabled", "email": "not_implemented", "ai": "rules_only"}


@router.patch("/competitions/{competition_id}/deadline", response_model=CompetitionOutput)
def change_deadline(competition_id: int, payload: DeadlineUpdate,
                    user: User = Depends(admin_user), db: Session = Depends(get_db)):
    competition = db.scalar(select(Competition).where(Competition.id == competition_id).with_for_update())
    if competition is None:
        raise HTTPException(404, "赛事不存在")
    if not settings.demo_mode or not competition.is_demo:
        raise HTTPException(400, "此入口只用于合成数据演练；真实赛事须由经核验的通知版本更新")
    before = {"deadline_at": competition.deadline_at.isoformat() if competition.deadline_at else None,
              "deadline_date": competition.deadline_date, "precision": competition.deadline_precision}
    competition.deadline_at = payload.deadline_at
    competition.deadline_date = payload.deadline_date.isoformat() if payload.deadline_date else None
    competition.deadline_precision = payload.precision
    competition.version += 1
    competition.evidence = {**competition.evidence, "deadline": {
        "quote": f"管理员合成演练：{payload.reason}", "origin": "demo_admin_edit",
        "value": payload.model_dump(mode="json"),
    }}
    replan_competition(db, competition)
    db.add(AuditLog(actor_id=user.id, action="demo_deadline_changed", object_id=competition.id,
                    detail={"before": before, "after": payload.model_dump(mode="json")}))
    db.commit()
    return competition


@router.post("/run-cycle")
def run_cycle():
    from app.worker import run_inline_cycle
    return run_inline_cycle()


@router.post("/import-fixtures")
def import_fixtures():
    if not settings.demo_mode:
        raise HTTPException(400, "演示模式已关闭")
    from app.seed import seed_demo
    return seed_demo()


@router.post("/demo-trigger")
def trigger_demo(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    if not settings.demo_mode:
        raise HTTPException(400, "演示模式已关闭")
    # Only fixture-backed pending jobs; never changes a real deadline or calls email.
    from app.models import Subscription
    pending = db.scalars(select(ReminderJob).join(Subscription).join(Competition).where(
        ReminderJob.state == "pending", Competition.is_demo.is_(True),
    ).limit(1)).first()
    if pending is None:
        raise HTTPException(400, "请先用学生账号订阅一个截止时间精确的演示赛事")
    pending.due_at = utcnow()
    db.add(AuditLog(actor_id=user.id, action="demo_advance_clock", object_id=pending.id,
                    detail={"note": "仅提前处理合成数据的站内提醒"}))
    db.commit()
    from app.worker import run_inline_cycle
    return run_inline_cycle()
