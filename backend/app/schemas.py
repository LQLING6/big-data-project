from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db import utc


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="before")
    @classmethod
    def aware_datetimes(cls, value):
        return utc(value) if isinstance(value, datetime) else value


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=128)


class UserOutput(ApiModel):
    id: int
    username: str
    role: str


class ProfileInput(BaseModel):
    major: str = Field(default="", max_length=100)
    school: str = Field(default="", max_length=100)
    level: Literal["本科", "专科", "硕士", "博士"] = "本科"
    grade: int | None = Field(default=None, ge=1, le=8)
    skills: list[str] = Field(default_factory=list, max_length=30)
    interests: list[str] = Field(default_factory=list, max_length=30)
    weekly_hours: float | None = Field(default=None, ge=0, le=100)
    unavailable_dates: list[date] = Field(default_factory=list, max_length=366)

    @field_validator("skills", "interests")
    @classmethod
    def clean_tags(cls, tags):
        if any(len(tag) > 40 for tag in tags):
            raise ValueError("单个标签不能超过40个字符")
        return list(dict.fromkeys(tag.strip().lower() for tag in tags if tag.strip()))


class ProfileOutput(ApiModel):
    major: str
    school: str
    level: str
    grade: int | None
    skills: list[str]
    interests: list[str]
    weekly_hours: float | None
    unavailable_dates: list[str]
    version: int


class CompetitionOutput(ApiModel):
    id: int
    title: str
    organizer: str
    category: str
    summary: str
    edition: str
    tags: list[str]
    skill_tags: list[str]
    allowed_majors: list[str]
    allowed_levels: list[str]
    allowed_school: str | None
    grade_min: int | None
    grade_max: int | None
    deadline_at: datetime | None
    deadline_date: str | None
    deadline_precision: str
    deadline_kind: str
    event_date: str | None
    source_url: str
    evidence: dict
    status: str
    review_status: str
    version: int
    is_demo: bool


class SubscriptionInput(BaseModel):
    competition_id: int
    lead_hours: int = Field(default=24, ge=1, le=720)


class DeadlineUpdate(BaseModel):
    deadline_at: datetime | None = None
    deadline_date: date | None = None
    precision: Literal["datetime", "date", "unknown"]
    reason: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def validate_precision(self):
        if self.precision == "datetime":
            if self.deadline_at is None or self.deadline_at.tzinfo is None:
                raise ValueError("精确截止时间必须带时区")
            if self.deadline_date is not None:
                raise ValueError("精确时间和日期不能同时提供")
        elif self.precision == "date":
            if self.deadline_date is None or self.deadline_at is not None:
                raise ValueError("日期精度仅允许提供deadline_date")
        elif self.deadline_at is not None or self.deadline_date is not None:
            raise ValueError("未知截止时间不能附带推测值")
        return self
