from sqlalchemy import select

from app.config import settings
from app.crawlers.fixture import FixtureAdapter
from app.db import SessionLocal
from app.models import Profile, Source, User
from app.security import hash_password
from app.services.ingestion import ingest_notice

DEMO_CREDENTIALS = {
    "student": "CampusComp-demo-2026!",
    "admin": "CampusComp-admin-2026!",
}


def seed_demo(session_factory=SessionLocal) -> dict:
    if not settings.demo_mode:
        raise RuntimeError("DEMO_MODE=false：禁止创建演示账号与数据")
    with session_factory.begin() as db:
        for username, password in DEMO_CREDENTIALS.items():
            if db.scalar(select(User).where(User.username == username)) is None:
                user = User(username=username, password_hash=hash_password(password), role="admin" if username == "admin" else "student")
                db.add(user)
                db.flush()
                db.add(Profile(user_id=user.id, major="计算机科学与技术", school="演示大学", level="本科", grade=2,
                               skills=["python", "sql"], interests=["数据分析", "人工智能"], weekly_hours=6,
                               unavailable_dates=[]))
        source = db.scalar(select(Source).where(Source.base_url == "https://example.org/campuscomp-demo/"))
        if source is None:
            source = Source(name="离线合成通知（非官方来源）", base_url="https://example.org/campuscomp-demo/",
                            is_demo=True, network_enabled=False, policy_status="fixture_only")
            db.add(source)
            db.flush()
        changed = 0
        # Anchor survives restarts, so an import does not silently move deadlines every day.
        for payload in FixtureAdapter(source.created_at).collect():
            _, updated = ingest_notice(db, source, payload, approve_demo=True)
            changed += int(updated)
    return {"imported_or_updated": changed, "dataset": "synthetic_only", "network_requests": 0}
