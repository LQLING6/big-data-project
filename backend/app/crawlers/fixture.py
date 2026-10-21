import json
from datetime import timedelta
from pathlib import Path

from app.db import utc


class FixtureAdapter:
    """Synthetic notices only; reads a bundled JSON file, never the Internet."""
    def __init__(self, anchor):
        self.anchor = utc(anchor).replace(hour=10, minute=0, second=0, microsecond=0)

    def collect(self) -> list[dict]:
        records = json.loads((Path(__file__).parents[1] / "fixtures" / "notices.json").read_text(encoding="utf-8"))
        result = []
        for record in records:
            deadline = self.anchor + timedelta(days=record["days"])
            precision = record["precision"]
            deadline_text = deadline.isoformat() if precision == "datetime" else deadline.date().isoformat() if precision == "date" else "未公布"
            result.append({
                "external_key": record["key"], "title": record["title"], "organizer": "赛知演示工作组（虚构）",
                "category": record["category"], "summary": record["summary"], "edition": str(self.anchor.year),
                "source_url": f"https://example.org/campuscomp-demo/{record['key']}",
                "tags": record["tags"], "skill_tags": record["skills"], "allowed_majors": record["majors"],
                "allowed_levels": record["levels"], "allowed_school": None, "grade_min": None, "grade_max": None,
                "deadline_at": deadline if precision == "datetime" else None,
                "deadline_date": deadline.date().isoformat() if precision == "date" else None,
                "deadline_precision": precision, "deadline_kind": "organizer", "event_date": None, "status": "open",
                "evidence": {
                    "deadline": {"quote": f"合成通知：报名截止 {deadline_text}", "origin": "bundled_fixture"},
                    "eligibility": {"quote": f"合成通知：培养层次 {','.join(record['levels'])}；专业 {','.join(record['majors']) or '不限'}", "origin": "bundled_fixture"},
                    "tags": {"quote": "平台演示分类标签，非官方资格判断", "origin": "editorial"},
                },
                "body": f"【合成演示数据】{record['title']}。{record['summary']} 报名截止：{deadline_text}。培养层次：{','.join(record['levels'])}。",
            })
        return result
