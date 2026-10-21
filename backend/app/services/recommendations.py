from datetime import datetime
from zoneinfo import ZoneInfo

from app.db import utc, utcnow
from app.models import Competition, Profile
from app.schemas import CompetitionOutput


def is_expired(competition: Competition, now: datetime | None = None) -> bool:
    now = now or utcnow()
    if competition.status != "open":
        return True
    if competition.deadline_precision == "datetime" and competition.deadline_at:
        return utc(competition.deadline_at) <= now
    if competition.deadline_precision == "date" and competition.deadline_date:
        return competition.deadline_date < now.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    return False


def overlap_score(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.5
    left_set = {item.strip().lower() for item in left}
    right_set = {item.strip().lower() for item in right}
    return len(left_set & right_set) / len(right_set)


def recommend(profile: Profile, competitions: list[Competition], now: datetime | None = None) -> dict:
    """Deterministic baseline. Never treats a matching score as eligibility proof."""
    now = now or utcnow()
    items, excluded = [], 0
    for competition in competitions:
        if competition.review_status != "approved" or is_expired(competition, now):
            excluded += 1
            continue
        unknown, conflicts = [], []
        for actual, allowed, label in [
            (profile.major, competition.allowed_majors, "专业"),
            (profile.level, competition.allowed_levels, "培养层次"),
            (profile.school, [competition.allowed_school] if competition.allowed_school else [], "学校"),
        ]:
            if allowed:
                if not actual:
                    unknown.append(f"{label}信息未填写")
                elif actual not in allowed:
                    conflicts.append(f"不满足{label}限制")
        if competition.grade_min is not None or competition.grade_max is not None:
            if profile.grade is None:
                unknown.append("年级信息未填写")
            elif ((competition.grade_min is not None and profile.grade < competition.grade_min)
                  or (competition.grade_max is not None and profile.grade > competition.grade_max)):
                conflicts.append("不满足年级限制")
        if conflicts:
            excluded += 1
            continue

        matched_skills = sorted(set(profile.skills) & set(competition.skill_tags))
        matched_interests = sorted(set(profile.interests) & set(competition.tags))
        warnings = list(unknown)
        if competition.event_date is None:
            warnings.append("比赛日程未明确，时间适配待确认")
            time_score = 0.5
        elif competition.event_date in profile.unavailable_dates:
            warnings.append("比赛日期与你的不可用日期冲突")
            time_score = 0.0
        else:
            time_score = 1.0
        if not competition.skill_tags or not profile.skills:
            warnings.append("技能匹配信息不完整")
        if competition.deadline_precision != "datetime":
            warnings.append("截止时间精度不足，不生成精确倒计时提醒")
        warnings.append("未提供官方工作量，不据此推测每周投入时长")

        dimensions = {
            "skills": overlap_score(profile.skills, competition.skill_tags),
            "interests": overlap_score(profile.interests, competition.tags),
            "major": 1.0 if competition.allowed_majors and profile.major in competition.allowed_majors else 0.5,
            "time": time_score,
        }
        score = round(100 * sum(dimensions[key] * weight for key, weight in
                                [("skills", 0.35), ("interests", 0.25), ("major", 0.20), ("time", 0.20)]))
        reasons = []
        if matched_skills:
            reasons.append({"code": "skill_match", "text": f"技能关联：{'、'.join(matched_skills)}", "evidence_field": "skill_tags"})
        if matched_interests:
            reasons.append({"code": "interest_match", "text": f"兴趣关联：{'、'.join(matched_interests)}", "evidence_field": "tags"})
        if not reasons:
            reasons.append({"code": "explore", "text": "暂无充分匹配依据，可进一步查看要求", "evidence_field": None})
        items.append({
            "competition": CompetitionOutput.model_validate(competition).model_dump(mode="json"),
            "score": score,
            "qualification": "待确认" if unknown else "未发现已知资格冲突",
            "reasons": reasons,
            "warnings": warnings,
            "dimensions": dimensions,
            "profile_version": profile.version,
            "competition_version": competition.version,
            "explanation_provider": "rules",
        })
    items.sort(key=lambda item: (item["qualification"] == "待确认", -item["score"], item["competition"]["id"]))
    return {"items": items, "excluded_count": excluded, "provider": "rules", "rule_version": "baseline-v1"}
