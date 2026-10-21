import hashlib
import json
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import AuditLog, Competition, Notice, NoticeVersion, Source
from app.services.reminders import replan_competition


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("来源URL必须是无账号信息的HTTPS地址")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))


def ingest_notice(db: Session, source: Source, payload: dict, *, approve_demo: bool = False) -> tuple[Competition, bool]:
    """Fixture-backed importer. A real adapter must supply reviewed, typed facts first."""
    if not source.is_demo:
        raise ValueError("真实来源导入尚未接入：先完成来源准入、字段校验与人工核验流程")
    url = canonical_url(payload["source_url"])
    if urlsplit(url).hostname != urlsplit(source.base_url).hostname:
        raise ValueError("通知不属于配置的来源域名")
    payload = {**payload, "source_url": url}
    # Hash structured facts as well as body; URL fragment changes do not create versions.
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    notice = db.scalar(select(Notice).where(Notice.source_id == source.id, Notice.canonical_url == url))
    competition = db.scalar(select(Competition).where(
        Competition.source_id == source.id, Competition.external_key == payload["external_key"],
    ))
    if notice and notice.current_hash == digest and competition:
        return competition, False
    if notice is None:
        notice = Notice(source_id=source.id, canonical_url=url, title=payload["title"], current_hash=digest)
        db.add(notice)
        db.flush()
    notice.current_hash = digest
    notice.title = payload["title"]
    notice.fetched_at = utcnow()
    version = db.scalar(select(NoticeVersion).where(NoticeVersion.notice_id == notice.id, NoticeVersion.body_hash == digest))
    if version is None:
        version = NoticeVersion(notice_id=notice.id, body_hash=digest, body=payload["body"])
        db.add(version)
        db.flush()
    values = {key: value for key, value in payload.items() if key not in {"body", "external_key"}}
    values.update(notice_version_id=version.id, is_demo=True, review_status="approved" if approve_demo else "pending")
    if competition is None:
        competition = Competition(source_id=source.id, external_key=payload["external_key"], **values)
        db.add(competition)
        db.flush()
    else:
        for key, value in values.items():
            setattr(competition, key, value)
        competition.version += 1
        replan_competition(db, competition)
    db.add(AuditLog(action="fixture_ingested", object_id=competition.id, detail={"notice_version_id": version.id}))
    return competition, True
