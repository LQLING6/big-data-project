from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceRef(BaseModel):
    """Evidence supporting one normalized fact."""

    model_config = ConfigDict(extra="forbid")

    quote: str = Field(min_length=1, max_length=1000)
    source_url: str
    captured_at: datetime
    origin: Literal["source_page", "source_api", "synthetic", "editorial"]
    version: str | None = Field(default=None, max_length=80)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        return _validate_https_url(value)

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("证据采集时间必须包含时区")
        return value


class DeadlineInput(BaseModel):
    """One deadline item; precision and values cannot contradict each other."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["school_selection", "organizer_registration", "competition_schedule"]
    precision: Literal["datetime", "date", "unknown"]
    at: datetime | None = None
    on_date: date | None = None
    evidence: EvidenceRef

    @field_validator("at")
    @classmethod
    def validate_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("精确截止时间必须包含时区")
        return value

    @model_validator(mode="after")
    def validate_precision(self) -> "DeadlineInput":
        if self.precision == "datetime":
            if self.at is None or self.on_date is not None:
                raise ValueError("datetime 精度必须且只能提供 at")
        elif self.precision == "date":
            if self.on_date is None or self.at is not None:
                raise ValueError("date 精度必须且只能提供 on_date")
        elif self.at is not None or self.on_date is not None:
            raise ValueError("unknown 精度不能附带推测日期")
        return self


class NormalizedNotice(BaseModel):
    """Source-neutral notice input shared with B's ingestion and D's evaluation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["c02-v1"] = "c02-v1"
    sample_type: Literal["synthetic", "real"]
    source_id: str = Field(min_length=1, max_length=80)
    external_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    organizer: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=40)
    summary: str = Field(min_length=1, max_length=4000)
    edition: str = Field(min_length=1, max_length=30)
    track: str = Field(min_length=1, max_length=80)
    source_url: str
    school_scope: str | None = Field(default=None, max_length=100)
    allowed_levels: list[str] = Field(default_factory=list, max_length=20)
    allowed_majors: list[str] = Field(default_factory=list, max_length=50)
    grade_min: int | None = Field(default=None, ge=1, le=8)
    grade_max: int | None = Field(default=None, ge=1, le=8)
    deadlines: list[DeadlineInput] = Field(min_length=1, max_length=10)
    entry_url: str | None = None
    event_date: date | None = None
    tags: list[str] = Field(default_factory=list, max_length=30)
    skill_tags: list[str] = Field(default_factory=list, max_length=30)
    field_evidence: dict[str, EvidenceRef] = Field(min_length=1)
    body: str = Field(min_length=1, max_length=50000)
    notice_version: int = Field(default=1, ge=1)
    parser_version: str = Field(min_length=1, max_length=80)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        return _validate_https_url(value)

    @field_validator("entry_url")
    @classmethod
    def validate_entry_url(cls, value: str | None) -> str | None:
        return _validate_https_url(value) if value else None

    @field_validator("allowed_levels", "allowed_majors", "tags", "skill_tags")
    @classmethod
    def clean_string_lists(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if any(len(value) > 80 for value in cleaned):
            raise ValueError("列表项不能超过80个字符")
        return list(dict.fromkeys(cleaned))

    @model_validator(mode="after")
    def validate_grade_range(self) -> "NormalizedNotice":
        if self.grade_min is not None and self.grade_max is not None and self.grade_min > self.grade_max:
            raise ValueError("grade_min 不能大于 grade_max")
        return self


class SampleEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case: str = Field(min_length=1, max_length=80)
    notice: NormalizedNotice


def _validate_https_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("URL不能为空")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("只允许无账号信息的HTTPS地址")
    if parts.username or parts.password:
        raise ValueError("URL不能包含账号或密码")
    if parts.port not in (None, 443):
        raise ValueError("HTTPS地址只能使用443端口")
    return value


def load_source_samples(path: Path | None = None) -> list[SampleEnvelope]:
    sample_path = path or Path(__file__).parents[1] / "fixtures" / "source_samples.json"
    raw = json.loads(sample_path.read_text(encoding="utf-8"))
    return [SampleEnvelope.model_validate(item) for item in raw]
