from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Competition, Notification, Profile, Subscription, User
from app.schemas import CompetitionOutput, ProfileInput, ProfileOutput, SubscriptionInput, UserOutput
from app.security import current_user
from app.services.recommendations import is_expired, recommend
from app.services.reminders import replan_subscription

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOutput)
def me(user: User = Depends(current_user)):
    return user


@router.get("/profile", response_model=ProfileOutput)
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.get(Profile, user.id)


@router.put("/profile", response_model=ProfileOutput)
def save_profile(payload: ProfileInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.get(Profile, user.id)
    for key, value in payload.model_dump(mode="json").items():
        setattr(profile, key, value)
    profile.version += 1
    db.commit()
    return profile


@router.get("/recommendations")
def recommendations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return recommend(db.get(Profile, user.id), db.scalars(select(Competition)).all())


@router.get("/subscriptions")
def subscriptions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Subscription).where(Subscription.user_id == user.id, Subscription.active.is_(True))).all()
    return [{"id": item.id, "lead_hours": item.lead_hours,
             "competition": CompetitionOutput.model_validate(db.get(Competition, item.competition_id)).model_dump(mode="json")}
            for item in items]


@router.post("/subscriptions")
def subscribe(payload: SubscriptionInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    competition = db.get(Competition, payload.competition_id)
    if competition is None or competition.review_status != "approved" or is_expired(competition):
        raise HTTPException(400, "赛事未发布或已截止")
    subscription = db.scalar(select(Subscription).where(
        Subscription.user_id == user.id, Subscription.competition_id == competition.id,
    ).with_for_update())
    changed = False
    if subscription is None:
        subscription = Subscription(user_id=user.id, competition_id=competition.id, lead_hours=payload.lead_hours)
        db.add(subscription)
        db.flush()
        changed = True
    elif not subscription.active or subscription.lead_hours != payload.lead_hours:
        subscription.active = True
        subscription.lead_hours = payload.lead_hours
        subscription.version += 1
        changed = True
    job = replan_subscription(db, subscription)
    if changed:
        db.add(Notification(
            user_id=user.id, competition_id=competition.id,
            dedup_key=f"subscription:{subscription.id}:v{subscription.version}", kind="subscription",
            title="订阅已保存", body=f"你已订阅《{competition.title}》。"
            + (f"已安排截止前{subscription.lead_hours}小时的站内提醒。" if job else "暂无可安排的未来精确提醒，请主动查看来源信息。"),
        ))
    db.commit()
    return {"id": subscription.id, "reminder_scheduled": job is not None, "channel": "in_app"}


@router.delete("/subscriptions/{subscription_id}")
def unsubscribe(subscription_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    subscription = db.scalar(select(Subscription).where(Subscription.id == subscription_id).with_for_update())
    if subscription is None or subscription.user_id != user.id:
        raise HTTPException(404, "订阅不存在")
    subscription.active = False
    subscription.version += 1
    replan_subscription(db, subscription)
    db.commit()
    return {"ok": True}


@router.get("/notifications")
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(100)).all()
    from app.db import utc
    return [{"id": item.id, "title": item.title, "body": item.body, "kind": item.kind,
             "channel": item.channel, "delivery_status": item.delivery_status,
             "read": item.read, "created_at": utc(item.created_at).isoformat()} for item in items]


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(Notification, notification_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(404, "通知不存在")
    item.read = True
    db.commit()
    return {"ok": True}
