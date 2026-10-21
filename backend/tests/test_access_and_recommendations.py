from datetime import timedelta

from sqlalchemy import select

from app.db import utcnow
from app.models import Competition
from app.services.ai import validate_reason_codes


def test_public_catalog_and_private_profile(client):
    assert len(client.get("/api/v1/competitions").json()) == 6
    assert client.get("/api/v1/me/profile").status_code == 401


def test_student_cannot_use_admin_api(client, student_headers):
    assert client.get("/api/v1/admin/sources", headers=student_headers).status_code == 403
    assert client.post("/api/v1/admin/import-fixtures", headers=student_headers).status_code == 403


def test_logout_revokes_token(client, student_headers):
    assert client.post("/api/v1/auth/logout", headers=student_headers).status_code == 200
    assert client.get("/api/v1/me", headers=student_headers).status_code == 401


def test_recommendations_enforce_level_and_report_uncertainty(client, student_headers):
    result = client.get("/api/v1/me/recommendations", headers=student_headers).json()
    assert result["provider"] == "rules"
    assert all("研究生" not in item["competition"]["title"] for item in result["items"])
    assert result["items"][0]["competition"]["title"] == "校园数据洞察挑战赛"
    assert all(any("日程未明确" in warning for warning in item["warnings"]) for item in result["items"])


def test_missing_major_is_not_claimed_eligible(client, student_headers):
    profile = client.get("/api/v1/me/profile", headers=student_headers).json()
    profile["major"] = ""
    assert client.put("/api/v1/me/profile", headers=student_headers, json=profile).status_code == 200
    items = client.get("/api/v1/me/recommendations", headers=student_headers).json()["items"]
    software = next(item for item in items if item["competition"]["category"] == "软件开发")
    assert software["qualification"] == "待确认"


def test_expired_competition_is_not_recommended(client, student_headers, session_factory):
    with session_factory.begin() as db:
        competition = db.scalar(select(Competition).where(Competition.external_key == "data-lab"))
        competition.deadline_at = utcnow() - timedelta(minutes=1)
        expired_id = competition.id
    assert all(item["competition"]["id"] != expired_id for item in client.get(
        "/api/v1/me/recommendations", headers=student_headers).json()["items"])
    assert client.post("/api/v1/me/subscriptions", headers=student_headers,
                       json={"competition_id": expired_id}).status_code == 400


def test_profile_does_not_allow_role_escalation(client, student_headers):
    profile = client.get("/api/v1/me/profile", headers=student_headers).json()
    profile["role"] = "admin"
    client.put("/api/v1/me/profile", headers=student_headers, json=profile)
    assert client.get("/api/v1/admin/status", headers=student_headers).status_code == 403


def test_ai_unknown_reason_fails_validation():
    import pytest
    with pytest.raises(ValueError):
        validate_reason_codes(["guaranteed_win"], [{"code": "skill_match", "text": "技能关联"}])
